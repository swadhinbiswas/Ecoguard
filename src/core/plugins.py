"""Plugin system — custom backends, guardrails, evaluators, and middleware."""

import importlib
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.core.config import settings
from src.core.logging import logger

_registered_plugins: dict[str, dict[str, Any]] = {
    "backends": {},
    "guardrails": {},
    "evaluators": {},
    "middleware": {},
}


class PluginBase(ABC):
    name: str = ""

    @abstractmethod
    def validate(self) -> bool: ...


class BackendPlugin(PluginBase):
    @abstractmethod
    def load(self, model_path: str) -> None: ...
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> dict: ...
    @abstractmethod
    def is_loaded(self) -> bool: ...
    @abstractmethod
    def unload(self) -> None: ...


class GuardrailPlugin(PluginBase):
    @abstractmethod
    async def check(self, prompt: str, metadata: dict) -> dict: ...


class EvaluatorPlugin(PluginBase):
    @abstractmethod
    async def evaluate(self, model_output: str, expected: str) -> dict: ...


def register_plugin(category: str, plugin: Any) -> None:
    name = getattr(plugin, "name", plugin.__class__.__name__)
    if category not in _registered_plugins:
        raise ValueError(f"Unknown plugin category: {category}")

    _registered_plugins[category][name] = plugin
    logger.info(f"Plugin registered: {category}/{name}")


def get_plugin(category: str, name: str) -> Optional[Any]:
    return _registered_plugins.get(category, {}).get(name)


def list_plugins(category: str) -> dict[str, Any]:
    return _registered_plugins.get(category, {})


def load_plugin_from_path(category: str, module_path: str, class_name: str) -> None:
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls()
        if isinstance(instance, PluginBase):
            register_plugin(category, instance)
        else:
            logger.warning(f"Plugin {class_name} does not implement PluginBase")
    except Exception as e:
        logger.error(f"Failed to load plugin {module_path}.{class_name}: {e}")


def load_plugins_from_config() -> None:
    plugins_config = getattr(settings, "plugins", {})
    if not plugins_config:
        return

    for category, plugins in plugins_config.items():
        if category not in _registered_plugins:
            continue
        for plugin_def in plugins:
            load_plugin_from_path(
                category, plugin_def.get("module", ""), plugin_def.get("class", "")
            )
