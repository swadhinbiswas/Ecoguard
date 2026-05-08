# System API

System endpoints provide health status, readiness checks, model information, benchmarking, and metrics.

## GET /api/v1/health

Returns the overall health of the service, including database and model status.

### Request

```bash
curl http://localhost:8000/api/v1/health
```

> No authentication required (public path).

### Response (200 OK)

```json
{
  "status": "healthy",
  "service": "eco-guard",
  "version": "0.3.0",
  "checks": {
    "database": "up",
    "model": "loaded"
  }
}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `status` | string | `healthy`, `degraded` | Overall service health |
| `service` | string | `"eco-guard"` | Service name |
| `version` | string | SemVer | Current application version |
| `checks.database` | string | `up`, `down` | Database connectivity |
| `checks.model` | string | `loaded`, `not_loaded` | Model loading status |

The status is `healthy` only if the database is up. It is `degraded` if the database is down (regardless of model status).

## GET /api/v1/ready

Kubernetes-style readiness probe. Returns 200 only if the model is fully loaded and ready to serve predictions.

### Request

```bash
curl http://localhost:8000/api/v1/ready
```

> No authentication required (public path).

### Response (200 OK)

```json
{
  "status": "ready"
}
```

### Response (503 Service Unavailable)

```json
{
  "detail": "Model not loaded"
}
```

## GET /api/v1/models

Lists the currently loaded model and cache status.

### Request

```bash
curl http://localhost:8000/api/v1/models \
  -H "X-API-Key: eco-guard-dev-key"
```

### Response (200 OK)

```json
{
  "models": {
    "backend": "LlamaCppBackend",
    "loaded": true
  },
  "cache_size": 42
}
```

For OpenAI-compatible backends:

```json
{
  "models": {
    "backend": "openai-compatible",
    "base_url": "http://localhost:11434",
    "model": "llama3",
    "loaded": true
  },
  "cache_size": 0
}
```

## GET /api/v1/benchmark

Runs a quick benchmark by executing 3 inference passes with the same prompt and reporting timing statistics.

### Request

```bash
curl http://localhost:8000/api/v1/benchmark \
  -H "X-API-Key: eco-guard-dev-key"
```

### Response (200 OK)

```json
{
  "model_path": "./models/tinyllama.gguf",
  "n_ctx": 2048,
  "n_threads": 4,
  "concurrency_limit": 4,
  "runs": [
    {
      "output": "Paris, the",
      "tokens": 10,
      "latency_ms": 95.43
    },
    {
      "output": "Paris, the",
      "tokens": 10,
      "latency_ms": 88.12
    },
    {
      "output": "Paris, the",
      "tokens": 10,
      "latency_ms": 91.55
    }
  ],
  "avg_latency_ms": 91.70,
  "min_latency_ms": 88.12,
  "max_latency_ms": 95.43,
  "tokens_per_second": 109.02
}
```

| Field | Description |
|-------|-------------|
| `model_path` | Path to the loaded GGUF model file |
| `n_ctx` | Context window size |
| `n_threads` | Number of CPU threads |
| `concurrency_limit` | Max concurrent inference limit |
| `runs` | Array of individual benchmark runs |
| `avg_latency_ms` | Mean latency across runs |
| `min_latency_ms` | Fastest run |
| `max_latency_ms` | Slowest run |
| `tokens_per_second` | Aggregate tokens / aggregate seconds |

The benchmark uses the hardcoded prompt `"The capital of France is"` with `temperature=0.0` and `max_tokens=10`.

### Error Response (503)

```json
{
  "detail": "Model not loaded"
}
```

## GET /api/v1/metrics/summary

High-level metrics summary for dashboards.

### Request

```bash
curl http://localhost:8000/api/v1/metrics/summary \
  -H "X-API-Key: eco-guard-dev-key"
```

### Response (200 OK)

```json
{
  "model_loaded": true,
  "cache_enabled": false,
  "cache_size": 0,
  "rate_limit_enabled": true,
  "drift_samples": 1432
}
```

## GET /metrics

Prometheus metrics endpoint in OpenMetrics format.

### Request

```bash
curl http://localhost:8000/metrics
```

> No authentication required (public path).

### Response

```
# HELP ecoguard_http_requests_total Total HTTP requests
# TYPE ecoguard_http_requests_total counter
ecoguard_http_requests_total{method="GET",endpoint="/api/v1/health",status="200"} 487.0
ecoguard_http_requests_total{method="POST",endpoint="/api/v1/predict",status="200"} 1523.0

# HELP ecoguard_http_request_duration_seconds HTTP request duration in seconds
# TYPE ecoguard_http_request_duration_seconds histogram
ecoguard_http_request_duration_seconds_bucket{le="0.005",method="POST",endpoint="/api/v1/predict"} 0.0
ecoguard_http_request_duration_seconds_bucket{le="0.01",method="POST",endpoint="/api/v1/predict"} 12.0
...

# HELP ecoguard_inference_requests_total Total inference requests
# TYPE ecoguard_inference_requests_total counter
ecoguard_inference_requests_total{status="success"} 1523.0
ecoguard_inference_requests_total{status="failure"} 3.0

# HELP ecoguard_inference_tokens_total Total tokens generated
# TYPE ecoguard_inference_tokens_total counter
ecoguard_inference_tokens_total 195216.0

# HELP ecoguard_drift_score Current statistical drift score
# TYPE ecoguard_drift_score gauge
ecoguard_drift_score 0.12

# HELP ecoguard_model_loaded Whether the inference model is loaded
# TYPE ecoguard_model_loaded gauge
ecoguard_model_loaded 1.0

# HELP ecoguard_rate_limited_total Total rate-limited requests
# TYPE ecoguard_rate_limited_total counter
ecoguard_rate_limited_total 5.0
```

## WebSocket /ws/metrics

Real-time metrics streaming over WebSocket. Sends JSON payloads every 2 seconds.

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/metrics');

ws.onmessage = (event) => {
  const metrics = JSON.parse(event.data);
  console.log('Model loaded:', metrics.model_loaded);
  console.log('Concurrency in use:', metrics.concurrency.in_use);
  console.log('Recent latencies:', metrics.latency.recent);
};
```

### Message Format

```json
{
  "timestamp": 1705312200,
  "model_loaded": true,
  "concurrency": {
    "max": 4,
    "in_use": 2
  },
  "latency": {
    "recent": [95.43, 88.12, 91.55, 102.3, 87.9]
  },
  "drift": {
    "samples": 1432
  }
}
```

| Field | Description |
|-------|-------------|
| `timestamp` | Unix epoch seconds |
| `model_loaded` | Whether the inference model is loaded |
| `concurrency.max` | Maximum concurrent inference slots |
| `concurrency.in_use` | Currently occupied slots |
| `latency.recent` | Last 10 inference latencies in milliseconds |
| `drift.samples` | Number of samples in the drift rolling window |

### Ping/Pong

Send `ping` to keep the connection alive:

```javascript
ws.send('ping');
// Receives: {"pong":true}
```

### Auto-Reconnect Example

```javascript
function connectMetrics() {
  const ws = new WebSocket('ws://localhost:8000/ws/metrics');
  ws.onmessage = (e) => updateDashboard(JSON.parse(e.data));
  ws.onclose = () => setTimeout(connectMetrics, 3000);
}
connectMetrics();
```
