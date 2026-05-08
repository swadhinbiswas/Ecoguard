import os

import pytest


@pytest.fixture(autouse=True)
def set_test_env():
    os.environ["ENVIRONMENT"] = "development"
    os.environ["LOG_LEVEL"] = "ERROR"
    os.environ["METRICS_ENABLED"] = "true"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["AUTH_ENABLED"] = "false"
    yield
    os.environ.pop("ENVIRONMENT", None)
    os.environ.pop("LOG_LEVEL", None)
    os.environ.pop("METRICS_ENABLED", None)
    os.environ.pop("RATE_LIMIT_ENABLED", None)
    os.environ.pop("AUTH_ENABLED", None)


@pytest.fixture(scope="session")
def _init_test_db():
    import asyncio

    from src.core.backend import init_backend
    from src.db.database import init_db

    async def _init():
        try:
            await init_db()
        except Exception:
            pass
        try:
            init_backend()
        except Exception:
            pass

    asyncio.run(_init())
    yield


@pytest.fixture(autouse=True)
def ensure_db(_init_test_db):
    pass
