"""Universal Agentic AI — API (Batch 1: Phases 1+2 core, Server Room feed).

Run: uvicorn app.main:app --host 0.0.0.0 --port 8100
"""
from __future__ import annotations

import os

import asyncio
import json as _json

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import monitor
from . import router as model_router
from .auth import AUTH, current_user
from .business import BUSINESS, TABLES as BIZ_TABLES
from .factory import create_agent as factory_create_agent
from .factory import load_factory_agents
from .engine import OBJECTIVES, load_persisted, submit_objective
from .events import BUS
from .incidents import INCIDENTS
from .registry import REGISTRY
from .watchdog import watchdog_report

app = FastAPI(title="Universal Agentic AI", version="0.3.0")
load_persisted()
load_factory_agents()
monitor.start()
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


class ObjectiveIn(BaseModel):
    title: str
    priority: str = "High"


class Credentials(BaseModel):
    email: str
    password: str


class ApprovalIn(BaseModel):
    action: str
    details: str = ""


def require_founder(authorization: str | None) -> dict:
    user = current_user(authorization)
    if user["role"] != "FOUNDER":
        raise HTTPException(403, "Founder role required for this action")
    return user


@app.post("/api/auth/register")
def register(body: Credentials) -> dict:
    if len(body.password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    try:
        # The first registered account becomes FOUNDER; later ones are USERs.
        import sqlite3 as _s
        with AUTH._conn() as c:
            count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        role = "FOUNDER" if count == 0 else "USER"
        user = AUTH.register(body.email, body.password, role=role)
    except Exception:
        raise HTTPException(409, "email already registered")
    BUS.emit(user["user_id"], "MAIN_AI", "USER_REGISTERED", f"Registered {user['email']} ({role})",
             status="OK")
    return user


@app.post("/api/auth/login")
def login(body: Credentials) -> dict:
    token = AUTH.login(body.email, body.password)
    if not token:
        raise HTTPException(401, "invalid credentials")
    return {"token": token, "token_type": "bearer"}


@app.get("/api/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    return current_user(authorization)


@app.get("/api/approvals")
def approvals(status: str | None = None,
              authorization: str | None = Header(default=None)) -> list[dict]:
    require_founder(authorization)
    return AUTH.list_approvals(status)


@app.post("/api/approvals")
def request_approval(body: ApprovalIn,
                     authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    rec = AUTH.request_approval(user["user_id"], body.action, body.details)
    BUS.emit(user["user_id"], "FOUNDER", "APPROVAL_REQUESTED",
             f"Level-3 approval requested: {body.action}", status="WARN")
    return rec


@app.post("/api/approvals/{approval_id}/{decision}")
def decide_approval(approval_id: str, decision: str,
                    authorization: str | None = Header(default=None)) -> dict:
    user = require_founder(authorization)
    if decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "decision must be APPROVED or REJECTED")
    if not AUTH.decide_approval(approval_id, decision, user["user_id"]):
        raise HTTPException(404, "pending approval not found")
    BUS.emit("FOUNDER", "MANAGEMENT_AI", f"APPROVAL_{decision}",
             f"{approval_id} {decision} by {user['user_id']}", status="OK")
    return {"approval_id": approval_id, "status": decision}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "universal-agentic-ai", "mode": "DEV",
            "agents": len(REGISTRY.agents), "departments": len(REGISTRY.list_departments()),
            "events": BUS.count()}


@app.get("/api/departments")
def departments() -> list[dict]:
    return REGISTRY.list_departments()


@app.get("/api/agents")
def agents(department_id: str | None = None) -> list[dict]:
    return [a.to_dict() for a in REGISTRY.list_agents(department_id)]


@app.get("/api/agents/{agent_id}")
def agent(agent_id: str) -> dict:
    a = REGISTRY.get(agent_id)
    if not a:
        raise HTTPException(404, "agent not found")
    return a.to_dict()


@app.post("/api/agents/{agent_id}/{action}")
def agent_action(agent_id: str, action: str,
                 authorization: str | None = Header(default=None)) -> dict:
    require_founder(authorization)
    mapping = {"pause": "PAUSED", "resume": "IDLE", "disable": "DISABLED",
               "quarantine": "QUARANTINED", "enable": "IDLE"}
    if action not in mapping:
        raise HTTPException(400, f"unknown action {action}")
    a = REGISTRY.set_status(agent_id, mapping[action])
    if not a:
        raise HTTPException(404, "agent not found")
    BUS.emit("FOUNDER", agent_id, f"AGENT_{action.upper()}", f"Agent {agent_id} -> {mapping[action]}",
             status="WARN")
    return a.to_dict()


@app.post("/api/objectives")
def create_objective(body: ObjectiveIn) -> dict:
    obj = submit_objective(body.title.strip(), body.priority)
    return {"objective_id": obj.objective_id, "status": obj.status}


@app.get("/api/objectives")
def list_objectives() -> list[dict]:
    return [o.to_dict() for o in OBJECTIVES.values()]


@app.get("/api/objectives/{objective_id}")
def get_objective(objective_id: str) -> dict:
    obj = OBJECTIVES.get(objective_id)
    if not obj:
        raise HTTPException(404, "objective not found")
    return obj.to_dict()


@app.get("/api/events")
def events(limit: int = Query(100, le=500), agent: str | None = None) -> list[dict]:
    return BUS.recent(limit=limit, agent=agent)


@app.get("/api/events/stream")
async def events_stream(request: Request):
    """Server-Sent Events: real engine events as they happen (Doc 26)."""
    async def gen():
        last = BUS.max_id()
        yield "data: {\"type\": \"connected\"}\n\n"
        while True:
            if await request.is_disconnected():
                break
            for ev in BUS.after(last):
                last = ev["id"]
                yield f"data: {_json.dumps(ev)}\n\n"
            await asyncio.sleep(1.0)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/monitor")
def monitor_snapshot() -> dict:
    return monitor.snapshot()


class FactoryAgentIn(BaseModel):
    name: str
    department_id: str
    skills: list[str] = []
    job: str = ""


@app.post("/api/factory/agents")
def factory_create(body: FactoryAgentIn,
                   authorization: str | None = Header(default=None)) -> dict:
    require_founder(authorization)
    try:
        agent = factory_create_agent(body.name.strip(), body.department_id.upper(),
                                     body.skills, body.job)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    BUS.emit("FOUNDER", "AGENT_CREATION_AI", "AGENT_CREATED",
             f"Agent Factory created {agent.agent_id} in {agent.department_id}", status="OK")
    return agent.to_dict()


class WorkspaceIn(BaseModel):
    name: str
    industry: str = ""


@app.post("/api/business/workspaces")
def create_workspace(body: WorkspaceIn) -> dict:
    return BUSINESS.create_workspace(body.name.strip(), body.industry)


@app.get("/api/business/workspaces")
def list_workspaces() -> list[dict]:
    return BUSINESS.list_workspaces()


@app.post("/api/business/{workspace_id}/{table}")
def add_record(workspace_id: str, table: str, data: dict) -> dict:
    if table not in BIZ_TABLES:
        raise HTTPException(404, f"unknown record type {table}")
    return BUSINESS.add_record(table, workspace_id, data)


@app.get("/api/business/{workspace_id}/{table}")
def list_records(workspace_id: str, table: str) -> list[dict]:
    if table not in BIZ_TABLES:
        raise HTTPException(404, f"unknown record type {table}")
    return BUSINESS.list_records(table, workspace_id)


@app.get("/api/business/{workspace_id}")
def workspace_counts(workspace_id: str) -> dict:
    return BUSINESS.counts(workspace_id)


@app.get("/api/model-router")
def model_router_stats() -> dict:
    return model_router.stats()


@app.get("/api/incidents")
def incidents(limit: int = Query(100, le=500), open_only: bool = False) -> list[dict]:
    return INCIDENTS.list(limit=limit, open_only=open_only)


@app.post("/api/incidents/{incident_id}/{action}")
def incident_action(incident_id: str, action: str) -> dict:
    mapping = {"resolve": "RESOLVED", "escalate": "ESCALATED", "reopen": "REOPENED",
               "monitor": "MONITORING", "block": "BLOCKED"}
    if action not in mapping:
        raise HTTPException(400, f"unknown action {action}")
    INCIDENTS.update(incident_id, status=mapping[action])
    BUS.emit("FOUNDER", "MANAGEMENT_AI", f"INCIDENT_{action.upper()}",
             f"{incident_id} -> {mapping[action]}", status="WARN")
    return {"incident_id": incident_id, "status": mapping[action]}


@app.get("/api/watchdog")
def watchdog() -> dict:
    """Independent watchdog (Mgmt AI spec section 12): checks the platform
    without going through Main AI / Management AI code paths."""
    return watchdog_report()


@app.get("/api/stats")
def stats() -> dict:
    agents = REGISTRY.list_agents()
    tasks = [t for o in OBJECTIVES.values() for t in o.tasks]
    return {
        "mode": "DEV",
        "total_agents": len(agents),
        "active_agents": sum(1 for a in agents if a.status == "RUNNING"),
        "idle_agents": sum(1 for a in agents if a.status == "IDLE"),
        "error_agents": sum(1 for a in agents if a.status in ("FAILED", "QUARANTINED")),
        "departments": len(REGISTRY.list_departments()),
        "objectives": len(OBJECTIVES),
        "tasks_running": sum(1 for t in tasks if t.status == "RUNNING"),
        "tasks_queued": sum(1 for t in tasks if t.status == "QUEUED"),
        "tasks_completed": sum(1 for t in tasks if t.status == "COMPLETED"),
        "tasks_failed": sum(1 for t in tasks if t.status == "FAILED"),
        "events": BUS.count(),
        **INCIDENTS.counts(),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
