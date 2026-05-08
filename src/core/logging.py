import logging
import sys
from typing import Any
import orjson
from src.core.config import settings


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("eco-guard")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    return logger


logger = setup_logging()


def log_inference(metadata: dict[str, Any]) -> None:
    logger.info(f"INFERENCE_METADATA: {orjson.dumps(metadata).decode('utf-8')}")
