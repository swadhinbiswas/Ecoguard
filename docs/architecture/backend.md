# Backend Abstraction

Eco-Guard abstracts LLM inference behind a unified backend interface, allowing you to switch between local GGUF models and remote OpenAI-compatible servers without changing API consumers.

## The ModelBackend Abstract Class

**Source:** `src/core/backend.py`

```python
class ModelBackend(ABC):
    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def load(self, model_path: str | None = None) -> None: ...

    @abstractmethod
    def generate(
        self, prompt: str, max_tokens: int = 128,
        temperature: float = 0.7, top_p: float | None = None,
        top_k: int | None = None, repeat_penalty: float | None = None,
    ) -> dict: ...

    @abstractmethod
    def generate_stream(
        self, prompt: str, max_tokens: int = 128,
        temperature: float = 0.7, top_p: float | None = None,
        top_k: int | None = None, repeat_penalty: float | None = None,
    ): ...

    @abstractmethod
    def unload(self) -> None: ...
```

All backends must implement these five methods. The `generate` method returns a dict with `choices` (list of `{"text": "..."}`) and `usage` (token counts). `generate_stream` returns an iterator/generator yielding dicts with the same structure per token.

## LlamaCppBackend

The local backend that loads GGUF model files directly using `llama-cpp-python`.

### How It Works

```python
class LlamaCppBackend(ModelBackend):
    def load(self, model_path: str | None = None) -> None:
        path = model_path or settings.model_path
        from llama_cpp import Llama
        self._model = Llama(
            model_path=path,
            n_ctx=settings.model_n_ctx,
            n_threads=settings.model_n_threads,
            n_batch=settings.model_n_batch,
            verbose=False,
        )
```

The model is loaded into memory on startup. llama.cpp provides CPU-optimized inference with configurable context length, thread count, and batch size.

### Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `MODEL_PATH` | `./models/tinyllama.gguf` | Path to GGUF model file |
| `MODEL_N_CTX` | `2048` | Context window size in tokens |
| `MODEL_N_THREADS` | `4` | Number of CPU threads for inference |
| `MODEL_N_BATCH` | `512` | Batch size for prompt processing |

### Hot-Swapping

The backend supports hot-swapping models at runtime. Calling `load()` with a new path first unloads the old model, then loads the new one. This is triggered automatically when deploying a model with the `direct` strategy:

```python
# In ModelRegistryService.deploy():
if strategy == DeploymentStrategy.DIRECT and os.path.exists(model.artifact_path):
    get_backend().load(model.artifact_path)
```

### Warmup

On startup, if `MODEL_WARMUP_ENABLED=true` (default), the backend runs a single inference with `MODEL_WARMUP_PROMPT` (default `"Hello"`) to pre-warm caches and verify the model responds correctly.

## OpenAICompatibleBackend

Connects to any server implementing the OpenAI `/v1/completions` API.

### Supported Backends

| Backend | `BACKEND` value | Default URL | Notes |
|---------|----------------|-------------|-------|
| vLLM | `vllm` | `http://localhost:8001` | High-throughput, GPU-optimized |
| Ollama | `ollama` | `http://localhost:11434` | Easy local setup |
| TGI (Text Generation Inference) | `tgi` | `http://localhost:8001` | HuggingFace's production server |
| OpenAI API | `openai` | `https://api.openai.com` | Requires API key |

All four use the same `OpenAICompatibleBackend` class:

```python
class OpenAICompatibleBackend(ModelBackend):
    def __init__(self, base_url: str, api_key: str = "", model_name: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self._loaded = True

    def generate(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        payload = {
            "model": self.model_name or "default",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # ... POST to {base_url}/v1/completions
```

### Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `BACKEND` | `llama-cpp` | Backend type: `llama-cpp`, `vllm`, `tgi`, `ollama`, `openai` |
| `BACKEND_URL` | `http://localhost:8001` | Base URL of the remote server |
| `BACKEND_API_KEY` | `""` | API key for OpenAI or authenticated servers |
| `BACKEND_MODEL` | `""` | Model name to pass in the `model` field |

### Authentication

The backend includes the API key in the `Authorization: Bearer <key>` header:

```python
headers = {"Content-Type": "application/json"}
if self.api_key:
    headers["Authorization"] = f"Bearer {self.api_key}"
```

## Backend Initialization

The backend is initialized once during app startup:

```python
def init_backend() -> ModelBackend:
    backend_type = getattr(settings, "backend", "llama-cpp")

    if backend_type in ("vllm", "tgi", "ollama", "openai"):
        _backend = OpenAICompatibleBackend(
            base_url=settings.backend_url,
            api_key=settings.backend_api_key,
            model_name=settings.backend_model,
        )
    else:
        _backend = LlamaCppBackend()

    _backend.load(settings.model_path)
    # Warmup if enabled
    return _backend
```

The global `_backend` is accessed via `get_backend()` throughout the codebase.

## Streaming Support

Both backends implement `generate_stream()`:

### LlamaCppBackend Streaming

Uses llama.cpp's built-in streaming:

```python
def generate_stream(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
    return self._model(
        prompt=prompt, max_tokens=max_tokens, temperature=temperature,
        stream=True, **kwargs
    )
```

The `stream=True` parameter causes llama.cpp to return a Python generator yielding token dicts.

### OpenAICompatibleBackend Streaming

Uses SSE (Server-Sent Events) parsing:

```python
def generate_stream(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
    payload = {"model": ..., "prompt": ..., "stream": True}
    with httpx.Client(timeout=300) as client:
        with client.stream("POST", f"{self.base_url}/v1/completions", json=payload) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    yield json.loads(chunk)
```

The `stream=True` parameter in the payload tells the OpenAI-compatible server to respond with SSE. The backend iterates over response lines, extracts `data:` lines, and parses the JSON chunks.

### SSE Output Format

Regardless of backend, the streaming service (`src/services/streaming_service.py`) wraps each token into SSE:

```
data: {"token":"The","index":1}

data: {"token":" capital","index":2}

data: {"request_id":"abc-123","token_count":2,"latency_ms":245.32,"done":true}
```

## Adding a New Backend

To add a custom backend, implement the `ModelBackend` ABC:

```python
class MyCustomBackend(ModelBackend):
    def __init__(self):
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str | None = None) -> None:
        # Initialize your model or connection
        self._loaded = True

    def generate(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        # Return: {"choices": [{"text": "output"}], "usage": {...}}
        return {
            "choices": [{"text": "generated text here"}],
            "usage": {"completion_tokens": 5, "prompt_tokens": 3, "total_tokens": 8},
        }

    def generate_stream(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        # Yield dicts: {"choices": [{"text": "token "}]}
        yield {"choices": [{"text": "generated "}]}
        yield {"choices": [{"text": "text "}]}

    def unload(self) -> None:
        self._loaded = False
```

Then register it in `init_backend()`:

```python
def init_backend() -> ModelBackend:
    backend_type = getattr(settings, "backend", "llama-cpp")

    if backend_type == "my-custom":
        _backend = MyCustomBackend()
    elif backend_type in ("vllm", "tgi", "ollama", "openai"):
        # ... existing code ...
    else:
        _backend = LlamaCppBackend()
```

Add the new backend type to the `Literal` type in `Settings`:

```python
backend: Literal["llama-cpp", "vllm", "tgi", "ollama", "openai", "my-custom"] = "llama-cpp"
```
