import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.engine import OUT_DIR  # noqa: E402
from app.main import app  # noqa: E402
from app.media import probe_duration  # noqa: E402

client = TestClient(app)


def test_film_objective_produces_real_mp4():
    r = client.post("/api/objectives", json={
        "title": "Create a 15-minute animated educational film about Artificial Intelligence"})
    oid = r.json()["objective_id"]
    deadline = time.time() + 180
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/objectives/{oid}").json()
        if final["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(1.0)
    assert final["status"] == "COMPLETED", final
    mp4 = os.path.join(OUT_DIR, oid, "preview.mp4")
    assert os.path.isfile(mp4) and os.path.getsize(mp4) > 10_000
    assert probe_duration(mp4) >= 10  # 10 cards x 2s = ~20s of real video
