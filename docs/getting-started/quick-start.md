# Quick Start

The fastest way to get Eco-Guard running with full MLOps capabilities.

## One Command

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

This starts the server with:
- SQLite database (auto-created)
- JWT auth (admin/admin)
- Metrics, rate limiting, circuit breaker
- WebSocket live telemetry
- Vue 3 SPA dashboard

Open `http://localhost:8000/dashboard` and log in.

## With a Model

Download a TinyLlama model and restart:

```bash
mkdir -p models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
  -O models/tinyllama.gguf
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Test inference:

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Authorization: Bearer $(curl -s -X POST 'http://localhost:8000/api/v1/auth/login?username=admin&password=admin' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')" \
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

uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

The server auto-detects PostgreSQL and uses it. All MLOps features (model registry, experiments, training jobs) become available.

## Docker Compose (All-in-One)

```bash
docker-compose up --build
```

Starts PostgreSQL + Eco-Guard together. Add a model volume in `docker-compose.yml` to mount your GGUF files.
