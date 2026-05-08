# System Design

Eco-Guard follows a **layered architecture** pattern that separates concerns across seven distinct layers. Each layer communicates only with the layers directly adjacent to it, ensuring clean separation of concerns and maintainability.

## Layer Overview

```
┌─────────────────────────────────────────────┐
│  Client Layer      (Browser / API Consumer) │
├─────────────────────────────────────────────┤
│  API Layer         (FastAPI Routes)         │
├─────────────────────────────────────────────┤
│  Middleware Layer  (Request Pipeline)       │
├─────────────────────────────────────────────┤
│  Service Layer     (Business Logic)         │
├─────────────────────────────────────────────┤
│  MLOps Layer       (Registry, Training...)  │
├─────────────────────────────────────────────┤
│  Backend Layer     (LLM Abstraction)        │
├─────────────────────────────────────────────┤
│  Data Layer        (PostgreSQL / SQLite)    │
└─────────────────────────────────────────────┘
```

## Client Layer

The client layer consumes the Eco-Guard API through:

- **REST API consumers** — any HTTP client (curl, Python `httpx`, JavaScript `fetch`)
- **WebSocket clients** — real-time metrics dashboard at `/ws/metrics`
- **Vue.js dashboard** — served as an SPA from `frontend/dist/`, mounted at `/dashboard`
- **Swagger UI** — interactive API docs at `/docs`
- **ReDoc** — alternative API docs at `/redoc`

## API Layer

The API layer is built with **FastAPI** and organizes endpoints into five router groups:

| Router | Prefix | Purpose |
|--------|--------|---------|
| `router` | `/api/v1` | Inference, health, auth, models, admin |
| `mlops_router` | `/api/v1/mlops` | Model registry, datasets, experiments, jobs |
| `dashboard` | `/dashboard` | Server-rendered HTML dashboard |
| `ws_router` | (WebSocket) | `/ws/metrics` live metrics stream |
| `app` root | `/` | Metrics, SPA serving |

The main FastAPI application is initialized in `src/main.py` with the `lifespan` async context manager managing startup and shutdown.

## Middleware Layer

Middleware wraps every HTTP request in a pipeline. Middleware executes in the order added to the FastAPI app:

1. **ShutdownMiddleware** (`@app.middleware("http")`) — rejects requests during graceful shutdown with HTTP 503
2. **CORSMiddleware** — cross-origin headers
3. **RequestLoggingMiddleware** — assigns request IDs, logs start/end, adds `X-Request-ID` and `X-Process-Time-Ms` headers
4. **TimeoutMiddleware** — enforces per-request timeouts (default 120s), returns 504
5. **GZipMiddleware** — compresses responses > 500 bytes
6. **PrometheusMetricsMiddleware** — records HTTP metrics (method, endpoint, status, duration)
7. **AuthMiddleware** — validates Bearer JWT, cookies, or `X-API-Key` headers

> **Order matters.** The shutdown guard runs first to reject requests before they enter the pipeline. Auth runs last so public paths (`/health`, `/docs`) are accessible before the auth check.

## Service Layer

The service layer contains business logic decoupled from HTTP concerns:

- **InferenceService** — orchestrates prediction: cache lookup → concurrency acquire → CPU inference via `asyncio.to_thread` → drift detection → logging → optional alerting + auto-retraining
- **StreamingInferenceService** — generates SSE streams for token-by-token output
- **CacheService** — LRU in-memory caching of inference results keyed by `(prompt, max_tokens, temperature)`
- **DriftDetector** — statistical drift detection using z-scores on a rolling latency window
- **Alerter** — sends webhook alerts on drift threshold breaches
- **BackgroundRunner** — manages background task lifecycle with graceful shutdown

## MLOps Layer

The MLOps layer (`src/mlops/`) provides the full machine learning operations lifecycle:

| Module | Responsibility |
|--------|---------------|
| `registry.py` | ModelRegistryService — register, promote, deploy, rollback models |
| `experiments.py` | ExperimentTracker — create experiments, log step metrics, compare |
| `training.py` | TrainingOrchestrator — create, start, complete, cancel training jobs |
| `pipeline.py` | DriftPipeline — check drift → create dataset → create training job |
| `dataset.py` | DatasetPipeline — create datasets from inference logs |
| `evaluation.py` | ModelEvaluator — evaluate models with test cases or from logs |
| `ab_testing.py` | ABTestService — route traffic, compare deployments |
| `quantization.py` | QuantizationPipeline — quantize GGUF models |
| `backup.py` | BackupService — PostgreSQL backup via pg_dump |
| `prompts.py` | PromptTemplateService — manage and render prompt templates |
| `usage.py` | APIUsageTracker — track request metrics by time window |
| `scheduler.py` | Scheduler — periodic drift check and cleanup loops |

## Backend Layer

The backend layer (`src/core/backend.py`) abstracts LLM inference behind the `ModelBackend` ABC:

- **LlamaCppBackend** — loads local GGUF files via `llama-cpp-python` for CPU inference
- **OpenAICompatibleBackend** — connects to vLLM, Ollama, TGI, or OpenAI via HTTP

Backend initialization happens during app startup in `init_backend()`. The backend type is controlled by the `BACKEND` environment variable.

## Data Layer

The data layer (`src/db/`) uses SQLAlchemy 2.0 async with dual-database support:

- **PostgreSQL** (asyncpg driver) — production database, connection pooling with QueuePool
- **SQLite** (aiosqlite) — automatic fallback when PostgreSQL is unavailable

Database sessions are provided via FastAPI dependency injection using `get_db()`.

## Request Lifecycle

A typical inference request flows through these stages:

```
1. Client sends POST /api/v1/predict
2. ShutdownMiddleware checks server state
3. CORSMiddleware adds CORS headers
4. RequestLoggingMiddleware assigns X-Request-ID, logs start
5. TimeoutMiddleware wraps call_next in asyncio.wait_for
6. GZipMiddleware intercepts response for compression
7. PrometheusMetricsMiddleware starts timing
8. AuthMiddleware verifies credentials (skips public paths)
9. Rate limiter (SlowAPI) checks client IP quota
10. FastAPI route handler dispatches
11. Prompt sanitization (null byte removal, length check)
12. InferenceService.generate():
    a. Cache lookup (if enabled)
    b. ConcurrencyLimiter.acquire() → asyncio.Semaphore
    c. asyncio.to_thread(backend.generate) — CPU inference
    d. ConcurrencyLimiter.release()
    e. Drift detection → drift score
    f. Log to database (InferenceLog)
    g. Alert if drift > threshold
    h. Auto-retraining pipeline if drift sustained
    i. Cache set (if enabled)
13. Metric recording (inference count, duration, tokens)
14. Response serialized as PredictionResponse
15. Response traverses middleware back (compression, metrics, logging)
16. Response delivered to client
```

## Async Design

Eco-Guard is built on Python's `asyncio` event loop with FastAPI. The async model ensures:

- **I/O-bound operations** (database queries, HTTP calls to external backends) run natively async
- **CPU-bound operations** (llama.cpp inference) run in a thread pool via `asyncio.to_thread()` to avoid blocking the event loop
- **WebSockets** use async patterns for real-time metrics broadcasting
- **Background tasks** run as `asyncio.Task` objects tracked in a set for graceful shutdown

### asyncio.to_thread for CPU Inference

The key design decision for inference is using `asyncio.to_thread()`:

```python
# src/services/inference_service.py
response_data = await asyncio.to_thread(lambda: backend.generate(**kwargs))
```

This offloads the synchronous `llama.cpp` model call to Python's default thread pool executor, keeping the event loop free to handle other requests (health checks, dashboard, metrics). This is essential because GGUF inference can take seconds per request and would otherwise block all other async operations.

## Concurrency Model

Inference concurrency is controlled by the `ConcurrencyLimiter` class:

```python
class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrent)
```

- Uses an `asyncio.Semaphore` with a configurable maximum (`MAX_CONCURRENT_INFERENCE`, default 4)
- Each inference request acquires the semaphore before dispatching to `asyncio.to_thread`
- The semaphore ensures at most N concurrent CPU inference operations, preventing memory exhaustion
- The limiter is a context manager (`async with inference_limiter:`) for clean acquire/release
- Available slots and in-use count are exposed via the WebSocket metrics stream

This semaphore-based model works because while llama.cpp inference runs on a thread, the semaphore is checked in the async context before the thread dispatch. If all 4 slots are taken, additional requests queue up on the semaphore's internal waiter list until a slot frees.
