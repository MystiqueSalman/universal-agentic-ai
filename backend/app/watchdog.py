"""Independent System Watchdog (Management AI Master Prompt v1.0, section 12).

Deliberately independent of the Main AI / Management AI execution paths: it
inspects storage and process state directly, so it can report — and later
trigger authorised recovery — even if the management layer itself is down.
It never depends on Management AI being operational to check Management AI.
"""
from __future__ import annotations

import os
import sqlite3
import time

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_STARTED = time.time()


def _db_ok(path: str, table: str) -> dict:
    try:
        with sqlite3.connect(path) as c:
            n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return {"ok": True, "rows": n}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def watchdog_report() -> dict:
    events = _db_ok(os.path.join(BASE, "data", "events.db"), "events")
    incidents = _db_ok(os.path.join(BASE, "data", "incidents.db"), "incidents")
    out_dir = os.path.join(BASE, "data", "outputs")
    outputs_ok = os.path.isdir(out_dir) and os.access(out_dir, os.W_OK)
    # Registry data file presence (data check, not a management-layer call).
    registry_file = os.path.join(BASE, "app", "registry.py")
    checks = {
        "event_store": events,
        "incident_store": incidents,
        "outputs_writable": {"ok": outputs_ok},
        "registry_present": {"ok": os.path.isfile(registry_file)},
        "process_uptime_seconds": round(time.time() - _STARTED, 1),
    }
    healthy = all(v.get("ok") for k, v in checks.items() if isinstance(v, dict))
    return {"watchdog": "INDEPENDENT", "healthy": healthy, "mode": "DEV", "checks": checks}
