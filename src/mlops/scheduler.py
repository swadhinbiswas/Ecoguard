import asyncio
from datetime import datetime, timezone

from src.core.config import settings
from src.core.logging import logger
from src.db.database import get_session_local
from src.mlops.pipeline import DriftPipeline


class Scheduler:
    def __init__(self):
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._tasks.append(asyncio.create_task(self._drift_check_loop()))
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        logger.info("Scheduler started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Scheduler stopped")

    async def _drift_check_loop(self) -> None:
        await asyncio.sleep(60)
        while self._running:
            try:
                async with get_session_local()() as db:
                    from src.services.drift_detector import drift_detector

                    if (
                        len(drift_detector._latency_history)
                        >= settings.drift_min_samples
                    ):
                        import numpy as np

                        recent = drift_detector._latency_history[-10:]
                        mean_lat = np.mean(recent)
                        std_lat = np.std(recent) + 1e-6
                        drift = min(1.0, abs(recent[-1] - mean_lat) / std_lat / 10)

                        if drift >= settings.drift_alert_threshold:
                            await DriftPipeline.check_and_trigger(
                                db=db,
                                drift_score=float(drift),
                            )
                    await db.commit()
            except Exception as e:
                logger.error(f"Scheduled drift check error: {e}")
            await asyncio.sleep(300)  # Every 5 minutes

    async def _cleanup_loop(self) -> None:
        await asyncio.sleep(120)
        while self._running:
            try:
                async with get_session_local()() as db:
                    from datetime import timedelta

                    from sqlalchemy import delete

                    from src.mlops.models import RetrainingTrigger

                    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
                    await db.execute(
                        delete(RetrainingTrigger).where(
                            RetrainingTrigger.acknowledged,
                            RetrainingTrigger.triggered_at < cutoff,
                        )
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Scheduled cleanup error: {e}")
            await asyncio.sleep(86400)  # Daily


scheduler = Scheduler()
