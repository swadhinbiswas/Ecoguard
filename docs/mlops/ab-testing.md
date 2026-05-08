# A/B Testing

A/B testing in Eco-Guard enables controlled comparison of model variants using live production traffic.

## Traffic Splitting Strategies

Eco-Guard supports four deployment strategies that affect how A/B testing works:

| Strategy | Splitting Method | Use Case |
|----------|-----------------|----------|
| `direct` | 100% to new model | Immediate switch (not A/B) |
| `canary` | Random percentage | Gradual rollout |
| `blue_green` | Full environment switch | Complete cutover |
| `ab_test` | Hash-based routing | Statistically valid comparison |

## Canary Deployment

Traffic is split randomly based on a percentage:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=canary" \
  -d "traffic_percent=10"
```

### How It Works

```python
if random.random() * 100 < dep.traffic_percent:
    # Route to new model (canary)
    return model, "canary_new"
else:
    # Route to previous model (baseline)
    return prev_model, "canary_baseline"
```

- Start with `traffic_percent=10` (10% to new, 90% to baseline)
- Monitor metrics for 24 hours
- Increase to 25%, then 50%, then 100% as confidence grows
- After reaching 100%, the baseline deployment is superseded

### Canary Rollout Plan

```
Phase 1: traffic_percent=10  → Monitor for 6 hours
Phase 2: traffic_percent=25  → Monitor for 12 hours
Phase 3: traffic_percent=50  → Monitor for 24 hours
Phase 4: traffic_percent=100 → Full switch
```

## A/B Test with Hash-Based Routing

For statistically valid A/B comparisons, use hash-based routing:

```bash
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=ab_test" \
  -d "traffic_percent=50"
```

### How It Works

```python
bucket = hash(request_id) % 100
if bucket < dep.traffic_percent:
    # Variant A (new model)
    return model, "ab_variant_a"
else:
    # Variant B (baseline)
    return baseline_model, "ab_variant_b"
```

Key properties:
- **Deterministic**: Same `request_id` always maps to the same variant
- **Uniform**: Hash modulo 100 distributes evenly across buckets
- **Stable**: Adding/removing variants doesn't re-shuffle existing assignments

## Comparing Deployments

Compare metrics between any two deployments:

```bash
curl "http://localhost:8000/api/v1/mlops/ab-test/compare?deployment_a_id=10&deployment_b_id=15&hours=24" \
  -H "X-API-Key: eco-guard-dev-key"
```

### Response

```json
{
  "deployment_a": {
    "model_name": "customer-support-v1",
    "model_version": "20250110",
    "total_requests": 5230,
    "avg_latency_ms": 95.4,
    "avg_tokens": 45.2,
    "avg_drift": 0.12
  },
  "deployment_b": {
    "model_name": "customer-support-v2",
    "model_version": "20250114",
    "total_requests": 2180,
    "avg_latency_ms": 78.3,
    "avg_tokens": 42.8,
    "avg_drift": 0.09
  }
}
```

### Comparison Dimensions

| Metric | What to Look For |
|--------|-----------------|
| `total_requests` | Ensure both variants received sufficient traffic |
| `avg_latency_ms` | Lower is better; the new model should not be slower |
| `avg_tokens` | Consistency of response length |
| `avg_drift` | Lower drift indicates more stable behavior |

## Metrics Comparison

### What to Compare

**Performance Metrics:**
- Average latency: Is the new model faster or slower?
- Token throughput: Does the new model generate more/fewer tokens?

**Quality Metrics:**
- Drift score: Is the new model more or less stable?
- Pass rate (from evaluation): Does the new model produce valid outputs consistently?

**Operational Metrics:**
- Error rate: Does the new model have more inference failures?
- Rate limiting: Is one variant being rate-limited more?

### Making Decisions

A good candidate model should show:

1. **Lower or comparable latency** (not significantly slower)
2. **Lower or comparable drift** (not less stable)
3. **Similar token counts** (consistent response patterns)
4. **Higher evaluation pass rate** (if evaluated separately)

If the new model shows:
- Higher latency → Investigate model size or quantization
- Higher drift → Model may be unstable; check training data quality
- Lower token counts → May be truncating responses; check max_tokens config

## Routing Logic Priority

When multiple deployment strategies are active, the routing logic resolves in this priority:

1. **Direct** deployments first (full traffic switch)
2. **Canary** deployments next (random percentage split)
3. **A/B Test** deployments last (hash-based split)

```python
direct_deps = [d for d in deployments if d.strategy == DIRECT]
if direct_deps:
    return direct_deps[0].model, "direct"

canary_deps = [d for d in deployments if d.strategy == CANARY]
if canary_deps:
    # Random split logic

ab_deps = [d for d in deployments if d.strategy == AB_TEST]
if ab_deps:
    # Hash-based split logic
```

This means if a direct deployment exists, canary and A/B tests are ignored. To run an A/B test, ensure no direct deployments are active for that model.

## A/B Test Duration

| Traffic Level | Recommended Duration | Rationale |
|--------------|---------------------|-----------|
| Low (< 10 req/min) | 48–72 hours | Need enough samples for significance |
| Medium (10–100 req/min) | 24–48 hours | Sufficient data for analysis |
| High (> 100 req/min) | 12–24 hours | Large sample sizes accumulate quickly |

## Ending an A/B Test

```bash
# If the new model wins: deploy as direct (100% traffic)
curl -X POST http://localhost:8000/api/v1/mlops/models/42/deploy \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "strategy=direct"

# If the baseline wins: rollback the A/B deployment
curl -X POST http://localhost:8000/api/v1/mlops/deployments/15/rollback \
  -H "X-API-Key: eco-guard-dev-key" \
  -d "reason=A/B test showed no improvement"
```
