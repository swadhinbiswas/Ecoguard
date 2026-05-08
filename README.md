<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/vue-3.4-green" alt="Vue">
  <img src="https://img.shields.io/badge/fastapi-0.104-teal" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-purple" alt="License">
  <img src="https://img.shields.io/badge/tests-85%20passed-brightgreen" alt="Tests">
  <img src="https://github.com/swadhinbiswas/Ecoguard/actions/workflows/ci.yml/badge.svg" alt="CI">
</p>

<h1 align="center">Eco-Guard</h1>
<p align="center"><strong>Production-Grade LLM Inference Gateway & MLOps Platform</strong></p>

---

Eco-Guard is a complete MLOps platform for serving, monitoring, and continuously improving LLMs. It handles the full lifecycle — serve models via REST/SSE streaming, collect inference metrics, detect statistical drift, auto-trigger QLoRA retraining, track experiments, manage a model registry with canary/blue-green deployments, and visualize everything through a Vue 3 dashboard.

## Why Eco-Guard?

| | Eco-Guard | Custom FastAPI | LangSmith | MLflow |
|---|---|---|---|---|
| **LLM serving** | REST + SSE streaming | DIY | No | No |
| **Multi-backend** | llama-cpp, vLLM, Ollama, TGI | DIY | No | No |
| **Drift detection** | Built-in z-score + alerts | Manual | Basic | No |
| **Auto-retraining** | Drift-triggered pipeline | DIY | No | No |
| **Model registry** | Full lifecycle (stage/deploy/rollback) | DIY | No | Yes |
| **Experiment tracking** | Metrics, comparison, charts | DIY | Yes | Yes |
| **Dashboard** | Vue 3 SPA, dark theme | DIY | Basic UI | Yes |
| **Deployment** | Helm, Docker, Render, Vercel | DIY | Cloud-only | Self-host |
| **Database** | PostgreSQL + SQLite fallback | DIY | Cloud | Self-host |
| **Cost** | Free, runs on laptop | Free | Paid | Free |

## Quick Start

```bash
# 1. Install dependencies (no Poetry — uses uv)
uv sync --group dev

# 2. Run the server — no PostgreSQL or GPU needed
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

That's it. SQLite fallback auto-creates the database. Visit `http://localhost:8000/dashboard`.

> **With a model:** Download a GGUF model to `./models/` and set `MODEL_PATH=./models/model.gguf` in `.env`.
> **With GPU:** Point at a running Ollama or vLLM instance via `BACKEND=vllm BACKEND_URL=http://gpu:8000`.

## Platform Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 Dashboard                       │
│  Login → Overview → Models → Inference → Drift → ...    │
├─────────────────────────────────────────────────────────┤
│                    REST + SSE API                        │
│  /predict  /predict/stream  /benchmark  /health  /admin  │
├─────────────────────────────────────────────────────────┤
│                   Middleware Stack                        │
│  CORS → Logging → Timeout → GZip → Metrics → Auth →     │
├─────────────────────────────────────────────────────────┤
│                   Service Layer                           │
│  Inference │ Streaming │ Drift │ Cache │ Alert │ Audit   │
├─────────────────────────────────────────────────────────┤
│                   MLOps Pipeline                          │
│  Registry → Dataset → Training → Experiment → Deploy     │
├─────────────────────────────────────────────────────────┤
│                   Backend Abstraction                     │
│  llama-cpp │ vLLM │ Ollama │ TGI │ OpenAI-compatible     │
├─────────────────────────────────────────────────────────┤
│                   Data Layer                              │
│  PostgreSQL (production) ←→ SQLite (fallback/dev)        │
└─────────────────────────────────────────────────────────┘
```

## Features

### Inference Gateway
- **REST endpoint** — `POST /api/v1/predict` with temperature, top_p, top_k, repeat_penalty
- **SSE streaming** — `POST /api/v1/predict/stream` — token-by-token via Server-Sent Events
- **Multi-backend** — llama-cpp (CPU), vLLM, Ollama, TGI, any OpenAI-compatible API
- **Concurrency limiting** — semaphore-based, configurable max concurrent inference
- **Circuit breaker** — closed/open/half-open states for external model backends
- **Request timeout** — configurable per-request deadline with 504 response

### Security
- **JWT authentication** — Bearer tokens, cookie-based sessions, login page
- **API key auth** — `X-API-Key` header, key generation and revocation
- **Rate limiting** — sliding-window per-IP, configurable burst/rate
- **Prompt sanitization** — null-byte injection prevention, character limit
- **RBAC** — admin/operator/viewer roles with path-level enforcement

### Observability
- **Prometheus metrics** — requests, latency, tokens, drift, rate limiting, model status
- **OpenTelemetry tracing** — OTLP export, auto-instruments FastAPI + SQLAlchemy
- **Structured logging** — JSON logs with request IDs for ingestion pipelines
- **WebSocket telemetry** — live metrics streaming at `ws://host:8000/ws/metrics`
- **Grafana dashboard** — 10-panel JSON dashboard included in `monitoring/grafana/`
- **Prometheus alerts** — 7 pre-built rules for error rate, latency, drift, model down

### MLOps Lifecycle

| Phase | Capability |
|---|---|
| **Register** | Model versioning with checksums, lineage, metadata |
| **Deploy** | Direct, canary (traffic %), blue-green, A/B test strategies |
| **Monitor** | Statistical drift detection (z-score), rolling window |
| **Alert** | Webhook + email notifications on drift threshold breach |
| **Train** | Job queue with lifecycle (queued → running → completed/failed) |
| **Experiment** | Hyperparameter tracking, per-step metrics, comparison view |
| **Retrain** | Auto-triggered: drift → dataset → QLoRA job → register |

### Dashboard (Vue 3 SPA)
- Login with JWT session cookies
- 7 pages: Overview, Model Registry, Inference Analytics, Drift Monitor, Experiments, Training Jobs, Datasets
- Dark theme, responsive layout, sidebar navigation
- Real-time health polling from backend

## Dataset Generation

The drift-triggered pipeline auto-creates fine-tuning datasets:

```bash
# Manually create a dataset from inference logs
curl -X POST http://localhost:8000/api/v1/mlops/datasets/create-from-logs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "weekly-data", "hours": 168, "limit": 1000}'

# Export as JSONL
curl http://localhost:8000/api/v1/mlops/datasets/1/export \
  -H "Authorization: Bearer $TOKEN"
```

## Monitoring Stack

```bash
# Prometheus scrape config
scrape_configs:
  - job_name: eco-guard
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

Import `monitoring/grafana/dashboard.json` into Grafana for pre-built dashboards.

## Deployment

### Render (one-click)
```bash
git push  # render.yaml auto-deploys web service + free PostgreSQL
```

### Vercel
```bash
vercel --prod
# Set env: ENVIRONMENT=production, ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET
```

### Kubernetes
```bash
helm install eco-guard ./helm/eco-guard \
  --set image.tag=latest \
  --set postgresql.auth.password=securepass
```

### Docker Compose
```bash
docker-compose up --build
```

## Development

```bash
make sync          # install deps
make run           # start server
make test          # run 85 tests
make lint          # ruff check
make format        # ruff format
make typecheck     # mypy
make check         # full CI: lint + typecheck + test
```

## Project Structure

```
├── src/
│   ├── api/            # REST routes, dashboard, MLOps, websocket
│   ├── core/           # Config, auth, backend, security, middleware
│   ├── db/             # SQLAlchemy async engine, session, migrations
│   ├── models/         # Pydantic schemas + SQLAlchemy ORM models
│   ├── services/       # Inference, streaming, drift, cache, alerts
│   ├── mlops/          # Registry, experiments, training, pipeline, eval
│   ├── monitoring/     # Prometheus metrics + middleware
│   └── templates/      # Jinja2 legacy templates (Vue SPA is primary)
├── frontend/           # Vue 3 + Vite SPA
├── tests/              # 85 tests, 9 files
├── helm/               # Kubernetes Helm chart
├── k8s/                # Raw K8s manifests
├── monitoring/         # Grafana dashboard + Prometheus alerts
├── load-tests/         # k6 load test scripts
├── alembic/            # Database migrations
└── docs/               # GitBook documentation
```

## Documentation

Full documentation is available in the [docs/](docs/) directory and at [GitBook](https://swadhinbiswas.gitbook.io/ecoguard).

## License

MIT — see [LICENSE](LICENSE) file.
