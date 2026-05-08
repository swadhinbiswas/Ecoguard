import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_predict_empty_prompt():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/predict",
            json={"prompt": "", "max_tokens": 128, "temperature": 0.7},
        )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_predict_prompt_too_long():
    long_prompt = "A" * 5000
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/predict",
            json={"prompt": long_prompt, "max_tokens": 128, "temperature": 0.7},
        )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_predict_invalid_max_tokens():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/predict",
            json={"prompt": "Hello", "max_tokens": 0, "temperature": 0.7},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_invalid_temperature():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/predict",
            json={"prompt": "Hello", "max_tokens": 128, "temperature": 3.0},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_missing_prompt():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/predict",
            json={"max_tokens": 128, "temperature": 0.7},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_model_not_loaded():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/predict",
            json={"prompt": "Hello", "max_tokens": 10, "temperature": 0.5},
        )
    assert response.status_code == 503
