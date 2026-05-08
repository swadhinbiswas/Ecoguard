# Datasets

Datasets are created from inference logs and serve as training data for model fine-tuning. They are stored as JSONL files with metadata in the database.

## Creating Datasets from Inference Logs

Extract records from the inference log table with quality filters:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/datasets/create-from-logs \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "name=high-quality-prompts" \
  -d "hours=168" \
  -d "min_tokens=4" \
  -d "max_drift=0.3" \
  -d "limit=10000"
```

### Filter Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `name` | (required) | — | Name for the dataset |
| `hours` | `168` | 1–2160 | Lookback window in hours (7 days default, max 90 days) |
| `min_tokens` | `1` | 0+ | Minimum completion tokens per record |
| `max_drift` | `1.0` | 0.0–1.0 | Maximum allowed drift score (lower = higher quality) |
| `limit` | `10000` | 1–100000 | Maximum records to include |

### How Filtering Works

```python
for log in logs:
    if log.drift_score and log.drift_score > max_drift:
        continue          # Skip records with high drift (degraded quality)
    if not log.prediction_output or not log.prediction_output.strip():
        continue          # Skip empty outputs
    records.append({
        "input": log.input_text,
        "output": log.prediction_output,
        "latency_ms": log.latency_ms,
        "timestamp": log.timestamp.isoformat(),
    })
```

### Quality Filters in Practice

- **`min_tokens=4`**: Excludes trivial responses (e.g., single-word answers)
- **`max_drift=0.3`**: Only includes records from low-drift periods (stable model behavior)
- **`hours=168`**: Uses the last week of data

## Dataset Format (JSONL)

Datasets are stored as JSONL (JSON Lines) files — one JSON object per line:

```jsonl
{"input": "What is the capital of France?", "output": "The capital of France is Paris, a city known for...", "latency_ms": 95.4, "timestamp": "2025-01-14T10:30:00Z"}
{"input": "Explain quantum computing.", "output": "Quantum computing leverages quantum mechanics...", "latency_ms": 245.1, "timestamp": "2025-01-14T10:31:00Z"}
{"input": "Write a Python function to sort a list.", "output": "Here's a Python function that sorts a list...", "latency_ms": 180.2, "timestamp": "2025-01-14T10:32:00Z"}
```

Each record contains:
| Field | Type | Description |
|-------|------|-------------|
| `input` | string | The original prompt |
| `output` | string | The model's generated response |
| `latency_ms` | float | Inference latency in milliseconds |
| `timestamp` | string | ISO 8601 timestamp of the inference |

### Storage Location

Datasets are stored on disk:

```
datasets/
└── high-quality-prompts/
    ├── 20250115-103000.jsonl
    ├── 20250116-150000.jsonl
    └── ...
```

The `file_path` in the `Dataset` record points to the specific version file.

## Quality Score

A quality score is computed automatically:

```python
quality_score = len(records) / max(len(logs), 1)
```

This represents the ratio of records that passed filters vs. total records scanned. A score of 1.0 means all records passed all filters.

## Listing Datasets

```bash
# All datasets
curl http://localhost:8000/api/v1/mlops/datasets \
  -H "X-API-Key: eco-guard-dev-key"

# Filter by name
curl "http://localhost:8000/api/v1/mlops/datasets?name=high-quality-prompts" \
  -H "X-API-Key: eco-guard-dev-key"

# With pagination
curl "http://localhost:8000/api/v1/mlops/datasets?limit=25&offset=0" \
  -H "X-API-Key: eco-guard-dev-key"
```

Response:

```json
{
  "items": [
    {
      "id": 5,
      "name": "high-quality-prompts",
      "version": "20250115-103000",
      "record_count": 4820,
      "quality_score": 0.482,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

## Dataset Statistics

Get aggregate statistics across all datasets:

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

## Export and Download

Download a dataset as a JSONL file:

```bash
curl http://localhost:8000/api/v1/mlops/datasets/5/export \
  -H "X-API-Key: eco-guard-dev-key" \
  -o dataset.jsonl
```

The response is a file download with `Content-Type: application/json` and a `Content-Disposition` filename like `high-quality-prompts-20250115-103000.jsonl`.

## Using Datasets in Training

### Linking to Training Jobs

When creating a training job, reference the dataset:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "name": "fine-tune-support-v2",
    "config": {"method": "qlora", "epochs": 3, "learning_rate": 2e-4},
    "dataset_id": 5,
    "output_model_name": "support-model-v2"
  }'
```

### Loading in Training Scripts

The JSONL format is directly usable by most fine-tuning frameworks:

```python
import json

def load_dataset(filepath):
    data = []
    with open(filepath) as f:
        for line in f:
            record = json.loads(line)
            data.append({
                "instruction": record["input"],
                "output": record["output"],
            })
    return data
```

## Dashboard Operations

The `/dashboard/datasets` page provides:

- **Stats overview** — total datasets and total records
- **Create form** — name, hours, min tokens, max drift, limit
- **Dataset list** — all datasets with version, record count, quality score

Create a dataset from the dashboard:

```
Name: high-quality-prompts
Hours: 168
Min Tokens: 4
Max Drift: 0.3
Limit: 10000
```

## Auto-Created Datasets

The drift pipeline automatically creates datasets named `drift-trigger-YYYYMMDD-HHMM` with:

- 168 hours (7 days) of logs
- `min_tokens=4`
- `max_drift` set to the triggering drift score
- `limit=5000` records

These are visible in the dataset list with `source=inference_logs`.
