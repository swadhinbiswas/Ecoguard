class EcoGuardException(Exception):
    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class ModelNotLoadedError(EcoGuardException):
    def __init__(self, message: str = "Model is not loaded"):
        super().__init__(message=message, status_code=503)


class ModelNotFoundError(EcoGuardException):
    def __init__(self, model_path: str):
        super().__init__(message=f"Model file not found: {model_path}", status_code=503)


class InferenceError(EcoGuardException):
    def __init__(self, message: str = "Inference failed"):
        super().__init__(message=message, status_code=500)


class ValidationError(EcoGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


class RateLimitExceededError(EcoGuardException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            status_code=429,
            detail=f"Too many requests. Retry after {retry_after} seconds.",
        )
        self.retry_after = retry_after


class DatabaseConnectionError(EcoGuardException):
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message=message, status_code=503)
