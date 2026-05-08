# Auto-Retraining

When drift is detected, Eco-Guard can automatically initiate a retraining pipeline — creating a dataset, a training job, and a trigger record for review.

## End-to-End Pipeline

```
Inference → Drift Score ≥ Threshold
      ↓
Webhook Alert + Auto-Retraining Pipeline
      ↓
1. Create Dataset (from recent inference logs)
2. Create Training Job (QLoRA config)
3. Create RetrainingTrigger record
4. (Operator acknowledges trigger)
5. (Operator starts training job)
6. (Model is trained and registered)
7. (Operator deploys retrained model)
```

## Trigger Configuration

### Threshold

```env
DRIFT_ALERT_THRESHOLD=0.8
```

The pipeline triggers when any inference call has a drift score ≥ this threshold. Lower values make the pipeline more sensitive.

### Cooldown Period

To prevent cascading triggers, the pipeline enforces a 1-hour cooldown:

```python
if recent:
    cooldown = (datetime.now(timezone.utc) - recent.triggered_at).total_seconds()
    if cooldown < 3600:  # 1 hour
        logger.debug(f"Retraining cooldown active ({cooldown:.0f}s remaining)")
        return None
```

After a trigger fires, no new auto-triggers occur for 60 minutes, even if drift persists. This prevents creating dozens of duplicate jobs during a sustained drift event.

## Pipeline Details

When drift exceeds the threshold and cooldown has elapsed:

### Step 1: Create Dataset

```python
dataset = await DatasetPipeline.create_from_inference_logs(
    db=db,
    name=f"drift-trigger-{timestamp}",
    hours=168,          # 7 days of logs
    min_tokens=4,       # Minimum 4 tokens per record
    max_drift=drift_score,  # Only records with drift ≤ current score
    limit=5000,         # Max 5000 records
    created_by="drift-pipeline",
)
```

The dataset captures the inference data that triggered the drift, filtered to include only quality records.

### Step 2: Create Training Job

```python
job_config = {
    "method": "qlora",
    "base_model": settings.model_path,
    "dataset_id": dataset.id,
    "epochs": 3,
    "learning_rate": 2e-4,
    "lora_r": 8,
    "lora_alpha": 16,
}

training_job = await TrainingOrchestrator.create_job(
    db=db,
    name=f"drift-retrain-{timestamp}",
    config=job_config,
    dataset_id=dataset.id,
    output_model_name=f"eco-guard-drift-fix-v{date}",
    trigger_type="drift",
    trigger_detail={"drift_score": drift_score, "threshold": threshold},
    created_by="drift-pipeline",
)
```

### Step 3: Create Trigger Record

```python
trigger = RetrainingTrigger(
    drift_score=drift_score,
    threshold=threshold,
    dataset_id=dataset.id,
    training_job_id=training_job.id,
    auto_triggered=True,
)
```

## Manual vs Auto Triggers

| Type | `auto_triggered` | Created By | Typical Use |
|------|-----------------|------------|-------------|
| Manual | `false` | `"admin"` or username | Operator-initiated retraining |
| Auto | `true` | `"drift-pipeline"` | Automated drift response |

Both types create jobs with `trigger_type="drift"` or `trigger_type="manual"` respectively.

## Acknowledging Triggers

Triggers require acknowledgment — this serves as a review step before training starts:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/drift-triggers/3/acknowledge \
  -H "X-API-Key: eco-guard-dev-key"
```

### Dashboard

On the `/dashboard/drift` page:
- Unacknowledged triggers are highlighted
- Click **Acknowledge** to mark as reviewed
- The trigger's `acknowledged_at` timestamp is recorded

### Listing Triggers

```bash
# All triggers
curl http://localhost:8000/api/v1/mlops/drift-triggers \
  -H "X-API-Key: eco-guard-dev-key"

# Unacknowledged only
curl "http://localhost:8000/api/v1/mlops/drift-triggers?acknowledged=false" \
  -H "X-API-Key: eco-guard-dev-key"
```

## Scheduled Drift Monitoring

In addition to per-request drift detection, the `Scheduler` runs a background check every 5 minutes:

```python
async def _drift_check_loop(self) -> None:
    while self._running:
        # Only check if we have enough samples
        if len(drift_detector._latency_history) >= drift_min_samples:
            # Compute drift from last 10 latencies
            drift = min(1.0, abs(recent[-1] - mean) / std / 10)

            if drift >= settings.drift_alert_threshold:
                await DriftPipeline.check_and_trigger(db, drift_score=drift)

        await asyncio.sleep(300)  # 5 minutes
```

This ensures drift is detected even between individual inference requests.

## Auto-Cleanup

A separate scheduled task cleans up old acknowledged triggers:

```python
async def _cleanup_loop(self) -> None:
    while self._running:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        await db.execute(
            delete(RetrainingTrigger).where(
                RetrainingTrigger.acknowledged,
                RetrainingTrigger.triggered_at < cutoff,
            )
        )
        await asyncio.sleep(86400)  # Daily
```

Acknowledged triggers older than 90 days are automatically deleted.

## Full Workflow Example

```bash
# 1. Configure thresholds
export DRIFT_ALERT_THRESHOLD=0.7
export ALERTING_WEBHOOK_URL=https://hooks.slack.com/...

# 2. Start the server (triggers will auto-fire on drift)
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# 3. Check for drift triggers
curl http://localhost:8000/api/v1/mlops/drift-triggers \
  -H "X-API-Key: eco-guard-dev-key"

# 4. Acknowledge the trigger (reviews the auto-created job)
curl -X POST http://localhost:8000/api/v1/mlops/drift-triggers/3/acknowledge \
  -H "X-API-Key: eco-guard-dev-key"

# 5. Start the auto-created training job
curl -X POST http://localhost:8000/api/v1/mlops/jobs/7/start \
  -H "X-API-Key: eco-guard-dev-key"

# 6. After training completes, register the output model
#    (done by the training script or manual registration)

# 7. Deploy the retrained model
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=canary" \
  -d "traffic_percent=20"
```
