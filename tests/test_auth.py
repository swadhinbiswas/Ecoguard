import pytest

from src.core.auth import APIKeyStore, AuthMiddleware


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
