"""End-to-end integration tests hitting real API endpoints via TestClient."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestE2E:
    async def test_health_endpoint(self, client):
        r = await client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "eco-guard"

    async def test_system_status(self, client):
        r = await client.get("/api/v1/system/status")
        assert r.status_code == 200
        data = r.json()
        assert "app_name" in data
        assert "version" in data

    async def test_auth_status(self, client):
        r = await client.get("/api/v1/auth/status")
        assert r.status_code in (200, 401)

    async def test_openai_models(self, client):
        r = await client.get("/v1/models")
        assert r.status_code == 200
        data = r.json()
        assert data["object"] == "list"

    async def test_cost_pricing(self, client):
        r = await client.get("/v1/cost/pricing")
        assert r.status_code == 200
        data = r.json()
        assert "default" in data or "gpt-4o" in data

    async def test_guardrails_list(self, client):
        r = await client.get("/v1/guardrails")
        assert r.status_code == 200

    async def test_benchmarks_list(self, client):
        r = await client.get("/api/v1/benchmarks")
        assert r.status_code == 200
        data = r.json()
        assert "benchmarks" in data
        assert "basic_qa" in data["benchmarks"]

    async def test_leaderboard(self, client):
        r = await client.get("/api/v1/leaderboard")
        assert r.status_code == 200

    async def test_analytics_summary(self, client):
        r = await client.get("/api/v1/analytics/summary")
        assert r.status_code == 200

    async def test_daily_digest(self, client):
        r = await client.get("/api/v1/digest")
        assert r.status_code == 200

    async def test_queue_status(self, client):
        r = await client.get("/api/v1/queue/status")
        assert r.status_code == 200
        data = r.json()
        assert "depth" in data

    async def test_cost_compare(self, client):
        r = await client.post(
            "/api/v1/cost/compare", json={"prompt": "Hello world", "max_tokens": 50}
        )
        assert r.status_code == 200
        data = r.json()
        assert "providers" in data
        assert len(data["providers"]) == 6

    async def test_cost_estimate(self, client):
        r = await client.get(
            "/v1/cost/estimate", params={"input_tokens": 100, "output_tokens": 50}
        )
        assert r.status_code == 200

    async def test_loadtest_no_model(self, client):
        r = await client.post(
            "/api/v1/load-test", json={"total_requests": 2, "concurrent": 1}
        )
        assert r.status_code in (200, 503)  # 503 if no model, 200 with errors

    async def test_hmac_sign(self, client):
        r = await client.post(
            "/api/v1/hmac/sign",
            json={
                "method": "POST",
                "path": "/test",
                "body": "hello",
                "secret": "mysecret",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "headers" in data
        assert "X-Signature" in data["headers"]

    async def test_seeds_redact(self, client):
        r = await client.get(
            "/api/v1/secrets/redact", params={"value": "mysecretpassword123"}
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["redacted"]) == len("mysecretpassword123")
        assert data["redacted"].startswith("myse")
        assert "*" in data["redacted"]

    async def test_providers_list(self, client):
        r = await client.get("/api/v1/providers")
        assert r.status_code == 200

    async def test_anomaly_recent(self, client):
        r = await client.get("/api/v1/anomaly/recent")
        assert r.status_code == 200

    async def test_sla_check(self, client):
        r = await client.get("/api/v1/sla")
        assert r.status_code == 200
