# Training Jobs

Training jobs orchestrate model fine-tuning runs. Each job tracks its configuration, status, and relationship to datasets and registered models.

## Job Lifecycle

```
queued → running → completed
              ↓         ↓
          cancelled   failed
```

| Status | Meaning | Next Action |
|--------|---------|-------------|
| `queued` | Job created, waiting to start | Call `start` endpoint |
| `running` | Training is in progress | Monitor progress |
| `completed` | Training finished successfully | Register output model |
| `failed` | Training encountered an error | Check `error_message`, fix, retry |
| `cancelled` | Training was manually stopped | Archive or delete |

## Creating Jobs

Create a training job with QLoRA configuration:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "name": "fine-tune-support-v2",
    "config": {
      "method": "qlora",
      "base_model": "./models/llama-3-8b.gguf",
      "dataset_id": 5,
      "epochs": 3,
      "learning_rate": 2e-4,
      "lora_r": 8,
      "lora_alpha": 16,
      "batch_size": 4,
      "max_seq_length": 512,
      "gradient_accumulation_steps": 2
    },
    "base_model_id": 1,
    "dataset_id": 5,
    "output_model_name": "support-model-v2",
    "trigger_type": "manual"
  }'
```

### QLoRA Configuration

| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| `method` | Training method | `"qlora"` |
| `epochs` | Number of training epochs | `1`–`5` |
| `learning_rate` | Optimizer learning rate | `2e-4` |
| `lora_r` | LoRA rank (low-rank dimension) | `8` or `16` |
| `lora_alpha` | LoRA alpha (scaling factor) | `16` or `32` |
| `batch_size` | Per-device batch size | `4`–`16` |
| `max_seq_length` | Maximum sequence length | `512`–`2048` |
| `gradient_accumulation_steps` | Gradient accumulation | `2`–`8` |

### Job Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable job name |
| `config` | Yes | Training configuration dict |
| `base_model_id` | No | Reference to a registered model |
| `dataset_id` | No | Reference to a dataset for training |
| `output_model_name` | No | Name for the model produced by this job |
| `trigger_type` | No | `manual`, `drift`, or `scheduled` |

## Trigger Types

### Manual

Standard user-initiated training. Default trigger type.

```bash
# trigger_type=manual (default)
```

### Drift

Automatically created by the drift pipeline when drift exceeds the threshold:

```python
job = await TrainingOrchestrator.create_job(
    db=db,
    name=f"drift-retrain-{timestamp}",
    config=job_config,
    dataset_id=dataset.id,
    trigger_type="drift",
    trigger_detail={"drift_score": 0.85, "threshold": 0.8},
)
```

### Scheduled

Jobs created by the scheduler for periodic retraining.

## Managing Jobs

### Start a Queued Job

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/start \
  -H "X-API-Key: eco-guard-dev-key"
```

Only jobs in `queued` status can be started. The response updates the status to `running` and sets `started_at`.

### Complete a Job

```bash
# Success
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/complete \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "success=true"

# Failure with error details
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/complete \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "success=false" \
  -d "error_message=Out of memory at step 342"
```

### Cancel a Job

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs/5/cancel \
  -H "X-API-Key: eco-guard-dev-key"
```

Any job (queued or running) can be cancelled.

## Listing Jobs

Query jobs with status and trigger type filters:

```bash
# All jobs
curl http://localhost:8000/api/v1/mlops/jobs \
  -H "X-API-Key: eco-guard-dev-key"

# Running jobs
curl "http://localhost:8000/api/v1/mlops/jobs?status=running" \
  -H "X-API-Key: eco-guard-dev-key"

# Drift-triggered jobs
curl "http://localhost:8000/api/v1/mlops/jobs?trigger_type=drift" \
  -H "X-API-Key: eco-guard-dev-key"

# Combined filter
curl "http://localhost:8000/api/v1/mlops/jobs?status=failed&trigger_type=drift&limit=25" \
  -H "X-API-Key: eco-guard-dev-key"
```

## Monitoring Job Progress

### Via Dashboard

The `/dashboard/jobs` page shows:
- All jobs with status badges (color-coded)
- Trigger type labels
- Configuration preview
- Start/completion timestamps
- Error messages for failed jobs
- Action buttons: Start, Complete, Cancel

### Via API

The status endpoint doesn't provide real-time progress (that's tracked via experiments). Instead:

1. **Create a job** → get `job.id`
2. **Create an experiment** linked to this job → `training_job_id=job.id`
3. **Log metrics** to the experiment during training
4. **Complete the job** when training finishes

```python
# Integration pattern
job = create_job(...)
exp = create_experiment(..., training_job_id=job.id)

start_job(job.id)

for step in training_loop:
    # ... training logic ...
    log_metric(exp.id, step, "eval_loss", loss)

complete_job(job.id, success=True)
complete_experiment(exp.id, status=COMPLETED)
```

## Job Response Example

```json
{
  "id": 5,
  "name": "fine-tune-support-v2",
  "status": "completed",
  "config": {
    "method": "qlora",
    "lora_r": 8,
    "lora_alpha": 16,
    "epochs": 3,
    "learning_rate": 0.0002
  },
  "trigger_type": "manual",
  "trigger_detail": null,
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T14:45:00Z",
  "error_message": null,
  "created_at": "2025-01-15T10:25:00Z",
  "created_by": "admin"
}
```
