import pytest
from httpx import ASGITransport, AsyncClient

from src.core.auth import APIKeyStore, AuthMiddleware, is_public_path
from src.main import app


class TestAPIKeyStore:
    def setup_method(self):
        self.store = APIKeyStore()

    def test_empty_store_rejects(self):
        assert self.store.validate("bad-key") is False

    def test_add_and_validate_key(self):
        self.store.add_key("test-key-123")
        assert self.store.validate("test-key-123") is True
        assert self.store.validate("wrong-key") is False

    def test_revoke_key(self):
        self.store.add_key("key-to-revoke")
        assert self.store.validate("key-to-revoke") is True
        self.store.revoke_key("key-to-revoke")
        assert self.store.validate("key-to-revoke") is False

    def test_generate_key(self):
        key = self.store.generate_key()
        assert key.startswith("eg-")
        assert len(key) > 10
        assert self.store.validate(key) is True

    def test_key_count(self):
        assert self.store.key_count == 0
        self.store.add_key("a")
        assert self.store.key_count == 1
        self.store.add_key("b")
        assert self.store.key_count == 2
        self.store.revoke_key("a")
        assert self.store.key_count == 1


class TestPublicPathMatching:
    def test_root_is_public_but_not_every_path(self):
        assert is_public_path("/") is True
        assert is_public_path("/api/v1/health") is True
        assert is_public_path("/static/app.css") is True
        assert is_public_path("/api/v1/predict") is False
        assert is_public_path("/dashboard/models") is False


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_accepts_json_body(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin"},
            )
        assert r.status_code == 200
        assert r.json()["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_rejects_query_param_credentials(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/v1/auth/login?username=admin&password=admin")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_demo_login_returns_viewer_role(self, monkeypatch):
        from src.core.config import settings

        monkeypatch.setattr(settings, "demo_mode", True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/auth/login",
                json={"username": "demo", "password": "demo"},
            )
        assert r.status_code == 200
        assert r.json()["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_demo_mode_blocks_mutating_routes(self, monkeypatch):
        from src.core.config import settings

        monkeypatch.setattr(settings, "demo_mode", True)
        monkeypatch.setattr(settings, "demo_read_only", True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/v1/mlops/jobs", json={})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DEMO_READ_ONLY"
