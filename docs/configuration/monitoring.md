# Monitoring

Eco-Guard exposes Prometheus metrics, supports OpenTelemetry tracing, provides a Grafana dashboard, and streams live metrics over WebSocket.

## Prometheus Metrics Catalog

All metric names are prefixed with `ecoguard_`.

### HTTP Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ecoguard_http_requests_total` | Counter | `method`, `endpoint`, `status` | Total HTTP requests by method, path, and status code |
| `ecoguard_http_request_duration_seconds` | Histogram | `method`, `endpoint` | HTTP request duration distribution |

**Histogram buckets:** `0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0` (seconds)

### Inference Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ecoguard_inference_requests_total` | Counter | `status` (`success`, `failure`) | Total inference requests |
| `ecoguard_inference_duration_seconds` | Histogram | (none) | Inference duration distribution |
| `ecoguard_inference_tokens_total` | Counter | (none) | Total tokens generated across all inferences |
| `ecoguard_inference_tokens_per_request` | Histogram | (none) | Tokens per inference request distribution |

**Inference duration buckets:** `0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0` (seconds)

**Tokens per request buckets:** `8, 16, 32, 64, 128, 256, 512, 1024`

### Health & Status Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ecoguard_drift_score` | Gauge | (none) | Current statistical drift score (0.0–1.0) |
| `ecoguard_model_loaded` | Gauge | (none) | Model loaded status: 1 = loaded, 0 = not loaded |
| `ecoguard_rate_limited_total` | Counter | (none) | Total rate-limited requests |

## Prometheus Scrape Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "eco-guard"
    scrape_interval: 15s
    metrics_path: "/metrics"
    static_configs:
      - targets: ["localhost:8000"]
```

### Kubernetes Annotations

The Kubernetes deployment includes Prometheus annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

With the Prometheus Operator, enable the ServiceMonitor in Helm values:

```yaml
monitoring:
  serviceMonitor:
    enabled: true
```

## Grafana Dashboard

Import the pre-built dashboard from `monitoring/grafana/dashboard.json`.

### Import Steps

1. In Grafana, go to **Dashboards → Import**
2. Upload `monitoring/grafana/dashboard.json` or paste the JSON
3. Select your Prometheus data source
4. Click **Import**

### Dashboard Panels

The dashboard includes the following panels:

| Panel | Type | Metric |
|-------|------|--------|
| HTTP Requests/s | Stat | `rate(ecoguard_http_requests_total[5m])` |
| Avg Latency (ms) | Stat | Average latency from histogram |
| Error Rate % | Stat | 5xx / total requests |
| Drift Score | Stat | `ecoguard_drift_score` |
| Model Loaded | Stat | `ecoguard_model_loaded` |
| Tokens/s | Stat | `rate(ecoguard_inference_tokens_total[5m])` |
| Request Rate by Status | Timeseries | 2xx, 4xx, 5xx rates |
| Latency Percentiles | Timeseries | p50, p95, p99 |
| Inference Latency | Timeseries | Average inference duration |
| Drift Score Over Time | Timeseries | `ecoguard_drift_score` |
| Token Throughput | Timeseries | Token generation rate |
| Top Endpoints | Bar Gauge | Request rate by endpoint |
| Rate Limited Requests | Timeseries | Rate limit hit rate |

### Dashboard Settings

- **Refresh:** 10 seconds
- **Time range:** Last 1 hour (adjustable)
- **UID:** `eco-guard`
- **Tags:** `eco-guard`, `llm`, `mlops`

## Built-in Alert Rules

Alert rules are defined in `monitoring/prometheus/alerts.yml`:

### HighErrorRate

```yaml
expr: sum(rate(ecoguard_http_requests_total{status=~"5.."}[5m])) /
      sum(rate(ecoguard_http_requests_total[5m])) > 0.05
for: 5m
severity: critical
```

Triggers when the 5xx error rate exceeds 5% over 5 minutes.

### HighLatency

```yaml
expr: histogram_quantile(0.95,
      rate(ecoguard_http_request_duration_seconds_bucket[5m])) > 5
for: 5m
severity: warning
```

Triggers when p95 latency exceeds 5 seconds.

### DriftThresholdExceeded

```yaml
expr: ecoguard_drift_score > 0.8
for: 1m
severity: warning
```

Triggers when the drift score exceeds 0.8.

### ModelNotLoaded

```yaml
expr: ecoguard_model_loaded == 0
for: 2m
severity: critical
```

Triggers when the model has been unloaded for more than 2 minutes.

### HighRateLimiting

```yaml
expr: rate(ecoguard_rate_limited_total[5m]) > 1
for: 5m
severity: warning
```

Triggers when rate-limited requests exceed 1 per second.

### LowTokenThroughput

```yaml
expr: rate(ecoguard_inference_tokens_total[5m]) < 1 and
      ecoguard_http_requests_total > 0
for: 10m
severity: info
```

Triggers when token throughput is abnormally low while requests are being served.

### InstanceDown

```yaml
expr: up{job="eco-guard"} == 0
for: 1m
severity: critical
```

Triggers when the instance is unreachable.

## Metrics Endpoint

The `/metrics` endpoint is always public (no authentication required). It returns Prometheus' OpenMetrics format:

```bash
curl http://localhost:8000/metrics
```

Metrics collection can be disabled:

```env
METRICS_ENABLED=false
```

## OpenTelemetry Configuration

Eco-Guard supports OpenTelemetry tracing with automatic instrumentation of FastAPI and SQLAlchemy.

### Setup

```env
METRICS_ENABLED=true
OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

When `OTLP_ENDPOINT` is set, spans are exported via OTLP over HTTP to the specified collector. The following spans are automatically captured:

- All HTTP requests (via `FastAPIInstrumentor`)
- SQLAlchemy queries (via `SQLAlchemyInstrumentor`)
- Inference operations (via custom `trace_inference()`)

### Custom Inference Spans

Each inference request creates a span with attributes:

```
Span: "inference"
Attributes:
  - request.id: "a1b2c3d4-..."
  - inference.prompt_length: 45
  - inference.latency_ms: 245.32
  - inference.token_count: 128
  - inference.drift_score: 0.12
  - model.path: "./models/tinyllama.gguf"
  - model.n_ctx: 2048
  - model.n_threads: 4
Events:
  - inference_complete: { request_id, latency_ms, token_count }
```

### Running a Local Collector

```bash
# Jaeger (all-in-one)
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# Then set:
OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

## WebSocket Live Metrics Format

The `/ws/metrics` WebSocket endpoint broadcasts real-time metrics every 2 seconds.

### Payload Format

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

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | int | Unix epoch seconds |
| `model_loaded` | bool | Model loaded status |
| `concurrency.max` | int | Maximum concurrent inference slots |
| `concurrency.in_use` | int | Currently occupied slots |
| `latency.recent` | list[float] | Last 10 inference latencies in ms |
| `drift.samples` | int | Samples in the drift rolling window |

### Connecting from JavaScript

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/metrics');

ws.onmessage = (event) => {
  const m = JSON.parse(event.data);
  document.getElementById('latency').textContent =
    m.latency.recent[m.latency.recent.length - 1]?.toFixed(1) + ' ms';
  document.getElementById('drift').textContent =
    m.drift.samples + ' samples in window';
  document.getElementById('concurrency').textContent =
    m.concurrency.in_use + ' / ' + m.concurrency.max;
};
```

### Ping/Pong

Keep the connection alive with ping/pong:

```javascript
setInterval(() => ws.send('ping'), 30000);
// Server responds: {"pong":true}
```
