from src.core.backend import get_backend
from src.core.config import settings
from src.core.logging import logger


class ModelRouter:
    def __init__(self):
        self._routes: dict[str, str] = {}
        self._default: str = settings.model_path

    def add_rule(self, pattern: str, model_path: str) -> None:
        self._routes[pattern.lower()] = model_path

    def remove_rule(self, pattern: str) -> None:
        self._routes.pop(pattern.lower(), None)

    def get_route(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for p, mp in sorted(self._routes.items(), key=lambda x: -len(x[0])):
            if p in prompt_lower:
                return mp
        return self._default

    def resolve(self, prompt: str) -> str:
        target = self.get_route(prompt)
        current = get_backend().info.get("path")
        if target != current:
            get_backend().load(target)
        return target

    @property
    def rules(self) -> dict[str, str]:
        return dict(self._routes)


model_router = ModelRouter()
