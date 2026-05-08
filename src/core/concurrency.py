import asyncio
from typing import Any, Coroutine


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max = max_concurrent

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def available(self) -> int:
        return self._semaphore._value

    @property
    def in_use(self) -> int:
        return self._max - self._semaphore._value

    async def acquire(self) -> bool:
        return True

    def release(self) -> None:
        pass

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *args):
        self._semaphore.release()

    async def run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        async with self:
            return await coro


inference_limiter = ConcurrencyLimiter(max_concurrent=4)
