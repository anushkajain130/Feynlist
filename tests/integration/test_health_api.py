"""API test: /health is cheap and works (baseline B-10 returned 500)."""


async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db_ok"] is True
    assert set(body) >= {"status", "db_ok", "scheduler_running", "agents_ready"}
