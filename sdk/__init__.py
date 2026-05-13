"""Eco-Guard Python SDK — drop-in OpenAI-compatible client."""

import json
from typing import Any, AsyncGenerator, Optional

import httpx


class EcoGuard:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def _aclient(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout)

    # ── Chat Completions ──────────────────────────────────────

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "default",
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        with self._client() as client:
            r = client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False,
                    **kwargs,
                },
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    async def achat(
        self,
        messages: list[dict[str, str]],
        model: str = "default",
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        async with self._aclient() as client:
            r = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False,
                    **kwargs,
                },
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "default",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ):
        with self._client().stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            },
            headers=self._headers,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield json.loads(data)

    async def achat_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "default",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async with self._aclient().stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            },
            headers=self._headers,
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield json.loads(data)

    # ── Legacy Completions ────────────────────────────────────

    def predict(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        with self._client() as client:
            r = client.post(
                f"{self.base_url}/api/v1/predict",
                json={
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    # ── Embeddings ────────────────────────────────────────────

    def embed(self, text: str | list[str], model: str = "default") -> dict[str, Any]:
        with self._client() as client:
            r = client.post(
                f"{self.base_url}/v1/embeddings",
                json={"model": model, "input": text},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    # ── Models ────────────────────────────────────────────────

    def models(self) -> dict[str, Any]:
        with self._client() as client:
            r = client.get(f"{self.base_url}/v1/models", headers=self._headers)
            r.raise_for_status()
            return r.json()

    # ── Cost ─────────────────────────────────────────────────

    def cost_estimate(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "default",
    ) -> dict[str, Any]:
        with self._client() as client:
            r = client.get(
                f"{self.base_url}/v1/cost/estimate",
                params={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": model,
                },
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    def cost_usage(self, hours: int = 24) -> dict[str, Any]:
        with self._client() as client:
            r = client.get(
                f"{self.base_url}/v1/cost/usage",
                params={"hours": hours},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    # ── Health ────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        with self._client() as client:
            r = client.get(f"{self.base_url}/api/v1/health", headers=self._headers)
            r.raise_for_status()
            return r.json()

    # ── Guardrails Check ─────────────────────────────────────

    def guardrails_check(self, prompt: str) -> dict[str, Any]:
        with self._client() as client:
            r = client.post(
                f"{self.base_url}/v1/guardrails/check",
                params={"prompt": prompt},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
