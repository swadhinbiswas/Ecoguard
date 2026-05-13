import asyncio
from typing import Any, Coroutine


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max = max_concurrent
        self._in_use_count = 0
        self._count_lock = asyncio.Lock()

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def available(self) -> int:
        return self._max - self._in_use_count

    @property
    def in_use(self) -> int:
        return self._in_use_count

    async def acquire(self) -> bool:
        await self._semaphore.acquire()
        async with self._count_lock:
            self._in_use_count += 1
        return True

    def release(self) -> None:
        self._semaphore.release()
        if self._in_use_count > 0:
            self._in_use_count -= 1

    async def __aenter__(self):
        await self._semaphore.acquire()
        async with self._count_lock:
            self._in_use_count += 1
        return self

    async def __aexit__(self, *args):
        self._semaphore.release()
        async with self._count_lock:
            if self._in_use_count > 0:
                self._in_use_count -= 1

    async def run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        async with self:
            return await coro


inference_limiter = ConcurrencyLimiter(max_concurrent=4)
