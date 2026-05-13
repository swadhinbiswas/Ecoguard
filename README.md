<div align="center">
  <img src="docs/media/architecture.svg" alt="Eco-Guard Architecture" width="100%">
</div>

<br>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/fastapi-0.115-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/vue-3.4-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white">
  <img src="https://img.shields.io/badge/postgresql-15-4169E1?style=flat-square&logo=postgresql&logoColor=white">
  <img src="https://img.shields.io/badge/redis-ready-DC382D?style=flat-square&logo=redis&logoColor=white">
  <img src="https://img.shields.io/badge/openai-compatible-10A37F?style=flat-square&logo=openai&logoColor=white">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white">
  <img src="https://img.shields.io/badge/kubernetes-ready-326CE5?style=flat-square&logo=kubernetes&logoColor=white">
  <img src="https://img.shields.io/badge/ci-passing-4c1?style=flat-square">
  <img src="https://img.shields.io/badge/tests-169/173-4c1?style=flat-square">
  <img src="https://img.shields.io/badge/license-MIT-8A2BE2?style=flat-square">
</p>

# Eco-Guard

**Self-hosted LLM inference gateway and MLOps platform.** Eco-Guard provides a production-grade control plane for serving, observing, and managing large language model inference — with cost tracking, content safety guardrails, and model lifecycle management — all deployable as a single Docker container.

---

## Table of Contents

1. [Key Features](#key-features)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [API Reference](#api-reference)
5. [Deployment](#deployment)
6. [Configuration](#configuration)
7. [Development](#development)
8. [Testing](#testing)
9. [Project Structure](#project-structure)
10. [Technology Stack](#technology-stack)
11. [Security & Data Protection](#security--data-protection)
12. [Contributing](#contributing)
13. [License](#license)

---

## Key Features

### Inference Gateway
- **OpenAI-compatible API** — Drop-in replacement for `/v1/chat/completions`, `/v1/embeddings`, and `/v1/models`. Works with any OpenAI SDK client.
- **Multi-backend support** — Connect to llama.cpp, Ollama, vLLM, HuggingFace TGI, or any OpenAI-compatible endpoint.
- **Streaming responses** — Server-sent events (SSE) for real-time token-by-token output.
- **Chat template engine** — Automatic model-specific formatting for Llama 3, Mistral, ChatML, Gemma, Zephyr, and more.
- **Function calling** — OpenAI-compatible tool/function calling with automatic response parsing.
- **Batch inference** — Submit up to 100 prompts in parallel with aggregated results.
- **Fallback chains** — Define model fallback sequences (Model A → Model B → Model C) with per-step timeouts.

### Content Safety
- **Guardrails pipeline** — Pluggable content safety with per-stage actions (block, flag, sanitize, allow).
- **Prompt injection detection** — Pattern-based detection of jailbreak attempts, role redefinition, ChatML injection, and DAN-mode prompts.
- **PII redaction** — Automatic detection and redaction of social security numbers, credit card numbers, email addresses, phone numbers, and IP addresses.
- **Content safety** — Detection of self-harm, violence, and hate speech keywords with severity classification.
- **Prompt anomaly detection** — Real-time detection of spam floods, repeated prompts, unusual token counts, and character pattern attacks.

### Cost & Governance
- **Per-model pricing** — Pre-configured pricing for GPT-4, GPT-4o, GPT-3.5, Claude 3 Sonnet/Haiku, and Llama 3 models.
- **Cost comparison** — Compare estimated costs across 6 providers before every request.
- **Budget caps** — Enforce spending limits per workspace with configurable alert thresholds.
- **Token counting** — Accurate token counting with tiktoken integration (fallback heuristic for unknown models).
- **Audit logging** — Every administrative action logged with user, IP address, and timestamp.
- **GDPR compliance** — Data export and right-to-deletion endpoints for user data.

### MLOps
- **Model registry** — Register, promote (Registered → Staging → Production → Archived), and roll back models with checksum verification.
- **Deployment strategies** — Direct, canary, blue-green, and A/B testing deployment methods.
- **Drift detection** — Statistical Z-score drift detection with automatic retraining pipeline triggers.
- **Experiment tracking** — Log metrics per training step with experiment comparison views.
- **Automated evaluation pipeline** — Run eval suites on model deployment. Gate rollouts based on pass/fail thresholds.
- **Benchmark suite** — Standard QA, reasoning, code generation, and summarization benchmarks.
- **Model leaderboard** — Rank models by latency, accuracy, token efficiency, and drift score.
- **RAG pipeline** — Document ingestion, semantic chunking, embedding, and context-aware retrieval.

### Observability
- **Prometheus metrics** — Out-of-the-box metrics endpoint with GPU utilization, request rate, latency distribution, and error rate.
- **OpenTelemetry tracing** — Distributed tracing with OTLP exporter for Jaeger/Tempo integration.
- **Structured logging** — JSON-formatted logs in production with UUID request correlation.
- **Real-time WebSocket** — Live metrics push to the dashboard with GPU, queue depth, and concurrency data.
- **Grafana dashboard** — 17-panel production dashboard included as JSON.
- **Health check** — Multi-component health: database, model, Redis, and GPU availability.

### Platform
- **Multi-tenancy** — Workspaces with members, roles (Owner, Admin, Member, Viewer), and token quotas.
- **JWT authentication** — HTTP-only secure cookies with brute-force protection and scrypt password hashing.
- **API key authentication** — Hashed API key storage with scopes and optional expiration.
- **SSO / OIDC** — Google and GitHub OAuth 2.0 integration.
- **Rate limiting** — Sliding window rate limiter with Redis Lua script backend and in-memory fallback.
- **Circuit breaker** — Redis-backed circuit breaker with automatic half-open recovery.
- **IP allowlisting** — CIDR-based IP access control for administrative endpoints.
- **GitOps configuration** — YAML config file with hot-reload for routes, API keys, guardrails, and pricing.

### Developer Experience
- **Python SDK** — Drop-in OpenAI SDK replacement with sync/async support.
- **CLI tool** — Command-line interface for chat, cost comparison, guardrails checking, and more.
- **HuggingFace Hub connector** — Search, inspect, and download models directly from HuggingFace.
- **Auto-optimizer** — LLM-powered prompt optimization with critique and suggestions.
- **Plugin system** — Extensible architecture for custom backends, guardrails, and evaluators.

---

## Architecture

Eco-Guard follows a layered middleware architecture. Every request passes through:

```
Security Headers → CORS → Request Logging → Timeout → Prometheus → Rate Limiter → Auth → Demo Mode → Route Handler
```

The backend abstraction layer supports multiple inference engines through a common interface, enabling hot-swapping between providers without restarting the server. All shared state (rate limits, circuit breakers, WebSocket broadcasts) is Redis-backed for multi-worker deployments.

<p align="center">
  <img src="docs/media/features.svg" alt="Feature Overview" width="100%">
</p>

---

## Quick Start

### Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager (`pip install uv`)
- Git LFS (optional, for model storage)

### Installation

```bash
git clone https://github.com/swadhinbiswas/Ecoguard.git
cd Ecoguard
uv sync --group dev
```

### Running

```bash
AUTH_ENABLED=false uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at `http://localhost:8000` for the landing page, `http://localhost:8000/dashboard` for the Vue SPA, or `http://localhost:8000/docs` for the interactive API documentation.

### With a Model

```bash
# Download a GGUF model
uv run huggingface-cli download TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF \
  tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
  --local-dir ./models

# Start with the model loaded
MODEL_PATH=./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
AUTH_ENABLED=false \
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Quick Start Flow

<p align="center">
  <img src="docs/media/quickstart.svg" alt="Quick Start" width="90%">
</p>

---

## API Reference

### OpenAI-Compatible Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/chat/completions` | Chat completion with streaming, tools, and JSON mode |
| POST | `/v1/embeddings` | Text embedding generation |
| GET | `/v1/models` | List available models |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check (database + model status) |
| GET | `/api/v1/health/enhanced` | Multi-component health (DB, model, Redis, GPU) |
| GET | `/api/v1/system/status` | System configuration status |
| GET | `/api/v1/benchmark` | Model benchmarking |
| GET | `/api/v1/version` | API version information |

### Inference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/predict` | Synchronous LLM inference |
| POST | `/api/v1/predict/stream` | Server-sent events streaming inference |
| POST | `/v1/batch/predict` | Batch inference (up to 100 prompts) |
| POST | `/v1/fallback/predict` | Fallback chain inference |
| POST | `/api/v1/inference/async` | Asynchronous inference with webhook callback |
| GET | `/api/v1/inference/async/{job_id}` | Poll async inference job status |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login with username/password (returns httpOnly JWT cookie) |
| POST | `/api/v1/auth/logout` | Clear authentication cookie |
| GET | `/api/v1/auth/status` | Check authentication state |
| GET | `/api/v1/auth/sso/providers` | List available SSO providers |
| GET | `/api/v1/auth/sso/{provider}/login` | SSO authorization URL |
| GET | `/api/v1/auth/sso/{provider}/callback` | SSO callback handler |

### MLOps

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/mlops/models/register` | Register a model |
| POST | `/api/v1/mlops/models/{id}/promote` | Promote model to next stage |
| POST | `/api/v1/mlops/models/{id}/deploy` | Deploy model with strategy |
| POST | `/api/v1/mlops/deployments/{id}/rollback` | Rollback deployment |
| GET | `/api/v1/mlops/drift-triggers` | List drift triggers |
| POST | `/api/v1/mlops/datasets/create-from-logs` | Create dataset from inference logs |
| POST | `/api/v1/mlops/experiments` | Create experiment |
| GET | `/api/v1/mlops/experiments/compare` | Compare experiments |
| POST | `/api/v1/mlops/jobs` | Create training job |
| POST | `/api/v1/mlops/finetune` | Execute fine-tuning job |
| POST | `/api/v1/mlops/evaluate` | Run model evaluation |

Full API documentation is available via the interactive Swagger UI at `/docs` when the server is running.

---

## Deployment

### Docker Compose (Recommended for Production)

```bash
# Set required secrets
export ECOGUARD_DOCKER_JWT_SECRET=$(openssl rand -hex 32)
export ECOGUARD_DOCKER_ADMIN_USERNAME=admin
export ECOGUARD_DOCKER_ADMIN_PASSWORD=$(openssl rand -hex 16)
export ECOGUARD_DOCKER_POSTGRES_PASSWORD=$(openssl rand -hex 16)

docker compose up --build -d
```

Starts three services: Eco-Guard API, PostgreSQL 15, and Redis 7 — with health checks, persistent volumes, and automatic database migrations.

### Kubernetes (Helm)

```bash
helm install eco-guard ./helm/eco-guard \
  --set secrets.jwtSecret="$(openssl rand -hex 32)" \
  --set secrets.adminUsername="admin" \
  --set secrets.adminPassword="$(openssl rand -hex 16)" \
  --set ingress.host="api.your-domain.com"
```

Includes: Deployment, Service, Ingress, HorizontalPodAutoscaler, NetworkPolicy, PodDisruptionBudget, ServiceMonitor, and PersistentVolumeClaim.

### Manual Deployment

```bash
# Production environment
export ENVIRONMENT=production
export JWT_SECRET=$(openssl rand -hex 32)
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=$(openssl rand -hex 16)
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/ecoguard?ssl=require"
export REDIS_URL="redis://user:pass@host:6379"
export CORS_ORIGINS='["https://your-domain.com"]'

uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Configuration

All configuration is managed via environment variables. A complete reference is available in `.env.example`.

### Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key for JWT signing (min 32 characters) | `openssl rand -hex 32` |
| `ADMIN_USERNAME` | Administrator username | `admin` |
| `ADMIN_PASSWORD` | Administrator password | `openssl rand -hex 16` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `CORS_ORIGINS` | Allowed CORS origins | `["https://your-domain.com"]` |

### Optional Features

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | (empty) | Redis connection string for shared state |
| `GUARDRAILS_ENABLED` | `false` | Enable content safety guardrails |
| `OTLP_ENDPOINT` | (empty) | OpenTelemetry collector endpoint |
| `BACKEND` | `llama-cpp` | Inference backend (llama-cpp, ollama, vllm, tgi, openai) |
| `AUTH_ENABLED` | `true` | Enable authentication middleware |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |

---

## Development

```bash
uv sync --group dev          # Install all dependencies
make run                      # Start development server
make test                     # Run test suite
make lint                     # Run code linter
make format                   # Format code
make check                    # Run lint + typecheck + tests
make migrate                  # Run database migrations
make seed                     # Generate demo data
```

---

## Testing

The test suite comprises **173 tests** across 13 test files:

| Category | Count | Description |
|----------|-------|-------------|
| Unit tests | 135 | Individual function and class tests |
| Integration tests | 19 | API endpoint tests via TestClient |
| End-to-end tests | 19 | Full request lifecycle tests |

Run the suite:

```bash
uv run pytest tests/ -v           # Verbose output
uv run pytest tests/ --cov=src    # With coverage report
```

---

## Project Structure

```
src/
├── main.py                  # FastAPI application entry point
├── api/                     # Route handlers (12 routers, 208 endpoints)
│   ├── routes.py            # Core API: health, predict, auth
│   ├── openai_routes.py     # OpenAI-compatible /v1/ endpoints
│   ├── mlops_routes.py      # MLOps: models, experiments, jobs, datasets
│   ├── enterprise_routes.py # Multi-tenancy: workspaces, webhooks, keys
│   ├── advanced_routes.py   # Advanced: AB testing, feedback, finetune
│   ├── production_routes.py # Production: traces, load test, compliance
│   ├── toolkit_routes.py    # Toolkit: RAG, leaderboard, chain, HF hub
│   └── websocket.py         # Real-time metrics WebSocket
├── core/                    # Business logic layer
│   ├── auth.py              # JWT + API key authentication
│   ├── backend.py           # LLM backend abstraction
│   ├── guardrails.py        # Content safety pipeline
│   ├── chat_templates.py    # Model-specific chat formatting
│   ├── enterprise.py        # Budget, queue, load balancer, auto-scaler
│   ├── production_state.py  # Redis-backed shared state
│   └── gitops.py            # YAML config hot-reload
├── services/                # Service layer
│   ├── chat_service.py      # OpenAI-compatible chat + embeddings
│   ├── inference_service.py # Legacy completions service
│   └── cost_tracker.py      # Per-model cost tracking
├── mlops/                   # MLOps modules
│   ├── registry.py          # Model registry with state machine
│   ├── quality.py           # Regression detection, anomalies, benchmarks
│   ├── rag.py               # RAG pipeline (ingest, chunk, retrieve)
│   └── gov.py               # Cron, audit, backup, key analytics
├── db/                      # Database layer
├── monitoring/              # Prometheus + GPU metrics
├── models/                  # Pydantic + SQLAlchemy models
└── templates/               # Jinja2 server-side templates
frontend/                    # Vue 3 SPA (16 pages)
│   ├── src/views/           # Page components
│   ├── src/components/      # Reusable components
│   └── src/stores/          # Pinia state management
sdk/                         # Python SDK + CLI
tests/                       # Test suite
alembic/                     # Database migrations (8 versions)
docs/                        # Documentation + SVG media
monitoring/                  # Grafana dashboard + Prometheus alerts
k8s/                         # Kubernetes raw manifests
helm/eco-guard/              # Helm chart
terraform/                   # Terraform IaC module
load-tests/                  # k6 load test scripts
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| API Framework | FastAPI | 0.115 |
| ASGI Server | Uvicorn | 0.34 |
| Frontend | Vue 3 (Composition API) | 3.4 |
| State Management | Pinia | 2.2 |
| Build Tool | Vite | 6.0 |
| Database | PostgreSQL / SQLite | 15 / 3 |
| ORM | SQLAlchemy (async) | 2.0 |
| Cache / State | Redis | 7 |
| Authentication | PyJWT | 2.12 |
| Metrics | Prometheus Client | 0.21 |
| Tracing | OpenTelemetry | 1.28 |
| Validation | Pydantic | 2.10 |
| Linting | Ruff | 0.11 |
| Testing | Pytest | 8.3 |
| Container | Docker | 27 |
| Orchestration | Kubernetes | 1.30 |
| IaC | Terraform | 1.10 |

---

## Security & Data Protection

Eco-Guard implements security best practices relevant for projects processing user data:

- **Authentication**: HTTP-only secure JWT cookies with brute-force protection and scrypt password hashing. API keys are stored as SHA-256 hashes.
- **Content Security Policy**: Default-src 'self' with restrictions on scripts, styles, images, and fonts. HSTS enabled in production.
- **Data export**: GDPR-compliant data export endpoint providing all user inference logs and feedback data.
- **Right to deletion**: Anonymization endpoint that replaces user data with `[REDACTED]` markers.
- **Data retention**: Configurable automatic log purging (default 90 days).
- **No external telemetry**: All data stays on your infrastructure. No analytics, no tracking, no phone-home.
- **Security headers**: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, and X-XSS-Protection.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/name`)
3. Install development dependencies (`uv sync --group dev`)
4. Make changes with tests
5. Run `make check` to verify lint, type checking, and tests
6. Submit a pull request against the `main` branch

Please ensure:
- All new features include tests
- Code passes `ruff format --check` and `ruff check`
- The PR description includes what changed and why

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with Python, FastAPI, Vue 3, and PostgreSQL. Deployable via Docker, Kubernetes, or Terraform.</sub>
</p>
