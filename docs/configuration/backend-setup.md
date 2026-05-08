# Backend Setup

Eco-Guard supports multiple inference backends. This guide covers setup for each.

## LlamaCppBackend (Local GGUF)

The default backend. Runs models locally on CPU using `llama-cpp-python`.

### Prerequisites

llama-cpp-python is installed automatically via `uv sync` as a project dependency. No additional setup is required.

### Download a Model

```bash
# Create models directory
mkdir -p models

# Download a GGUF model (example: TinyLlama 1.1B)
curl -L -o models/tinyllama.gguf \
  https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
```

### Configure

```env
BACKEND=llama-cpp
MODEL_PATH=./models/tinyllama.gguf
MODEL_N_CTX=2048
MODEL_N_THREADS=4
MODEL_N_BATCH=512
MODEL_WARMUP_ENABLED=true
MODEL_WARMUP_PROMPT=Hello
```

### Test

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

```bash
curl http://localhost:8000/api/v1/health
```

Expected output:
```json
{"status":"healthy","service":"eco-guard",...,"checks":{"database":"up","model":"loaded"}}
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `Model file not found` | Verify `MODEL_PATH` points to an existing `.gguf` file |
| `ModuleNotFoundError: No module named 'llama_cpp'` | Run `uv sync` to install dependencies |
| Slow inference | Increase `MODEL_N_THREADS`, reduce `MODEL_N_CTX`, or use a smaller model |
| OOM during model load | Reduce `MODEL_N_CTX` or use a smaller quantized model |

## vLLM Backend

[vLLM](https://github.com/vllm-project/vllm) is a high-throughput, GPU-optimized inference server.

### Setup

```bash
# Install vLLM
pip install vllm

# Start the vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --host 0.0.0.0 \
  --port 8001
```

### Configure Eco-Guard

```env
BACKEND=vllm
BACKEND_URL=http://localhost:8001
BACKEND_MODEL=meta-llama/Llama-3.2-1B-Instruct
```

### Test

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{"prompt":"Explain machine learning","max_tokens":50}'
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Connection refused to vLLM | Verify vLLM is running on the correct port |
| `BACKEND_URL` must include protocol | Use `http://` not just `localhost:8001` |
| GPU OOM | Reduce `max-model-len` in vLLM or use a smaller model |

## Ollama Backend

[Ollama](https://ollama.com) provides easy local model management.

### Setup

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2

# Ollama serves on port 11434 by default
```

### Configure Eco-Guard

```env
BACKEND=ollama
BACKEND_URL=http://localhost:11434
BACKEND_MODEL=llama3.2
```

### Test

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{"prompt":"What is 2+2?","max_tokens":20}'
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Ollama not running | Run `ollama serve` |
| Model not found | Run `ollama pull <model>` first |
| `BACKEND_MODEL` mismatch | Must match the exact model name in `ollama list` |

## TGI Backend

Hugging Face's [Text Generation Inference](https://github.com/huggingface/text-generation-inference).

### Setup

```bash
# Run TGI via Docker
docker run --gpus all -p 8001:80 \
  -e HF_TOKEN=$HF_TOKEN \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id meta-llama/Llama-3.2-1B-Instruct
```

### Configure Eco-Guard

```env
BACKEND=tgi
BACKEND_URL=http://localhost:8001
BACKEND_MODEL=meta-llama/Llama-3.2-1B-Instruct
```

### Common Issues

| Issue | Solution |
|-------|----------|
| TGI requires GPU | Use `--disable-custom-kernels` for CPU-only, but it's not recommended |
| Auth required for gated models | Set `HF_TOKEN` environment variable in the Docker container |

## OpenAI Backend

Connect to the OpenAI API directly.

### Configure

```env
BACKEND=openai
BACKEND_URL=https://api.openai.com
BACKEND_API_KEY=sk-your-key-here
BACKEND_MODEL=gpt-3.5-turbo-instruct
```

> **Note:** Use `gpt-3.5-turbo-instruct` for the `/v1/completions` endpoint. Chat models like `gpt-4o` use the `/v1/chat/completions` endpoint, which requires a different API format.

### Test

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eco-guard-dev-key" \
  -d '{"prompt":"Write a haiku about AI","max_tokens":20}'
```

## Testing Connectivity

Use the health endpoint to verify backend connectivity:

```bash
curl http://localhost:8000/api/v1/health | jq .
```

The `checks.model` field should show `"loaded"`.

For a full end-to-end test:

```bash
# Check if the model responds
curl http://localhost:8000/api/v1/benchmark
```

If the benchmark returns timing data, the backend is working correctly.

## Switching Backends at Runtime

While the backend is initialized at startup, you can change models at runtime via the model registry's deploy feature. Deploying a model with `strategy=direct` hot-swaps the model in the `LlamaCppBackend`.
