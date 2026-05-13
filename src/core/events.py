"""Webhook event system — subscribe to events, deliver via HTTP."""

import asyncio
import json
import time
from typing import Any, Callable

import httpx

from src.core.config import settings
from src.core.logging import logger


class EventType:
    MODEL_DEPLOYED = "model.deployed"
    MODEL_ROLLED_BACK = "model.rolled_back"
    DRIFT_DETECTED = "drift.detected"
    DRIFT_THRESHOLD_EXCEEDED = "drift.threshold_exceeded"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    RETRAINING_TRIGGERED = "retraining.triggered"
    QUOTA_EXCEEDED = "quota.exceeded"
    HEALTH_DEGRADED = "health.degraded"


_event_handlers: dict[str, list[Callable]] = {}
_webhook_urls: list[str] = []


def register_handler(event_type: str, handler: Callable) -> None:
    if event_type not in _event_handlers:
        _event_handlers[event_type] = []
    _event_handlers[event_type].append(handler)


def register_webhook(url: str) -> None:
    if url not in _webhook_urls:
        _webhook_urls.append(url)
        logger.info(f"Webhook registered: {url}")


def deregister_webhook(url: str) -> None:
    if url in _webhook_urls:
        _webhook_urls.remove(url)


async def emit(event_type: str, data: dict[str, Any]) -> None:
    event = {
        "event": event_type,
        "timestamp": time.time(),
        "data": data,
    }

    for handler in _event_handlers.get(event_type, []):
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Event handler error ({event_type}): {e}")

    if _webhook_urls:
        await _deliver_webhooks(event)


async def _deliver_webhooks(event: dict[str, Any]) -> None:
    payload = json.dumps(event).encode()
    headers = {
        "Content-Type": "application/json",
        "X-EcoGuard-Event": event["event"],
    }

    async with httpx.AsyncClient(timeout=10) as client:
        for url in _webhook_urls:
            try:
                await client.post(url, content=payload, headers=headers)
            except Exception as e:
                logger.warning(f"Webhook delivery failed ({url}): {e}")


def setup_default_webhooks() -> None:
    if settings.alerting_webhook_url:
        register_webhook(settings.alerting_webhook_url)
