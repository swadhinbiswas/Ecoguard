# Vercel Deployment

Eco-Guard can be deployed on [Vercel](https://vercel.com) as a serverless Python API with a static frontend.

## vercel.json Configuration

```json
{
  "buildCommand": "cd frontend && npm install && npm run build && cd ..",
  "outputDirectory": "frontend/dist",
  "installCommand": "pip install -r requirements.txt",
  "routes": [
    { "src": "/api/(.*)", "dest": "src.main:app" },
    { "src": "/metrics", "dest": "src.main:app" },
    { "src": "/ws/(.*)", "dest": "src.main:app" },
    { "handle": "filesystem" },
    { "src": "/(.*)", "dest": "/index.html" }
  ]
}
```

### Build Configuration

| Key | Value | Description |
|-----|-------|-------------|
| `buildCommand` | npm install + build | Builds the Vue.js frontend |
| `outputDirectory` | `frontend/dist` | Static files served from here |
| `installCommand` | `pip install -r requirements.txt` | Installs Python dependencies |

### Route Handling

Routes are processed in order:

1. **`/api/(.*)`** — Proxy to Python FastAPI app (`src.main:app`)
2. **`/metrics`** — Proxy metrics endpoint to FastAPI
3. **`/ws/(.*)`** — Proxy WebSocket connections to FastAPI
4. **`filesystem`** — Serve static files from `frontend/dist` (JS, CSS, assets)
5. **`/(.*)`** — SPA fallback: serve `index.html` for all other routes

This split ensures:
- API calls (`/api/...`, `/metrics`, `/ws/...`) are handled by Python
- Static assets (`/assets/...`) are served directly from the CDN
- Vue.js SPA routes (`/dashboard`, `/dashboard/models`, etc.) are handled client-side

## Environment Variables

Set in the Vercel dashboard (**Settings → Environment Variables**):

### Required

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ecoguard
ENVIRONMENT=production
```

### Model Configuration

```env
BACKEND=openai                  # Use remote backend (recommended for Vercel)
BACKEND_URL=https://api.openai.com
BACKEND_API_KEY=sk-...
BACKEND_MODEL=gpt-3.5-turbo-instruct
```

> **Vercel is not suitable for local GGUF models.** Use a remote backend (`vllm`, `ollama`, `openai`) since Vercel's serverless functions have no persistent filesystem and limited resources.

### Security

```env
JWT_SECRET=<random-64-char-string>
AUTH_ENABLED=true
API_KEYS=["your-production-key"]
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<secure-password>
CORS_ORIGINS=["https://eco-guard.vercel.app"]
```

### Rate Limiting

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=50         # Lower for serverless
RATE_LIMIT_WINDOW_SECONDS=60
```

## Cold Start Considerations

Vercel serverless functions have cold start latency. Factors affecting cold starts:

| Factor | Impact |
|--------|--------|
| Python 3.12 | ~500ms–2s cold start |
| Large dependencies | Increases cold start time |
| llama-cpp-python | Not recommended on Vercel (filesystem access) |

### Mitigations

1. **Use a remote backend**: Set `BACKEND=openai` or `BACKEND=vllm` to avoid local model loading
2. **Keep dependencies minimal**: Only include what's needed
3. **Disable model warmup**: `MODEL_WARMUP_ENABLED=false` since no local model
4. **Use Vercel Pro** for reduced cold starts with more concurrent executions

## Limitations

### WebSocket Support

Vercel has limited WebSocket support. The `/ws/metrics` endpoint may not work reliably in serverless environments. For WebSocket functionality:
- Use Vercel's Serverless Functions with `experimental-edge` runtime
- Or deploy the WebSocket server separately (Docker/Kubernetes/Render)

### File System

Vercel functions have a **read-only filesystem** with a `/tmp` writable directory. This means:

- **No local GGUF models**: Cannot load `.gguf` files with `llama-cpp-python`
- **No SQLite fallback**: The `data/ecoguard.db` fallback won't persist between invocations
- **External PostgreSQL is required**: Always set `DATABASE_URL`
- **Datasets are stored in `/tmp`**: They're ephemeral and lost between invocations

### Execution Duration

| Plan | Max Duration |
|------|-------------|
| Hobby (free) | 10 seconds |
| Pro | 60 seconds |

This means:
- Long inference requests may time out on free tier
- Set `REQUEST_TIMEOUT_SECONDS=8` on the free tier
- Upgrade to Pro for production inference workloads

### Memory

| Plan | Max Memory |
|------|-----------|
| Hobby | 1024 MB |
| Pro | 3008 MB |

## Deployment Steps

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel
   ```

3. **Set environment variables** in the Vercel dashboard

4. **Connect a PostgreSQL database** (use Railway, Supabase, Neon, or Render):
   ```bash
   vercel env add DATABASE_URL production
   ```

5. **Set up a remote backend** (if using OpenAI):
   ```bash
   vercel env add BACKEND production
   vercel env add BACKEND_URL production
   vercel env add BACKEND_API_KEY production
   ```

6. **Redeploy** with environment variables:
   ```bash
   vercel --prod
   ```

## Recommended Architecture for Vercel

For a production Vercel deployment, use this architecture:

```
┌─────────────────────────────────────┐
│  Vercel (Frontend + API Gateway)    │
│  - Vue.js SPA served from CDN       │
│  - API routes proxied to FastAPI    │
│  - FastAPI connects to remote LLM   │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐  ┌──────────────┐
│PostgreSQL│  │Remote Backend│
│(Neon/   │  │(vLLM/Ollama/ │
│ Supabase)│  │ OpenAI)      │
└────────┘  └──────────────┘
```

- **Frontend**: Served from Vercel's global CDN
- **API**: FastAPI serverless functions
- **Database**: Managed PostgreSQL (Neon, Supabase, Railway)
- **Model**: Remote inference server (vLLM on RunPod, Ollama on a VPS, or OpenAI API)
