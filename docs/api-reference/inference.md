# Inference API

## POST /api/v1/predict

Synchronously generate a text completion from the loaded LLM.

### Request

```json
{
  "prompt": "The capital of France is",
  "max_tokens": 128,
  "temperature": 0.7,
  "top_p": null,
  "top_k": null,
  "repeat_penalty": null
}
```

| Parameter | Type | Required | Default | Range | Description |
|-----------|------|----------|---------|-------|-------------|
| `prompt` | string | **Yes** | — | 1–4000 chars | The input text for the LLM |
| `max_tokens` | integer | No | `128` | 1–2048 | Maximum tokens to generate |
| `temperature` | float | No | `0.7` | 0.0–2.0 | Sampling temperature (higher = more random) |
| `top_p` | float | No | `null` | 0.0–1.0 | Nucleus sampling probability |
| `top_k` | integer | No | `null` | 1–100 | Top-k sampling (tokens considered) |
| `repeat_penalty` | float | No | `null` | 1.0–2.0 | Penalty for repeating tokens |

> **Note:** `top_p`, `top_k`, and `repeat_penalty` are optional. When omitted, the backend uses its defaults.

### Response (200 OK)

```json
{
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "output": "Paris, the capital of France, is one of the most...",
  "latency_ms": 245.32,
  "token_count": 128,
  "timestamp": "2025-01-15T10:30:00.123456Z",
  "drift_score": 0.12
}
```

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string (UUID) | Unique request identifier |
| `output` | string | Generated text completion |
| `latency_ms` | float | Inference time in milliseconds |
| `token_count` | integer | Number of completion tokens generated |
| `timestamp` | string (ISO 8601) | UTC timestamp of the response |
| `drift_score` | float or null | Statistical drift score (0.0–1.0) |

### Example: Basic curl Request

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "prompt": "Explain quantum computing in simple terms:",
    "max_tokens": 200,
    "temperature": 0.5
  }'
```

### Example: With Bearer Token Auth

```bash
# First, get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=admin" | jq -r '.access_token')

# Then make a prediction
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "prompt": "Write a haiku about machine learning:",
    "max_tokens": 50,
    "temperature": 0.9,
    "top_p": 0.92
  }'
```

### Example: With Top-K and Repeat Penalty

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{
    "prompt": "Once upon a time in a digital world,",
    "max_tokens": 150,
    "temperature": 0.8,
    "top_k": 40,
    "repeat_penalty": 1.1
  }'
```

### Error Responses

#### 400 — Empty Prompt

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"prompt": ""}'
```

```json
{
  "detail": "Prompt cannot be empty"
}
```

#### 400 — Prompt Too Long

```json
{
  "detail": "Prompt exceeds maximum character limit of 4000"
}
```

#### 401 — Unauthorized

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid authentication"
  }
}
```

#### 429 — Rate Limited

```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

**Response headers:**
```
X-RateLimit-Limit: 100
Retry-After: 45
```

#### 503 — Model Not Loaded

```json
{
  "detail": "Model not loaded"
}
```

#### 500 — Inference Failed

```json
{
  "detail": "Internal inference error"
}
```

## POST /api/v1/predict/stream

Stream tokens as Server-Sent Events (SSE) in real-time.

### Request

Same request body as `/api/v1/predict`.

### Response

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

Each event is a JSON object on a `data:` line, followed by a blank line:

```
data: {"token":"The","index":1}

data: {"token":" capital","index":2}

data: {"token":" of","index":3}

data: {"request_id":"abc-123","token_count":3,"latency_ms":145.67,"done":true}
```

**Token event fields:**
| Field | Type | Description |
|-------|------|-------------|
| `token` | string | The generated token text |
| `index` | integer | 1-based token index |

**Done event fields:**
| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique request identifier |
| `token_count` | integer | Total tokens generated |
| `latency_ms` | float | Total streaming time |
| `done` | boolean | Always `true` for the final event |

**Error event:**
```
data: {"error":"Inference failed","done":true}
```

### Example: Streaming curl

```bash
curl -X POST http://localhost:8000/api/v1/predict/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -N \
  -d '{
    "prompt": "List the planets in order:",
    "max_tokens": 64,
    "temperature": 0.3
  }'
```

> The `-N` flag disables curl's buffering, which is essential for seeing streaming output in real-time.

### Example: JavaScript fetch with SSE

```javascript
const response = await fetch('http://localhost:8000/api/v1/predict/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'eco-guard-dev-key',
  },
  body: JSON.stringify({
    prompt: 'Write a short story:',
    max_tokens: 128,
    temperature: 0.8,
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  const lines = text.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      if (data.done) {
        console.log('Complete:', data);
      } else {
        process.stdout.write(data.token);
      }
    }
  }
}
```

## Prompt Sanitization

All prompts are sanitized before inference:

- **Null bytes** (`\x00`) are stripped
- **Whitespace** is trimmed from both ends
- **Length** is capped at `MAX_INPUT_CHARS` (default 4000)

Prompts exceeding the limit or empty after sanitization will receive a 400 error before any model computation.

## Response Caching

When `CACHE_ENABLED=true`, identical `(prompt, max_tokens, temperature)` requests return cached results with:

```json
{
  "request_id": "...",
  "output": "cached result",
  "latency_ms": 0.0,
  "token_count": 0,
  "timestamp": "...",
  "drift_score": null
}
```

Note the `latency_ms: 0.0` and `token_count: 0` for cache hits.
