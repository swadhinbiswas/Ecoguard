# Model Evaluation

Model evaluation measures the quality of a loaded model using test cases — either built-in defaults, extracted from inference logs, or custom user-provided cases.

## Built-in Evaluation with Test Cases

The default evaluator ships with four built-in test prompts:

```python
default_test_cases = [
    {"prompt": "The capital of France is", "expected_tokens": 3},
    {"prompt": "1 + 1 =", "expected_tokens": 1},
    {"prompt": "The color of the sky is", "expected_tokens": 3},
    {"prompt": "Python is a", "expected_tokens": 5},
]
```

### Running Evaluation from Logs

Evaluate using random samples from inference logs:

```bash
curl -X POST "http://localhost:8000/api/v1/mlops/evaluate?sample_size=20" \
  -H "X-API-Key: eco-guard-dev-key"
```

This:
1. Randomly samples `sample_size` inputs from `inference_logs` where `token_count > 0`
2. Uses these as test cases (with `max_tokens=50`, `temperature=0.0`)
3. Runs each through the loaded model using `asyncio.to_thread()`
4. Reports pass/fail per test case and aggregate metrics

### Response

```json
{
  "status": "completed",
  "model": "./models/tinyllama.gguf",
  "test_cases": 20,
  "passed": 18,
  "failed": 2,
  "pass_rate": 90.0,
  "total_latency_ms": 1890.5,
  "avg_latency_ms": 94.53,
  "total_tokens": 95,
  "tokens_per_second": 50.24,
  "elapsed_ms": 1920.1,
  "results": [
    {
      "prompt": "What is the capital of France?",
      "output": "Paris, the capital of France...",
      "tokens": 5,
      "latency_ms": 90.5,
      "passed": true
    },
    {
      "prompt": "Explain quantum computing.",
      "error": "Model not loaded",
      "passed": false
    }
  ]
}
```

| Metric | Description |
|--------|-------------|
| `status` | `"completed"` or `"no_data"` if no logs available |
| `test_cases` | Number of test prompts evaluated |
| `passed` | Number of test cases that produced tokens (`tokens > 0`) |
| `failed` | Number of test cases with errors or zero tokens |
| `pass_rate` | Percentage passed (`passed / test_cases * 100`) |
| `total_latency_ms` | Sum of all inference latencies |
| `avg_latency_ms` | Mean latency per test case |
| `total_tokens` | Total completion tokens across all test cases |
| `tokens_per_second` | `total_tokens / (total_latency / 1000)` |
| `elapsed_ms` | Wall-clock time for the entire evaluation |
| `results` | Per-test-case details |

### Pass/Fail Criteria

A test case passes if:
- The model generates at least 1 token
- No exception occurs during inference

A test case fails if:
- The model throws an exception
- The model generates 0 tokens

## Custom Test Cases

Provide your own test cases for targeted evaluation:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/evaluate/custom \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "test_cases": [
      {"prompt": "Translate to French: Hello", "expected_tokens": 2},
      {"prompt": "Summarize: The quick brown fox jumps over the lazy dog", "expected_tokens": 10},
      {"prompt": "Write a haiku about AI", "max_tokens": 50},
      {"prompt": "What is 2 + 2?", "expected_tokens": 3}
    ],
    "model_path": null
  }'
```

Each test case supports:
| Field | Required | Description |
|-------|----------|-------------|
| `prompt` | Yes | The input prompt |
| `expected_tokens` | No | Expected token count (informational only) |
| `max_tokens` | No | Override default max_tokens (default: 50) |

The `model_path` parameter is optional — if omitted, the currently loaded model is evaluated. If provided, the evaluator attempts to load the specified model first.

## Evaluation from Inference Logs

The `evaluate_from_logs` method samples inference logs to create test cases:

```python
result = await db.execute(
    select(InferenceLog.input_text, InferenceLog.prediction_output)
    .where(InferenceLog.token_count > 0)
    .order_by(func.random())
    .limit(sample_size)
)
rows = result.all()

test_cases = [
    {"prompt": r.input_text, "expected_tokens": 5}
    for r in rows if r.input_text
]
```

Benefits:
- Tests on real prompts from actual users
- Random sampling prevents selection bias
- Only uses previous successful inferences (`token_count > 0`)

## Evaluation Use Cases

### Pre-Deployment Validation

Before promoting a model to production:

```bash
# 1. Load the candidate model
POST /api/v1/mlops/models/42/deploy (strategy=direct)

# 2. Run evaluation
POST /api/v1/mlops/evaluate?sample_size=30

# 3. Check pass_rate and avg_latency_ms
# If satisfactory, keep deployed
# If not, rollback
POST /api/v1/mlops/deployments/X/rollback -d "reason=Low pass rate in evaluation"
```

### Regression Testing

```bash
# Run the same custom test cases against different model versions
curl -X POST http://localhost:8000/api/v1/mlops/evaluate/custom \
  -d '{"test_cases": [{"prompt": "What is 1+1?"}, {"prompt": "The sky is"}]}'

# Compare results between model versions
```

### Continuous Monitoring

Run periodic evaluations using the scheduler to detect quality degradation independently of drift detection.

## Evaluation Metrics Deep Dive

### Pass Rate

```
pass_rate = (passed / total_test_cases) * 100
```

A model that generates valid (non-empty) output for all prompts has a 100% pass rate. A model that crashes or produces empty output on some prompts has a lower rate.

### Tokens Per Second

```
tokens_per_second = total_tokens / (total_latency_ms / 1000)
```

This measures the model's generation speed. Higher values indicate faster inference. Compare this across model versions to quantify performance changes.

### Latency (avg, total, per-case)

Latency is measured per test case using `time.perf_counter()` around the `asyncio.to_thread(backend.generate)` call. Total latency sums all cases. Average latency is total divided by test case count.
