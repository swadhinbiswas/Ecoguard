from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Eco-Guard"
    app_version: str = "0.2.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    database_url: str = ""
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_echo: bool = False

    model_path: str = "./models/tinyllama.gguf"
    model_n_ctx: int = 2048
    model_n_threads: int = 4
    model_n_batch: int = 512

    max_input_chars: int = 4000
    cors_origins: list[str] = ["*"]

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    cache_enabled: bool = False
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 1000

    drift_window_size: int = 100
    drift_min_samples: int = 10

    metrics_enabled: bool = True

    auth_enabled: bool = True
    api_keys: list[str] = []
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    admin_username: str = ""
    admin_password: str = ""

    demo_mode: bool = False
    demo_username: str = "demo"
    demo_password: str = "demo"
    demo_read_only: bool = True
    demo_allow_inference: bool = False

    backend: Literal["llama-cpp", "vllm", "tgi", "ollama", "openai"] = "llama-cpp"
    backend_url: str = "http://localhost:8001"
    backend_api_key: str = ""
    backend_model: str = ""

    request_timeout_seconds: int = 120
    circuit_breaker_enabled: bool = True

    db_max_retries: int = 5
    db_retry_base_delay: float = 0.5

    max_concurrent_inference: int = 4
    model_warmup_enabled: bool = True
    model_warmup_prompt: str = "Hello"

    drift_alert_threshold: float = 0.8
    alerting_webhook_url: str = ""

    auto_migrate: bool = False

    shutdown_drain_timeout: float = 15.0

    otlp_endpoint: str = ""
    redis_url: str = ""
    guardrails_enabled: bool = False
    ip_allowlist: list[str] = []
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


def validate_production_settings() -> None:
    if settings.environment != "production":
        return

    errors: list[str] = []
    if settings.auth_enabled:
        if not settings.admin_username or not settings.admin_password:
            errors.append("ADMIN_USERNAME/ADMIN_PASSWORD must be set")
        if not settings.jwt_secret or len(settings.jwt_secret) < 32:
            errors.append("JWT_SECRET must be at least 32 characters")
    if settings.cors_origins == ["*"]:
        errors.append("CORS_ORIGINS must be restricted")
    if not settings.database_url:
        errors.append("DATABASE_URL is required")
    elif not settings.database_url.startswith("postgresql+asyncpg://"):
        errors.append("DATABASE_URL must point to PostgreSQL")

    if errors:
        joined = "; ".join(errors)
        raise RuntimeError(f"Unsafe production configuration: {joined}")
