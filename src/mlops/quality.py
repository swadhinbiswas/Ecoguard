"""Model regression detection, prompt anomaly detection, standardized benchmark suite."""

import asyncio
import hashlib
import statistics
import time
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.logging import logger
from src.db.database import Base

# ── Model Regression Detection ─────────────────────────────────


class RegressionCheck(Base):
    __tablename__ = "regression_checks"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True, nullable=False)
    baseline_model_id = Column(Integer, nullable=False)
    test_suite_name = Column(String(128), nullable=False)
    baseline_score = Column(Float, nullable=False)
    new_score = Column(Float, nullable=False)
    score_delta = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)
    max_allowed_degradation = Column(Float, default=0.05)  # 5% max drop
    checked_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    details = Column(JSON, nullable=True)


class RegressionDetector:
    def __init__(self, max_degradation: float = 0.05):
        self.max_degradation = max_degradation
        self._baselines: dict[str, dict[str, float]] = {}

    def record_baseline(
        self, model_id: int, suite_name: str, metrics: dict[str, float]
    ) -> None:
        key = f"{model_id}:{suite_name}"
        self._baselines[key] = metrics

    async def check_regression(
        self,
        db: AsyncSession,
        model_id: int,
        baseline_model_id: int,
        test_suite_name: str,
        new_metrics: dict[str, float],
    ) -> dict[str, Any]:
        baseline_key = f"{baseline_model_id}:{test_suite_name}"
        baseline = self._baselines.get(baseline_key, {})

        # Compute scores
        baseline_score = 0.0
        new_score = 0.0
        comparisons: list[dict] = []

        metrics_to_check = ["accuracy", "latency_ms", "token_efficiency", "perplexity"]
        for metric in metrics_to_check:
            base_val = baseline.get(metric, new_metrics.get(metric, 0))
            new_val = new_metrics.get(metric, 0)
            if base_val == 0:
                continue

            # For latency, lower is better (invert)
            if metric == "latency_ms" or metric == "perplexity":
                delta = (base_val - new_val) / max(base_val, 0.001)
            else:
                delta = (new_val - base_val) / max(base_val, 0.001)

            comparisons.append(
                {
                    "metric": metric,
                    "baseline": round(base_val, 4),
                    "new": round(new_val, 4),
                    "delta_pct": round(delta * 100, 2),
                    "degraded": delta < -self.max_degradation,
                }
            )

            baseline_score += 1.0 / len(metrics_to_check)
            new_score += (1.0 + delta) / len(metrics_to_check)

        score_delta = new_score - baseline_score
        passed = score_delta >= -self.max_degradation

        check = RegressionCheck(
            model_id=model_id,
            baseline_model_id=baseline_model_id,
            test_suite_name=test_suite_name,
            baseline_score=round(baseline_score, 4),
            new_score=round(new_score, 4),
            score_delta=round(score_delta, 4),
            passed=passed,
            max_allowed_degradation=self.max_degradation,
            details={"comparisons": comparisons},
        )
        db.add(check)
        await db.flush()

        if not passed:
            logger.warning(
                f"Regression detected: model={model_id} vs baseline={baseline_model_id} "
                f"(delta={score_delta:.4f}, threshold={-self.max_degradation})"
            )

        return {
            "passed": passed,
            "score_delta": round(score_delta, 4),
            "comparisons": comparisons,
            "check_id": check.id,
        }


regression_detector = RegressionDetector()


# ── Prompt Anomaly Detection ───────────────────────────────────


class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(64), index=True)
    anomaly_type = Column(
        String(32), nullable=False
    )  # spam_flood, injection_attempt, unusual_tokens, pattern_repeat
    prompt_preview = Column(Text)
    score = Column(Float)
    details = Column(JSON)
    detected_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    blocked = Column(Boolean, default=False)


class PromptAnomalyDetector:
    def __init__(self, window_seconds: int = 60, flood_threshold: int = 50):
        self.window_seconds = window_seconds
        self.flood_threshold = flood_threshold
        self._request_times: deque = deque(maxlen=1000)
        self._prompt_hashes: deque = deque(maxlen=500)

    async def check(self, request_id: str, prompt: str) -> tuple[bool, Optional[dict]]:
        """Returns (is_anomaly, anomaly_details)."""
        now = time.monotonic()

        # 1. Flood detection
        self._request_times.append(now)
        cutoff = now - self.window_seconds
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()
        recent_requests = len(self._request_times)

        if recent_requests > self.flood_threshold:
            return True, {
                "type": "spam_flood",
                "score": recent_requests / self.flood_threshold,
                "details": f"{recent_requests} requests in {self.window_seconds}s",
            }

        # 2. Repeated prompt detection
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        self._prompt_hashes.append((now, prompt_hash))

        # Count recent identical prompts
        recent_hashes = [h for t, h in self._prompt_hashes if t > cutoff]
        hash_counts = Counter(recent_hashes)
        repeats = hash_counts.get(prompt_hash, 0)

        if repeats > 10:
            return True, {
                "type": "pattern_repeat",
                "score": repeats / 10,
                "details": f"Same prompt sent {repeats} times in {self.window_seconds}s",
            }

        # 3. Unusual token count
        token_count = len(prompt.split())
        if token_count > 5000:
            return True, {
                "type": "unusual_tokens",
                "score": token_count / 5000,
                "details": f"Prompt with {token_count} tokens (threshold: 5000)",
            }

        # 4. Repeated character patterns (base64 encoded attacks, etc.)
        if len(prompt) > 100 and len(set(prompt)) < 5:
            return True, {
                "type": "pattern_repeat",
                "score": 1.0,
                "details": "Repetitive character pattern detected",
            }

        return False, None

    async def log_anomaly(
        self,
        db: AsyncSession,
        request_id: str,
        anomaly_type: str,
        prompt: str,
        score: float,
        details: dict,
        blocked: bool = True,
    ) -> AnomalyLog:
        log = AnomalyLog(
            request_id=request_id,
            anomaly_type=anomaly_type,
            prompt_preview=prompt[:500],
            score=score,
            details=details,
            blocked=blocked,
        )
        db.add(log)
        await db.flush()
        return log

    async def get_recent_anomalies(
        self, db: AsyncSession, hours: int = 24, limit: int = 50
    ) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(AnomalyLog)
            .where(AnomalyLog.detected_at >= cutoff)
            .order_by(AnomalyLog.detected_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                "id": log_entry.id,
                "type": log_entry.anomaly_type,
                "score": log_entry.score,
                "blocked": log_entry.blocked,
                "details": log_entry.details,
                "detected_at": log_entry.detected_at.isoformat()
                if log_entry.detected_at
                else None,
            }
            for log_entry in logs
        ]


anomaly_detector = PromptAnomalyDetector()


# ── Model Benchmark Suite ──────────────────────────────────────


class BenchmarkSuite:
    _STANDARD_BENCHMARKS = {
        "basic_qa": [
            {"prompt": "What is the capital of France?", "expected_contains": "Paris"},
            {"prompt": "What is 2+2?", "expected_contains": "4"},
            {
                "prompt": "Who wrote Romeo and Juliet?",
                "expected_contains": "Shakespeare",
            },
            {"prompt": "What year did World War II end?", "expected_contains": "1945"},
            {
                "prompt": "What is the chemical symbol for water?",
                "expected_contains": "H2O",
            },
        ],
        "reasoning": [
            {
                "prompt": "If a train travels 60 miles in 2 hours, what is its speed in mph?",
                "expected_contains": "30",
            },
            {
                "prompt": "A bat and ball cost $1.10 totalog_entry. The bat costs $1 more than the ballog_entry. How much is the ball?",
                "expected_contains": "0.05",
            },
            {
                "prompt": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
                "expected_contains": "5",
            },
        ],
        "code_generation": [
            {
                "prompt": "Write a Python function to check if a number is prime.",
                "expected_contains": "def",
            },
            {
                "prompt": "Write a SQL query to find duplicate emails in a users table.",
                "expected_contains": "SELECT",
            },
            {
                "prompt": "Write JavaScript code to reverse a string.",
                "expected_contains": "reverse",
            },
        ],
        "summarization": [
            {
                "prompt": "Summarize: The quick brown fox jumps over the lazy dog. This sentence contains every letter of the English alphabet at least once and is often used to test typewriters and keyboards.",
                "expected_min_tokens": 5,
            },
        ],
    }

    @classmethod
    async def run_suite(
        cls,
        suite_name: str = "basic_qa",
        model_path: str | None = None,
    ) -> dict[str, Any]:
        if suite_name not in cls._STANDARD_BENCHMARKS:
            return {"error": f"Unknown benchmark: {suite_name}"}

        test_cases = cls._STANDARD_BENCHMARKS[suite_name]
        backend = get_backend()
        results: list[dict] = []
        passed = 0
        total_latency = 0.0
        total_tokens = 0

        for case in test_cases:
            t0 = time.perf_counter()
            try:
                output = await asyncio.to_thread(
                    lambda c=case: backend.generate(
                        prompt=c["prompt"], max_tokens=64, temperature=0.0
                    )
                )
                latency = (time.perf_counter() - t0) * 1000
                output_text = output["choices"][0]["text"]
                tokens = output["usage"]["completion_tokens"]
                total_latency += latency
                total_tokens += tokens

                ok = True
                if "expected_contains" in case:
                    ok = case["expected_contains"].lower() in output_text.lower()
                elif "expected_min_tokens" in case:
                    ok = tokens >= case["expected_min_tokens"]

                if ok:
                    passed += 1

                results.append(
                    {
                        "prompt": case["prompt"][:80],
                        "output": output_text[:200],
                        "passed": ok,
                        "latency_ms": round(latency, 2),
                        "tokens": tokens,
                    }
                )
            except Exception as e:
                results.append(
                    {"prompt": case["prompt"][:80], "error": str(e), "passed": False}
                )

        total = len(test_cases)
        return {
            "benchmark": suite_name,
            "test_cases": total,
            "passed": passed,
            "score": round(passed / max(total, 1), 4),
            "avg_latency_ms": round(total_latency / max(total, 1), 2),
            "total_tokens": total_tokens,
            "results": results,
        }

    @classmethod
    async def run_all_benchmarks(cls) -> dict[str, Any]:
        suites: dict[str, dict] = {}
        for name in cls._STANDARD_BENCHMARKS:
            suites[name] = await cls.run_suite(name)

        return {
            "suites": suites,
            "overall_score": round(
                statistics.mean(s["score"] for s in suites.values()), 4
            ),
        }

    @classmethod
    def list_benchmarks(cls) -> list[str]:
        return list(cls._STANDARD_BENCHMARKS.keys())


benchmark_suite = BenchmarkSuite()
