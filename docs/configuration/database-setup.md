# Database Setup

Eco-Guard uses a dual-database architecture with PostgreSQL as the primary and SQLite as automatic fallback.

## PostgreSQL Setup

### Option 1: Docker (Recommended for Development)

Add PostgreSQL to your `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: ecoguard
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d ecoguard"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

```bash
docker-compose up -d postgres
```

Or use the full `docker-compose.yml` which includes both the API and PostgreSQL:

```bash
make docker-up
```

### Option 2: Local Installation

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo -u postgres createuser ecoguard -P
sudo -u postgres createdb ecoguard -O ecoguard
```

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
createdb ecoguard
```

### Option 3: Cloud Providers

**Render:**
```yaml
# render.yaml
databases:
  - name: eco-guard-db
    databaseName: ecoguard
    plan: free
```
The `DATABASE_URL` is automatically injected as an environment variable via `fromDatabase`.

**AWS RDS / Google Cloud SQL / Azure PostgreSQL:**
Provision a PostgreSQL instance and set the connection URL:

```env
DATABASE_URL=postgresql+asyncpg://user:password@your-host.region.rds.amazonaws.com:5432/ecoguard
```

### Connection URL Format

```
postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
```

The `+asyncpg` suffix is **required** — it tells SQLAlchemy to use the asyncpg driver for async I/O.

## SQLite Auto-Fallback

When PostgreSQL is unreachable, Eco-Guard automatically falls back to SQLite.

### How It Works

1. On startup, `init_db()` attempts to connect to PostgreSQL
2. If the connection fails, the system logs a warning and creates a SQLite database at `data/ecoguard.db`
3. All tables are created automatically via `Base.metadata.create_all`
4. The application continues running with SQLite as the database

```python
async def init_db() -> None:
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

### Fallback Behavior

- **Startup log:** `PostgreSQL unavailable — falling back to SQLite (data/ecoguard.db)`
- **No data migration:** If you later connect PostgreSQL, existing SQLite data is not migrated
- **No connection pooling:** SQLite uses `NullPool` (direct connections, not pooled)

### Checking Current Database

```bash
curl http://localhost:8000/api/v1/health
```

If the database is reachable, `checks.database` will show `"up"`.

## Connection Pooling Configuration

PostgreSQL connection pooling uses SQLAlchemy's `QueuePool`:

```env
DB_POOL_SIZE=20           # Persistent connections kept open
DB_MAX_OVERFLOW=10        # Additional connections under load (max 30)
DB_POOL_TIMEOUT=30        # Wait time for a connection (seconds)
```

### Pool Sizing Guidelines

| Load | `DB_POOL_SIZE` | `DB_MAX_OVERFLOW` |
|------|---------------|-------------------|
| Light (< 10 req/s) | 5 | 5 |
| Moderate (10–100 req/s) | 20 | 10 |
| Heavy (> 100 req/s) | 40 | 20 |

The pool is automatically sized based on environment:

```python
pool_class = NullPool if settings.environment == "development" else QueuePool
```

In development mode, `NullPool` is used (no connection reuse) for easier debugging.

### Connection Validation

`pool_pre_ping=True` is always enabled. This runs `SELECT 1` before each connection checkout to detect stale connections from server restarts or network blips.

## Migrations

Eco-Guard uses **Alembic** for database migrations.

### Configure Alembic

The `alembic.ini` file reads `DATABASE_URL` from the environment:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname  # Overridden by env.py
```

### Running Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Generate a new migration from model changes
uv run alembic revision --autogenerate -m "add user email column"

# View migration history
uv run alembic history

# Roll back one migration
uv run alembic downgrade -1

# Roll back to a specific revision
uv run alembic downgrade abc123def
```

### Auto-Migration on Startup

```env
AUTO_MIGRATE=true
```

When enabled, the application runs `alembic upgrade head` during startup. **Use with caution in production** — consider running migrations as a separate deployment step.

### Makefile Shortcuts

```bash
make migrate        # Apply migrations
make migrate-new    # Create new migration (prompts for message)
```

## Backup and Restore

### Using the API

```bash
# Create a backup
curl -X POST http://localhost:8000/api/v1/mlops/backup \
  -H "X-API-Key: eco-guard-dev-key"

# List backups
curl http://localhost:8000/api/v1/mlops/backup \
  -H "X-API-Key: eco-guard-dev-key"
```

Requires `pg_dump` installed on the server. The API backs up only the PostgreSQL database.

### Manual Backup

```bash
# Backup
pg_dump -h localhost -U postgres -d ecoguard \
  --no-owner --no-acl \
  -f backups/ecoguard-backup-$(date +%Y%m%d-%H%M%S).sql

# Restore
psql -h localhost -U postgres -d ecoguard < backups/ecoguard-backup-20250115.sql
```

### SQLite Backup

SQLite databases are a single file:

```bash
cp data/ecoguard.db backups/ecoguard-sqlite-$(date +%Y%m%d).db
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `DATABASE_URL` parse error | Incorrect URL format | Ensure `+asyncpg` suffix: `postgresql+asyncpg://...` |
| "PostgreSQL unavailable" on startup | PostgreSQL not running or wrong credentials | Check PostgreSQL is running: `pg_isready -U postgres -d ecoguard` |
| `asyncpg.exceptions.TooManyConnectionsError` | Pool exhausted | Increase `DB_POOL_SIZE` or `DB_MAX_OVERFLOW` |
| Connections hang indefinitely | Network issue between app and PostgreSQL | Enable `pool_pre_ping` (already enabled by default) |
| SQLite lock errors under concurrency | SQLite is single-writer | Switch to PostgreSQL for production workloads |
| Migrations fail | Schema mismatch | Generate a new migration with `--autogenerate` |
