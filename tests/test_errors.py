import pytest

from src.core.error_codes import (
    ERROR_MESSAGES,
    EcoGuardError,
    ErrorCode,
    error_response,
)


class TestErrorCodes:
    def test_all_codes_have_messages(self):
        for code in ErrorCode:
            assert code in ERROR_MESSAGES

    def test_error_response_format(self):
        resp = error_response(ErrorCode.VALIDATION_ERROR, "Bad input")
        assert resp["error"]["code"] == "VALIDATION_ERROR"
        assert resp["error"]["message"] == "Bad input"

    def test_error_response_default_message(self):
        resp = error_response(ErrorCode.MODEL_NOT_LOADED)
        assert resp["error"]["message"] == ERROR_MESSAGES[ErrorCode.MODEL_NOT_LOADED]

    def test_eco_guard_error(self):
        exc = EcoGuardError(ErrorCode.TIMEOUT)
        assert exc.code == ErrorCode.TIMEOUT
        assert "timed out" in exc.detail.lower()

    def test_eco_guard_error_custom_detail(self):
        exc = EcoGuardError(ErrorCode.INTERNAL_ERROR, "Custom message")
        assert exc.detail == "Custom message"


class TestConcurrencyLimiter:
    @pytest.mark.asyncio
    async def test_initial_state(self):
        from src.core.concurrency import ConcurrencyLimiter

        limiter = ConcurrencyLimiter(max_concurrent=3)
        assert limiter.max_concurrent == 3
        assert limiter.in_use == 0
        assert limiter.available == 3

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        from src.core.concurrency import ConcurrencyLimiter

        limiter = ConcurrencyLimiter(max_concurrent=2)
        async with limiter:
            assert limiter.in_use == 1
        assert limiter.in_use == 0

    @pytest.mark.asyncio
    async def test_run_method(self):
        from src.core.concurrency import ConcurrencyLimiter

        limiter = ConcurrencyLimiter(max_concurrent=1)
        result = await limiter.run(__import__("asyncio").sleep(0.01))
        assert result is None


class TestSchemas:
    def test_prediction_request_defaults(self):
        from src.models.schemas import PredictionRequest

        req = PredictionRequest(prompt="Hello")
        assert req.max_tokens == 128
        assert req.temperature == 0.7
        assert req.top_p is None
        assert req.top_k is None
        assert req.repeat_penalty is None

    def test_prediction_request_full(self):
        from src.models.schemas import PredictionRequest

        req = PredictionRequest(
            prompt="Test",
            max_tokens=512,
            temperature=0.5,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.2,
        )
        assert req.prompt == "Test"
        assert req.max_tokens == 512
        assert req.temperature == 0.5
        assert req.top_p == 0.9
        assert req.top_k == 40
        assert req.repeat_penalty == 1.2

    def test_prediction_request_invalid_top_p(self):
        from pydantic import ValidationError

        from src.models.schemas import PredictionRequest

        with pytest.raises(ValidationError):
            PredictionRequest(prompt="Test", top_p=1.5)

    def test_max_tokens_upper_bound(self):
        from src.models.schemas import PredictionRequest

        req = PredictionRequest(prompt="Test", max_tokens=2048)
        assert req.max_tokens == 2048

    def test_max_tokens_exceeds_bound(self):
        from pydantic import ValidationError

        from src.models.schemas import PredictionRequest

        with pytest.raises(ValidationError):
            PredictionRequest(prompt="Test", max_tokens=3000)
