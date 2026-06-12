"""End-to-end happy path with DEMO_MODE.

Upload sample CSV → /analyze (clarify → re-call with answer) → /storymap.

Tests run with DEMO_MODE=true and all external-service API keys forcibly
emptied — pydantic-settings reads .env by default and a developer with real
DASHSCOPE/DEEPSEEK/MAPBOX keys in .env would otherwise hit real APIs from
inside the test, which (a) hits the network, (b) costs tokens, and (c) leaks
httpx connections across the TestClient's short-lived event loop.
"""

from __future__ import annotations

import os
from pathlib import Path

# These must be set before importing app.* so the lru-cached Settings picks
# them up. os.environ takes precedence over .env in pydantic-settings.
os.environ["DEMO_MODE"] = "true"
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["MAPBOX_ACCESS_TOKEN"] = ""

from fastapi.testclient import TestClient    # noqa: E402

from app.main import app    # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "app" / "mock" / "sample_branches.csv"


def test_upload_then_storymap():
    client = TestClient(app)

    with SAMPLE.open("rb") as fh:
        r = client.post("/upload", files={"file": ("sample.csv", fh, "text/csv")})
    assert r.status_code == 200, r.text
    network_id = r.json()["id"]
    assert network_id

    # First /analyze — expect a clarify event (synchronous SSE consumption).
    # The TestClient streams SSE as a body; we read raw and look for the clarify event.
    with client.stream("POST", "/analyze", json={"network_id": network_id}) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes())
    assert b"event: clarify" in body, body[:1000]

    # Second /analyze with the answer — expect storymap_ready then done.
    with client.stream("POST", "/analyze",
                       json={"network_id": network_id, "clarification_answer": "retail"}) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes())
    assert b"event: storymap_ready" in body
    assert b"event: done" in body

    # Extract storymap id from the body — it's in the storymap_ready payload.
    import json, re
    m = re.search(rb'event: storymap_ready\s*\ndata: (\{.*?\})\s*\n', body)
    assert m, body[:2000]
    payload = json.loads(m.group(1))
    storymap_id = payload["storymap_id"]

    r = client.get(f"/storymap/{storymap_id}")
    assert r.status_code == 200, r.text
    sm = r.json()
    # 5 base sections; dynamic methodologies may add a findings section.
    assert len(sm["sections"]) >= 5
    assert sm["network_id"] == network_id
