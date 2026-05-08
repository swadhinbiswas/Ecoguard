from typing import AsyncGenerator

from src.db.database import get_session_local


async def get_db() -> AsyncGenerator:
    """Dependency injection for database sessions."""
    session_factory = get_session_local()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
