# Middleware Stack

Eco-Guard's middleware pipeline is the backbone of every HTTP request. Middleware executes in a defined order, and that order **matters critically** for correctness, security, and observability.

## Middleware Execution Order

```
Request → [1] → [2] → [3] → [4] → [5] → [6] → [7] → Route Handler
                        ↓
Response ← [1] ← [2] ← [3] ← [4] ← [5] ← [6] ← [7] ← Route Handler
```

| # | Middleware | Purpose |
|---|-----------|---------|
| 1 | ShutdownMiddleware | Reject requests during graceful shutdown |
| 2 | CORSMiddleware | Cross-origin resource sharing headers |
| 3 | RequestLoggingMiddleware | Request ID, timing, structured logging |
| 4 | TimeoutMiddleware | Enforce per-request time limit |
| 5 | GZipMiddleware | Response compression |
| 6 | PrometheusMetricsMiddleware | HTTP metrics collection |
| 7 | AuthMiddleware | Authentication and authorization |

### Why Order Matters

1. **Shutdown runs first** — if the server is draining, every request should be rejected immediately with 503. Running it first avoids unnecessary work in other middleware.

2. **CORS runs early** — browsers send preflight `OPTIONS` requests that need CORS headers regardless of auth status. CORS must process before auth.

3. **Logging is early, Auth is late** — logging captures everything for observability. Auth is last so that public endpoints (`/health`, `/docs`) don't traverse auth at all — they're skipped by path prefix matching.

4. **Timeout wraps the remaining stack** — the `asyncio.wait_for()` call in TimeoutMiddleware wraps `call_next()`, which includes all downstream middleware and the route handler. The 504 response it generates still passes back through logging/compression/metrics.

## ShutdownMiddleware

Rejects requests with HTTP 503 during server shutdown drain period.

```python
# Defined inline in src/main.py
@app.middleware("http")
async def shutdown_middleware(request: Request, call_next):
    if _shutting_down:
        return JSONResponse(
            status_code=503,
            content={"detail": "Server is shutting down"},
            headers={"Connection": "close"},
        )
    return await call_next(request)
```

| Option | Default | Description |
|--------|---------|-------------|
| `SHUTDOWN_DRAIN_TIMEOUT` | `15.0` | Seconds to wait for in-flight requests before closing connections |

The `_shutting_down` flag is set during the lifespan shutdown phase. The server sleeps for `shutdown_drain_timeout` seconds before proceeding, giving Kubernetes or Docker time to stop sending traffic.

## CORSMiddleware

Starlette's built-in `CORSMiddleware` configured for API access patterns.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms", "X-RateLimit-Limit", "X-API-Key"],
)
```

| Option | Default | Description |
|--------|---------|-------------|
| `CORS_ORIGINS` | `["*"]` | Allowed origins (JSON array string in `.env`) |
| `allow_methods` | `GET, POST, DELETE, OPTIONS` | Allowed HTTP methods |
| `expose_headers` | `X-Request-ID`, `X-Process-Time-Ms`, ... | Headers accessible to browser JS |

For production, set `CORS_ORIGINS` to your frontend domain:

```env
CORS_ORIGINS=["https://dashboard.example.com"]
```

## RequestLoggingMiddleware

Assigns a UUID request ID and logs the lifecycle of every request.

**Source:** `src/core/middleware.py`

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()
        # ... logs request start, completion, or failure
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(process_time)
        return response
```

**Log output:**
```
INFO  Request started: POST /api/v1/predict - ID: a1b2c3d4-...
INFO  Request completed: POST /api/v1/predict - Status: 200 - Latency: 245.32ms - ID: a1b2c3d4-...
ERROR Request failed: POST /api/v1/predict - Error: Model not loaded - Latency: 1.23ms - ID: a1b2c3d4-...
```

| Header | Description |
|--------|-------------|
| `X-Request-ID` | UUID v4, unique per request |
| `X-Process-Time-Ms` | Total processing time in milliseconds |

## TimeoutMiddleware

Enforces a maximum wall-clock time for each request.

**Source:** `src/core/timeout.py`

```python
class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: int | None = None):
        self.timeout = timeout_seconds or settings.request_timeout_seconds
        self._skip_paths = {"/metrics", "/api/v1/health", "/api/v1/ready"}
```

| Option | Default | Description |
|--------|---------|-------------|
| `REQUEST_TIMEOUT_SECONDS` | `120` | Max request duration before 504 response |

Skipped paths: `/metrics`, `/api/v1/health`, `/api/v1/ready` (health checks should never time out).

**Behavior:** Uses `asyncio.wait_for(call_next(request), timeout=self.timeout)`. If the timeout expires before the route handler completes, the middleware returns HTTP 504 with `{"detail":"Request timeout"}`.

## GZipMiddleware

Starlette's built-in `GZipMiddleware` for response compression.

```python
app.add_middleware(GZipMiddleware, minimum_size=500)
```

| Setting | Value | Description |
|---------|-------|-------------|
| `minimum_size` | `500` bytes | Responses smaller than this are not compressed |

## PrometheusMetricsMiddleware

Records per-request HTTP metrics using `prometheus_client`.

**Source:** `src/monitoring/metrics.py`

```python
class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        http_requests_total.labels(method, endpoint, status).inc()
        http_request_duration_seconds.labels(method, endpoint).observe(duration)
        return response
```

| Option | Default | Description |
|--------|---------|-------------|
| `METRICS_ENABLED` | `true` | Enable/disable all metrics collection |

Skipped paths: `/metrics`, `/health`, `/api/v1/health` (metrics endpoint should not self-instrument).

## AuthMiddleware

Validates authentication credentials. Runs last in the middleware chain.

**Source:** `src/core/auth.py`

```python
class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, require_auth: bool = True):
        self.require_auth = require_auth
```

| Option | Default | Description |
|--------|---------|-------------|
| `AUTH_ENABLED` | `true` | Enable/disable authentication requirement |
| `JWT_SECRET` | `"eco-guard-jwt-secret-change-in-production"` | HMAC secret for JWT tokens |
| `JWT_ALGORITHM` | `"HS256"` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `1440` | Token lifetime (24 hours) |
| `API_KEYS` | `["eco-guard-dev-key"]` | List of valid API keys |
| `ADMIN_USERNAME` | `"admin"` | Dashboard login username |
| `ADMIN_PASSWORD` | `"admin"` | Dashboard login password |

### Authentication Methods

The middleware checks credentials in this order:

1. **Bearer JWT** — `Authorization: Bearer <token>` header
2. **Cookie** — `eco_guard_token` cookie (used by dashboard session)
3. **API Key** — `X-API-Key: <key>` header or `?api_key=<key>` query param

### Public Paths

The following paths are **always public** and skip authentication:

```
/, /docs, /redoc, /openapi.json, /metrics,
/api/v1/health, /api/v1/ready,
/dashboard/login, /static/,
/api/v1/auth/login, /api/v1/auth/status
```

Dashboard routes (`/dashboard/*`) receive a special redirect (HTTP 302) to the login page when unauthenticated, rather than a JSON 401 error. All other protected routes return:

```json
{"error":{"code":"UNAUTHORIZED","message":"Missing or invalid authentication"}}
```

with HTTP 401 and a `WWW-Authenticate: Bearer` header.

### SlowAPI Rate Limiter

In addition to the middleware stack, rate limiting is handled by SlowAPI's `Limiter`:

```python
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

| Option | Default | Description |
|--------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window size in seconds |

Rate limit responses include headers:
- `X-RateLimit-Limit`: Max requests allowed
- `Retry-After`: Seconds until the next window

## Example Configuration

Full middleware configuration in `.env`:

```env
# CORS
CORS_ORIGINS=["https://dashboard.example.com"]

# Timeout
REQUEST_TIMEOUT_SECONDS=120

# Metrics
METRICS_ENABLED=true

# Auth
AUTH_ENABLED=true
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
API_KEYS=["eg-prod-key-1","eg-prod-key-2"]
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-password

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Shutdown
SHUTDOWN_DRAIN_TIMEOUT=15.0
```
