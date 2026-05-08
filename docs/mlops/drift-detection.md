# Drift Detection

Drift detection continuously monitors inference behavior for statistical deviations that indicate model degradation.

## How Drift Detection Works

Eco-Guard uses a **z-score based latency drift detector** that tracks a rolling window of inference latencies:

```python
class StatisticalDriftDetector:
    def __init__(self, window_size: int = 100):
        self._latency_history: List[float] = []
        self._token_history: List[int] = []

    def update_and_check(self, latency: float, token_count: int) -> float:
        # Append to rolling window
        self._latency_history.append(latency)
        self._token_history.append(token_count)

        # Maintain window size
        if len(self._latency_history) > self.window_size:
            self._latency_history.pop(0)
            self._token_history.pop(0)

        # Need minimum samples
        if len(self._latency_history) < 10:
            return 0.0

        # Compute z-score
        mean_latency = np.mean(self._latency_history[:-1])  # exclude current
        std_latency = np.std(self._latency_history[:-1]) + 1e-6  # avoid /0
        z_score = abs(latency - mean_latency) / std_latency

        # Normalize to 0.0–1.0 scale
        drift_score = min(1.0, z_score / 10.0)
        return float(drift_score)
```

### Step by Step

1. Every inference call records its latency and token count
2. Latency is appended to a rolling window (default size: 100)
3. When the window has at least 10 samples:
   - Compute the **mean** and **standard deviation** of all latencies except the current one
   - Calculate the **z-score**: `abs(latency - mean) / std`
   - Normalize to **0.0–1.0** by dividing the z-score by 10 and capping at 1.0
4. The drift score is stored on the `InferenceLog` record and exposed as a Prometheus gauge

### Interpretation

| Drift Score | Meaning |
|-------------|---------|
| 0.0 – 0.3 | Normal operation, no drift |
| 0.3 – 0.5 | Mild deviation, worth monitoring |
| 0.5 – 0.8 | Significant deviation, potential issue |
| 0.8 – 1.0 | Critical drift, likely degraded performance |

## Rolling Window Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DRIFT_WINDOW_SIZE` | `100` | Number of latency samples in the rolling window |
| `DRIFT_MIN_SAMPLES` | `10` | Minimum samples before drift calculation starts |

### Tuning Guidelines

- **Larger window** (200–500): More stable baseline, slower to detect sudden changes
- **Smaller window** (50–100): Faster to detect changes, more volatile
- **Higher `DRIFT_MIN_SAMPLES`**: Prevents false positives during cold start

## Drift Score Sources

Drift scores are computed at multiple points:

### 1. Per-Request (Primary)

Every call to `POST /api/v1/predict` computes a drift score:

```python
drift_score = drift_detector.update_and_check(latency_ms, token_count)
```

The score is:
- Stored in the `InferenceLog.drift_score` column
- Exposed as Prometheus gauge `ecoguard_drift_score`
- Checked against `DRIFT_ALERT_THRESHOLD` for triggering alerts and retraining

### 2. Scheduled Check (Secondary)

The `Scheduler` runs every 5 minutes as a backup:

```python
async def _drift_check_loop(self) -> None:
    while self._running:
        # Compute drift from recent 10 latencies
        if drift >= settings.drift_alert_threshold:
            await DriftPipeline.check_and_trigger(db, drift_score=drift)
        await asyncio.sleep(300)
```

This catches sustained drift even if individual requests don't trigger the threshold.

## Viewing Drift in Dashboard

The `/dashboard/drift` page displays:

- **Current avg drift** — mean drift score over last 24 hours
- **Samples in window** — number of latency samples being tracked
- **Drift timeline** — chart of drift scores over time
- **Trigger list** — all retraining triggers with acknowledgment status
- **Threshold indicator** — current `DRIFT_ALERT_THRESHOLD` value

### Color Coding

In the inference table, drift scores are color-coded:
- **Green** (< 0.4): Normal
- **Yellow** (0.4–0.7): Elevated
- **Red** (> 0.7): Critical

## Alerting on Threshold Breach

When the drift score exceeds `DRIFT_ALERT_THRESHOLD` (default: 0.8):

### 1. Webhook Alert

```python
if drift_score >= settings.drift_alert_threshold:
    alerter = get_alerter(webhook_url=settings.alerting_webhook_url)
    await alerter.send_drift_alert(
        drift_score=drift_score,
        latency_ms=latency_ms,
        token_count=token_count,
        threshold=settings.drift_alert_threshold,
    )
```

Configure the webhook URL:
```env
ALERTING_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
```

### 2. Prometheus Alert

The alert rule `DriftThresholdExceeded` fires when `ecoguard_drift_score > 0.8` for 1 minute.

### 3. Auto-Retraining Pipeline

The drift pipeline automatically creates a dataset and training job for remediation (see [Auto-Retraining](auto-retraining.md)).

## Drift Score in API Responses

The drift score is included in every prediction response:

```json
{
  "request_id": "abc-123",
  "output": "The capital of France is Paris...",
  "latency_ms": 245.32,
  "token_count": 128,
  "timestamp": "2025-01-15T10:30:00Z",
  "drift_score": 0.12
}
```

## Limitations

- **Univariate**: Only latency-based drift is detected. The detector does not analyze output quality or semantic drift.
- **Z-score normalization**: The `/10.0` divisor is a heuristic; extremely stable systems may show inflated scores on small deviations.
- **Token drift**: `_token_history` is maintained but not currently used in the drift calculation. Future versions may incorporate token count variance as a second signal.
