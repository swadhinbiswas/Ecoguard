"""Cost tracking: per-model pricing, token counting, and cost analytics."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.inference import InferenceLog

# ── Pricing Configuration ─────────────────────────────────────


@dataclass
class ModelPricing:
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0


# Default pricing table (USD per 1k tokens)
_DEFAULT_PRICING: dict[str, ModelPricing] = {
    "llama-3-8b": ModelPricing(input_cost_per_1k=0.00006, output_cost_per_1k=0.00006),
    "llama-3-70b": ModelPricing(input_cost_per_1k=0.00059, output_cost_per_1k=0.00079),
    "gpt-3.5-turbo": ModelPricing(input_cost_per_1k=0.0005, output_cost_per_1k=0.0015),
    "gpt-4": ModelPricing(input_cost_per_1k=0.03, output_cost_per_1k=0.06),
    "gpt-4o": ModelPricing(input_cost_per_1k=0.0025, output_cost_per_1k=0.01),
    "claude-3-sonnet": ModelPricing(input_cost_per_1k=0.003, output_cost_per_1k=0.015),
    "claude-3-haiku": ModelPricing(
        input_cost_per_1k=0.00025, output_cost_per_1k=0.00125
    ),
    "default": ModelPricing(input_cost_per_1k=0.0, output_cost_per_1k=0.0),
}


class CostEstimate(BaseModel):
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    model: str


class CostSummary(BaseModel):
    period_hours: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost: float
    models: list[dict]


class CostTracker:
    _custom_pricing: dict[str, ModelPricing] = {}

    @classmethod
    def get_pricing(cls, model: str) -> ModelPricing:
        if model in cls._custom_pricing:
            return cls._custom_pricing[model]
        model_lower = model.lower()
        for key, pricing in _DEFAULT_PRICING.items():
            if key in model_lower or model_lower in key:
                return pricing
        return _DEFAULT_PRICING["default"]

    @classmethod
    def set_pricing(cls, model: str, input_per_1k: float, output_per_1k: float) -> None:
        cls._custom_pricing[model] = ModelPricing(
            input_cost_per_1k=input_per_1k, output_cost_per_1k=output_per_1k
        )

    @classmethod
    def estimate_cost(
        cls, input_tokens: int, output_tokens: int, model: str = "default"
    ) -> CostEstimate:
        pricing = cls.get_pricing(model)
        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k
        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=round(input_cost, 6),
            output_cost=round(output_cost, 6),
            total_cost=round(input_cost + output_cost, 6),
            model=model,
        )

    @classmethod
    async def get_usage_summary(
        cls,
        db: AsyncSession,
        hours: int = 24,
    ) -> CostSummary:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(InferenceLog).where(InferenceLog.timestamp >= cutoff)
        )
        logs = result.scalars().all()

        total_requests = len(logs)
        total_tokens = sum(log.token_count for log in logs)
        estimated_cost = sum(
            (log.token_count / 1000) * 0.0015
            for log in logs
            if log.token_count and log.timestamp
        )

        return CostSummary(
            period_hours=hours,
            total_requests=total_requests,
            total_input_tokens=total_tokens // 2,
            total_output_tokens=total_tokens // 2,
            estimated_cost=round(estimated_cost, 4),
            models=[],
        )


cost_tracker = CostTracker()
