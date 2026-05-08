import asyncio

import pytest

from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class TestCircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.5,
            half_open_max_calls=2,
        )

    @pytest.mark.asyncio
    async def test_closed_state_initially(self):
        assert self.cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call_keeps_closed(self):
        async def success():
            return "ok"

        result = await self.cb.call(success)
        assert result == "ok"
        assert self.cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        async def fail():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await self.cb.call(fail)

        assert self.cb.state == CircuitBreaker.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        async def quick():
            return "ok"

        async def fail():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await self.cb.call(fail)

        with pytest.raises(CircuitBreakerOpenError):
            await self.cb.call(quick)

    @pytest.mark.asyncio
    async def test_recovery_to_half_open(self):
        async def fail():
            raise RuntimeError("fail")

        async def success():
            return "ok"

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await self.cb.call(fail)

        assert self.cb.state == CircuitBreaker.OPEN

        await asyncio.sleep(0.6)
        result = await self.cb.call(success)
        assert result == "ok"
        assert self.cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_fails_opens_again(self):
        async def fail():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await self.cb.call(fail)

        await asyncio.sleep(0.6)
        with pytest.raises(RuntimeError):
            await self.cb.call(fail)

        assert self.cb.state == CircuitBreaker.OPEN


class TestBackgroundRunner:
    @pytest.mark.asyncio
    async def test_task_runs_and_completes(self):
        from src.services.background import background_runner

        results = []

        async def task():
            results.append("done")

        await background_runner.submit(task(), name="test-task")
        await asyncio.sleep(0.1)
        assert "done" in results

    @pytest.mark.asyncio
    async def test_task_exception_is_handled(self):
        from src.services.background import background_runner

        async def failing_task():
            raise ValueError("test error")

        await background_runner.submit(failing_task(), name="failing-task")
        await asyncio.sleep(0.1)
