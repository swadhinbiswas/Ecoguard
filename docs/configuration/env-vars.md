# Environment Variables

Complete reference of all 42 environment variables used by Eco-Guard.

## Application

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `APP_NAME` | `str` | `"Eco-Guard"` | Display name used in logs, metrics, and dashboard |
| `APP_VERSION` | `str` | `"0.2.0"` | SemVer version, shown in API responses and health checks |
| `ENVIRONMENT` | `str` | `"development"` | Runtime environment: `development`, `staging`, `production`, `test` |
| `DEBUG` | `bool` | `false` | Enable debug mode (more verbose logging) |
| `LOG_LEVEL` | `str` | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

## Server

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `HOST` | `str` | `"0.0.0.0"` | Bind address for the HTTP server |
| `PORT` | `int` | `8000` | Bind port for the HTTP server |
| `WORKERS` | `int` | `1` | Number of uvicorn worker processes |

## Database

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `DATABASE_URL` | `str` | `"postgresql+asyncpg://postgres:password@localhost:5432/ecoguard"` | PostgreSQL connection URL with asyncpg driver |
| `DB_POOL_SIZE` | `int` | `20` | SQLAlchemy connection pool size (PostgreSQL only) |
| `DB_MAX_OVERFLOW` | `int` | `10` | Additional connections above pool_size under load |
| `DB_POOL_TIMEOUT` | `int` | `30` | Seconds to wait for a connection from the pool |
| `DB_ECHO` | `bool` | `false` | Log all SQL statements (debug only) |
| `DB_MAX_RETRIES` | `int` | `5` | Max retry attempts for initial database connection |
| `DB_RETRY_BASE_DELAY` | `float` | `0.5` | Base delay for exponential backoff on connection retry |
| `AUTO_MIGRATE` | `bool` | `false` | Run Alembic migrations automatically on startup |

## Model

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `MODEL_PATH` | `str` | `"./models/tinyllama.gguf"` | Path to the GGUF model file |
| `MODEL_N_CTX` | `int` | `2048` | Context window size in tokens |
| `MODEL_N_THREADS` | `int` | `4` | Number of CPU threads for llama.cpp inference |
| `MODEL_N_BATCH` | `int` | `512` | Batch size for prompt processing |

## Backend

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `BACKEND` | `str` | `"llama-cpp"` | Backend type: `llama-cpp`, `vllm`, `tgi`, `ollama`, `openai` |
| `BACKEND_URL` | `str` | `"http://localhost:8001"` | Base URL for OpenAI-compatible backends |
| `BACKEND_API_KEY` | `str` | `""` | API key for the remote backend (Bearer auth) |
| `BACKEND_MODEL` | `str` | `""` | Model name sent in the `model` field to the backend |

## Security

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `MAX_INPUT_CHARS` | `int` | `4000` | Maximum characters allowed in a prompt |
| `ALLOWED_HOSTS` | `list[str]` | `["*"]` | Allowed host header values |
| `CORS_ORIGINS` | `list[str]` | `["*"]` | Allowed CORS origins (JSON array) |

## Rate Limiting

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `bool` | `true` | Enable client IP-based rate limiting |
| `RATE_LIMIT_REQUESTS` | `int` | `100` | Maximum requests per window per client |
| `RATE_LIMIT_WINDOW_SECONDS` | `int` | `60` | Window duration in seconds |

## Caching

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `CACHE_ENABLED` | `bool` | `false` | Enable in-memory inference result caching |
| `CACHE_TTL_SECONDS` | `int` | `300` | Time-to-live for cached entries |
| `CACHE_MAX_ENTRIES` | `int` | `1000` | Maximum cache entries (LRU eviction) |

## Drift Detection

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `DRIFT_WINDOW_SIZE` | `int` | `100` | Rolling window size for latency samples |
| `DRIFT_MIN_SAMPLES` | `int` | `10` | Minimum samples before drift calculation starts |
| `DRIFT_ALERT_THRESHOLD` | `float` | `0.8` | Drift score threshold for alerting and auto-retraining (0.0–1.0) |

## Monitoring

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `METRICS_ENABLED` | `bool` | `true` | Enable Prometheus metrics and OpenTelemetry tracing |
| `OTLP_ENDPOINT` | `str` | `""` | OpenTelemetry collector endpoint URL |

## Authentication

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `AUTH_ENABLED` | `bool` | `true` | Require authentication for protected endpoints |
| `API_KEYS` | `list[str]` | `["eco-guard-dev-key"]` | Valid API keys (JSON array) |
| `JWT_SECRET` | `str` | `"eco-guard-jwt-secret-change-in-production"` | HMAC secret for JWT signing |
| `JWT_ALGORITHM` | `str` | `"HS256"` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `int` | `1440` | JWT token lifetime in minutes (24 hours) |
| `ADMIN_USERNAME` | `str` | `"admin"` | Default admin login username |
| `ADMIN_PASSWORD` | `str` | `"admin"` | Default admin login password |

## Retraining & Protection

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `MAX_CONCURRENT_INFERENCE` | `int` | `4` | Maximum simultaneous inference operations |
| `MODEL_WARMUP_ENABLED` | `bool` | `true` | Run a warmup inference on startup |
| `MODEL_WARMUP_PROMPT` | `str` | `"Hello"` | Prompt used for model warmup |
| `REQUEST_TIMEOUT_SECONDS` | `int` | `120` | Per-request timeout before 504 response |
| `CIRCUIT_BREAKER_ENABLED` | `bool` | `true` | Enable circuit breaker for model calls |
| `ALERTING_WEBHOOK_URL` | `str` | `""` | Webhook URL for drift alert notifications |
| `SHUTDOWN_DRAIN_TIMEOUT` | `float` | `15.0` | Seconds to wait for in-flight requests during shutdown |

## Boolean Values

Boolean settings accept: `true`, `True`, `TRUE`, `1`, `yes`, `on` (and their false equivalents).

## List Values

List settings use JSON array syntax in `.env`:

```env
CORS_ORIGINS=["https://example.com","https://app.example.com"]
API_KEYS=["key-one","key-two","key-three"]
```

For environment variables in the shell, use proper quoting:

```bash
export API_KEYS='["key-one","key-two"]'
```
