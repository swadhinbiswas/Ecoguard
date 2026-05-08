"""Test configuration and settings."""

import pytest

from src.core.config import Settings, settings, validate_production_settings


class TestSettings:
    def test_defaults(self):
        assert settings.app_name == "Eco-Guard"
        assert settings.app_version == "0.2.0"
        assert settings.environment in ("development", "test")
        assert settings.port == 8000
        assert settings.max_input_chars == 4000

    def test_rate_limit_defaults(self):
        assert isinstance(settings.rate_limit_enabled, bool)
        assert settings.rate_limit_requests == 100
        assert settings.rate_limit_window_seconds == 60

    def test_model_defaults(self):
        assert settings.model_n_ctx == 2048
        assert settings.model_n_threads == 4
        assert settings.model_n_batch == 512

    def test_settings_type(self):
        assert isinstance(settings, Settings)

    def test_cache_settings(self):
        assert settings.cache_enabled is False
        assert settings.cache_ttl_seconds == 300
        assert settings.cache_max_entries == 1000

    def test_production_validation_rejects_unsafe_defaults(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "admin_username", "admin")
        monkeypatch.setattr(settings, "admin_password", "admin")
        monkeypatch.setattr(settings, "jwt_secret", "short")
        monkeypatch.setattr(settings, "api_keys", ["eco-guard-dev-key"])
        monkeypatch.setattr(settings, "cors_origins", ["*"])
        monkeypatch.setattr(
            settings, "database_url", "sqlite+aiosqlite:///data/ecoguard.db"
        )

        with pytest.raises(RuntimeError) as excinfo:
            validate_production_settings()

        message = str(excinfo.value)
        assert "ADMIN_USERNAME/ADMIN_PASSWORD" in message
        assert "JWT_SECRET" in message
        assert "PostgreSQL" in message

    def test_production_validation_allows_safe_config(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "admin_username", "owner")
        monkeypatch.setattr(settings, "admin_password", "strong-password")
        monkeypatch.setattr(settings, "jwt_secret", "x" * 32)
        monkeypatch.setattr(settings, "api_keys", [])
        monkeypatch.setattr(settings, "cors_origins", ["https://demo.example.com"])
        monkeypatch.setattr(
            settings,
            "database_url",
            "postgresql+asyncpg://user:pass@localhost:5432/ecoguard",
        )

        validate_production_settings()

    def test_system_status_reports_setup_requirements(self):
        from src.api.routes import _setup_required

        required = _setup_required()
        assert isinstance(required, list)
