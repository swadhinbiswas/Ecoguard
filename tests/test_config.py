"""Test configuration and settings."""

import pytest

from src.core.config import Settings, settings


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
