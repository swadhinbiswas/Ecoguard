# Configuration

Eco-Guard uses **pydantic-settings** for configuration management. All settings are defined in a single `Settings` class in `src/core/config.py` and loaded from environment variables and/or a `.env` file.

## Configuration System

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Eco-Guard"
    # ... 42 configuration variables ...

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

## Environment Variable Precedence

Settings are resolved in the following order (higher takes priority):

```
1. Environment variable (exported in shell)     ← highest
2. .env file value                              ← medium
3. Python default in Settings class             ← lowest
```

This means:
- If a variable is set in both the shell and `.env`, the shell value wins
- If a variable is only in `.env`, the `.env` value is used
- If a variable is in neither, the Python default applies

### Example

```bash
# Settings class default
port: int = 8000   # used if nothing else is set

# .env file
PORT=9000          # used if no shell variable

# Shell
export PORT=8080   # always wins
```

## .env File

Create a `.env` file in the project root. Copy from the provided template:

```bash
cp .env.example .env
```

File format:

```env
# Comments start with #
KEY=value
ANOTHER_KEY=another value
BOOLEAN_FLAG=true
INTEGER_VALUE=42
JSON_ARRAY=["item1","item2"]
```

### .env.example Reference

The complete `.env.example` file:

```env
# Application
APP_NAME=Eco-Guard
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ecoguard
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Model
MODEL_PATH=./models/tinyllama.gguf
MODEL_N_CTX=2048
MODEL_N_THREADS=4

# Security
MAX_INPUT_CHARS=4000
CORS_ORIGINS=["*"]

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Caching
CACHE_ENABLED=false
CACHE_TTL_SECONDS=300
CACHE_MAX_ENTRIES=1000

# Drift Detection
DRIFT_WINDOW_SIZE=100
DRIFT_MIN_SAMPLES=10

# Monitoring
METRICS_ENABLED=true

# Authentication
AUTH_ENABLED=false
API_KEYS=[]

# Request Protection
REQUEST_TIMEOUT_SECONDS=120
CIRCUIT_BREAKER_ENABLED=true
MAX_CONCURRENT_INFERENCE=4

# Model Warmup
MODEL_WARMUP_ENABLED=true
MODEL_WARMUP_PROMPT=Hello

# Drift & Retraining
DRIFT_ALERT_THRESHOLD=0.8
ALERTING_WEBHOOK_URL=

# Database Migrations
AUTO_MIGRATE=false
DB_MAX_RETRIES=5
DB_RETRY_BASE_DELAY=0.5

# Shutdown
SHUTDOWN_DRAIN_TIMEOUT=15.0
```

## Configuration Groups

Settings are organized into logical groups:

| Group | Variables |
|-------|-----------|
| **App** | `app_name`, `app_version`, `environment`, `debug`, `log_level` |
| **Server** | `host`, `port`, `workers` |
| **Database** | `database_url`, `db_pool_size`, `db_max_overflow`, `db_pool_timeout`, `db_echo`, `db_max_retries`, `db_retry_base_delay`, `auto_migrate` |
| **Model** | `model_path`, `model_n_ctx`, `model_n_threads`, `model_n_batch` |
| **Backend** | `backend`, `backend_url`, `backend_api_key`, `backend_model` |
| **Security** | `max_input_chars`, `allowed_hosts`, `cors_origins` |
| **Rate Limiting** | `rate_limit_enabled`, `rate_limit_requests`, `rate_limit_window_seconds` |
| **Caching** | `cache_enabled`, `cache_ttl_seconds`, `cache_max_entries` |
| **Drift** | `drift_window_size`, `drift_min_samples`, `drift_alert_threshold` |
| **Monitoring** | `metrics_enabled`, `otlp_endpoint` |
| **Auth** | `auth_enabled`, `api_keys`, `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes`, `admin_username`, `admin_password` |
| **Retraining** | `max_concurrent_inference`, `model_warmup_enabled`, `model_warmup_prompt`, `alerting_webhook_url` |
| **Shutdown** | `shutdown_drain_timeout`, `request_timeout_seconds`, `circuit_breaker_enabled` |

## Accessing Settings in Code

Import the global `settings` singleton:

```python
from src.core.config import settings

print(settings.app_name)        # "Eco-Guard"
print(settings.port)            # 8000
print(settings.database_url)    # "postgresql+asyncpg://..."
```

## Type Validation

pydantic-settings validates types at startup. Invalid values cause the application to fail immediately:

```python
# These will crash at startup with a clear error:
port: int = 8000              # Must be integer
log_level: Literal["DEBUG", "INFO", ...]  # Must be one of these values
environment: Literal["development", "staging", "production", "test"]
cors_origins: list[str] = ["*"]  # Must be JSON array in .env
```

## Environment-Specific Configurations

### Development

```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
AUTH_ENABLED=false
DB_ECHO=true
```

### Production

```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
AUTH_ENABLED=true
API_KEYS=["your-secure-key"]
JWT_SECRET=your-random-secret
ADMIN_PASSWORD=secure-password
CORS_ORIGINS=["https://your-domain.com"]
```
