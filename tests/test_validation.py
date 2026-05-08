import pytest
from fastapi import HTTPException

from src.core.exceptions import (
    EcoGuardException,
    InferenceError,
    ModelNotFoundError,
    ModelNotLoadedError,
    RateLimitExceededError,
    ValidationError,
)
from src.core.security import MAX_INPUT_CHARS, sanitize_prompt


class TestSanitizePrompt:
    def test_valid_prompt(self):
        prompt = "Explain stochastic gradient descent."
        assert sanitize_prompt(prompt) == prompt

    def test_with_whitespace(self):
        prompt = "   hello world   "
        assert sanitize_prompt(prompt) == "hello world"

    def test_empty_string_raises(self):
        with pytest.raises(HTTPException) as excinfo:
            sanitize_prompt("")
        assert excinfo.value.status_code == 400

    def test_whitespace_only_raises(self):
        with pytest.raises(HTTPException) as excinfo:
            sanitize_prompt("   ")
        assert excinfo.value.status_code == 400

    def test_too_long_raises(self):
        prompt = "A" * (MAX_INPUT_CHARS + 1)
        with pytest.raises(HTTPException) as excinfo:
            sanitize_prompt(prompt)
        assert excinfo.value.status_code == 400

    def test_exactly_max_length(self):
        prompt = "A" * MAX_INPUT_CHARS
        assert sanitize_prompt(prompt) == prompt

    def test_null_byte_injection(self):
        prompt = "Hello\x00World"
        assert sanitize_prompt(prompt) == "HelloWorld"

    def test_multiple_null_bytes(self):
        prompt = "\x00Hello\x00World\x00"
        assert sanitize_prompt(prompt) == "HelloWorld"

    def test_special_characters(self):
        prompt = "Hello\nWorld\t!@#$%^&*()"
        assert sanitize_prompt(prompt) == "Hello\nWorld\t!@#$%^&*()"


class TestExceptions:
    def test_eco_guard_exception(self):
        exc = EcoGuardException("Test error")
        assert exc.status_code == 500
        assert exc.message == "Test error"

    def test_model_not_loaded_error(self):
        exc = ModelNotLoadedError()
        assert exc.status_code == 503
        assert "Model is not loaded" in exc.message

    def test_model_not_found_error(self):
        exc = ModelNotFoundError("/path/to/model.gguf")
        assert exc.status_code == 503
        assert "/path/to/model.gguf" in exc.message

    def test_inference_error(self):
        exc = InferenceError()
        assert exc.status_code == 500
        assert "Inference failed" in exc.message

    def test_validation_error(self):
        exc = ValidationError("Bad input")
        assert exc.status_code == 400

    def test_rate_limit_exceeded_error(self):
        exc = RateLimitExceededError(retry_after=30)
        assert exc.status_code == 429
        assert exc.retry_after == 30
