# MLOps API

All MLOps endpoints are under `/api/v1/mlops/` and require authentication.

## Model Registry

### POST /api/v1/mlops/models/register

Register a new model in the registry.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/register \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "name=my-finetuned-model" \
  -d "artifact_path=./models/finetuned.gguf" \
  -d "base_model=llama-3-8b" \
  -d "framework=llama-cpp" \
  -d "description=Fine-tuned on customer support data"
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Model name |
| `artifact_path` | Yes | File path to the GGUF model |
| `version` | No | Auto-generated as `YYYYMMDD-HHMMSS` if omitted |
| `base_model` | No | Base model name (e.g., `llama-3-8b`) |
| `framework` | No | Default `llama-cpp` |
| `description` | No | Free-text description |

**Response:**

```json
{
  "id": 42,
  "name": "my-finetuned-model",
  "version": "20250115-103000",
  "status": "registered",
  "artifact_path": "./models/finetuned.gguf",
  "artifact_checksum": "abc123def456...",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### GET /api/v1/mlops/models

List registered models with optional filters.

```bash
curl "http://localhost:8000/api/v1/mlops/models?status=production&limit=10" \
  -H "X-API-Key: eco-guard-dev-key"
```

| Query Param | Default | Description |
|-------------|---------|-------------|
| `status` | (none) | Filter by status: `registered`, `staging`, `production`, `archived`, `failed` |
| `name` | (none) | Filter by exact model name |
| `limit` | `50` | Max 200 |
| `offset` | `0` | Pagination offset |

**Response:** Array of model objects under `items`.

### POST /api/v1/mlops/models/{model_id}/promote

Change a model's status.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/promote \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "target_status=staging"
```

Promoting to `production` automatically archives any other `production` models with the same name.

### POST /api/v1/mlops/models/{model_id}/deploy

Deploy a model using a specified strategy.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=canary" \
  -d "traffic_percent=20"
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `strategy` | `direct` | `direct`, `canary`, `blue_green`, `ab_test` |
| `traffic_percent` | `100` | Traffic percentage for canary/AB strategies |

**Response:** Returns both model and deployment objects.

### POST /api/v1/mlops/deployments/{deployment_id}/rollback

Roll back a deployment.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/deployments/15/rollback \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "reason=Latency increased by 40%"
```

## Dataset Pipeline

### POST /api/v1/mlops/datasets/create-from-logs

Create a dataset from recent inference logs.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/datasets/create-from-logs \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "name=high-quality-prompts" \
  -d "hours=168" \
  -d "min_tokens=4" \
  -d "max_drift=0.3" \
  -d "limit=10000"
```

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `name` | (required) | — | Dataset name |
| `hours` | `168` | 1–2160 | Lookback window (7 days default) |
| `min_tokens` | `1` | 0+ | Minimum tokens per record |
| `max_drift` | `1.0` | 0.0–1.0 | Maximum drift score (lower = higher quality) |
| `limit` | `10000` | 1–100000 | Max records to include |

### GET /api/v1/mlops/datasets

List datasets.

```bash
curl "http://localhost:8000/api/v1/mlops/datasets?name=high-quality-prompts&limit=25" \
  -H "X-API-Key: eco-guard-dev-key"
```

### GET /api/v1/mlops/datasets/stats

Get aggregate dataset statistics.

```bash
curl http://localhost:8000/api/v1/mlops/datasets/stats \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "total_datasets": 12,
  "total_records": 45600
}
```

### GET /api/v1/mlops/datasets/{dataset_id}/export

Download a dataset as a JSONL file.

```bash
curl http://localhost:8000/api/v1/mlops/datasets/5/export \
  -H "X-API-Key: eco-guard-dev-key" \
  -o dataset.jsonl
```

## Experiment Tracking

### POST /api/v1/mlops/experiments

Create an experiment.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/experiments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "name": "qlora-experiment-1",
    "base_model": "llama-3-8b",
    "hyperparameters": {"lora_r": 8, "lora_alpha": 16, "epochs": 3, "learning_rate": 2e-4},
    "dataset_version": "20250115-103000",
    "notes": "Testing QLoRA with rank 8"
  }'
```

### POST /api/v1/mlops/experiments/{experiment_id}/metrics

Log a metric for a specific step.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/experiments/10/metrics \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "step=100" \
  -d "metric_name=eval_loss" \
  -d "metric_value=0.342"
```

The system auto-tracks best metrics:
- For `eval_loss`: lower is better (minimum tracked)
- For `eval_accuracy`: higher is better (maximum tracked)

### GET /api/v1/mlops/experiments/{experiment_id}

Get experiment details with all metrics.

```bash
curl http://localhost:8000/api/v1/mlops/experiments/10 \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "id": 10,
  "name": "qlora-experiment-1",
  "base_model": "llama-3-8b",
  "hyperparameters": {"lora_r": 8, "lora_alpha": 16, "epochs": 3},
  "status": "running",
  "best_metric": "eval_loss",
  "best_metric_value": 0.324,
  "total_steps": 500,
  "metrics": [
    {"step": 100, "name": "eval_loss", "value": 0.342},
    {"step": 200, "name": "eval_loss", "value": 0.336},
    {"step": 300, "name": "eval_loss", "value": 0.324}
  ]
}
```

### GET /api/v1/mlops/experiments

List experiments with optional status filter.

```bash
curl "http://localhost:8000/api/v1/mlops/experiments?status=running" \
  -H "X-API-Key: eco-guard-dev-key"
```

### POST /api/v1/mlops/experiments/compare

Compare experiments by a specific metric.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/experiments/compare \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "experiment_ids": [10, 11, 12],
    "metric_name": "eval_loss"
  }'
```

```json
{
  "10": {"final_value": 0.324, "best_value": 0.324, "steps": 500},
  "11": {"final_value": 0.356, "best_value": 0.348, "steps": 500},
  "12": {"final_value": 0.512, "best_value": 0.498, "steps": 300}
}
```

## Training Jobs

### POST /api/v1/mlops/jobs

Create a training job.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "name": "drift-retrain-20250115",
    "config": {
      "method": "qlora",
      "epochs": 3,
      "learning_rate": 2e-4,
      "lora_r": 8,
      "lora_alpha": 16
    },
    "dataset_id": 5,
    "output_model_name": "eco-guard-drift-fix-v2",
    "trigger_type": "manual"
  }'
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Job name |
| `config` | Yes | Training configuration (QLoRA params, etc.) |
| `base_model_id` | No | Reference to a registered model |
| `dataset_id` | No | Reference to a dataset |
| `output_model_name` | No | Name for the resulting model |
| `trigger_type` | No | `manual`, `drift`, or `scheduled` (default `manual`) |

### POST /api/v1/mlops/jobs/{job_id}/start

Start a queued job (status: `queued` → `running`).

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/start \
  -H "X-API-Key: eco-guard-dev-key"
```

### POST /api/v1/mlops/jobs/{job_id}/complete

Mark a job as completed or failed.

```bash
# Success
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/complete \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "success=true"

# Failure
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/complete \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "success=false" \
  -d "error_message=OOM during training"
```

### POST /api/v1/mlops/jobs/{job_id}/cancel

Cancel a job.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/cancel \
  -H "X-API-Key: eco-guard-dev-key"
```

### GET /api/v1/mlops/jobs

List training jobs with filters.

```bash
curl "http://localhost:8000/api/v1/mlops/jobs?status=running&trigger_type=drift" \
  -H "X-API-Key: eco-guard-dev-key"
```

## Drift Triggers

### GET /api/v1/mlops/drift-triggers

List drift retraining triggers.

```bash
curl "http://localhost:8000/api/v1/mlops/drift-triggers?acknowledged=false&limit=20" \
  -H "X-API-Key: eco-guard-dev-key"
```

### POST /api/v1/mlops/drift-triggers/{trigger_id}/acknowledge

Acknowledge a drift trigger.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/drift-triggers/3/acknowledge \
  -H "X-API-Key: eco-guard-dev-key"
```

## Model Evaluation

### POST /api/v1/mlops/evaluate

Evaluate the currently loaded model using inference logs as test cases.

```bash
curl -X POST "http://localhost:8000/api/v1/mlops/evaluate?sample_size=30" \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "status": "completed",
  "model": "./models/tinyllama.gguf",
  "test_cases": 30,
  "passed": 28,
  "failed": 2,
  "pass_rate": 93.33,
  "total_latency_ms": 2845.5,
  "avg_latency_ms": 94.85,
  "total_tokens": 145,
  "tokens_per_second": 50.96,
  "elapsed_ms": 2900.1,
  "results": [
    {"prompt": "...", "output": "...", "tokens": 5, "latency_ms": 90.5, "passed": true},
    ...
  ]
}
```

### POST /api/v1/mlops/evaluate/custom

Evaluate with custom test cases.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/evaluate/custom \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "test_cases": [
      {"prompt": "The capital of France is", "expected_tokens": 3},
      {"prompt": "1 + 1 =", "expected_tokens": 1},
      {"prompt": "The color of the sky is", "expected_tokens": 3}
    ]
  }'
```

## Quantization

### POST /api/v1/mlops/models/{model_id}/quantize

Quantize a registered GGUF model to a smaller format.

```bash
curl -X POST "http://localhost:8000/api/v1/mlops/models/42/quantize?method=q4_k_m&output_name=my-model-q4" \
  -H "X-API-Key: eco-guard-dev-key"
```

Available methods: `q4_0`, `q4_k_m` (recommended), `q5_k_m`, `q8_0`.

## Backup

### POST /api/v1/mlops/backup

Create a PostgreSQL database backup.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/backup \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "status": "completed",
  "filepath": "backups/ecoguard-backup-20250115-103000.sql",
  "filename": "ecoguard-backup-20250115-103000.sql",
  "size_mb": 2.45,
  "timestamp": "20250115-103000"
}
```

Requires `pg_dump` installed on the server.

### GET /api/v1/mlops/backup

List existing backups.

```bash
curl http://localhost:8000/api/v1/mlops/backup \
  -H "X-API-Key: eco-guard-dev-key"
```

## Prompt Templates

### GET /api/v1/mlops/prompts

List prompt templates, optionally filtered by tag.

```bash
curl "http://localhost:8000/api/v1/mlops/prompts?tag=support" \
  -H "X-API-Key: eco-guard-dev-key"
```

### POST /api/v1/mlops/prompts

Create a prompt template.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/prompts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "name": "customer-support",
    "template": "You are a {{role}}. Help the customer with: {{query}}",
    "description": "Customer support response template",
    "variables": ["role", "query"],
    "tags": ["support", "customer"]
  }'
```

### POST /api/v1/mlops/prompts/{template_id}/render

Render a template with variable values.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/prompts/3/render \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "variables": {"role": "technical support agent", "query": "password reset"}
  }'
```

```json
{
  "rendered": "You are a technical support agent. Help the customer with: password reset"
}
```

## A/B Testing

### GET /api/v1/mlops/ab-test/compare

Compare metrics between two deployments.

```bash
curl "http://localhost:8000/api/v1/mlops/ab-test/compare?deployment_a_id=10&deployment_b_id=15&hours=48" \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "deployment_a": {
    "model_name": "baseline-v1",
    "model_version": "20250110",
    "total_requests": 5230,
    "avg_latency_ms": 95.4,
    "avg_tokens": 45.2,
    "avg_drift": 0.12
  },
  "deployment_b": {
    "model_name": "candidate-v2",
    "model_version": "20250114",
    "total_requests": 2180,
    "avg_latency_ms": 78.3,
    "avg_tokens": 42.8,
    "avg_drift": 0.09
  }
}
```

## Usage Analytics

### GET /api/v1/mlops/usage

Get aggregate usage statistics.

```bash
curl "http://localhost:8000/api/v1/mlops/usage?hours=24" \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "period_hours": 24,
  "total_requests": 15230,
  "total_tokens": 1952160,
  "avg_latency_ms": 98.5,
  "rate_limit": {"max_requests": 100, "window_seconds": 60}
}
```

### GET /api/v1/mlops/usage/timeline

Get per-minute usage over a period.

```bash
curl "http://localhost:8000/api/v1/mlops/usage/timeline?hours=6" \
  -H "X-API-Key: eco-guard-dev-key"
```

## Router Rules

### GET /api/v1/mlops/router/rules

List model routing rules.

```bash
curl http://localhost:8000/api/v1/mlops/router/rules \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "default": "./models/tinyllama.gguf",
  "rules": {
    "code": "./models/code-llama.gguf",
    "translate": "./models/translator.gguf"
  }
}
```

### POST /api/v1/mlops/router/rules

Add a routing rule.

```bash
curl -X POST http://localhost:8000/api/v1/mlops/router/rules \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "pattern=code" \
  -d "model_path=./models/code-llama.gguf"
```

### DELETE /api/v1/mlops/router/rules

Remove a routing rule.

```bash
curl -X DELETE "http://localhost:8000/api/v1/mlops/router/rules?pattern=code" \
  -H "X-API-Key: eco-guard-dev-key"
```

## Audit Log

### GET /api/v1/mlops/audit

Query audit logs for MLOps operations.

```bash
curl "http://localhost:8000/api/v1/mlops/audit?action=deploy&resource_type=model&limit=50" \
  -H "X-API-Key: eco-guard-dev-key"
```

| Query Param | Description |
|-------------|-------------|
| `action` | Filter by action type |
| `actor` | Filter by actor name |
| `resource_type` | Filter by resource type (e.g., `model`, `dataset`) |
| `limit` | Max 500 |
| `offset` | Pagination offset |
