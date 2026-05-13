"""Multi-modal support, load testing, compliance exports, model quantization,
cold start optimization, and HMAC request signing."""

import asyncio
import base64
import hashlib
import hmac
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.logging import logger
from src.models.inference import InferenceLog

# ── Multi-Modal Support ────────────────────────────────────────


class MultiModalHandler:
    """Process images alongside text for vision-capable models."""

    @staticmethod
    def encode_image(path: str) -> str:
        """Read image file and return base64 data URI."""
        import os

        if not os.path.isfile(path):
            raise FileNotFoundError(f"Image not found: {path}")

        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime_map = {
            "jpg": "jpeg",
            "jpeg": "jpeg",
            "png": "png",
            "gif": "gif",
            "webp": "webp",
            "bmp": "bmp",
        }
        mime = mime_map.get(ext, "jpeg")

        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/{mime};base64,{data}"

    @staticmethod
    def build_multimodal_prompt(
        text: str,
        images: list[str] | None = None,
    ) -> str:
        """Build a prompt that includes image descriptions for models without native vision."""
        parts = [text]
        if images:
            parts.append("\n\nThe user provided the following images:")
            for i, img in enumerate(images, 1):
                if img.startswith("data:"):
                    parts.append(f"  Image {i}: [base64-encoded {len(img)} bytes]")
                elif os.path.isfile(img):
                    parts.append(f"  Image {i}: {img} ({os.path.getsize(img)} bytes)")
                else:
                    parts.append(f"  Image {i}: {img}")
        return "\n".join(parts)

    @staticmethod
    def build_vision_messages(
        text: str,
        image_paths: list[str] | None = None,
    ) -> list[dict]:
        """Build OpenAI-compatible vision messages."""
        content: list[dict] = [{"type": "text", "text": text}]

        if image_paths:
            for path in image_paths:
                data_uri = MultiModalHandler.encode_image(path)
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri, "detail": "auto"},
                    }
                )

        return [{"role": "user", "content": content}]


# ── Load Testing Tool ──────────────────────────────────────────


class LoadTester:
    def __init__(self, base_url: str = ""):
        self.base_url = base_url

    async def run_load_test(
        self,
        endpoint: str = "/api/v1/predict",
        payload: dict | None = None,
        concurrent: int = 10,
        total_requests: int = 100,
        timeout: float = 30,
    ) -> dict[str, Any]:
        import httpx

        test_payload = payload or {
            "prompt": "Hello, how are you?",
            "max_tokens": 32,
            "temperature": 0.7,
        }

        latencies: list[float] = []
        errors: list[str] = []
        tokens_total = 0
        start_time = time.perf_counter()

        sem = asyncio.Semaphore(concurrent)

        async def _make_request(i: int):
            async with sem:
                t0 = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        url = f"{self.base_url}{endpoint}"
                        r = await client.post(url, json=test_payload)
                        if r.status_code == 200:
                            data = r.json()
                            tokens = data.get("token_count", 0) or data.get(
                                "usage", {}
                            ).get("completion_tokens", 0)
                            return (time.perf_counter() - t0) * 1000, tokens, None
                        else:
                            return (
                                (time.perf_counter() - t0) * 1000,
                                0,
                                f"HTTP {r.status_code}",
                            )
                except Exception as e:
                    return (time.perf_counter() - t0) * 1000, 0, str(e)

        tasks = [_make_request(i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks)

        for lat, tokens, err in results:
            latencies.append(lat)
            tokens_total += tokens
            if err:
                errors.append(err)

        total_time = time.perf_counter() - start_time

        if not latencies:
            return {"error": "No requests completed"}

        latencies.sort()
        n = len(latencies)

        return {
            "total_requests": total_requests,
            "concurrent": concurrent,
            "total_time_seconds": round(total_time, 2),
            "requests_per_second": round(total_requests / max(total_time, 0.001), 2),
            "errors": len(errors),
            "error_rate_pct": round(len(errors) / max(total_requests, 1) * 100, 2),
            "total_tokens": tokens_total,
            "latency_ms": {
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
                "avg": round(statistics.mean(latencies), 2),
                "p50": round(latencies[int(n * 0.50)] if n > 1 else latencies[0], 2),
                "p95": round(latencies[int(n * 0.95)] if n > 1 else latencies[0], 2),
                "p99": round(latencies[int(n * 0.99)] if n > 1 else latencies[0], 2),
            },
            "error_samples": errors[:10],
        }


load_tester = LoadTester()


# ── Compliance & Data Export ───────────────────────────────────


class ComplianceExporter:
    @staticmethod
    async def export_user_data(
        db: AsyncSession,
        username: str,
    ) -> dict[str, Any]:
        """GDPR-style data export for a user."""
        logs_result = await db.execute(
            select(InferenceLog)
            .where(InferenceLog.input_text.contains(username))
            .order_by(InferenceLog.timestamp.desc())
            .limit(1000)
        )
        logs = logs_result.scalars().all()

        from src.mlops.advanced import UserFeedback

        fb_result = await db.execute(
            select(UserFeedback).where(UserFeedback.username == username)
        )
        feedbacks = fb_result.scalars().all()

        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "username": username,
            "inference_logs": [
                {
                    "request_id": log_entry.request_id,
                    "timestamp": log_entry.timestamp.isoformat()
                    if log_entry.timestamp
                    else None,
                    "input": log_entry.input_text,
                    "output": log_entry.prediction_output,
                }
                for log_entry in logs
            ],
            "feedback": [
                {
                    "rating": f.rating,
                    "text": f.feedback_text,
                    "category": f.category,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in feedbacks
            ],
        }
        return data

    @staticmethod
    async def delete_user_data(
        db: AsyncSession,
        username: str,
    ) -> dict[str, Any]:
        """Right to deletion — anonymize user's inference logs."""
        logs_result = await db.execute(
            select(InferenceLog).where(InferenceLog.input_text.contains(username))
        )
        logs = logs_result.scalars().all()

        count = 0
        for log in logs:
            log.input_text = "[REDACTED]"
            log.prediction_output = "[REDACTED]"
            count += 1

        from src.mlops.advanced import UserFeedback

        fb_result = await db.execute(
            select(UserFeedback).where(UserFeedback.username == username)
        )
        fbs = fb_result.scalars().all()
        for fb in fbs:
            await db.delete(fb)

        await db.flush()
        return {"deleted_logs": count, "deleted_feedback": len(fbs)}

    @staticmethod
    async def enforce_retention(
        db: AsyncSession,
        max_days: int = 90,
    ) -> dict[str, Any]:
        """Automatically purge logs older than max_days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)

        result = await db.execute(
            select(InferenceLog).where(InferenceLog.timestamp < cutoff)
        )
        old_logs = result.scalars().all()

        count = 0
        for log in old_logs:
            await db.delete(log)
            count += 1

        await db.flush()
        logger.info(f"Data retention: purged {count} logs older than {max_days} days")
        return {
            "purged_logs": count,
            "retention_days": max_days,
            "cutoff": cutoff.isoformat(),
        }


# ── Model Quantization on the Fly ──────────────────────────────


class DynamicQuantizer:
    """Manage model quantization levels based on load."""

    _quantization_levels = {
        "full": {"bits": 16, "memory_factor": 1.0, "quality": 1.0},
        "q8": {"bits": 8, "memory_factor": 0.5, "quality": 0.98},
        "q4": {"bits": 4, "memory_factor": 0.25, "quality": 0.92},
    }

    _current_level: str = "full"
    _load_history: list[float] = []

    @classmethod
    def get_recommended_level(cls, current_qps: float) -> str:
        cls._load_history.append(current_qps)
        if len(cls._load_history) > 30:
            cls._load_history.pop(0)

        if not cls._load_history:
            return "full"

        avg_qps = statistics.mean(cls._load_history)
        max_available = 20  # example max QPS for full precision

        if avg_qps > max_available * 1.5:
            return "q4"  # heavy load — aggressive quantization
        elif avg_qps > max_available:
            return "q8"  # moderate load
        return "full"

    @classmethod
    async def apply_quantization(
        cls,
        level: str,
        model_path: str,
    ) -> dict[str, Any]:
        """Apply quantization level to a model (requires llama.cpp or similar)."""
        if level not in cls._quantization_levels:
            return {"error": f"Unknown quantization level: {level}"}

        config = cls._quantization_levels[level]
        cls._current_level = level

        # In production, this would shell out to llama.cpp quantize:
        # subprocess.run(["llama-quantize", model_path, output_path, level])
        # For now, log the intent
        logger.info(
            f"Quantization: switching to {level} "
            f"(bits={config['bits']}, memory={config['memory_factor']:.0%})"
        )

        return {
            "level": level,
            "bits": config["bits"],
            "memory_factor": config["memory_factor"],
            "quality": config["quality"],
            "model_path": model_path,
        }


# ── Cold Start Optimization ────────────────────────────────────


class ColdStartOptimizer:
    _warmup_cache: dict[str, Any] = {}
    _preload_queue: asyncio.Queue = asyncio.Queue()

    @staticmethod
    async def warmup_model(model_path: str, warmup_prompt: str = "Hello") -> dict:
        """Pre-warm a model by running a dummy inference."""
        backend = get_backend()
        if backend.info.get("path") != model_path:
            backend.load(model_path)

        t0 = time.perf_counter()
        result = backend.generate(prompt=warmup_prompt, max_tokens=5, temperature=0.0)
        latency_ms = (time.perf_counter() - t0) * 1000

        logger.info(f"Cold start warmup: {model_path} ({latency_ms:.0f}ms)")
        return {
            "model": model_path,
            "warmup_latency_ms": round(latency_ms, 2),
            "output": result["choices"][0]["text"],
            "success": True,
        }

    @staticmethod
    async def preload_popular_models(model_paths: list[str]) -> dict:
        """Preload a set of frequently-used models."""
        results: list[dict] = []
        for path in model_paths:
            try:
                await ColdStartOptimizer.warmup_model(path)
                results.append({"path": path, "status": "warm"})
            except Exception as e:
                results.append({"path": path, "status": "failed", "error": str(e)})

        return {"preloaded": len(model_paths), "results": results}

    @staticmethod
    async def predict_load(db: AsyncSession, lookback_hours: int = 24) -> dict:
        """Predict upcoming load based on historical usage patterns."""
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=lookback_hours)

        result = await db.execute(
            select(
                func.count(InferenceLog.id).label("total"),
                func.avg(InferenceLog.latency_ms).label("avg_latency"),
                func.avg(InferenceLog.token_count).label("avg_tokens"),
            ).where(InferenceLog.timestamp >= cutoff)
        )
        row = result.one_or_none()

        if not row or not row[0]:
            return {"prediction": "no_data"}

        total, avg_lat, avg_tok = row
        hours = max(lookback_hours, 1)
        avg_rph = total / hours

        return {
            "period_hours": lookback_hours,
            "total_requests": total,
            "avg_requests_per_hour": round(avg_rph, 2),
            "avg_latency_ms": round(avg_lat or 0, 2),
            "avg_tokens_per_request": round(avg_tok or 0, 2),
            "recommendation": "preload" if avg_rph > 50 else "no_action",
        }


# ── HMAC Request Signing ──────────────────────────────────────


class HMACSigner:
    @staticmethod
    def sign_request(
        method: str,
        path: str,
        body: bytes,
        secret: str,
        timestamp: int | None = None,
    ) -> dict[str, str]:
        """Sign an API request with HMAC-SHA256."""
        ts = timestamp or int(time.time())
        message = f"{method}|{path}|{ts}|{body.decode() if body else ''}"
        signature = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        return {
            "X-Signature": signature,
            "X-Timestamp": str(ts),
            "X-Algorithm": "HMAC-SHA256",
        }

    @staticmethod
    def verify_signature(
        method: str,
        path: str,
        body: bytes,
        signature: str,
        timestamp: str,
        secret: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify an HMAC-signed request."""
        try:
            ts = int(timestamp)
            if abs(int(time.time()) - ts) > max_age_seconds:
                return False

            expected = HMACSigner.sign_request(method, path, body, secret, ts)
            return hmac.compare_digest(
                signature.encode(), expected["X-Signature"].encode()
            )
        except (ValueError, TypeError):
            return False

    @staticmethod
    def verify_request_headers(
        method: str,
        path: str,
        body: bytes,
        headers: dict,
        secret: str,
    ) -> bool:
        signature = headers.get("X-Signature", "")
        timestamp = headers.get("X-Timestamp", "")
        if not signature or not timestamp:
            return False
        return HMACSigner.verify_signature(
            method, path, body, signature, timestamp, secret
        )


hmac_signer = HMACSigner()
multi_modal = MultiModalHandler()
dynamic_quantizer = DynamicQuantizer()
cold_start = ColdStartOptimizer()
compliance = ComplianceExporter()
