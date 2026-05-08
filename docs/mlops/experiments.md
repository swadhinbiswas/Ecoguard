# Experiment Tracking

Experiment tracking records training runs, logs per-step metrics, and enables head-to-head comparisons between experiments.

## Creating Experiments

An experiment captures a training configuration and its relationship to a model and dataset:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/experiments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "name": "qlora-rank-16",
    "base_model": "llama-3-8b",
    "hyperparameters": {
      "method": "qlora",
      "lora_r": 16,
      "lora_alpha": 32,
      "epochs": 3,
      "learning_rate": 2e-4,
      "batch_size": 8
    },
    "dataset_version": "20250115-103000",
    "notes": "Testing higher rank for better quality"
  }'
```

### Experiment Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable experiment name |
| `base_model` | Yes | Base model identifier |
| `hyperparameters` | Yes | Dict of training hyperparameters |
| `dataset_version` | No | Version string of the dataset used |
| `notes` | No | Free-text notes about the experiment |

### Experiment Statuses

| Status | Meaning |
|--------|---------|
| `running` | Training is in progress |
| `completed` | Training finished successfully |
| `failed` | Training encountered an error |
| `cancelled` | Training was manually cancelled |

## Logging Metrics Per Step

Log metrics at each training step to track progress:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/experiments/10/metrics \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "step=100" \
  -d "metric_name=eval_loss" \
  -d "metric_value=0.342"

curl -X POST http://localhost:8000/api/v1/mlops/experiments/10/metrics \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "step=100" \
  -d "metric_name=eval_accuracy" \
  -d "metric_value=0.892"
```

You can log multiple metric names per step (e.g., `eval_loss`, `eval_accuracy`, `perplexity`).

## Auto-Tracking Best Metric

The experiment tracker automatically identifies the best metric value:

- **`eval_loss`**: lower is better → minimum is tracked as `best_metric_value`
- **`eval_accuracy`**: higher is better → maximum is tracked as `best_metric_value`
- **Other metrics**: the first occurrence's direction is autodetected

```python
if metric_name == "eval_loss":
    if best_metric_value is None or metric_value < best_metric_value:
        best_metric = "eval_loss"
        best_metric_value = metric_value
elif metric_name == "eval_accuracy":
    if best_metric_value is None or metric_value > best_metric_value:
        best_metric = "eval_accuracy"
        best_metric_value = metric_value
```

The `total_steps` field tracks the maximum step number logged so far.

### Training Loop Integration

```python
for step in range(num_steps):
    train_loss = train_one_step(...)

    if step % log_interval == 0:
        eval_loss, eval_acc = evaluate(...)

        # Log to Eco-Guard
        requests.post(
            f"{base_url}/api/v1/mlops/experiments/{exp_id}/metrics",
            headers={"X-API-Key": api_key},
            data={"step": step, "metric_name": "eval_loss", "metric_value": eval_loss},
        )
        requests.post(
            f"{base_url}/api/v1/mlops/experiments/{exp_id}/metrics",
            headers={"X-API-Key": api_key},
            data={"step": step, "metric_name": "eval_accuracy", "metric_value": eval_acc},
        )
```

## Viewing an Experiment

Get full experiment details including all logged metrics:

```bash
curl http://localhost:8000/api/v1/mlops/experiments/10 \
  -H "X-API-Key: eco-guard-dev-key"
```

```json
{
  "id": 10,
  "name": "qlora-rank-16",
  "base_model": "llama-3-8b",
  "hyperparameters": {"lora_r": 16, "lora_alpha": 32, "epochs": 3, "learning_rate": 2e-4},
  "status": "completed",
  "best_metric": "eval_loss",
  "best_metric_value": 0.324,
  "total_steps": 500,
  "metrics": [
    {"step": 100, "name": "eval_loss", "value": 0.342},
    {"step": 100, "name": "eval_accuracy", "value": 0.892},
    {"step": 200, "name": "eval_loss", "value": 0.336},
    {"step": 200, "name": "eval_accuracy", "value": 0.901},
    {"step": 300, "name": "eval_loss", "value": 0.324},
    {"step": 300, "name": "eval_accuracy", "value": 0.915}
  ]
}
```

### Metrics Chart (Dashboard)

The experiment detail page at `/dashboard/experiments/{id}` renders a chart of all metrics over steps. Each metric name gets its own line series.

## Comparing Experiments

Compare multiple experiments side-by-side on a specific metric:

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

- `final_value`: last logged value for the metric
- `best_value`: minimum (for loss) or maximum (for accuracy)
- `steps`: total number of steps logged with this metric

### Dashboard Comparison

On the experiments dashboard page, enter comma-separated experiment IDs and a metric name to compare:

```
IDs: 10,11,12
Metric: eval_loss
```

Results show each experiment's final value, best value, and step count.

## Listing Experiments

```bash
# All experiments
curl http://localhost:8000/api/v1/mlops/experiments \
  -H "X-API-Key: eco-guard-dev-key"

# Filter by status
curl "http://localhost:8000/api/v1/mlops/experiments?status=completed" \
  -H "X-API-Key: eco-guard-dev-key"

# Filter by status and paginate
curl "http://localhost:8000/api/v1/mlops/experiments?status=running&limit=10&offset=0" \
  -H "X-API-Key: eco-guard-dev-key"
```

Experiments are sorted by most recently started first.

## Completing Experiments

When training finishes, mark the experiment as completed or failed:

```python
# In your training script, after training:
await ExperimentTracker.complete_experiment(
    db=db,
    experiment_id=10,
    status=ExperimentStatus.COMPLETED,
    artifact_path="./models/finetuned-v3.gguf",
)
```
