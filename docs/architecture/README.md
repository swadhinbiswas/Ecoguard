# Architecture

Eco-Guard follows a layered architecture designed for maintainability and scalability.

## System Design

```
┌─────────────────────────────────────────────────────┐
│                  Client Layer                        │
│   Vue 3 SPA │ curl │ Python SDK │ WebSocket         │
├─────────────────────────────────────────────────────┤
│                  API Gateway (FastAPI)                │
│   /api/v1/predict │ /predict/stream │ /health        │
│   /api/v1/mlops/* │ /dashboard/*    │ /ws/metrics    │
├─────────────────────────────────────────────────────┤
│              Middleware Pipeline                      │
│   Shutdown → CORS → Logging → Timeout → GZip →      │
│   Metrics → Auth                                     │
├─────────────────────────────────────────────────────┤
│               Service Layer                           │
│   InferenceService │ StreamingService │ Drift        │
│   CacheService │ Alerter │ BackgroundRunner          │
├─────────────────────────────────────────────────────┤
│               MLOps Layer                             │
│   Registry │ Dataset │ Training │ Experiments        │
│   Deployment │ Pipeline │ Scheduler                  │
├─────────────────────────────────────────────────────┤
│               Backend Abstraction                     │
│   ModelBackend (ABC)                                  │
│   ├── LlamaCppBackend                                │
│   └── OpenAICompatibleBackend                        │
├─────────────────────────────────────────────────────┤
│               Data Layer                              │
│   PostgreSQL ←→ SQLite (auto-fallback)               │
│   Alembic migrations │ AsyncSession                  │
└─────────────────────────────────────────────────────┘
```

## Request Flow

```
Client Request
    │
    ▼
Shutdown Middleware (reject if draining)
    │
    ▼
CORS Middleware (allow origins)
    │
    ▼
Request Logging (UUID + timing)
    │
    ▼
Timeout Middleware (120s default)
    │
    ▼
GZip Middleware (>500 bytes)
    │
    ▼
Prometheus Metrics Middleware
    │
    ▼
Auth Middleware (JWT/API key/cookie)
    │
    ▼
Route Handler
    │
    ▼
Service Layer (business logic)
    │
    ▼
Backend Adapter (model inference)
    │
    ▼
Response → back through middleware stack
```

## Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.104+ |
| ASGI Server | Uvicorn |
| Frontend | Vue 3 + Vite + Vue Router + Pinia |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 15 / aiosqlite (fallback) |
| Migrations | Alembic |
| Model Serving | llama-cpp-python / HTTP proxy |
| Metrics | Prometheus client |
| Tracing | OpenTelemetry |
| Auth | PyJWT |
| Validation | Pydantic v2 |
| Serialization | orjson |
| Drift Detection | NumPy (z-score) |
| Rate Limiting | slowapi |
| Package Manager | uv |
| Container | Docker multi-stage |
| Orchestration | Kubernetes + Helm |
