import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_agent_factory_creates_live_agent():
    r = client.post("/api/factory/agents", json={
        "name": "Hospital Administration AI", "department_id": "D19",
        "skills": ["hospital", "administration"], "job": "Hospital admin specialist"})
    assert r.status_code == 200, r.text
    aid = r.json()["agent_id"]
    assert client.get(f"/api/agents/{aid}").status_code == 200
    bad = client.post("/api/factory/agents", json={"name": "X AI", "department_id": "D99"})
    assert bad.status_code == 400


def test_business_os_tenant_isolation():
    ws1 = client.post("/api/business/workspaces",
                      json={"name": "Acme Realty", "industry": "Real estate"}).json()
    ws2 = client.post("/api/business/workspaces",
                      json={"name": "Beta Salon", "industry": "Beauty"}).json()
    client.post(f"/api/business/{ws1['workspace_id']}/leads",
                json={"name": "Lead One", "source": "web", "status": "NEW"})
    leads1 = client.get(f"/api/business/{ws1['workspace_id']}/leads").json()
    leads2 = client.get(f"/api/business/{ws2['workspace_id']}/leads").json()
    assert len(leads1) == 1 and leads1[0]["name"] == "Lead One"
    assert leads2 == []  # tenant isolation: other workspace sees nothing
    counts = client.get(f"/api/business/{ws1['workspace_id']}").json()
    assert counts["leads"] == 1


def test_monitor_snapshot():
    r = client.get("/api/monitor").json()
    assert r["monitor_running"] is True
