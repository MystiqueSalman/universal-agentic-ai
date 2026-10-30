"""Agent Health Monitor (Batch 05; Mgmt AI spec sections 4 + 21, master
prompt section 21 of v3.0 Part VI). A background daemon records a heartbeat
for every non-disabled agent every few seconds and flags agents that are
RUNNING but whose heartbeat/task has gone stale as STALLED (an event +
incident at MEDIUM severity). It never marks IDLE/WAITING agents as failed.
"""
from __future__ import annotations

import threading
import time

from .events import BUS
from .incidents import INCIDENTS
from .registry import REGISTRY

HEARTBEATS: dict[str, float] = {}
_STARTED = threading.Event()
_INTERVAL = 5.0
_STALE_SECONDS = 120.0


def _loop() -> None:
    task_started: dict[str, float] = {}
    while True:
        now = time.time()
        for a in REGISTRY.list_agents():
            if a.status in ("DISABLED", "OFFLINE", "QUARANTINED"):
                continue
            HEARTBEATS[a.agent_id] = now
            if a.status == "RUNNING" and a.current_task:
                task_started.setdefault(a.current_task, now)
                if now - task_started[a.current_task] > _STALE_SECONDS:
                    a.status = "STALLED"
                    inc = INCIDENTS.create(agent_id=a.agent_id, department_id=a.department_id,
                                           task_id=a.current_task, parent_task=None,
                                           message="Agent RUNNING with no progress beyond "
                                                   f"{int(_STALE_SECONDS)}s — marked STALLED",
                                           category="Performance degradation",
                                           agent_failure_count=a.tasks_failed + 1)
                    BUS.emit("SYSTEM_MONITOR_AI", "MANAGEMENT_AI", "AGENT_STALLED",
                             f"{a.agent_id} stalled on {a.current_task}; {inc['incident_id']} opened",
                             task_id=a.current_task, status="WARN")
                    task_started.pop(a.current_task, None)
            else:
                task_started.pop(a.current_task or "", None)
        time.sleep(_INTERVAL)


def start() -> None:
    if _STARTED.is_set():
        return
    _STARTED.set()
    threading.Thread(target=_loop, daemon=True, name="health-monitor").start()
    BUS.emit("SYSTEM_MONITOR_AI", "MANAGEMENT_AI", "MONITOR_STARTED",
             "Agent Health Monitor daemon started (5s heartbeats)", status="OK")


def snapshot() -> dict:
    now = time.time()
    return {"monitor_running": _STARTED.is_set(), "tracked_agents": len(HEARTBEATS),
            "stale_seconds_threshold": _STALE_SECONDS,
            "oldest_heartbeat_age_s": (round(now - min(HEARTBEATS.values()), 1)
                                       if HEARTBEATS else None)}
