import httpx
import json
from typing import Optional
from src.core.config import settings
from src.core.logging import logger


class WebhookAlerter:
    def __init__(self, webhook_url: str | None = None):
        self._url = webhook_url

    async def send_drift_alert(
        self,
        drift_score: float,
        latency_ms: float,
        token_count: int,
        threshold: float = 0.8,
    ) -> None:
        if not self._url:
            return
        if drift_score < threshold:
            return

        payload = {
            "text": (
                f"*Eco-Guard Drift Alert*\n"
                f"Drift Score: `{drift_score:.4f}` (threshold: {threshold})\n"
                f"Latency: `{latency_ms:.2f}ms`\n"
                f"Tokens: `{token_count}`\n"
                f"Environment: `{settings.environment}`"
            )
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._url, json=payload)
                if resp.status_code >= 400:
                    logger.warning(f"Webhook alert failed: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Webhook alert delivery failed: {e}")

    async def send_health_alert(self, message: str, severity: str = "warning") -> None:
        if not self._url:
            return

        emoji = "🔴" if severity == "critical" else "🟡"
        payload = {
            "text": (
                f"{emoji} *Eco-Guard Health Alert* [{severity.upper()}]\n"
                f"{message}\n"
                f"Environment: `{settings.environment}`"
            )
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self._url, json=payload)
        except Exception as e:
            logger.error(f"Health alert delivery failed: {e}")


_alerter: Optional[WebhookAlerter] = None


def get_alerter(webhook_url: str | None = None) -> WebhookAlerter:
    global _alerter
    if _alerter is None:
        _alerter = WebhookAlerter(webhook_url=webhook_url)
    return _alerter
