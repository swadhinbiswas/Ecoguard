# Docker Deployment

Eco-Guard provides a multi-stage Dockerfile and docker-compose.yml for containerized deployment.

## Dockerfile Overview

The Dockerfile uses a **multi-stage build** with `uv` (Astral's Python package manager):

```dockerfile
# Stage 1: Build
FROM python:3.11-slim AS builder
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
COPY pyproject.toml ./
RUN uv venv && uv sync --no-dev

# Stage 2: Runtime
FROM python:3.11-slim
COPY --from=builder /app/.venv /app/.venv
COPY . .
USER appuser
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Key Design Decisions

- **Non-root user**: The runtime stage creates an `appuser` with no sudo access
- **Build cache**: `pyproject.toml` is copied before source code for layer caching
- **`--no-dev`**: Only production dependencies are installed in the final image
- **Health check**: Docker HEALTHCHECK pings `/api/v1/health` every 30 seconds

## docker-compose.yml Setup

The compose file defines two services:

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/ecoguard
      - MODEL_PATH=/app/models/tinyllama.gguf
      - ENVIRONMENT=production
    volumes:
      - ./models:/app/models:ro
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=ecoguard
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Building and Running

### Quick Start

```bash
# Build and start all services
make docker-up

# Or manually:
docker-compose up --build -d
```

### Check Status

```bash
# View logs
docker-compose logs -f api

# Check health
curl http://localhost:8000/api/v1/health
```

### Stop

```bash
make docker-down
# Or:
docker-compose down
```

## Environment Variables

Set additional variables in the `environment` section of `docker-compose.yml`:

```yaml
environment:
  - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/ecoguard
  - MODEL_PATH=/app/models/tinyllama.gguf
  - ENVIRONMENT=production
  - LOG_LEVEL=INFO
  - RATE_LIMIT_ENABLED=true
  - METRICS_ENABLED=true
  - CACHE_ENABLED=false
  - JWT_SECRET=your-production-secret
  - API_KEYS=["your-production-key"]
  - ADMIN_PASSWORD=secure-password
  - MAX_CONCURRENT_INFERENCE=4
```

Or use an env file:

```yaml
api:
  env_file:
    - .env.production
```

## Volume Mounts for Models

Models are mounted as read-only volumes:

```yaml
volumes:
  - ./models:/app/models:ro    # Read-only mount
```

### Preparing Models

```bash
# Create models directory
mkdir -p models

# Download your GGUF model
curl -L -o models/tinyllama.gguf \
  https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

# Or copy a local model
cp /path/to/your-model.gguf models/
```

Update `MODEL_PATH` in the compose file:

```yaml
- MODEL_PATH=/app/models/your-model.gguf
```

## Health Checks

Both services have health checks:

```yaml
# API service
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 30s

# PostgreSQL
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres -d ecoguard"]
  interval: 10s
  timeout: 5s
  retries: 5
```

## Production Considerations

### Resource Limits

```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '0.5'
        memory: 512M
```

### Logging

```yaml
api:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

### Restart Policy

```yaml
api:
  restart: unless-stopped   # Restart unless manually stopped
```

### Network Security

```yaml
api:
  ports:
    - "127.0.0.1:8000:8000"   # Bind to localhost only

# Use a reverse proxy (nginx, traefik) for public access
```

## Common Issues

| Issue | Solution |
|-------|----------|
| `Model file not found` | Ensure the model is in `./models/` and `MODEL_PATH` uses `/app/models/...` |
| PostgreSQL connection refused | Wait for PostgreSQL health check to pass; check `DATABASE_URL` hostname |
| Permission denied on volumes | Ensure `./models` directory is readable |
| Port already in use | Change the host port: `"8080:8000"` instead of `"8000:8000"` |
| Container exits immediately | Check logs: `docker-compose logs api` |

## Build Variants

### GPU Support (NVIDIA)

```dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04
# ... install Python, dependencies, and llama-cpp-python with CUDA support
```

### Full Docker Compose with Monitoring

```yaml
services:
  api: ...
  postgres: ...
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
    ports:
      - "9090:9090"
  grafana:
    image: grafana/grafana
    volumes:
      - ./monitoring/grafana:/etc/grafana/provisioning
    ports:
      - "3000:3000"
```
