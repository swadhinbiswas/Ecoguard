# Getting Started

Eco-Guard is a production-grade MLOps platform for serving and improving LLMs. This guide covers everything you need to get started.

## Prerequisites

- **Python 3.12+**
- **uv** (package manager) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Node.js 20+** (for frontend development only)
- **PostgreSQL** (optional — SQLite fallback included)
- **GGUF model file** (optional — backend can proxy to remote services)

## Installation

```bash
# Clone the repository
git clone git@github.com:swadhinbiswas/Ecoguard.git
cd Ecoguard

# Install dependencies
uv sync --group dev

# Copy environment file
cp .env.example .env

# Run the server
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## First Run

Without any additional setup, Eco-Guard starts with:

- **SQLite database** auto-created in `data/ecoguard.db`
- **llama-cpp backend** (model optional — server starts clean without one)
- **JWT authentication** enabled (default: `admin/admin`)
- **Dashboard** at `http://localhost:8000/dashboard`

## Adding a Model

### Option 1: Local GGUF (CPU)

```bash
mkdir -p models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
  -O models/tinyllama.gguf
```

### Option 2: Ollama (free, local)

```bash
ollama pull tinyllama
ollama serve
# In .env: BACKEND=ollama BACKEND_URL=http://localhost:11434 BACKEND_MODEL=tinyllama
```

### Option 3: vLLM / TGI (GPU)

```bash
# In .env: BACKEND=vllm BACKEND_URL=http://gpu-server:8000 BACKEND_MODEL=meta-llama/Llama-3.2-3B
```

## Testing the API

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Login to get a token
curl -X POST "http://localhost:8000/api/v1/auth/login?username=admin&password=admin"

# Run inference (use token from login)
export TOKEN="your-jwt-token"
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain quantum computing.", "max_tokens": 64, "temperature": 0.7}'
```

## Next Steps

- [Architecture Overview](../architecture/README.md) — understand how Eco-Guard works
- [Configuration Guide](../configuration/README.md) — all 40+ environment variables
- [MLOps Guide](../mlops/README.md) — model registry, experiments, retraining
- [API Reference](../api-reference/README.md) — complete endpoint documentation
- [Deployment Guide](../deployment/README.md) — Docker, K8s, Render, Vercel
