import os
import threading
from typing import Optional, TYPE_CHECKING
from src.core.config import settings
from src.core.logging import logger
from src.core.exceptions import ModelNotFoundError, ModelNotLoadedError
from src.monitoring.metrics import set_model_loaded

if TYPE_CHECKING:
    from llama_cpp import Llama


class ModelLoader:
    _instance: Optional["ModelLoader"] = None
    _lock = threading.Lock()
    _model: Optional["Llama"] = None
    _model_path: Optional[str] = None

    def __new__(cls) -> "ModelLoader":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelLoader, cls).__new__(cls)
            return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_info(self) -> dict:
        if self._model is None:
            return {"loaded": False, "path": None}
        return {"loaded": True, "path": self._model_path}

    def load_model(self, model_path: str | None = None) -> None:
        path = model_path or settings.model_path
        if self._model is not None and self._model_path == path:
            return

        with self._lock:
            if self._model is not None and self._model_path == path:
                return

            if self._model is not None:
                logger.info(f"Switching model from {self._model_path} to {path}")
                self._model = None
                set_model_loaded(False)

            logger.info(f"Loading model from {path}...")
            if not os.path.exists(path):
                logger.warning(f"Model file not found at {path}")
                raise ModelNotFoundError(path)

            try:
                from llama_cpp import Llama

                self._model = Llama(
                    model_path=path,
                    n_ctx=settings.model_n_ctx,
                    n_threads=settings.model_n_threads,
                    n_batch=settings.model_n_batch,
                    verbose=False,
                )
                self._model_path = path
                set_model_loaded(True)
                logger.info(f"Model loaded successfully: {path}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                set_model_loaded(False)
                raise

    def get_model(self) -> "Llama":
        if self._model is None:
            raise ModelNotLoadedError()
        return self._model

    def unload_model(self) -> None:
        with self._lock:
            if self._model is not None:
                self._model = None
                self._model_path = None
                set_model_loaded(False)
                logger.info("Model unloaded")


class ModelRegistry:
    _models: dict[str, dict] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, name: str, path: str, metadata: dict | None = None) -> None:
        with cls._lock:
            cls._models[name] = {"path": path, "metadata": metadata or {}}

    @classmethod
    def get(cls, name: str) -> dict | None:
        return cls._models.get(name)

    @classmethod
    def list_models(cls) -> dict[str, dict]:
        with cls._lock:
            return dict(cls._models)

    @classmethod
    def remove(cls, name: str) -> bool:
        with cls._lock:
            if name in cls._models:
                del cls._models[name]
                return True
            return False


model_loader = ModelLoader()
