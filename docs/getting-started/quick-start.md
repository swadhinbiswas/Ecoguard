# Quick Start

The fastest way to get Eco-Guard running with full MLOps capabilities.

## One Command

```bash
uv sync --group dev
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

This starts the server with:
- SQLite database (auto-created in `data/ecoguard.db`)
- Metrics, rate limiting, circuit breaker
- WebSocket live telemetry
- Vue 3 SPA dashboard
- Swagger API docs at `/docs`

Auth is **disabled by default** in development. To enable it, set:
```bash
export AUTH_ENABLED=true
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=your-password
export JWT_SECRET=your-secret-at-least-32-chars
```

## With a Model

Download a GGUF model and start:

```bash
mkdir -p models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
  -O models/tinyllama.gguf

export MODEL_PATH=./models/tinyllama.gguf
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Test inference (with auth enabled):

```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Make a prediction
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is machine learning?", "max_tokens": 64, "temperature": 0.7}'
```

## With PostgreSQL

```bash
docker run -d --name ecoguard-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=ecoguard \
  -p 5432:5432 postgres:15-alpine

export DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ecoguard
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

The server auto-detects PostgreSQL and uses it. All MLOps features (model registry, experiments, training jobs) become available.

## With Docker Compose (Production)

```bash
export JWT_SECRET="your-long-random-secret-at-least-32-chars"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="your-strong-password"
docker compose up --build
```

Starts PostgreSQL + Eco-Guard together with production validation enabled.
