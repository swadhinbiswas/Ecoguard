import asyncio
from typing import Any, Awaitable

from src.core.logging import logger


class BackgroundTaskRunner:
    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        self._running = True

    async def submit(self, coro: Awaitable[Any], name: str = "unnamed") -> None:
        task = asyncio.create_task(self._run_task(coro, name))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_task(self, coro: Awaitable[Any], name: str) -> None:
        try:
            await coro
        except Exception as e:
            logger.error(f"Background task '{name}' failed: {e}")

    async def shutdown(self, timeout: float = 10.0) -> None:
        self._running = False
        if not self._tasks:
            return
        logger.info(f"Waiting for {len(self._tasks)} background tasks to complete...")
        pending = list(self._tasks)
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Background tasks did not complete within {timeout}s")
            for task in pending:
                task.cancel()

    @property
    def pending_count(self) -> int:
        return len(self._tasks)


background_runner = BackgroundTaskRunner()
