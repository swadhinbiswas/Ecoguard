from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Eco-Guard"
    app_version: str = "0.2.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/ecoguard"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_echo: bool = False

    model_path: str = "./models/tinyllama.gguf"
    model_n_ctx: int = 2048
    model_n_threads: int = 4
    model_n_batch: int = 512

    max_input_chars: int = 4000
    allowed_hosts: list[str] = ["*"]
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
    api_keys: list[str] = ["eco-guard-dev-key"]
    jwt_secret: str = "eco-guard-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    admin_username: str = "admin"
    admin_password: str = "admin"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
