"""GitOps-native YAML configuration with hot-reload."""

import asyncio
import os
from typing import Any, Optional

import yaml

from src.core.logging import logger


class GitOpsConfig:
    _config: dict[str, Any] = {}
    _watcher_task: Optional[asyncio.Task] = None
    _callbacks: list = []

    @classmethod
    def load(cls, path: str = "ecoguard.yaml") -> dict[str, Any]:
        if not os.path.isfile(path):
            logger.debug(f"GitOps config not found: {path}")
            return {}

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            cls._config = data
            logger.info(f"GitOps config loaded: {path}")
            cls._fire_callbacks()
            return data
        except Exception as e:
            logger.error(f"Failed to load GitOps config: {e}")
            return {}

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = cls._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    @classmethod
    def on_change(cls, callback) -> None:
        cls._callbacks.append(callback)

    @classmethod
    def _fire_callbacks(cls) -> None:
        for cb in cls._callbacks:
            try:
                cb(cls._config)
            except Exception as e:
                logger.error(f"GitOps callback error: {e}")

    @classmethod
    async def watch(cls, path: str = "ecoguard.yaml", interval: int = 10) -> None:
        logger.info(f"GitOps watcher started: {path} (interval={interval}s)")

        last_mtime: Optional[float] = None
        cls.load(path)

        while True:
            await asyncio.sleep(interval)
            try:
                if not os.path.isfile(path):
                    continue
                mtime = os.path.getmtime(path)
                if last_mtime is not None and mtime != last_mtime:
                    logger.info(f"GitOps config changed, reloading: {path}")
                    cls.load(path)
                last_mtime = mtime
            except Exception as e:
                logger.error(f"GitOps watch error: {e}")

    @classmethod
    def apply_routes(cls, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or cls._config
        routes = cfg.get("routes", {})
        if not routes:
            return

        from src.core.router import model_router

        for pattern, model_path in routes.items():
            model_router.add_rule(pattern, model_path)
        logger.info(f"Applied {len(routes)} router rules from GitOps config")

    @classmethod
    def apply_api_keys(cls, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or cls._config
        keys = cfg.get("api_keys", [])
        if not keys:
            return

        from src.core.auth import get_api_key_store

        store = get_api_key_store()
        for key in keys:
            store.add_key(key)
        logger.info(f"Applied {len(keys)} API keys from GitOps config")

    @classmethod
    def apply_models(cls, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or cls._config
        models = cfg.get("models", {})
        if not models:
            return

        for model_name, model_config in models.items():
            from src.services.cost_tracker import CostTracker

            CostTracker.set_pricing(
                model=model_name,
                input_per_1k=model_config.get("input_cost_per_1k", 0.0),
                output_per_1k=model_config.get("output_cost_per_1k", 0.0),
            )
        logger.info(f"Applied pricing for {len(models)} models from GitOps config")

    @classmethod
    def apply_rate_limits(cls, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or cls._config
        rate_limits = cfg.get("rate_limits", {})
        if not rate_limits:
            return
        logger.info(
            f"Rate limits from GitOps: {rate_limits.get('requests', 'default')}/{rate_limits.get('window_seconds', 'default')}s"
        )

    @classmethod
    def apply_guardrails(cls, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or cls._config
        guardrails = cfg.get("guardrails", {})
        if not guardrails:
            return

        from src.core.guardrails import get_guardrails

        pipeline = get_guardrails()

        enabled = guardrails.get("enabled", [])
        if enabled:
            for name in enabled:
                if name == "pii":
                    from src.core.guardrails import PIIGuardrail

                    pipeline.add_guardrail(PIIGuardrail())
                elif name == "injection":
                    from src.core.guardrails import PromptInjectionGuardrail

                    pipeline.add_guardrail(PromptInjectionGuardrail())
                elif name == "content_safety":
                    from src.core.guardrails import ContentSafetyGuardrail

                    pipeline.add_guardrail(ContentSafetyGuardrail())

            logger.info(f"Guardrails from GitOps: active={pipeline.active_guardrails}")


gitops = GitOpsConfig()

# Register callbacks
GitOpsConfig.on_change(GitOpsConfig.apply_routes)
GitOpsConfig.on_change(GitOpsConfig.apply_api_keys)
GitOpsConfig.on_change(GitOpsConfig.apply_models)
GitOpsConfig.on_change(GitOpsConfig.apply_guardrails)
GitOpsConfig.on_change(GitOpsConfig.apply_rate_limits)
