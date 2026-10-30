import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.incidents import IncidentStore  # noqa: E402
from app.main import app  # noqa: E402
from app.registry import REGISTRY  # noqa: E402

client = TestClient(app)


def test_ops_hierarchy_registered_under_management_ai():
    for aid in ("SYSTEM_MONITOR_AI", "DIAGNOSTIC_AI", "ROOT_CAUSE_ANALYSIS_AI", "CODE_REPAIR_AI",
                "REGRESSION_TESTING_AI", "CYBERSECURITY_AUDITOR_AI", "DISASTER_RECOVERY_AI",
                "INDEPENDENT_VERIFICATION_AI"):
        a = REGISTRY.get(aid)
        assert a is not None, aid
        assert a.manager == "MANAGEMENT_AI"


def test_severity_classification():
    assert IncidentStore.classify("MAIN_AI", 1, False) == "CRITICAL"
    assert IncidentStore.classify("MANAGEMENT_AI", 1, False) == "CRITICAL"
    assert IncidentStore.classify("WEB_RESEARCH_AI", 2, False) == "HIGH"
    assert IncidentStore.classify("WEB_RESEARCH_AI", 1, True) == "HIGH"
    assert IncidentStore.classify("WEB_RESEARCH_AI", 1, False) == "MEDIUM"


def test_watchdog_endpoint():
    r = client.get("/api/watchdog").json()
    assert r["watchdog"] == "INDEPENDENT"
    assert r["healthy"] is True
    assert r["checks"]["event_store"]["ok"] is True


def test_self_healing_end_to_end():
    r = client.post("/api/objectives",
                    json={"title": "[fail-first] Build a complete CRM system for a real estate company"})
    oid = r.json()["objective_id"]
    deadline = time.time() + 40
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/objectives/{oid}").json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.3)
    # Every non-quality task fails once, gets reassigned, and completes.
    assert final["status"] == "COMPLETED", final
    inc = client.get("/api/incidents?limit=50").json()
    mine = [i for i in inc if i["parent_task"] == oid]
    assert mine, "incidents must be recorded for injected failures"
    assert all(i["status"] == "RESOLVED" for i in mine), mine
    assert all("Level-1 self-healing" in i["resolution"] for i in mine)
    ev = client.get("/api/events?limit=200").json()
    assert any(e["event_type"] == "RECOVERY_COMPLETE" for e in ev)
