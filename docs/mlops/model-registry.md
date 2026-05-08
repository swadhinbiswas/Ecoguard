# Model Registry

The model registry is the central catalog for all LLM artifacts in Eco-Guard. It tracks model lineage, status, and deployment history.

## Registry Lifecycle

Models progress through a defined lifecycle:

```
registered → staging → production → archived
                ↓
              failed
```

| Status | Meaning |
|--------|---------|
| `registered` | Model is known to the system but not yet validated |
| `staging` | Model is being tested before production deployment |
| `production` | Model is actively serving traffic |
| `archived` | Model is no longer in use, but retained for rollback |
| `failed` | Model failed validation or deployment |

### Automatic Archiving

When a model is promoted to `production`, any existing `production` model with the same name is automatically archived. This ensures only one production version per model name at a time.

## Registering Models

Register a model with metadata about its origin and characteristics:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/register \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "name=customer-support-fine-tuned" \
  -d "artifact_path=./models/support-v2.gguf" \
  -d "base_model=llama-3-8b" \
  -d "framework=llama-cpp" \
  -d "description=Fine-tuned on 10k customer support conversations"
```

The system automatically:
- Generates a version string (`YYYYMMDD-HHMMSS`) if none is provided
- Computes a SHA-256 checksum of the model file for integrity verification
- Records the timestamp and creator

### Stored Metadata

```json
{
  "id": 42,
  "name": "customer-support-fine-tuned",
  "version": "20250115-103000",
  "status": "registered",
  "artifact_path": "./models/support-v2.gguf",
  "artifact_checksum": "e3b0c44298fc1c149afbf4c8996fb924...",
  "base_model": "llama-3-8b",
  "framework": "llama-cpp",
  "parameters": null,
  "metrics": null,
  "tags": null,
  "description": "Fine-tuned on 10k customer support conversations",
  "created_at": "2025-01-15T10:30:00Z",
  "deployed_at": null,
  "created_by": "admin"
}
```

### Promoting Models

Advance a model through the lifecycle:

```bash
# To staging
curl -X POST http://localhost:8000/api/v1/mlops/models/42/promote \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "target_status=staging"

# To production (archives previous production model with same name)
curl -X POST http://localhost:8000/api/v1/mlops/models/42/promote \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "target_status=production"

# To archived
curl -X POST http://localhost:8000/api/v1/mlops/models/42/promote \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "target_status=archived"
```

## Deployment Strategies

When deploying a model to production, you can choose from four strategies:

### Direct

Immediate full traffic switch. The new model is loaded into the backend and all inference requests use it.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=direct"
```

- All traffic goes to the new model immediately
- Previous model is archived
- Hot-swap: backend.load() is called automatically if the model file is local

### Canary

Gradual traffic shift based on a percentage. A random roll determines whether each request uses the new or old model.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=canary" \
  -d "traffic_percent=20"
```

- 20% of traffic routes to the new model, 80% to the previous
- Increase `traffic_percent` over time as confidence grows
- Previous deployment is marked as `superseded`

### Blue-Green

Two complete environments: the new model is fully deployed alongside the old one, and traffic switches over in one operation.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=blue_green"
```

### A/B Test

Hash-based routing ensures the same request ID always goes to the same model variant. This enables statistically valid comparisons.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=ab_test" \
  -d "traffic_percent=50"
```

- `hash(request_id) % 100 < traffic_percent` → new model (variant A)
- Otherwise → previous model (variant B)
- Deterministic: same request ID always gets same variant

## Rollback Process

Roll back a deployment to restore the previous production model:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/deployments/15/rollback \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "reason=Latency spike to 500ms"
```

What happens during rollback:
1. The deployment is marked as `rolled_back` with a timestamp and reason
2. The deployed model is archived (`status = archived`)
3. The most recently archived model with the same name is restored to `production`
4. If the restored model's artifact is local, the backend is hot-swapped to load it

## Hot-Swapping

When deploying with `strategy=direct` or rolling back, the backend automatically loads the new model:

```python
if strategy == DeploymentStrategy.DIRECT and os.path.exists(model.artifact_path):
    get_backend().load(model.artifact_path)
```

This works for `LlamaCppBackend` with local GGUF files. For remote backends (vLLM, Ollama, etc.), model switching is handled by the remote server.

## Listing Models

Query models with status and name filters:

```bash
# All production models
curl "http://localhost:8000/api/v1/mlops/models?status=production" \
  -H "X-API-Key: eco-guard-dev-key"

# Specific model name
curl "http://localhost:8000/api/v1/mlops/models?name=customer-support-fine-tuned" \
  -H "X-API-Key: eco-guard-dev-key"

# Paginated
curl "http://localhost:8000/api/v1/mlops/models?limit=25&offset=50" \
  -H "X-API-Key: eco-guard-dev-key"
```

## Dashboard Operations

The `/dashboard/models` page provides:

- **Register form** — name, artifact path, base model, framework, description
- **Model list** — all registered models with status badges
- **Deploy button** — promote and deploy any model
- **Rollback button** — rollback active deployments
