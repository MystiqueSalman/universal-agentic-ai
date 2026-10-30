"""Auth + Founder approval queue (Batch 04; Doc 17 precursor).

Users register/login; passwords are PBKDF2-hashed, tokens are random and
stored server-side. Roles: FOUNDER and USER. Dev-mode rule (explicit, logged):
when UAA_REQUIRE_AUTH is not set, requests without a token act as FOUNDER so
the local dev loop keeps working; set UAA_REQUIRE_AUTH=1 to enforce tokens.
Level-3 actions (Management AI spec section 11) never execute directly —
they are queued as approval requests for the Founder.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import threading
import time
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "auth.db")


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()


class AuthStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT,
                salt TEXT, role TEXT, workspace_id TEXT, created_at REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY, user_id TEXT, created_at REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY, ts REAL, requested_by TEXT, action TEXT,
                details TEXT, status TEXT, decided_by TEXT)""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def register(self, email: str, password: str, role: str = "USER") -> dict:
        salt = secrets.token_hex(16)
        uid = "USR-" + uuid.uuid4().hex[:8].upper()
        ws = "WS-" + uuid.uuid4().hex[:8].upper()
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                      (uid, email.lower(), _hash(password, salt), salt, role, ws, time.time()))
        return {"user_id": uid, "email": email.lower(), "role": role, "workspace_id": ws}

    def login(self, email: str, password: str) -> str | None:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            row = c.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
        if not row or _hash(password, row["salt"]) != row["password_hash"]:
            return None
        token = secrets.token_urlsafe(32)
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO tokens VALUES (?,?,?)", (token, row["user_id"], time.time()))
        return token

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            row = c.execute("""SELECT u.user_id,u.email,u.role,u.workspace_id FROM tokens t
                               JOIN users u ON u.user_id=t.user_id WHERE t.token=?""",
                            (token,)).fetchone()
        return dict(row) if row else None

    def request_approval(self, requested_by: str, action: str, details: str) -> dict:
        aid = "APR-" + uuid.uuid4().hex[:8].upper()
        rec = {"approval_id": aid, "ts": time.time(), "requested_by": requested_by,
               "action": action, "details": details, "status": "PENDING", "decided_by": ""}
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",
                      tuple(rec[k] for k in ("approval_id", "ts", "requested_by", "action",
                                             "details", "status", "decided_by")))
        return rec

    def list_approvals(self, status: str | None = None) -> list[dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            if status:
                rows = c.execute("SELECT * FROM approvals WHERE status=? ORDER BY ts DESC",
                                 (status,)).fetchall()
            else:
                rows = c.execute("SELECT * FROM approvals ORDER BY ts DESC").fetchall()
        return [dict(r) for r in rows]

    def decide_approval(self, approval_id: str, decision: str, decided_by: str) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE approvals SET status=?, decided_by=? WHERE approval_id=? "
                            "AND status='PENDING'", (decision, decided_by, approval_id))
            return cur.rowcount > 0


AUTH = AuthStore()


def current_user(authorization: str | None) -> dict:
    """Resolve the caller. Dev mode: no token -> FOUNDER (see module docstring)."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    user = AUTH.user_for_token(token)
    if user:
        return user
    if os.environ.get("UAA_REQUIRE_AUTH") == "1":
        return {"user_id": "ANON", "email": "", "role": "ANON", "workspace_id": ""}
    return {"user_id": "FOUNDER-DEV", "email": "founder@local", "role": "FOUNDER",
            "workspace_id": "WS-FOUNDER"}
