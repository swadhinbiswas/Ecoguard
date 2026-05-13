import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

import orjson

from src.core.config import settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry, default=str)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("eco-guard")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if settings.environment == "production":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
        handler.setLevel(getattr(logging, settings.log_level, logging.INFO))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    return logger


logger = setup_logging()


def log_inference(metadata: dict[str, Any]) -> None:
    metadata_for_log = {k: v for k, v in metadata.items() if k != "prompt"}
    logger.info(f"INFERENCE_METADATA: {orjson.dumps(metadata_for_log).decode('utf-8')}")
