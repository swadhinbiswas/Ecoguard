"""Integration tests for end-to-end flows."""

import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.integration
class TestHealthFlow:
    @pytest.mark.asyncio
    async def test_root_returns_info(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "Eco-Guard"
        assert "version" in data
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_health_returns_checks(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert "checks" in data
        assert "database" in data["checks"]
        assert "model" in data["checks"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/metrics")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_models_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/models")
        assert r.status_code == 200
        assert "models" in r.json()

    @pytest.mark.asyncio
    async def test_metrics_summary(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/metrics/summary")
        assert r.status_code == 200
        data = r.json()
        assert "model_loaded" in data


@pytest.mark.integration
class TestPredictionFlow:
    @pytest.mark.asyncio
    async def test_predict_requires_prompt(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/v1/predict", json={})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_rejects_empty_prompt(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/predict",
                json={"prompt": "", "max_tokens": 10, "temperature": 0.5},
            )
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_predict_rejects_long_prompt(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/predict",
                json={"prompt": "A" * 5000, "max_tokens": 10, "temperature": 0.5},
            )
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_predict_validates_max_tokens_range(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/predict",
                json={"prompt": "Hello", "max_tokens": 0, "temperature": 0.5},
            )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_validates_temperature_range(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/predict",
                json={"prompt": "Hello", "max_tokens": 10, "temperature": 3.0},
            )
        assert r.status_code == 422


@pytest.mark.integration
class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_404_on_nonexistent_route(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/nonexistent")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_503_on_predict_no_model(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/predict",
                json={"prompt": "Test", "max_tokens": 5, "temperature": 0.5},
            )
        assert r.status_code == 503

    @pytest.mark.asyncio
    async def test_readiness_503_no_model(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/ready")
        assert r.status_code == 503


@pytest.mark.integration
class TestMiddlewareHeaders:
    @pytest.mark.asyncio
    async def test_request_id_header(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/health")
            assert "X-Request-ID" in r.headers

    @pytest.mark.asyncio
    async def test_process_time_header(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/health")
            assert "X-Process-Time-Ms" in r.headers
