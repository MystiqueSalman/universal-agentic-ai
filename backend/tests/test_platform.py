import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_auth_flow_and_roles():
    email = "founder-test@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "longpassword1"})
    assert r.status_code in (200, 409)
    r = client.post("/api/auth/login", json={"email": email, "password": "wrongpassword"})
    assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": email, "password": "longpassword1"})
    assert r.status_code == 200
    token = r.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == email and me["workspace_id"]


def test_approval_queue():
    r = client.post("/api/approvals", json={"action": "Change production DB schema",
                                            "details": "Level-3 test"})
    assert r.status_code == 200
    aid = r.json()["approval_id"]
    assert r.json()["status"] == "PENDING"
    r = client.post(f"/api/approvals/{aid}/APPROVED")
    assert r.json()["status"] == "APPROVED"
    pend = client.get("/api/approvals?status=PENDING").json()
    assert all(a["approval_id"] != aid for a in pend)


def test_model_router_stats():
    r = client.get("/api/model-router").json()
    assert r["available"] is False  # tests force local mode
    assert "calls" in r


def test_watchdog_and_stats_still_ok():
    assert client.get("/api/watchdog").json()["healthy"] is True
    s = client.get("/api/stats").json()
    assert s["total_agents"] >= 323
