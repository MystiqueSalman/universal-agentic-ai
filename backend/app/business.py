"""Universal Business OS core (Batch 07; Master Prompt v3.0 sections 30-31).

Workspaces with tenant-scoped records: customers, leads and appointments.
Every record carries a workspace_id and every read is filtered by it —
tenant isolation is enforced in the query, not by convention.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "business.db")
TABLES = {"customers": ("name", "email", "phone", "notes"),
          "leads": ("name", "email", "phone", "source", "status", "notes"),
          "appointments": ("title", "with_name", "when_ts", "status", "notes")}


class BusinessStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY, name TEXT, industry TEXT, created_at REAL)""")
            for table, cols in TABLES.items():
                coldefs = ", ".join(f"{col} TEXT" for col in cols)
                c.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
                    record_id TEXT PRIMARY KEY, workspace_id TEXT, created_at REAL, {coldefs})""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def create_workspace(self, name: str, industry: str = "") -> dict:
        ws = {"workspace_id": "WS-" + uuid.uuid4().hex[:8].upper(), "name": name,
              "industry": industry, "created_at": time.time()}
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO workspaces VALUES (?,?,?,?)",
                      (ws["workspace_id"], name, industry, ws["created_at"]))
        return ws

    def list_workspaces(self) -> list[dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT * FROM workspaces ORDER BY created_at")]

    def add_record(self, table: str, workspace_id: str, data: dict) -> dict:
        cols = TABLES[table]
        rec = {"record_id": "REC-" + uuid.uuid4().hex[:8].upper(), "workspace_id": workspace_id,
               "created_at": time.time()}
        rec.update({col: str(data.get(col, "")) for col in cols})
        fields = ["record_id", "workspace_id", "created_at", *cols]
        with self._lock, self._conn() as c:
            c.execute(f"INSERT INTO {table} ({','.join(fields)}) "
                      f"VALUES ({','.join('?' * len(fields))})",
                      tuple(rec[f] for f in fields))
        return rec

    def list_records(self, table: str, workspace_id: str) -> list[dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(
                f"SELECT * FROM {table} WHERE workspace_id=? ORDER BY created_at DESC",
                (workspace_id,)).fetchall()]

    def counts(self, workspace_id: str) -> dict:
        with self._conn() as c:
            return {t: c.execute(f"SELECT COUNT(*) FROM {t} WHERE workspace_id=?",
                                 (workspace_id,)).fetchone()[0] for t in TABLES}


BUSINESS = BusinessStore()
