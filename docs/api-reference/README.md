# API Reference

Eco-Guard exposes a REST API organized into functional groups. All endpoints are versioned under `/api/v1/`.

## API Groups

| Group | Prefix | Description |
|-------|--------|-------------|
| **System** | `/api/v1` | Health, readiness, model listing, benchmarking |
| **Inference** | `/api/v1` | LLM prediction and streaming |
| **Streaming** | `/api/v1/predict/stream` | Server-Sent Events token stream |
| **MLOps** | `/api/v1/mlops` | Model registry, experiments, training, drift, evaluation |
| **Admin** | `/api/v1/admin` | Logs, statistics, cache management |
| **Auth** | `/api/v1/auth` | Login, token refresh, auth status |
| **Observability** | `/metrics` | Prometheus metrics endpoint |
| **Dashboard** | `/dashboard` | Server-rendered HTML dashboard |
| **WebSocket** | `/ws/metrics` | Live metrics streaming |

## Base URL

All API endpoints are relative to the server's base URL:

```
http://localhost:8000        (development)
https://your-domain.com      (production)
```

## Authentication Methods

Eco-Guard supports three authentication methods. Protected endpoints return HTTP 401 with:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid authentication"
  }
}
```

### Bearer JWT

Obtain a token via `/api/v1/auth/login`:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=admin"
```

```json
{"access_token": "eyJhbGci...", "token_type": "bearer"}
```

Use the token in subsequent requests:

```bash
curl -H "Authorization: Bearer eyJhbGci..." \
  http://localhost:8000/api/v1/predict -d '{"prompt":"Hello"}'
```

### API Key

Pass an API key via the `X-API-Key` header or `?api_key=` query parameter:

```bash
curl -H "X-API-Key: eco-guard-dev-key" \
  http://localhost:8000/api/v1/predict -d '{"prompt":"Hello"}'
```

### Cookie Session

The web dashboard uses a `eco_guard_token` cookie. The API also accepts this cookie for browser-based requests.

## Common Response Formats

### Success

Successful responses return the requested data directly:

```json
{
  "request_id": "a1b2c3d4-...",
  "output": "Generated text here",
  "latency_ms": 245.32,
  "token_count": 15,
  "timestamp": "2025-01-15T10:30:00Z",
  "drift_score": 0.12
}
```

### Validation Error (400)

```json
{
  "detail": "Prompt cannot be empty"
}
```

### Error Response

Errors from the error code system use a structured format:

```json
{
  "error": {
    "code": "MODEL_NOT_LOADED",
    "message": "The inference model is not loaded"
  }
}
```

## Rate Limiting

Rate limiting uses a sliding window algorithm. When exceeded:

**HTTP 429** with headers:
- `X-RateLimit-Limit`: Maximum requests allowed per window (e.g., `100`)
- `Retry-After`: Seconds until the window resets (e.g., `60`)

```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INTERNAL_ERROR` | 500 | Unexpected internal error |
| `MODEL_NOT_LOADED` | 503 | The inference model is not loaded |
| `MODEL_NOT_FOUND` | 503 | The specified model file was not found |
| `INFERENCE_FAILED` | 500 | Model inference failed to complete |
| `VALIDATION_ERROR` | 400 | The request payload failed validation |
| `RATE_LIMITED` | 429 | Too many requests — rate limit exceeded |
| `UNAUTHORIZED` | 401 | Missing or invalid API credentials |
| `NOT_FOUND` | 404 | The requested resource was not found |
| `SERVICE_UNAVAILABLE` | 503 | The service is temporarily unavailable |
| `TIMEOUT` | 504 | The request timed out |
| `DB_CONNECTION_FAILED` | 503 | Database connection failed |
| `CIRCUIT_OPEN` | 503 | Circuit breaker is open — model calls suspended |
| `CONCURRENCY_LIMIT` | 503 | Too many concurrent requests — try again later |

## HTTP Status Code Summary

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid input, empty prompt, prompt too long |
| 401 | Unauthorized | Missing or invalid credentials |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Inference failure, unexpected error |
| 503 | Service Unavailable | Model not loaded, DB down, circuit open |
| 504 | Gateway Timeout | Request exceeded timeout |

## Pagination

List endpoints accept `limit` and `offset` query parameters:

```
GET /api/v1/mlops/models?limit=50&offset=0
```

Response includes the items array (not wrapped in pagination metadata for MLOps endpoints; the admin logs endpoint includes `total`, `limit`, `offset`).

## OpenAPI Specification

The full OpenAPI schema is available at:

- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`
- **Raw JSON:** `/openapi.json`
