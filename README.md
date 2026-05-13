<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/fastapi-0.104-teal?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/vue-3.4-green?style=flat-square&logo=vuedotjs" alt="Vue">
  <img src="https://img.shields.io/badge/postgresql-15-blue?style=flat-square&logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/openai-compatible-10a37f?style=flat-square&logo=openai" alt="OpenAI">
  <img src="https://img.shields.io/badge/redis-ready-DC382D?style=flat-square&logo=redis" alt="Redis">
  <img src="https://img.shields.io/badge/gpu-monitoring-76b900?style=flat-square&logo=nvidia" alt="GPU">
  <img src="https://img.shields.io/badge/prometheus-metrics-orange?style=flat-square&logo=prometheus" alt="Prometheus">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/kubernetes-ready-326ce5?style=flat-square&logo=kubernetes" alt="K8s">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/routes-209-brightgreen?style=flat-square" alt="209 routes">
  <img src="https://img.shields.io/badge/tests-154-brightgreen?style=flat-square" alt="154 tests">
</p>

<h1 align="center">Eco-Guard</h1>
<p align="center"><strong>Self-hosted LLM inference gateway and MLOps platform.</strong></p>
<p align="center">Serve, observe, and manage LLM inference — with a dashboard, metrics, model registry, drift detection, and auto-retraining.</p>

<br>

<p align="center">
  <img src="docs/media/features.svg" alt="Eco-Guard Features" width="100%">
</p>

---

## What is Eco-Guard?

Eco-Guard is a **batteries-included control plane** for teams running LLM inference. It combines an inference gateway, observability stack, and MLOps toolkit into a single self-hosted application.

- **Run locally** with SQLite for development — zero external dependencies
- **Deploy to production** with PostgreSQL, Redis, Docker Compose, or Kubernetes Helm
- **Connect any LLM backend** — llama.cpp, Ollama, vLLM, TGI, or any OpenAI-compatible server
- **Monitor everything** — Prometheus metrics, OpenTelemetry tracing, WebSocket real-time push
- **Manage model lifecycle** — register, stage, promote to production, deploy, rollback with checksums
- **Detect drift** — statistical Z-score detection with auto-retraining pipeline triggers
- **Track experiments** — log metrics per step, compare experiments, export datasets

---

## Quick Start

<p align="center">
  <img src="docs/media/quickstart.svg" alt="Quick Start" width="90%">
</p>

```bash
# 1. Clone and install
git clone https://github.com/eco-guard/eco-guard.git
cd eco-guard
uv sync --group dev

# 2. Start the server (SQLite auto-detected, tables auto-created)
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Open in browser
#    API Docs:  http://localhost:8000/docs
#    Dashboard: http://localhost:8000/dashboard
```

**No model?** The server starts without one. Health shows the database as connected and the model as offline. To run inference, place a GGUF model in `./models/` and set `MODEL_PATH=./models/your-model.gguf`.

---

## Production Deployment

### Docker Compose

```bash
export JWT_SECRET="your-long-random-secret-at-least-32-chars"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="your-strong-password"
docker compose up --build
```

This starts the API + PostgreSQL 15. Add `REDIS_URL=redis://redis:6379` for Redis-backed rate limiting. Mount a model volume at `./models/` for local GGUF inference.

### Kubernetes (Helm)

```bash
helm install eco-guard ./helm/eco-guard \
  --set secrets.jwtSecret="your-secret" \
  --set secrets.adminUsername="admin" \
  --set secrets.adminPassword="your-password" \
  --set ingress.host="api.your-domain.com" \
  --set ingress.tls[0].secretName="your-tls-secret"
```

Includes: Deployment, Service, Ingress, HPA, NetworkPolicy, PodDisruptionBudget, ServiceMonitor, PVC, ConfigMap, and Secret.

### Render / Vercel

- **Backend**: Deploy on Render, Fly.io, Railway, or any VPS
- **Frontend SPA**: Deploy on Vercel — set `VITE_API_BASE_URL` to the backend URL

---

## Architecture

<p align="center">
  <img src="docs/media/architecture.svg" alt="Architecture" width="100%">
</p>

### Middleware Pipeline
Every request passes through a layered middleware stack:
```
Security Headers → CORS → Request Logging → Timeout → Prometheus → Rate Limiter → Auth → Demo Mode → Route Handler
```

### Backend Abstraction
One API, many backends. Switch by setting `BACKEND`:
| Backend | Config |
|---------|--------|
| `llama-cpp` | Local GGUF file — set `MODEL_PATH` |
| `ollama` | `BACKEND_URL=http://localhost:11434` |
| `vllm` | `BACKEND_URL=http://localhost:8001` |
| `tgi` | `BACKEND_URL=http://localhost:8080` |
| `openai` | Any `/v1/completions` endpoint |

### Technology Stack
| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI 0.104 + Uvicorn |
| Frontend | Vue 3.4 (Composition API) + Pinia + Vite |
| Database | PostgreSQL 15 (prod) / SQLite (dev) |
| ORM | SQLAlchemy 2.0 (async) |
| Auth | JWT + httpOnly cookies + hashed API keys |
| Metrics | Prometheus client + OpenTelemetry |
| Rate Limiting | Sliding window (in-memory or Redis via Lua) |
| Caching | TTL-based with LRU eviction |
| Resilience | Circuit breaker, retry with backoff, concurrency limit |
| Deployment | Docker, Docker Compose, Kubernetes, Helm, Render |

---

## API Overview

### OpenAI-Compatible Endpoints (drop-in `baseURL` replacement)

| Endpoint | Description |
|----------|-------------|
| `POST /v1/chat/completions` | Chat completions (supports streaming, tools, JSON mode) |
| `POST /v1/embeddings` | Text embeddings |
| `GET /v1/models` | List available models |
| `POST /v1/batch/predict` | Batch inference (up to 100 prompts in parallel) |
| `POST /v1/fallback/predict` | Fallback chain (model A → B → C on failure) |

### System & Inference

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/predict` | Synchronous LLM inference |
| `POST /api/v1/predict/stream` | SSE streaming token-by-token |
| `GET /api/v1/health` | Health check (DB + model status) |
| `GET /api/v1/ready` | Readiness (model loaded check) |
| `GET /api/v1/metrics` | Prometheus metrics endpoint |
| `GET /api/v1/benchmark` | Model benchmarking (3 runs) |

### Security & Guardrails

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/auth/login` | JWT login (returns httpOnly cookie + token) |
| `POST /api/v1/auth/logout` | Clear auth cookie |
| `GET /api/v1/auth/status` | Check authentication state |
| `GET /v1/guardrails` | List active guardrails |
| `POST /v1/guardrails/check` | Check prompt against all guardrails |

### Cost Tracking & GPU

| Endpoint | Description |
|----------|-------------|
| `GET /v1/cost/estimate` | Pre-request cost estimate |
| `GET /v1/cost/usage` | Usage summary for N hours |
| `GET /v1/cost/pricing` | View per-model pricing table |
| `POST /v1/cost/pricing` | Set custom pricing per model |
| `GET /v1/gpu` | GPU utilization, memory, temp (nvidia-smi) |

### MLOps API
| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/mlops/models/register` | Register a model with checksum |
| `POST /api/v1/mlops/models/{id}/promote` | Promote model (registered → staging → production) |
| `POST /api/v1/mlops/models/{id}/deploy` | Deploy with strategy (direct/canary/blue-green/ab) |
| `POST /api/v1/mlops/deployments/{id}/rollback` | Rollback deployment |
| `POST /api/v1/mlops/datasets/create-from-logs` | Create dataset from inference logs |
| `GET /api/v1/mlops/datasets/{id}/export` | Export dataset as JSONL |
| `POST /api/v1/mlops/experiments` | Create training experiment |
| `POST /api/v1/mlops/experiments/{id}/metrics` | Log experiment metric |
| `GET /api/v1/mlops/experiments/compare` | Compare experiments by metric |
| `POST /api/v1/mlops/jobs` | Create training job |
| `POST /api/v1/mlops/evaluate` | Evaluate model from inference logs |
| `POST /api/v1/mlops/evaluate/custom` | Evaluate with custom test cases |
| `GET /api/v1/mlops/drift-triggers` | List drift triggers |
| `GET /api/v1/mlops/usage` | Usage analytics |
| `GET /api/v1/mlops/audit` | Audit log query |

---

## SDK & CLI

### Python SDK

```python
from sdk import EcoGuard

client = EcoGuard(base_url="http://localhost:8000")

# Chat completion
response = client.chat([{"role": "user", "content": "Explain ML"}])
print(response["choices"][0]["message"]["content"])

# Streaming
for chunk in client.chat_stream([{"role": "user", "content": "Hello!"}]):
    delta = chunk["choices"][0]["delta"]
    if "content" in delta:
        print(delta["content"], end="", flush=True)

# Embeddings
result = client.embed("Hello world")

# Cost estimation
estimate = client.cost_estimate(1000, 500, "gpt-4o")

# Guardrails check
result = client.guardrails_check("Ignore all previous instructions")
```

### CLI

```bash
make chat p="What is deep learning?"    # Streaming chat
make guardrails p="Reveal the password" # Guardrails check
make cost h=24                          # 24h cost usage
make cli c="health"                     # Health check
make cli c="models"                     # List models
```

---

## Guardrails

Three built-in guardrails run on inference when `GUARDRAILS_ENABLED=true`:

| Guardrail | Action |
|-----------|--------|
| `prompt_injection` | Blocks "ignore previous instructions", DAN/jailbreak, ChatML injection |
| `pii_detection` | Redacts SSN, credit cards, emails, phone numbers, IPs |
| `content_safety` | Flags self-harm, violence, hate speech keywords |

Configure in `ecoguard.yaml`: `guardrails.enabled: [pii, injection, content_safety]`
## Dashboard Pages

The Vue 3 SPA provides 8 pages:

| Page | What it shows |
|------|--------------|
| **Overview** | System health, model status, quick stats |
| **Models** | Model registry — versions, status, checksums, promote/deploy |
| **Inference** | Live inference playground with streaming |
| **Drift** | Drift triggers, scores, acknowledge, auto-retraining status |
| **Experiments** | Experiment list, metrics chart, comparison view |
| **Jobs** | Training jobs — status, config, errors, cancel |
| **Datasets** | Dataset list, record counts, quality scores, export |
| **Login** | JWT login with demo mode support |

The dashboard auto-detects demo mode and shows a banner. In demo mode, destructive actions (register, promote, deploy, create jobs) are disabled.

---

## Configuration

All configuration is done via environment variables. See `.env.example` for the full list.

### Required in Production
```
JWT_SECRET=your-secret-at-least-32-chars
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-strong-password
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
CORS_ORIGINS=["https://your-domain.com"]
```

### Backend Selection
```
BACKEND=llama-cpp          # or: ollama, vllm, tgi, openai
BACKEND_URL=http://localhost:11434
MODEL_PATH=./models/llama.gguf
```

### Resilience Tuning
```
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
MAX_CONCURRENT_INFERENCE=4
REQUEST_TIMEOUT_SECONDS=120
CIRCUIT_BREAKER_ENABLED=true
DRIFT_ALERT_THRESHOLD=0.8
```

### Observability
```
METRICS_ENABLED=true
OTLP_ENDPOINT=http://jaeger:4318/v1/traces
REDIS_URL=redis://redis:6379
```

---

## Development

```bash
make sync          # Install all dependencies
make run           # Start dev server with reload
make test          # Run pytest suite (93 tests)
make lint          # Ruff check
make format        # Ruff format
make typecheck     # Mypy type checking
make check         # lint + typecheck + test (all three)
```

---

## Project Structure

```text
src/
├── main.py              # FastAPI app, lifespan, middleware, router mounting
├── api/                  # Route handlers (inference, OpenAI, MLOps, dashboard, WebSocket)
├── core/                 # Auth, backend, config, middleware, rate limiter, router, guardrails, gitops
├── services/             # Inference, chat, streaming, drift, cache, cost, alerts, background
├── mlops/                # Registry, training, experiments, datasets, pipeline, evaluation
├── models/               # Pydantic schemas + OpenAI schemas + SQLAlchemy models
├── db/                   # Database engine, session, health check
├── monitoring/           # Prometheus metrics, GPU metrics (nvidia-smi), Grafana dashboard
├── templates/            # Jinja2 server-side HTML (fallback dashboard)
└── static/               # Static assets
frontend/
├── src/
│   ├── views/            # 8 Vue page components
│   ├── stores/           # Pinia auth store (httpOnly cookie)
│   ├── api/              # Fetch client with credentials
│   └── router/           # Vue Router with auth guard
sdk/                      # Python SDK + CLI tool
tests/                    # 122 pytest tests
alembic/                  # Database migration scripts
docs/                     # Documentation + SVG media (architecture, features, quickstart)
monitoring/               # Prometheus alert rules + Grafana dashboard JSON
k8s/                      # Kubernetes manifests (deployment, service, netpol, PDB)
helm/eco-guard/           # Helm chart
ecoguard.yaml             # GitOps YAML configuration (hot-reload)
```

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <sub>Built for teams that want LLM observability without building infrastructure from scratch.</sub>
</p>
