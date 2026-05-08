from enum import Enum


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    DB_CONNECTION_FAILED = "DB_CONNECTION_FAILED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    CONCURRENCY_LIMIT = "CONCURRENCY_LIMIT"


ERROR_MESSAGES = {
    ErrorCode.INTERNAL_ERROR: "An unexpected internal error occurred",
    ErrorCode.MODEL_NOT_LOADED: "The inference model is not loaded",
    ErrorCode.MODEL_NOT_FOUND: "The specified model file was not found",
    ErrorCode.INFERENCE_FAILED: "Model inference failed to complete",
    ErrorCode.VALIDATION_ERROR: "The request payload failed validation",
    ErrorCode.RATE_LIMITED: "Too many requests — rate limit exceeded",
    ErrorCode.UNAUTHORIZED: "Missing or invalid API credentials",
    ErrorCode.NOT_FOUND: "The requested resource was not found",
    ErrorCode.SERVICE_UNAVAILABLE: "The service is temporarily unavailable",
    ErrorCode.TIMEOUT: "The request timed out",
    ErrorCode.DB_CONNECTION_FAILED: "Database connection failed",
    ErrorCode.CIRCUIT_OPEN: "Circuit breaker is open — model calls suspended",
    ErrorCode.CONCURRENCY_LIMIT: "Too many concurrent requests — try again later",
}


def error_response(code: ErrorCode, detail: str | None = None) -> dict:
    return {
        "error": {
            "code": code.value,
            "message": detail or ERROR_MESSAGES.get(code, "Unknown error"),
        }
    }


class EcoGuardError(Exception):
    def __init__(self, code: ErrorCode, detail: str | None = None):
        self.code = code
        self.detail = detail or ERROR_MESSAGES.get(code, "Unknown error")
        super().__init__(self.detail)
