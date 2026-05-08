from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from src.core.config import settings
from src.core.logging import logger

Base = declarative_base()

_engine = None
_async_session_local = None
_using_sqlite = False


def _get_engine_kwargs(pool_class) -> dict:
    kwargs: dict = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,
        "poolclass": pool_class,
    }
    if pool_class != NullPool:
        kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
            }
        )
    return kwargs


def _create_sqlite_engine():
    import os

    os.makedirs("data", exist_ok=True)
    url = "sqlite+aiosqlite:///data/ecoguard.db"
    return create_async_engine(url, echo=settings.db_echo, poolclass=NullPool)


def _create_postgres_engine():
    pool_class = NullPool if settings.environment == "development" else QueuePool
    return create_async_engine(settings.database_url, **_get_engine_kwargs(pool_class))


async def _probe_postgres() -> bool:
    try:
        engine = _create_postgres_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    raise RuntimeError("Database not initialized")


def get_session_local():
    global _async_session_local
    if _async_session_local is not None:
        return _async_session_local
    raise RuntimeError("Database not initialized")


def is_sqlite() -> bool:
    return _using_sqlite


async def init_db() -> None:
    global _engine, _async_session_local, _using_sqlite

    postgres_ok = await _probe_postgres()

    if postgres_ok:
        _engine = _create_postgres_engine()
        _using_sqlite = False
        logger.info("Using PostgreSQL database")
    else:
        if settings.environment == "production":
            raise RuntimeError("PostgreSQL is required in production")
        _engine = _create_sqlite_engine()
        _using_sqlite = True
        logger.info(
            "PostgreSQL unavailable — falling back to SQLite (data/ecoguard.db)"
        )

    _async_session_local = sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with _engine.begin() as conn:
            if settings.environment == "production":
                logger.info("Skipping automatic schema creation in production")
            else:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")


async def close_db() -> None:
    global _engine
    if _engine is not None:
        try:
            await _engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.debug(f"DB close skipped: {e}")
        _engine = None


async def check_db_health() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
