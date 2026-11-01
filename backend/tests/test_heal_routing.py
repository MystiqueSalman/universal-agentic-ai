"""Regression tests for the 2026-11-01 audit defect: junk fragment skills
("c", "a", "b", "to", ...) substring-matched almost any keyword, so the
C/C++ Developer agent absorbed unrelated tasks — above all through the
Level-1 self-healing reassignment path, which shares find_by_skill.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.registry import REGISTRY  # noqa: E402

client = TestClient(app)


def test_fragment_skills_no_longer_hijack_routing():
    # The audit's exact failure shape: software-delivery keywords that have
    # nothing to do with C programming must not select the C/C++ agent,
    # neither for primary assignment nor as the healing replacement.
    for keywords in (["product", "requirements"],
                     ["architecture", "design"],
                     ["documentation", "writing"],
                     ["database", "schema"]):
        picked = REGISTRY.find_by_skill(keywords, "D12")
        assert picked is not None
        assert picked.agent_id != "C_C_DEVELOPER_AI", (keywords, picked.agent_id)
        healed = REGISTRY.find_by_skill(keywords, "D12", exclude={picked.agent_id})
        assert healed is None or healed.agent_id != "C_C_DEVELOPER_AI", (
            keywords, healed.agent_id if healed else None)


def test_legitimate_short_skill_routing_still_works():
    # An actual C task must still find the C/C++ agent (exact match, len < 3).
    picked = REGISTRY.find_by_skill(["c", "programming"], "D12")
    assert picked is not None and picked.agent_id == "C_C_DEVELOPER_AI"


def test_healed_tasks_do_not_land_on_c_agent():
    r = client.post("/api/objectives", json={
        "title": "[fail-first] Build a CRM web application for a real-estate company"})
    assert r.status_code == 200, r.text
    oid = r.json()["objective_id"]
    deadline = time.time() + 120
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/objectives/{oid}").json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.5)
    assert final["status"] == "COMPLETED", final
    healed = [t for t in final["tasks"] if (t.get("attempts") or 1) > 1]
    assert healed, "chaos hook should have forced at least one heal"
    for t in healed:
        assert t["agent_id"] != "C_C_DEVELOPER_AI", t
