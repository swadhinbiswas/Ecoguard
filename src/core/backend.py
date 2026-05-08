import json
import os
from abc import ABC, abstractmethod
from typing import Optional

from src.core.config import settings
from src.core.exceptions import ModelNotLoadedError
from src.core.logging import logger
from src.monitoring.metrics import set_model_loaded


class ModelBackend(ABC):
    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def load(self, model_path: str | None = None) -> None: ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
    ) -> dict: ...

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
    ): ...

    @abstractmethod
    def unload(self) -> None: ...

    @property
    def info(self) -> dict:
        return {"backend": self.__class__.__name__, "loaded": self.is_loaded()}


class LlamaCppBackend(ModelBackend):
    def __init__(self):
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self, model_path: str | None = None) -> None:
        path = model_path or settings.model_path
        if not os.path.exists(path):
            logger.warning(f"Model file not found: {path}")
            raise FileNotFoundError(f"Model not found: {path}")

        from llama_cpp import Llama

        self._model = Llama(
            model_path=path,
            n_ctx=settings.model_n_ctx,
            n_threads=settings.model_n_threads,
            n_batch=settings.model_n_batch,
            verbose=False,
        )
        set_model_loaded(True)
        logger.info(f"LlamaCpp backend loaded: {path}")

    def generate(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        if self._model is None:
            raise ModelNotLoadedError()
        return self._model(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            **{k: v for k, v in kwargs.items() if v is not None},
        )

    def generate_stream(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        if self._model is None:
            raise ModelNotLoadedError()
        return self._model(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            **{k: v for k, v in kwargs.items() if v is not None},
        )

    def unload(self) -> None:
        self._model = None
        set_model_loaded(False)


class OpenAICompatibleBackend(ModelBackend):
    def __init__(self, base_url: str, api_key: str = "", model_name: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self._loaded = True

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str | None = None) -> None:
        self._loaded = True
        set_model_loaded(True)
        logger.info(f"OpenAI backend connected: {self.base_url}")

    def generate(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        import httpx

        payload = {
            "model": self.model_name or "default",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=300) as client:
                resp = client.post(
                    f"{self.base_url}/v1/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                choice = data["choices"][0]
                text = choice.get("text", "")
                if not text and "message" in choice:
                    text = choice["message"].get("content", "")

                usage = data.get("usage", {})
                return {
                    "choices": [{"text": text}],
                    "usage": {
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                }
        except Exception as e:
            logger.error(f"OpenAI backend error: {e}")
            raise

    def generate_stream(self, prompt, max_tokens=128, temperature=0.7, **kwargs):
        import httpx

        payload = {
            "model": self.model_name or "default",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=300) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/v1/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk == "[DONE]":
                                break
                            try:
                                yield json.loads(chunk)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    def unload(self) -> None:
        self._loaded = False
        set_model_loaded(False)

    @property
    def info(self) -> dict:
        return {
            "backend": "openai-compatible",
            "base_url": self.base_url,
            "model": self.model_name,
            "loaded": self._loaded,
        }


_backend: Optional[ModelBackend] = None


def get_backend() -> ModelBackend:
    global _backend
    if _backend is None:
        raise RuntimeError("Backend not initialized")
    return _backend


def init_backend() -> ModelBackend:
    global _backend

    backend_type = getattr(settings, "backend", "llama-cpp")

    if backend_type in ("vllm", "tgi", "ollama", "openai"):
        url = getattr(settings, "backend_url", "http://localhost:8001")
        key = getattr(settings, "backend_api_key", "")
        model = getattr(settings, "backend_model", "")
        _backend = OpenAICompatibleBackend(base_url=url, api_key=key, model_name=model)
        logger.info(f"Initialized {backend_type} backend at {url}")
    else:
        _backend = LlamaCppBackend()
        logger.info("Initialized llama-cpp backend")

    model_path = os.getenv("MODEL_PATH", settings.model_path)
    try:
        _backend.load(model_path)
        if settings.model_warmup_enabled:
            result = _backend.generate(
                prompt=settings.model_warmup_prompt,
                max_tokens=5,
                temperature=0.0,
            )
            logger.info(
                f"Model warmup complete — tokens: {result['usage']['completion_tokens']}"
            )
    except Exception as e:
        logger.warning(f"Model not loaded: {e}")
        # Don't crash — backend connects lazily

    return _backend


def shutdown_backend() -> None:
    global _backend
    if _backend is not None:
        _backend.unload()
        _backend = None
