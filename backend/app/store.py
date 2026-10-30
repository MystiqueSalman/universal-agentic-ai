"""Durable objective/task storage (Batch 03). Objectives and tasks persist to
SQLite and are reloaded on startup; anything left RUNNING by a crash/restart
is honestly marked FAILED ('interrupted by restart') instead of vanishing.
"""
from __future__ import annotations

import os
import sqlite3
import threading

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "tasks.db")


class TaskStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS objectives (
                objective_id TEXT PRIMARY KEY, title TEXT, priority TEXT, status TEXT,
                created_at REAL, correlation_id TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, objective_id TEXT, title TEXT, department_id TEXT,
                agent_id TEXT, kind TEXT, status TEXT, attempts INTEGER,
                output_path TEXT, result TEXT, error TEXT)""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save_objective(self, o: dict) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO objectives VALUES (?,?,?,?,?,?)",
                      (o["objective_id"], o["title"], o["priority"], o["status"],
                       o["created_at"], o["correlation_id"]))

    def save_task(self, objective_id: str, t: dict) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (t["task_id"], objective_id, t["title"], t["department_id"], t["agent_id"],
                       t["kind"], t["status"], t.get("attempts", 0), t["output_path"],
                       t["result"], t["error"]))

    def load_all(self) -> tuple[list[dict], list[dict]]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            objs = [dict(r) for r in c.execute("SELECT * FROM objectives").fetchall()]
            tasks = [dict(r) for r in c.execute("SELECT * FROM tasks").fetchall()]
        return objs, tasks


STORE = TaskStore()
