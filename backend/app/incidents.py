"""Incident management (Management AI Master Prompt v1.0, sections 5-6, 10, 13).

Incident records persist to SQLite with the section-6 field set and lifecycle.
Severity rules (section 5):
- Main AI / Management AI failure -> CRITICAL
- Same agent failing 2+ times, or a whole objective failing -> HIGH
- Single task/agent failure -> MEDIUM
- Recoverable warnings -> LOW / INFORMATIONAL
Level-1 self-healing (section 10/11): bounded retry by reassigning the task to
another available specialist with matching skills. No other automatic repair
is permitted at this level; everything else escalates.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "incidents.db")

LIFECYCLE = ("DETECTED", "CLASSIFIED", "INVESTIGATING", "ROOT_CAUSE_IDENTIFIED",
             "REPAIR_PLANNED", "REPAIR_IN_PROGRESS", "TESTING", "VERIFIED", "RESOLVED",
             "BLOCKED", "ESCALATED", "FAILED_TO_REPAIR", "MONITORING", "REOPENED")
OPEN_STATES = ("DETECTED", "CLASSIFIED", "INVESTIGATING", "ROOT_CAUSE_IDENTIFIED",
               "REPAIR_PLANNED", "REPAIR_IN_PROGRESS", "TESTING", "BLOCKED", "ESCALATED",
               "FAILED_TO_REPAIR", "MONITORING", "REOPENED")


class IncidentStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY, ts REAL, affected_system TEXT, agent_id TEXT,
                department_id TEXT, task_id TEXT, parent_task TEXT, category TEXT,
                severity TEXT, message TEXT, status TEXT, retry_history TEXT,
                suspected_cause TEXT, diagnosis TEXT, proposed_solution TEXT,
                resolution TEXT)""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def classify(agent_id: str, agent_failure_count: int, objective_failed: bool) -> str:
        if agent_id in ("MAIN_AI", "MANAGEMENT_AI"):
            return "CRITICAL"
        if objective_failed or agent_failure_count >= 2:
            return "HIGH"
        return "MEDIUM"

    def create(self, agent_id: str, department_id: str, task_id: str | None,
               parent_task: str | None, message: str, category: str = "Workflow failure",
               agent_failure_count: int = 1, objective_failed: bool = False) -> dict:
        inc = {
            "incident_id": "INC-" + uuid.uuid4().hex[:8].upper(),
            "ts": time.time(), "affected_system": "task-engine", "agent_id": agent_id,
            "department_id": department_id, "task_id": task_id, "parent_task": parent_task,
            "category": category,
            "severity": self.classify(agent_id, agent_failure_count, objective_failed),
            "message": message, "status": "CLASSIFIED", "retry_history": "[]",
            "suspected_cause": "", "diagnosis": "", "proposed_solution": "",
            "resolution": "",
        }
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      tuple(inc[k] for k in ("incident_id", "ts", "affected_system", "agent_id",
                                             "department_id", "task_id", "parent_task", "category",
                                             "severity", "message", "status", "retry_history",
                                             "suspected_cause", "diagnosis", "proposed_solution",
                                             "resolution")))
        return inc

    def update(self, incident_id: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE incidents SET {cols} WHERE incident_id=?",
                      (*fields.values(), incident_id))

    def list(self, limit: int = 100, open_only: bool = False) -> list[dict]:
        q = "SELECT * FROM incidents"
        if open_only:
            q += " WHERE status IN (%s)" % ",".join("?" * len(OPEN_STATES))
        q += " ORDER BY ts DESC LIMIT ?"
        args = (*OPEN_STATES, limit) if open_only else (limit,)
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(q, args).fetchall()]

    def counts(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            open_n = c.execute("SELECT COUNT(*) FROM incidents WHERE status IN (%s)"
                               % ",".join("?" * len(OPEN_STATES)), OPEN_STATES).fetchone()[0]
            crit = c.execute("SELECT COUNT(*) FROM incidents WHERE severity='CRITICAL' "
                             "AND status IN (%s)" % ",".join("?" * len(OPEN_STATES)),
                             OPEN_STATES).fetchone()[0]
        return {"incidents_total": total, "incidents_open": open_n, "incidents_critical_open": crit}


INCIDENTS = IncidentStore()
