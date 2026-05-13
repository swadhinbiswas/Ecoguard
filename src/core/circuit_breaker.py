import asyncio
import inspect
import time
from typing import Callable, TypeVar

from src.core.logging import logger

T = TypeVar("T")


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._state = self.CLOSED
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        async with self._lock:
            if self._state == self.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker: OPEN -> HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN. Retry in {self.recovery_timeout - (time.monotonic() - self._last_failure_time):.1f}s"
                    )

            if self._state == self.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        "Circuit breaker is HALF_OPEN - max trial calls reached"
                    )
                self._half_open_calls += 1

        try:
            result = (
                await func(*args, **kwargs)
                if inspect.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
        except Exception:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                if (
                    self._state == self.CLOSED
                    and self._failure_count >= self.failure_threshold
                ):
                    self._state = self.OPEN
                    logger.warning(
                        f"Circuit breaker: CLOSED -> OPEN ({self._failure_count} failures)"
                    )
                elif self._state == self.HALF_OPEN:
                    self._state = self.OPEN
                    logger.warning("Circuit breaker: HALF_OPEN -> OPEN")
            raise

        async with self._lock:
            if self._state == self.HALF_OPEN:
                self._state = self.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED")
            else:
                self._failure_count = 0

        return result

    async def reset(self) -> None:
        async with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0


class CircuitBreakerOpenError(Exception):
    pass


model_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    half_open_max_calls=2,
)
