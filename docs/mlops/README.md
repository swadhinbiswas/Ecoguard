# MLOps Guide

Eco-Guard's MLOps layer provides a complete machine learning operations lifecycle for LLMs — from model registration through deployment, drift monitoring, and automatic retraining.

## Lifecycle Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Register    │───>│   Promote    │───>│   Deploy     │
│  Model       │    │  to Staging  │    │  to Prod     │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                    ┌──────────────────────────┘
                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Detect      │<───│  Monitor     │<───│  Serve       │
│  Drift       │    │  Metrics     │    │  Traffic     │
└──────────────┘    └──────────────┘    └──────────────┘
       │
       ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Create      │───>│  Start       │───>│  Register    │
│  Dataset     │    │  Training    │    │  New Model   │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                    ┌──────────────────────────┘
                    ▼
              (back to Deploy)
```

## Component Overview

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| **Model Registry** | Track model versions, status, and artifacts | Every time you create or receive a new model |
| **Deployments** | Manage how models are rolled out to production | When promoting models from staging/testing |
| **Datasets** | Create training datasets from inference logs | Before starting a fine-tuning run |
| **Experiments** | Track training metrics across runs | During and after model training |
| **Training Jobs** | Orchestrate model training/fine-tuning | When you need to improve model performance |
| **Drift Detection** | Monitor for statistical drift in model behavior | Continuously, in production |
| **Auto-Retraining** | Automatically trigger retraining on drift | When you want hands-off model maintenance |
| **Model Evaluation** | Assess model quality with test cases | Before promoting a model to production |
| **A/B Testing** | Compare model variants with live traffic | When choosing between candidate models |
| **Quantization** | Compress models for faster inference | To reduce model size and improve latency |

## How the Pieces Fit Together

### Manual Fine-Tuning Flow

1. **Collect data** — Inference logs automatically record every prediction with latency and drift scores
2. **Create dataset** — Use `POST /api/v1/mlops/datasets/create-from-logs` with quality filters
3. **Create experiment** — Set up an experiment with hyperparameters
4. **Create training job** — Configure QLoRA or full fine-tuning parameters
5. **Start training** — The job orchestrates the training run; log metrics per step
6. **Register model** — Register the output model in the registry
7. **Evaluate** — Run evaluation with test cases or inference logs
8. **Deploy** — Promote to production with canary, blue-green, or A/B strategy

### Automated Retraining Flow

1. **Production inference** runs continuously
2. **Drift detector** computes z-scores on a rolling latency window
3. When drift exceeds `DRIFT_ALERT_THRESHOLD`:
   - A webhook alert is sent
   - A dataset is auto-created from recent inference logs
   - A training job is auto-created with QLoRA config
   - A `RetrainingTrigger` record is created
4. **Acknowledge** the trigger after reviewing
5. **Start** the auto-created training job
6. **Deploy** the retrained model

### Scheduled Drift Checks

The `Scheduler` runs drift checks every 5 minutes:

```python
async def _drift_check_loop(self) -> None:
    while self._running:
        # Compute drift from recent latencies
        if drift >= settings.drift_alert_threshold:
            await DriftPipeline.check_and_trigger(db, drift_score=drift)
        await asyncio.sleep(300)
```

This is in addition to per-request drift checks, providing a periodic safety net.

## API Structure

All MLOps endpoints are prefixed with `/api/v1/mlops/` and require authentication:

```
/api/v1/mlops/models/*       — Model Registry
/api/v1/mlops/datasets/*     — Dataset Pipeline
/api/v1/mlops/experiments/*  — Experiment Tracking
/api/v1/mlops/jobs/*         — Training Jobs
/api/v1/mlops/drift-triggers/* — Drift Management
/api/v1/mlops/evaluate/*     — Model Evaluation
/api/v1/mlops/ab-test/*      — A/B Testing
/api/v1/mlops/usage/*        — Usage Analytics
/api/v1/mlops/router/*       — Model Router Rules
/api/v1/mlops/prompts/*      — Prompt Templates
/api/v1/mlops/backup         — Database Backup
/api/v1/mlops/audit          — Audit Logs
```

## Dashboard

The web dashboard at `/dashboard` provides a visual interface for:

- **Overview** — key metrics, model status, drift score
- **Models** — register, deploy, rollback models
- **Inference** — recent requests, latency distribution
- **Drift** — drift timeline, triggers, threshold configuration
- **Experiments** — create, view, compare experiments
- **Jobs** — create, start, complete training jobs
- **Datasets** — create from logs, view stats

Access the dashboard at `http://localhost:8000/dashboard` after starting the server. Login with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
