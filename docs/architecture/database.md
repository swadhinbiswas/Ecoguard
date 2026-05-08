# Database Layer

Eco-Guard uses a **dual-database design** with automatic fallback, async sessions, and Alembic migrations.

## Dual-Database Architecture

```
┌─────────────────────────────────┐
│         Application             │
├─────────────────────────────────┤
│  AsyncSession (via get_db DI)   │
├──────────────┬──────────────────┤
│  PostgreSQL  │  SQLite (fallback)│
│  (asyncpg)   │  (aiosqlite)      │
└──────────────┴──────────────────┘
```

**Source:** `src/db/database.py`

The system tries PostgreSQL first. If PostgreSQL is unreachable, it automatically falls back to SQLite stored at `data/ecoguard.db`.

### Auto-Detection and Fallback

```python
async def init_db() -> None:
    global _engine, _async_session_local, _using_sqlite

    postgres_ok = await _probe_postgres()

    if postgres_ok:
        _engine = _create_postgres_engine()
        _using_sqlite = False
        logger.info("Using PostgreSQL database")
    else:
        _engine = _create_sqlite_engine()
        _using_sqlite = True
        logger.info("PostgreSQL unavailable — falling back to SQLite (data/ecoguard.db)")
```

The probe function connects to PostgreSQL and runs `SELECT 1`:

```python
async def _probe_postgres() -> bool:
    try:
        engine = _create_postgres_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False
```

### SQLite Fallback Engine

```python
def _create_sqlite_engine():
    os.makedirs("data", exist_ok=True)
    url = "sqlite+aiosqlite:///data/ecoguard.db"
    return create_async_engine(url, echo=settings.db_echo, poolclass=NullPool)
```

SQLite uses `NullPool` since SQLite doesn't support connection pooling. The database file is created automatically in the `data/` directory.

### PostgreSQL Engine

```python
def _create_postgres_engine():
    pool_class = NullPool if settings.environment == "development" else QueuePool
    return create_async_engine(settings.database_url, **_get_engine_kwargs(pool_class))
```

| Mode | Pool Type | Rationale |
|------|-----------|-----------|
| `development` | `NullPool` | Easier debugging, no stale connections |
| `production` | `QueuePool` | Connection reuse for performance |

## AsyncSession Pattern

Database sessions use FastAPI dependency injection for automatic lifecycle management.

**Source:** `src/db/session.py`

```python
async def get_db() -> AsyncGenerator:
    session_factory = get_session_local()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

Usage in route handlers:

```python
@router.post("/predict")
async def predict(
    request_data: PredictionRequest,
    db: AsyncSession = Depends(get_db),
):
    # db is automatically committed on success, rolled back on error
    db.add(InferenceLog(...))
    # commit happens after the handler returns
```

The pattern ensures:
- **Auto-commit** on successful handler execution
- **Auto-rollback** on any exception
- **Auto-close** in the `finally` block
- **No manual session management** in route handlers

## Connection Pooling

PostgreSQL connection pooling is configured via SQLAlchemy's `QueuePool`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DB_POOL_SIZE` | `20` | Maximum number of persistent connections in the pool |
| `DB_MAX_OVERFLOW` | `10` | Additional connections beyond pool_size under load |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for an available connection before error |
| `DB_ECHO` | `false` | Log all SQL statements (debugging only) |

Pool configuration is applied in `_get_engine_kwargs()`:

```python
def _get_engine_kwargs(pool_class) -> dict:
    kwargs = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,
        "poolclass": pool_class,
    }
    if pool_class != NullPool:
        kwargs.update({
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
        })
    return kwargs
```

`pool_pre_ping=True` ensures stale connections (from PostgreSQL restarts or network issues) are detected and recycled via a `SELECT 1` before each checkout.

## Alembic Migrations

Migrations are managed by **Alembic**, configured in `alembic.ini`.

### Running Migrations

```bash
# Apply all pending migrations
make migrate
# or:
uv run alembic upgrade head

# Generate a new migration from model changes
uv run alembic revision --autogenerate -m "description of change"
```

### Auto-Migration

Set `AUTO_MIGRATE=true` to run migrations automatically on startup:

```python
# In lifespan() in src/main.py
if settings.auto_migrate:
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

> **Note:** Auto-migration is disabled by default. Enable it only in environments where you control deployment timing.

## Database Tables

Eco-Guard uses **11 database tables** across two categories:

### Inference & Logging

| Table | Model | Purpose |
|-------|-------|---------|
| `inference_logs` | `InferenceLog` | Every prediction request: prompt, output, latency, tokens, drift score |
| `audit_log` | `AuditLog` | Audit trail for all MLOps operations (register, deploy, rollback, etc.) |

### MLOps

| Table | Model | Purpose |
|-------|-------|---------|
| `model_registry` | `ModelRegistry` | Registered models: name, version, status, artifact path, checksum |
| `training_jobs` | `TrainingJob` | Training job lifecycle: config, status, trigger type, timestamps |
| `datasets` | `Dataset` | Created datasets: name, version, file path, record count, filters |
| `deployments` | `Deployment` | Deployment records: strategy, traffic percent, rollback info |
| `training_experiments` | `TrainingExperiment` | Experiment metadata: hyperparameters, best metric, status |
| `experiment_metrics` | `ExperimentMetric` | Per-step metrics logged during experiments |
| `retraining_triggers` | `RetrainingTrigger` | Drift-triggered retraining records |
| `prompt_templates` | `PromptTemplate` | Reusable prompt templates with variable substitution |
| `api_usage_logs` | `APIUsageLog` | API usage tracking for billing/analytics |

### Table Details

#### `inference_logs`
```
id, request_id (unique, indexed), timestamp, input_text, prediction_output,
latency_ms, token_count, confidence_score, drift_score
```

#### `model_registry`
```
id, name (indexed), version, status (ENUM: registered/staging/production/archived/failed),
artifact_path, artifact_checksum, base_model, framework, parameters (JSON),
metrics (JSON), tags (JSON), description, created_at, deployed_at, created_by
```

#### `training_jobs`
```
id, name (indexed), status (ENUM: queued/running/completed/failed/cancelled),
base_model_id (FK→model_registry), dataset_id (FK→datasets), config (JSON),
output_model_name, started_at, completed_at, error_message, trigger_type,
trigger_detail (JSON), created_at, created_by
```

#### `datasets`
```
id, name (indexed), version, format, file_path, record_count, source,
filters (JSON), quality_score, created_at, created_by
```

#### `deployments`
```
id, model_id (FK→model_registry), strategy (ENUM: direct/canary/blue_green/ab_test),
status, traffic_percent, config (JSON), deployed_at, rolled_back_at,
rollback_reason, deployed_by
```

#### `training_experiments`
```
id, name (indexed), training_job_id (FK→training_jobs), base_model,
dataset_version, hyperparameters (JSON), status (ENUM: running/completed/failed/cancelled),
best_metric, best_metric_value, total_steps, artifact_path, notes,
started_at, completed_at, created_by
```

#### `experiment_metrics`
```
id, experiment_id (FK→training_experiments, indexed), step, metric_name (indexed),
metric_value, timestamp
```

#### `retraining_triggers`
```
id, drift_score, threshold, dataset_id (FK→datasets),
training_job_id (FK→training_jobs), acknowledged, auto_triggered,
triggered_at, acknowledged_at
```

#### `prompt_templates`
```
id, name (unique, indexed), description, template, variables (JSON),
tags (JSON), usage_count, created_at, updated_at
```

#### `audit_log`
```
id, action (ENUM), actor, resource_type, resource_id, detail (JSON),
timestamp
```

#### `api_usage_logs`
```
id, api_key_hash, endpoint, latency_ms, token_count, status_code,
timestamp, request_id
```

## Health Check

Database health is checked via `check_db_health()`:

```python
async def check_db_health() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
```

This is called by the `/api/v1/health` endpoint and the service unavailable (503) exception handler.

## Retry Logic

Database connection initialization includes retry logic in `src/core/retry.py` with configurable parameters:

| Setting | Default | Description |
|---------|---------|------------|
| `DB_MAX_RETRIES` | `5` | Maximum retry attempts for database connection |
| `DB_RETRY_BASE_DELAY` | `0.5` | Base delay in seconds (exponential backoff) |
