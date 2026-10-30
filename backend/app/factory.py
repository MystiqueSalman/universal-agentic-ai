"""Agent Factory (Batch 06; Master Prompt v3.0 section 37).

Creates specialist agents from a structured request: validates the
department, derives the agent record (section 8 fields), registers it live,
and persists it so factory agents survive restarts. Founder-gated at the API
layer (creating agents is a Level-3-class action; in dev mode the Founder
identity applies — see auth.py).
"""
from __future__ import annotations

import os
import sqlite3
import threading

from .registry import DEPARTMENTS, REGISTRY, Agent, slug

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "factory.db")


class FactoryStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS factory_agents (
                agent_id TEXT PRIMARY KEY, name TEXT, department_id TEXT,
                skills TEXT, job TEXT)""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save(self, agent_id: str, name: str, department_id: str, skills: list[str], job: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO factory_agents VALUES (?,?,?,?,?)",
                      (agent_id, name, department_id, ",".join(skills), job))

    def load_all(self) -> list[dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT * FROM factory_agents").fetchall()]


FACTORY = FactoryStore()


def create_agent(name: str, department_id: str, skills: list[str], job: str = "") -> Agent:
    if department_id not in DEPARTMENTS:
        raise ValueError(f"unknown department {department_id}")
    agent_id = slug(name)
    if agent_id in REGISTRY.agents:
        agent_id = f"{department_id}_{agent_id}"
    dept = DEPARTMENTS[department_id]
    manager = "MANAGEMENT_AI" if department_id == "D01" else slug(f"{dept['name']} Manager")
    agent = Agent(agent_id=agent_id, name=name, department_id=department_id,
                  department=dept["name"], manager=manager, role="SPECIALIST",
                  skills=sorted(set([s.lower() for s in skills] + ["factory-created"])))
    REGISTRY.agents[agent_id] = agent
    FACTORY.save(agent_id, name, department_id, agent.skills, job)
    return agent


def load_factory_agents() -> int:
    n = 0
    for rec in FACTORY.load_all():
        if rec["agent_id"] in REGISTRY.agents:
            continue
        dept = DEPARTMENTS[rec["department_id"]]
        manager = "MANAGEMENT_AI" if rec["department_id"] == "D01" else slug(f"{dept['name']} Manager")
        REGISTRY.agents[rec["agent_id"]] = Agent(
            agent_id=rec["agent_id"], name=rec["name"], department_id=rec["department_id"],
            department=dept["name"], manager=manager, role="SPECIALIST",
            skills=rec["skills"].split(",") if rec["skills"] else [])
        n += 1
    return n
