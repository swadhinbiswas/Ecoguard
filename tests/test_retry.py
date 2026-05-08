import pytest
from src.core.retry import retry_with_backoff


class TestRetry:
    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        call_count = 0

        async def success():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_with_backoff(success, max_retries=2, base_delay=0.01)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_succeed(self):
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient error")
            return "recovered"

        result = await retry_with_backoff(
            fail_then_succeed, max_retries=3, base_delay=0.01
        )
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhaust_retries_raises(self):
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("persistent error")

        with pytest.raises(ConnectionError):
            await retry_with_backoff(always_fail, max_retries=2, base_delay=0.01)

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_uses_default_retries(self):
        call_count = 0

        async def fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("error")

        with pytest.raises(ConnectionError):
            await retry_with_backoff(fail, base_delay=0.01)

        assert call_count == 6
