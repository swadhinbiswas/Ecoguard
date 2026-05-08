# Model Setup

Eco-Guard supports multiple model backends. Choose based on your hardware.

## Backend Comparison

| Backend | Hardware | Speed | Setup | Cost |
|---|---|---|---|---|
| **llama-cpp** | CPU | Slow | Local file | Free |
| **Ollama** | CPU/GPU | Fast | `ollama serve` | Free |
| **vLLM** | GPU | Fastest | Docker/conda | Free |
| **TGI** | GPU | Fast | Docker | Free |
| **OpenAI-compatible** | Remote | Varies | API key | Usage-based |

## llama-cpp (CPU, Default)

```bash
mkdir -p models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
  -O models/tinyllama.gguf
```

No `.env` changes needed — `BACKEND=llama-cpp` is the default.

## Ollama (Recommended for Development)

Ollama provides optimized GPU-accelerated inference out of the box.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull tinyllama
ollama pull llama3.2

# Set in .env
BACKEND=ollama
BACKEND_URL=http://localhost:11434
BACKEND_MODEL=tinyllama
```

## vLLM (Production GPU)

```bash
# Start vLLM server
pip install vllm
vllm serve meta-llama/Llama-3.2-3B-Instruct --port 8001

# Set in .env
BACKEND=vllm
BACKEND_URL=http://localhost:8001
BACKEND_MODEL=meta-llama/Llama-3.2-3B-Instruct
```

## OpenAI-Compatible (Any Provider)

Works with OpenAI, Azure, Anthropic-compatible, Together AI, Groq, etc.

```bash
# Set in .env
BACKEND=openai
BACKEND_URL=https://api.openai.com
BACKEND_API_KEY=sk-...
BACKEND_MODEL=gpt-4o-mini
```

Any service implementing the `/v1/completions` OpenAI API endpoint is supported.

## Hot-Swapping Models

Eco-Guard can switch models without restarting. Use the MLOps API:

```bash
# Register a new model
curl -X POST http://localhost:8000/api/v1/mlops/models/register \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=my-model" \
  -F "artifact_path=./models/new-model.gguf"

# Deploy it (replaces production model)
curl -X POST http://localhost:8000/api/v1/mlops/models/1/deploy \
  -H "Authorization: Bearer $TOKEN"
```
