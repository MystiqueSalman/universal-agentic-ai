"""Live event bus (Doc 26 precursor) — every real agent communication emits
one event here. Events persist to SQLite so the Server Room survives restarts,
and every event carries the fields section 18 of the master prompt requires:
sender, receiver, task id, parent task, event type, timestamp, status,
correlation id. Secrets never enter events.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "events.db")


class EventBus:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, sender TEXT, receiver TEXT,
                event_type TEXT, task_id TEXT, parent_task TEXT, correlation_id TEXT,
                status TEXT, message TEXT, mode TEXT)""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def emit(self, sender: str, receiver: str, event_type: str, message: str,
             task_id: str | None = None, parent_task: str | None = None,
             correlation_id: str | None = None, status: str = "INFO") -> dict:
        ev = {
            "ts": time.time(), "sender": sender, "receiver": receiver,
            "event_type": event_type, "task_id": task_id, "parent_task": parent_task,
            "correlation_id": correlation_id or uuid.uuid4().hex[:12],
            "status": status, "message": message, "mode": "DEV",
        }
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO events (ts,sender,receiver,event_type,task_id,parent_task,"
                      "correlation_id,status,message,mode) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (ev["ts"], sender, receiver, event_type, task_id, parent_task,
                       ev["correlation_id"], status, message, ev["mode"]))
        return ev

    def recent(self, limit: int = 100, agent: str | None = None) -> list[dict]:
        q = "SELECT id,ts,sender,receiver,event_type,task_id,parent_task,correlation_id,status,message,mode FROM events"
        args: list = []
        if agent:
            q += " WHERE sender=? OR receiver=?"
            args += [agent, agent]
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        keys = ["id", "ts", "sender", "receiver", "event_type", "task_id", "parent_task",
                "correlation_id", "status", "message", "mode"]
        return [dict(zip(keys, r)) for r in rows]

    def after(self, last_id: int, limit: int = 200) -> list[dict]:
        """Events with id > last_id, oldest first — the SSE cursor read."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id,ts,sender,receiver,event_type,task_id,parent_task,correlation_id,"
                "status,message,mode FROM events WHERE id>? ORDER BY id ASC LIMIT ?",
                (last_id, limit)).fetchall()
        keys = ["id", "ts", "sender", "receiver", "event_type", "task_id", "parent_task",
                "correlation_id", "status", "message", "mode"]
        return [dict(zip(keys, r)) for r in rows]

    def max_id(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COALESCE(MAX(id),0) FROM events").fetchone()[0]

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM events").fetchone()[0]


BUS = EventBus()
