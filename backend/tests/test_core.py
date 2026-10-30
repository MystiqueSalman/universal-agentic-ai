import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.engine import plan_objective, Objective  # noqa: E402
from app.main import app  # noqa: E402
from app.registry import REGISTRY  # noqa: E402

client = TestClient(app)


def test_registry_has_20_departments_and_full_catalogue():
    depts = REGISTRY.list_departments()
    assert len(depts) == 20
    assert len(REGISTRY.agents) >= 230  # 20 managers + 2 central + 200+ specialists (some cross-dept dedup)


def test_agent_record_fields():
    a = REGISTRY.get("MAIN_AI")
    d = a.to_dict()
    for key in ("agent_id", "name", "department", "manager", "skills", "status", "version", "quality_score"):
        assert key in d


def test_planner_templates():
    film = plan_objective(Objective("PRJ-T1", "Create a 15-minute animated educational film about AI"))
    assert len(film) >= 7 and any(t.department_id == "D06" for t in film)
    crm = plan_objective(Objective("PRJ-T2", "Build a complete CRM system for a real estate company"))
    assert any(t.department_id == "D12" for t in crm)
    assert film[-1].kind == "quality" or crm[-2].kind == "quality"


def test_health_and_catalogue_api():
    assert client.get("/api/health").json()["status"] == "ok"
    assert len(client.get("/api/departments").json()) == 20
    assert len(client.get("/api/agents").json()) >= 230


def test_objective_end_to_end():
    r = client.post("/api/objectives", json={"title": "Build a complete CRM system for a real estate company"})
    oid = r.json()["objective_id"]
    deadline = time.time() + 30
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/objectives/{oid}").json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.3)
    assert final["status"] == "COMPLETED", final
    assert final["progress_pct"] == 100
    assert all(t["agent_id"] for t in final["tasks"])
    ev = client.get("/api/events?limit=50").json()
    assert any(e["event_type"] == "OBJECTIVE_RECEIVED" for e in ev)
    assert any(e["event_type"] == "REPORT_DELIVERED" for e in ev)


def test_agent_actions():
    r = client.post("/api/agents/WEB_RESEARCH_AI/pause")
    assert r.json()["status"] == "PAUSED"
    r = client.post("/api/agents/WEB_RESEARCH_AI/resume")
    assert r.json()["status"] == "IDLE"
