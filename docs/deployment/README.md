# Deployment

Eco-Guard supports multiple deployment strategies from simple single-machine setups to production Kubernetes clusters.

## Deployment Options

| Method | Best For | Complexity |
|--------|----------|------------|
| **Local (uvicorn)** | Development, testing | Minimal |
| **Docker Compose** | Single-server production, demos | Low |
| **Kubernetes** | Production clusters, auto-scaling | Medium |
| **Render** | Quick cloud deployment, free tier | Low |
| **Vercel** | Serverless deployment | Low |

## Choosing an Approach

### Use Local Development When...
- You're developing or testing changes
- You need hot-reload for rapid iteration
- You're running on a laptop or single machine

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Use Docker Compose When...
- You want reproducible deployments on a single server
- You need PostgreSQL alongside the API
- You want simple volume management for models

```bash
docker-compose up -d
```

### Use Kubernetes When...
- You need horizontal scaling (HPA)
- You have an existing Kubernetes cluster
- You need zero-downtime rolling updates
- You want integrated monitoring (Prometheus, Grafana)

```bash
kubectl apply -f k8s/
```

### Use Render When...
- You want quick cloud deployment without infrastructure management
- You're comfortable with the free tier limitations
- You need a managed PostgreSQL database

### Use Vercel When...
- You want serverless deployment
- Your frontend is the primary concern
- You understand cold-start limitations for Python APIs

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.11+ | 3.12+ |
| RAM | 512 MB | 2 GB+ (for model loading) |
| Disk | 1 GB | 5 GB+ (for models and database) |
| CPU | 2 cores | 4+ cores (for CPU inference) |
| Model Storage | 500 MB | 10 GB+ (multiple models) |

## Common Configuration

Regardless of deployment method, configure these essential variables:

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ecoguard
MODEL_PATH=/path/to/model.gguf

# Strongly recommended for production
ENVIRONMENT=production
JWT_SECRET=<random-64-char-string>
API_KEYS=["your-production-key"]
ADMIN_PASSWORD=<secure-password>
CORS_ORIGINS=["https://your-domain.com"]
```

## Deployment Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Change `JWT_SECRET` from default
- [ ] Change `ADMIN_PASSWORD` from default
- [ ] Set `API_KEYS` to production keys
- [ ] Configure `CORS_ORIGINS` to your domain
- [ ] Set up PostgreSQL (not relying on SQLite fallback)
- [ ] Download model file to `MODEL_PATH`
- [ ] Configure `BACKEND_URL` if using remote backend
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure `ALERTING_WEBHOOK_URL` for alerts
- [ ] Test health endpoint: `GET /api/v1/health`
- [ ] Test inference endpoint: `POST /api/v1/predict`
