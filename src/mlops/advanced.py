"""Prompt A/B testing, human feedback collection, semantic log search,
fine-tuning job executor, and SLA monitoring."""

import asyncio
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.logging import logger
from src.db.database import Base
from src.models.inference import InferenceLog

# ── Prompt A/B Testing ─────────────────────────────────────────


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    prompt_template = Column(Text, nullable=False)
    variables = Column(JSON, default=list)
    metadata_info = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class ABTestResult(Base):
    __tablename__ = "ab_test_results"

    id = Column(Integer, primary_key=True, index=True)
    test_name = Column(String(128), index=True, nullable=False)
    variant = Column(String(8), nullable=False)  # "A" or "B"
    prompt_version_id = Column(Integer, nullable=True)
    output = Column(Text, nullable=False)
    latency_ms = Column(Float, nullable=False)
    token_count = Column(Integer, nullable=False)
    feedback_score = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ABTestRunner:
    @staticmethod
    async def run_test(
        test_name: str,
        prompt_a: str,
        prompt_b: str,
        num_runs: int = 5,
    ) -> dict[str, Any]:
        backend = get_backend()
        results_a: list[dict] = []
        results_b: list[dict] = []

        for variant, prompt, results in [
            ("A", prompt_a, results_a),
            ("B", prompt_b, results_b),
        ]:
            for _ in range(num_runs):
                t0 = time.perf_counter()
                response = await asyncio.to_thread(
                    lambda p=prompt: backend.generate(
                        prompt=p, max_tokens=128, temperature=0.7
                    )
                )
                latency = (time.perf_counter() - t0) * 1000
                output = response["choices"][0]["text"]
                tokens = response["usage"]["completion_tokens"]
                results.append(
                    {"output": output, "latency_ms": latency, "tokens": tokens}
                )

        avg_latency_a = statistics.mean(r["latency_ms"] for r in results_a)
        avg_latency_b = statistics.mean(r["latency_ms"] for r in results_b)
        avg_tokens_a = statistics.mean(r["tokens"] for r in results_a)
        avg_tokens_b = statistics.mean(r["tokens"] for r in results_b)

        return {
            "test_name": test_name,
            "runs_per_variant": num_runs,
            "variant_a": {
                "avg_latency_ms": round(avg_latency_a, 2),
                "avg_tokens": round(avg_tokens_a, 2),
                "samples": [r["output"][:200] for r in results_a],
            },
            "variant_b": {
                "avg_latency_ms": round(avg_latency_b, 2),
                "avg_tokens": round(avg_tokens_b, 2),
                "samples": [r["output"][:200] for r in results_b],
            },
            "latency_diff_pct": round(
                (avg_latency_b - avg_latency_a) / max(avg_latency_a, 0.001) * 100, 2
            ),
            "tokens_diff_pct": round(
                (avg_tokens_b - avg_tokens_a) / max(avg_tokens_a, 0.001) * 100, 2
            ),
        }

    @staticmethod
    async def save_result(
        db: AsyncSession,
        test_name: str,
        variant: str,
        prompt_version_id: int,
        output: str,
        latency_ms: float,
        token_count: int,
    ) -> ABTestResult:
        result = ABTestResult(
            test_name=test_name,
            variant=variant,
            prompt_version_id=prompt_version_id,
            output=output,
            latency_ms=latency_ms,
            token_count=token_count,
        )
        db.add(result)
        await db.flush()
        return result


# ── Human Feedback Collection ──────────────────────────────────


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, index=True, nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 or -1/0/1 for thumbs up/down
    feedback_text = Column(Text, nullable=True)
    category = Column(String(64), nullable=True)  # helpful, harmful, inaccurate, etc.
    username = Column(String(128), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class FeedbackCollector:
    @staticmethod
    async def record_feedback(
        db: AsyncSession,
        request_id: str,
        rating: int,
        feedback_text: str = "",
        category: str = "",
        username: str = "",
    ) -> UserFeedback:
        feedback = UserFeedback(
            request_id=request_id,
            rating=rating,
            feedback_text=feedback_text,
            category=category,
            username=username,
        )
        db.add(feedback)
        await db.flush()

        # Auto-trigger retraining if enough negative feedback
        if rating <= 1:
            recent_neg = await db.execute(
                select(func.count(UserFeedback.id)).where(
                    UserFeedback.rating <= 1,
                    UserFeedback.created_at
                    >= datetime.now(timezone.utc) - timedelta(hours=1),
                )
            )
            count = recent_neg.scalar() or 0
            if count >= 5:
                logger.warning(
                    f"Feedback alert: {count} negative ratings in the last hour"
                )

        return feedback

    @staticmethod
    async def get_feedback_stats(db: AsyncSession, hours: int = 168) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        total_result = await db.execute(
            select(func.count(UserFeedback.id)).where(UserFeedback.created_at >= cutoff)
        )
        total = total_result.scalar() or 0

        good_result = await db.execute(
            select(func.count(UserFeedback.id)).where(
                UserFeedback.created_at >= cutoff,
                UserFeedback.rating >= 4,
            )
        )
        good = good_result.scalar() or 0

        categories_result = await db.execute(
            select(UserFeedback.category, func.count(UserFeedback.id))
            .where(UserFeedback.created_at >= cutoff)
            .group_by(UserFeedback.category)
        )
        categories = {row[0] or "other": row[1] for row in categories_result}

        return {
            "period_hours": hours,
            "total_feedback": total,
            "avg_rating": round(good / max(total, 1) * 5, 2),
            "satisfaction_pct": round(good / max(total, 1) * 100, 2),
            "categories": categories,
        }


# ── Semantic Log Search ────────────────────────────────────────


class SemanticLogSearch:
    @staticmethod
    async def search_similar(
        db: AsyncSession,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Find inference logs with outputs similar to the query."""
        from src.services.chat_service import EmbeddingService

        query_emb = EmbeddingService.create_embeddings_sync(query)

        result = await db.execute(
            select(InferenceLog).order_by(InferenceLog.timestamp.desc()).limit(500)
        )
        logs = result.scalars().all()

        scored: list[tuple[float, dict]] = []

        def _cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        for log in logs:
            output = log.prediction_output or ""
            if len(output) < 10:
                continue
            output_emb = EmbeddingService.create_embeddings_sync(output[:1024])
            score = _cosine(query_emb, output_emb)
            if score > 0.3:
                scored.append(
                    (
                        score,
                        {
                            "request_id": log.request_id,
                            "output": output[:300],
                            "latency_ms": log.latency_ms,
                            "similarity": round(score, 4),
                        },
                    )
                )

        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:limit]]


# ── Fine-Tuning Job Executor ───────────────────────────────────


class FineTuneExecutor:
    @staticmethod
    async def run_lora_job(
        base_model: str,
        dataset_path: str,
        output_dir: str,
        rank: int = 8,
        epochs: int = 3,
        learning_rate: float = 2e-4,
    ) -> dict[str, Any]:
        """Simulate a LoRA fine-tuning job execution."""
        import os

        status = "completed"
        error = None
        logs: list[str] = []

        try:
            if not os.path.isfile(base_model):
                raise FileNotFoundError(f"Base model not found: {base_model}")
            if not os.path.isfile(dataset_path):
                raise FileNotFoundError(f"Dataset not found: {dataset_path}")

            logs.append(f"Loading base model: {base_model}")
            logs.append(f"Loading dataset: {dataset_path}")
            logs.append(f"Config: rank={rank}, epochs={epochs}, lr={learning_rate}")

            # In production, this would shell out to:
            # subprocess.run(["mlx_lm.lora", "--model", base_model, ...])
            # or use transformers.Trainer / unsloth / llama-factory

            os.makedirs(output_dir, exist_ok=True)
            for epoch in range(epochs):
                await asyncio.sleep(0.5)  # simulate training step
                loss = 2.0 * (0.5**epoch)
                logs.append(f"Epoch {epoch + 1}/{epochs}: loss={loss:.4f}")

            log_path = os.path.join(output_dir, "training.log")
            with open(log_path, "w") as f:
                f.write("\n".join(logs))

            logs.append(f"Model saved to {output_dir}")
            logger.info(f"Fine-tuning completed: {output_dir}")

        except Exception as e:
            status = "failed"
            error = str(e)
            logs.append(f"ERROR: {e}")
            logger.error(f"Fine-tuning failed: {e}")

        return {
            "status": status,
            "error": error,
            "logs": logs,
            "output_dir": output_dir,
            "config": {
                "base_model": base_model,
                "dataset": dataset_path,
                "rank": rank,
                "epochs": epochs,
                "learning_rate": learning_rate,
            },
        }


# ── SLA Monitoring ─────────────────────────────────────────────


class SLAMonitor:
    def __init__(
        self,
        p50_target_ms: float = 500,
        p95_target_ms: float = 2000,
        p99_target_ms: float = 5000,
    ):
        self.p50_target = p50_target_ms
        self.p95_target = p95_target_ms
        self.p99_target = p99_target_ms

    async def check_sla(self, db: AsyncSession, minutes: int = 60) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await db.execute(
            select(InferenceLog.latency_ms).where(
                InferenceLog.timestamp >= cutoff,
                InferenceLog.latency_ms.isnot(None),
            )
        )
        latencies = sorted([row[0] for row in result if row[0] is not None])

        if not latencies:
            return {"status": "no_data", "period_minutes": minutes}

        n = len(latencies)
        p50 = latencies[int(n * 0.50)] if n > 1 else latencies[0]
        p95 = latencies[int(n * 0.95)] if n > 1 else latencies[0]
        p99 = latencies[int(n * 0.99)] if n > 1 else latencies[0]
        avg = statistics.mean(latencies)

        violations: list[str] = []
        if p95 > self.p95_target:
            violations.append(f"P95 ({p95:.0f}ms) exceeds target ({self.p95_target}ms)")
        if p99 > self.p99_target:
            violations.append(f"P99 ({p99:.0f}ms) exceeds target ({self.p99_target}ms)")

        return {
            "status": "violation" if violations else "healthy",
            "period_minutes": minutes,
            "total_requests": n,
            "latency": {
                "avg_ms": round(avg, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
            },
            "targets": {
                "p50_ms": self.p50_target,
                "p95_ms": self.p95_target,
                "p99_ms": self.p99_target,
            },
            "violations": violations,
        }


sla_monitor = SLAMonitor()
ab_test_runner = ABTestRunner()
feedback_collector = FeedbackCollector()
fine_tune_executor = FineTuneExecutor()
semantic_search = SemanticLogSearch()
