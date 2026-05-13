"""Budget caps, priority request queue, cross-provider load balancer, auto-scaling rules."""

import asyncio
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import logger
from src.db.database import Base
from src.services.cost_tracker import cost_tracker

# ── Budget Caps ────────────────────────────────────────────────


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, index=True, nullable=False)
    period = Column(String(16), default="monthly")  # daily, weekly, monthly
    cap_amount_usd = Column(Float, nullable=False)
    current_spend = Column(Float, default=0.0)
    alert_threshold_pct = Column(Float, default=80.0)  # alert at 80%
    reset_at = Column(DateTime(timezone=True), nullable=False)
    last_alert_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)


class BudgetManager:
    @staticmethod
    async def check_budget(
        db: AsyncSession, workspace_id: int, estimated_cost: float
    ) -> tuple[bool, str]:
        """Returns (allowed, message). Blocks if over cap."""
        result = await db.execute(
            select(Budget).where(Budget.workspace_id == workspace_id, Budget.is_active)
        )
        budget = result.scalar_one_or_none()
        if not budget:
            return True, ""

        now = datetime.now(timezone.utc)
        if now >= budget.reset_at:
            budget.current_spend = 0
            period_days = {"daily": 1, "weekly": 7, "monthly": 30}
            budget.reset_at = now + timedelta(days=period_days.get(budget.period, 30))

        new_spend = budget.current_spend + estimated_cost
        if new_spend > budget.cap_amount_usd:
            return (
                False,
                f"Budget exceeded: ${budget.current_spend:.4f} / ${budget.cap_amount_usd:.4f}",
            )

        budget.current_spend = new_spend

        # Alert at threshold
        pct = (budget.current_spend / budget.cap_amount_usd) * 100
        if pct >= budget.alert_threshold_pct:
            cooldown_ok = not budget.last_alert_at or (
                now - budget.last_alert_at
            ) > timedelta(hours=1)
            if cooldown_ok:
                budget.last_alert_at = now
                logger.warning(
                    f"Budget alert: {pct:.0f}% used (${budget.current_spend:.4f}/${budget.cap_amount_usd:.4f})"
                )

        await db.flush()
        return True, ""

    @staticmethod
    async def set_budget(
        db: AsyncSession,
        workspace_id: int,
        cap_amount: float,
        period: str = "monthly",
        alert_pct: float = 80.0,
    ) -> Budget:
        result = await db.execute(
            select(Budget).where(Budget.workspace_id == workspace_id)
        )
        budget = result.scalar_one_or_none()

        period_days = {"daily": 1, "weekly": 7, "monthly": 30}
        reset_at = datetime.now(timezone.utc) + timedelta(
            days=period_days.get(period, 30)
        )

        if budget:
            budget.cap_amount_usd = cap_amount
            budget.alert_threshold_pct = alert_pct
            budget.period = period
            budget.reset_at = reset_at
            budget.current_spend = 0
            budget.is_active = True
        else:
            budget = Budget(
                workspace_id=workspace_id,
                cap_amount_usd=cap_amount,
                period=period,
                alert_threshold_pct=alert_pct,
                reset_at=reset_at,
            )
            db.add(budget)

        await db.flush()
        return budget

    @staticmethod
    async def get_budget_status(db: AsyncSession, workspace_id: int) -> dict:
        result = await db.execute(
            select(Budget).where(Budget.workspace_id == workspace_id)
        )
        budget = result.scalar_one_or_none()
        if not budget:
            return {"has_budget": False}

        return {
            "has_budget": True,
            "cap_amount": budget.cap_amount_usd,
            "current_spend": round(budget.current_spend, 6),
            "remaining": round(budget.cap_amount_usd - budget.current_spend, 6),
            "usage_pct": round((budget.current_spend / budget.cap_amount_usd) * 100, 2)
            if budget.cap_amount_usd > 0
            else 0,
            "period": budget.period,
            "alert_pct": budget.alert_threshold_pct,
        }


budget_manager = BudgetManager()


# ── Priority Request Queue ─────────────────────────────────────


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(order=True)
class QueuedRequest:
    priority: int = field(compare=True)
    request_id: str = field(compare=False)
    prompt: str = field(compare=False)
    max_tokens: int = field(compare=False)
    temperature: float = field(compare=False)
    enqueued_at: float = field(compare=False)


class PriorityQueue:
    def __init__(self, max_size: int = 10000):
        self._queues: dict[Priority, asyncio.Queue] = {
            Priority.HIGH: asyncio.Queue(maxsize=max_size),
            Priority.MEDIUM: asyncio.Queue(maxsize=max_size),
            Priority.LOW: asyncio.Queue(maxsize=max_size),
        }
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._queue_depth = {"high": 0, "medium": 0, "low": 0}

    async def enqueue(
        self,
        request_id: str,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.7,
        priority: Priority = Priority.MEDIUM,
    ) -> None:
        item = QueuedRequest(
            priority={"high": 0, "medium": 1, "low": 2}[priority.value],
            request_id=request_id,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            enqueued_at=time.monotonic(),
        )
        await self._queues[priority].put(item)
        self._queue_depth[priority.value] = self._queues[priority].qsize()

    async def dequeue(self) -> Optional[QueuedRequest]:
        # Check high first, then medium, then low
        for priority in [Priority.HIGH, Priority.MEDIUM, Priority.LOW]:
            try:
                item = self._queues[priority].get_nowait()
                self._queue_depth[priority.value] = self._queues[priority].qsize()
                return item
            except asyncio.QueueEmpty:
                continue
        return None

    @property
    def depth(self) -> dict:
        return {
            "high": self._queues[Priority.HIGH].qsize(),
            "medium": self._queues[Priority.MEDIUM].qsize(),
            "low": self._queues[Priority.LOW].qsize(),
            "total": sum(q.qsize() for q in self._queues.values()),
        }

    async def start_worker(self, process_func: callable, interval: float = 0.1):
        self._running = True
        while self._running:
            item = await self.dequeue()
            if item:
                try:
                    await process_func(item)
                except Exception as e:
                    logger.error(f"Queue worker error: {e}")
            await asyncio.sleep(interval)

    def stop_worker(self):
        self._running = False


priority_queue = PriorityQueue()


# ── Cross-Provider Load Balancer ───────────────────────────────


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str = ""
    model: str = "default"
    weight: float = 1.0  # routing weight
    max_concurrent: int = 100
    current_load: int = 0
    healthy: bool = True
    last_error_at: Optional[float] = None


class ProviderLoadBalancer:
    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._lock = asyncio.Lock()

    def register(self, provider: ProviderConfig) -> None:
        self._providers[provider.name] = provider
        logger.info(f"Provider registered: {provider.name} ({provider.base_url})")

    def deregister(self, name: str) -> None:
        self._providers.pop(name, None)

    async def get_best_provider(self, model: str = "") -> Optional[ProviderConfig]:
        """Returns the best provider based on: health > cost > weight > load."""
        async with self._lock:
            candidates = [
                p
                for p in self._providers.values()
                if p.healthy and p.current_load < p.max_concurrent
            ]
            if not candidates:
                # Try unhealthy ones as last resort
                candidates = [p for p in self._providers.values()]
                if not candidates:
                    return None

            # Sort by cost (cheapest first), then by weight, then by current_load
            def _sort_key(p: ProviderConfig) -> tuple:
                pricing = cost_tracker.get_pricing(model or p.model)
                cost = pricing.input_cost_per_1k + pricing.output_cost_per_1k
                return (cost, -p.weight, p.current_load)

            candidates.sort(key=_sort_key)
            best = candidates[0]
            best.current_load += 1
            return best

    def release_provider(self, name: str) -> None:
        provider = self._providers.get(name)
        if provider and provider.current_load > 0:
            provider.current_load -= 1

    def mark_unhealthy(self, name: str) -> None:
        provider = self._providers.get(name)
        if provider:
            provider.healthy = False
            provider.last_error_at = time.monotonic()
            logger.warning(f"Provider marked unhealthy: {name}")

    def mark_healthy(self, name: str) -> None:
        provider = self._providers.get(name)
        if provider:
            provider.healthy = True
            logger.info(f"Provider recovered: {name}")

    async def auto_recovery(self):
        """Periodically check unhealthy providers."""
        while True:
            now = time.monotonic()
            for name, p in list(self._providers.items()):
                if not p.healthy and p.last_error_at and (now - p.last_error_at) > 60:
                    # Try a health check
                    try:
                        import httpx

                        async with httpx.AsyncClient(timeout=5) as client:
                            r = await client.get(f"{p.base_url}/health")
                            if r.status_code == 200:
                                self.mark_healthy(name)
                    except Exception:
                        pass
            await asyncio.sleep(30)

    def get_status(self) -> dict:
        return {
            name: {
                "base_url": p.base_url,
                "model": p.model,
                "weight": p.weight,
                "healthy": p.healthy,
                "current_load": p.current_load,
                "max_concurrent": p.max_concurrent,
            }
            for name, p in self._providers.items()
        }


provider_lb = ProviderLoadBalancer()


# ── Auto-Scaling Rules ─────────────────────────────────────────


class ScalingRule(Base):
    __tablename__ = "scaling_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    metric = Column(
        String(64), nullable=False
    )  # queue_depth, avg_latency, error_rate, gpu_util
    condition = Column(String(8), nullable=False)  # gt, lt
    threshold = Column(Float, nullable=False)
    action = Column(
        String(32), nullable=False
    )  # scale_up, scale_down, preload_model, quantize
    action_value = Column(
        JSON, nullable=True
    )  # e.g., {"target_replicas": 4, "model_path": "..."}
    cooldown_minutes = Column(Integer, default=5)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, default=True)


class AutoScaler:
    _current_load: deque = deque(maxlen=100)

    @staticmethod
    def record_load(latency_ms: float):
        AutoScaler._current_load.append(latency_ms)

    @staticmethod
    def get_current_metrics() -> dict:
        loads = list(AutoScaler._current_load)
        if not loads:
            return {
                "avg_latency_ms": 0,
                "queue_depth": priority_queue.depth["total"],
                "gpu_util_pct": 0,
            }

        return {
            "avg_latency_ms": round(statistics.mean(loads), 2),
            "p95_latency_ms": round(
                sorted(loads)[int(len(loads) * 0.95)] if len(loads) > 1 else loads[0], 2
            ),
            "queue_depth": priority_queue.depth["total"],
            "gpu_util_pct": 0,  # populated by GPU monitor if available
        }

    @staticmethod
    async def evaluate_rules(db: AsyncSession) -> list[dict]:
        result = await db.execute(select(ScalingRule).where(ScalingRule.enabled))
        rules = result.scalars().all()

        metrics = AutoScaler.get_current_metrics()
        triggered: list[dict] = []
        now = datetime.now(timezone.utc)

        for rule in rules:
            if rule.last_triggered_at:
                if (now - rule.last_triggered_at) < timedelta(
                    minutes=rule.cooldown_minutes
                ):
                    continue

            value = metrics.get(rule.metric, 0)
            should_trigger = False

            if rule.condition == "gt" and value > rule.threshold:
                should_trigger = True
            elif rule.condition == "lt" and value < rule.threshold:
                should_trigger = True

            if should_trigger:
                rule.last_triggered_at = now
                triggered.append(
                    {
                        "rule": rule.name,
                        "metric": rule.metric,
                        "value": value,
                        "threshold": rule.threshold,
                        "action": rule.action,
                        "action_value": rule.action_value,
                    }
                )
                logger.info(
                    f"Auto-scale triggered: {rule.name} "
                    f"({rule.metric}={value} {rule.condition} {rule.threshold} → {rule.action})"
                )

        if triggered:
            await db.flush()
        return triggered

    @staticmethod
    async def set_rule(
        db: AsyncSession,
        name: str,
        metric: str,
        condition: str,
        threshold: float,
        action: str,
        action_value: dict | None = None,
    ) -> ScalingRule:
        rule = ScalingRule(
            name=name,
            metric=metric,
            condition=condition,
            threshold=threshold,
            action=action,
            action_value=action_value or {},
        )
        db.add(rule)
        await db.flush()
        return rule


auto_scaler = AutoScaler()
