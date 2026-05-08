import hashlib
import time
import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from src.core.config import settings
from src.core.logging import logger


class APIUsageTracker:
    @staticmethod
    async def track_request(
        db: AsyncSession,
        api_key_hash: str,
        endpoint: str,
        latency_ms: float,
        token_count: int,
        status_code: int,
    ) -> None:
        pass

    @staticmethod
    async def get_usage(
        db: AsyncSession,
        api_key_hash: str | None = None,
        hours: int = 24,
    ) -> dict:
        from datetime import datetime, timezone, timedelta
        from src.models.inference import InferenceLog

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(
                func.count(InferenceLog.id).label("total"),
                func.sum(InferenceLog.token_count).label("tokens"),
                func.avg(InferenceLog.latency_ms).label("avg_lat"),
            ).where(InferenceLog.timestamp >= cutoff)
        )
        row = result.one_or_none()
        return {
            "period_hours": hours,
            "total_requests": int(row.total) if row and row.total else 0,
            "total_tokens": int(row.tokens) if row and row.tokens else 0,
            "avg_latency_ms": round(float(row.avg_lat), 2)
            if row and row.avg_lat
            else 0,
            "rate_limit": {
                "max_requests": settings.rate_limit_requests,
                "window_seconds": settings.rate_limit_window_seconds,
            },
        }

    @staticmethod
    async def get_usage_by_minute(
        db: AsyncSession,
        hours: int = 6,
    ) -> list[dict]:
        from datetime import datetime, timezone, timedelta
        from src.models.inference import InferenceLog
        from sqlalchemy import text

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(
                func.date_trunc("minute", InferenceLog.timestamp).label("minute"),
                func.count(InferenceLog.id).label("count"),
                func.avg(InferenceLog.latency_ms).label("avg_lat"),
            )
            .where(InferenceLog.timestamp >= cutoff)
            .group_by(text("1"))
            .order_by(text("1"))
            .limit(360)
        )
        return [
            {
                "minute": row.minute.isoformat() if row.minute else None,
                "count": row.count,
                "avg_latency_ms": round(float(row.avg_lat), 2) if row.avg_lat else 0,
            }
            for row in result.all()
        ]
