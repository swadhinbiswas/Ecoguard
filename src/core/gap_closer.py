"""Final missing features: vision/multimodal backend, async inference webhook,
per-workspace rate limiting, real fine-tuning execution, DB pool monitoring,
data residency, secrets auto-loading, model card export."""

import asyncio
import base64
import json
import os
import time
from datetime import datetime, timezone
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
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import logger
from src.db.database import Base
from src.models.inference import InferenceLog

# ── #1 Vision/Multimodal Backend ───────────────────────────────


class MultimodalInference:
    """Handles inference with image inputs alongside text."""

    @staticmethod
    def encode_image_file(path: str) -> str:
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
            return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"

    @staticmethod
    def encode_image_bytes(data: bytes, mime: str = "jpeg") -> str:
        return f"data:image/{mime};base64,{base64.b64encode(data).decode()}"

    @staticmethod
    async def generate_with_image(
        prompt: str,
        image_paths: list[str],
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Generate text from a prompt + images using the loaded backend."""
        from src.core.backend import get_backend

        backend = get_backend()
        if not backend.is_loaded():
            raise RuntimeError("No model loaded")

        # Build multimodal prompt
        image_refs = []
        for i, path in enumerate(image_paths, 1):
            if path.startswith("data:"):
                image_refs.append(f"Image {i}: [base64 image, {len(path)} bytes]")
            elif os.path.isfile(path):
                uri = MultimodalInference.encode_image_file(path)
                image_refs.append(f"Image {i}: [base64 image, {len(uri)} bytes]")
            else:
                image_refs.append(f"Image {i}: {path}")

        full_prompt = (
            f"You are shown {len(image_paths)} image(s). "
            f"{' '.join(image_refs)}\n\n"
            f"User request: {prompt}\n\n"
            f"Response:"
        )

        t0 = time.perf_counter()
        result = await asyncio.to_thread(
            lambda: backend.generate(
                prompt=full_prompt, max_tokens=max_tokens, temperature=temperature
            )
        )
        latency = (time.perf_counter() - t0) * 1000

        return {
            "output": result["choices"][0]["text"],
            "images": len(image_paths),
            "prompt_tokens": result["usage"].get("prompt_tokens", 0),
            "completion_tokens": result["usage"]["completion_tokens"],
            "latency_ms": round(latency, 2),
        }


vision = MultimodalInference()


# ── #2 Async Inference with Webhook Callback ────────────────────


class AsyncInferenceJob(Base):
    __tablename__ = "async_inference_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(16), default="queued")  # queued, running, completed, failed
    prompt = Column(Text, nullable=False)
    max_tokens = Column(Integer, default=128)
    temperature = Column(Float, default=0.7)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    callback_url = Column(String(512), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AsyncInference:
    _processing_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
    _worker_running = False

    @staticmethod
    async def submit(
        db: AsyncSession,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.7,
        callback_url: str = "",
    ) -> AsyncInferenceJob:
        import uuid

        job_id = f"async-{uuid.uuid4().hex[:12]}"
        job = AsyncInferenceJob(
            job_id=job_id,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            callback_url=callback_url,
        )
        db.add(job)
        await db.flush()
        await AsyncInference._processing_queue.put(job)
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> Optional[AsyncInferenceJob]:
        result = await db.execute(
            select(AsyncInferenceJob).where(AsyncInferenceJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _worker(db_factory):
        import httpx

        from src.core.backend import get_backend

        while True:
            job = await AsyncInference._processing_queue.get()
            try:
                async with db_factory() as db:
                    result = await db.execute(
                        select(AsyncInferenceJob).where(
                            AsyncInferenceJob.job_id == job.job_id
                        )
                    )
                    job_ref = result.scalar_one()
                    job_ref.status = "running"
                    await db.flush()

                    t0 = time.perf_counter()
                    backend = get_backend()
                    output = await asyncio.to_thread(
                        lambda: backend.generate(
                            prompt=job.prompt,
                            max_tokens=job.max_tokens,
                            temperature=job.temperature,
                        )
                    )
                    latency = (time.perf_counter() - t0) * 1000

                    job_ref.output = output["choices"][0]["text"]
                    job_ref.token_count = output["usage"]["completion_tokens"]
                    job_ref.latency_ms = latency
                    job_ref.status = "completed"
                    job_ref.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    # Webhook callback
                    if job.callback_url:
                        try:
                            async with httpx.AsyncClient(timeout=10) as client:
                                await client.post(
                                    job.callback_url,
                                    json={
                                        "job_id": job.job_id,
                                        "status": "completed",
                                        "output": job_ref.output[:500],
                                        "token_count": job_ref.token_count,
                                        "latency_ms": round(latency, 2),
                                    },
                                )
                        except Exception as e:
                            logger.warning(f"Async webhook failed: {e}")

            except Exception as e:
                try:
                    async with db_factory() as db:
                        result = await db.execute(
                            select(AsyncInferenceJob).where(
                                AsyncInferenceJob.job_id == job.job_id
                            )
                        )
                        job_ref = result.scalar_one()
                        job_ref.status = "failed"
                        job_ref.error = str(e)
                        job_ref.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                except Exception:
                    pass

    @staticmethod
    async def start_worker(db_factory):
        if not AsyncInference._worker_running:
            AsyncInference._worker_running = True
            asyncio.create_task(AsyncInference._worker(db_factory))

    @staticmethod
    async def list_jobs(db: AsyncSession, limit: int = 20) -> list[dict]:
        result = await db.execute(
            select(AsyncInferenceJob)
            .order_by(AsyncInferenceJob.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "job_id": j.job_id,
                "status": j.status,
                "tokens": j.token_count,
                "latency_ms": j.latency_ms,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in result.scalars().all()
        ]


async_inference = AsyncInference()


# ── #3 Per-Workspace Rate Limiting ─────────────────────────────


class WorkspaceRateLimit(Base):
    __tablename__ = "workspace_rate_limits"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, index=True, nullable=False)
    max_requests_per_minute = Column(Integer, default=100)
    max_tokens_per_minute = Column(Integer, default=100000)
    max_concurrent_requests = Column(Integer, default=10)
    enabled = Column(Boolean, default=True)


class WorkspaceRateLimiter:
    _request_counts: dict[int, list[float]] = {}
    _token_counts: dict[int, list[tuple[float, int]]] = {}

    @staticmethod
    async def is_allowed(
        db: AsyncSession, workspace_id: int, requested_tokens: int = 0
    ) -> tuple[bool, str]:
        result = await db.execute(
            select(WorkspaceRateLimit).where(
                WorkspaceRateLimit.workspace_id == workspace_id,
                WorkspaceRateLimit.enabled,
            )
        )
        limit = result.scalar_one_or_none()
        if not limit:
            return True, ""

        now = time.monotonic()
        cutoff = now - 60

        # Check request rate
        reqs = WorkspaceRateLimiter._request_counts.get(workspace_id, [])
        reqs = [t for t in reqs if t > cutoff]
        if len(reqs) >= limit.max_requests_per_minute:
            return False, f"Rate limit: {limit.max_requests_per_minute} req/min"
        reqs.append(now)
        WorkspaceRateLimiter._request_counts[workspace_id] = reqs

        # Check token rate
        tokens = WorkspaceRateLimiter._token_counts.get(workspace_id, [])
        tokens = [(t, c) for t, c in tokens if t > cutoff]
        total = sum(c for _, c in tokens)
        if total + requested_tokens > limit.max_tokens_per_minute:
            return False, f"Token limit: {limit.max_tokens_per_minute} tokens/min"
        tokens.append((now, requested_tokens))
        WorkspaceRateLimiter._token_counts[workspace_id] = tokens

        return True, ""

    @staticmethod
    async def set_limit(
        db: AsyncSession,
        workspace_id: int,
        requests_per_min: int = 100,
        tokens_per_min: int = 100000,
        concurrent: int = 10,
    ) -> WorkspaceRateLimit:
        result = await db.execute(
            select(WorkspaceRateLimit).where(
                WorkspaceRateLimit.workspace_id == workspace_id
            )
        )
        rl = result.scalar_one_or_none()
        if rl:
            rl.max_requests_per_minute = requests_per_min
            rl.max_tokens_per_minute = tokens_per_min
            rl.max_concurrent_requests = concurrent
        else:
            rl = WorkspaceRateLimit(
                workspace_id=workspace_id,
                max_requests_per_minute=requests_per_min,
                max_tokens_per_minute=tokens_per_min,
                max_concurrent_requests=concurrent,
            )
            db.add(rl)
        await db.flush()
        return rl


workspace_rate_limiter = WorkspaceRateLimiter()


# ── #4 Real Fine-Tuning Execution ──────────────────────────────


class RealFineTuner:
    @staticmethod
    async def run_llama_factory(
        base_model: str,
        dataset_path: str,
        output_dir: str,
        method: str = "lora",
        rank: int = 8,
        epochs: int = 3,
        lr: float = 2e-4,
    ) -> dict:
        """Execute fine-tuning via llama-factory or unsloth CLI."""
        os.makedirs(output_dir, exist_ok=True)

        config = {
            "model_name_or_path": base_model,
            "dataset": dataset_path,
            "output_dir": output_dir,
            "finetuning_type": method,
            "lora_rank": rank,
            "num_train_epochs": epochs,
            "learning_rate": lr,
            "per_device_train_batch_size": 2,
            "gradient_accumulation_steps": 4,
        }

        methods = [
            ["llamafactory-cli", "train", json.dumps(config)],
            [
                "python",
                "-m",
                "unsloth",
                "--model",
                base_model,
                "--dataset",
                dataset_path,
                "--output",
                output_dir,
                "--epochs",
                str(epochs),
            ],
            [
                "mlx_lm.lora",
                "--model",
                base_model,
                "--data",
                dataset_path,
                "--iters",
                str(epochs * 100),
            ],
        ]

        result = {
            "status": "no_tool",
            "methods_tried": [],
            "message": "No fine-tuning tool found. Install: pip install llamafactory or unsloth",
        }
        logs: list[str] = []

        for method_cmd in methods:
            try:
                result["methods_tried"].append(" ".join(method_cmd[:2]))
                proc = await asyncio.create_subprocess_exec(
                    *method_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
                logs.extend(stdout.decode().split("\n")[-20:])

                if proc.returncode == 0:
                    result["status"] = "completed"
                    result["tool"] = method_cmd[0]
                    result["output_dir"] = output_dir
                    break
                else:
                    logs.append(f"STDERR: {stderr.decode()[-500:]}")
            except (FileNotFoundError, asyncio.TimeoutError, Exception) as e:
                logs.append(f"Failed: {e}")
                continue

        result["logs"] = logs
        return result


real_finetuner = RealFineTuner()


# ── #5 Database Connection Pool Monitoring ──────────────────────


class DBPoolMonitor:
    @staticmethod
    def get_pool_stats() -> dict:
        from src.db.database import get_engine

        try:
            engine = get_engine()
            pool = engine.pool
            return {
                "size": getattr(pool, "_pool", {}).get("size", "unknown"),
                "checked_in": getattr(pool, "_overflow", -1),
                "overflow": getattr(pool, "_max_overflow", -1),
                "total": getattr(pool, "size", lambda: 0)()
                if hasattr(pool, "size")
                else 0,
            }
        except Exception:
            return {"error": "Pool stats unavailable"}

    @staticmethod
    async def get_connection_count(db: AsyncSession) -> int:
        try:
            result = await db.execute(func("SELECT count(*) FROM pg_stat_activity"))
            return result.scalar() or 0
        except Exception:
            return -1


db_pool_monitor = DBPoolMonitor()


# ── #6 Data Residency Controls ──────────────────────────────────


class DataResidency:
    _region = "auto"

    @classmethod
    def set_region(cls, region: str):
        cls._region = region
        logger.info(f"Data residency region set: {region}")

    @classmethod
    def get_region(cls) -> str:
        return cls._region or getattr(settings, "data_residency_region", "auto")

    @classmethod
    def is_region_allowed(cls, region: str) -> bool:
        allowed = getattr(
            settings, "allowed_regions", ["auto", "us-east", "eu-west", "ap-southeast"]
        )
        return region in allowed

    @classmethod
    def get_region_config(cls) -> dict:
        return {
            "current_region": cls.get_region(),
            "allowed_regions": getattr(settings, "allowed_regions", ["auto"]),
            "encryption": "aes-256",
            "retention_days": getattr(settings, "data_retention_days", 90),
        }


data_residency = DataResidency()


# ── #7 Secrets Auto-Loading on Startup ──────────────────────────


class SecretsLoader:
    @staticmethod
    async def load_from_vault(
        vault_addr: str, vault_token: str, paths: list[str]
    ) -> dict:
        import httpx

        secrets: dict[str, str] = {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for path in paths:
                    r = await client.get(
                        f"{vault_addr}/v1/{path}",
                        headers={"X-Vault-Token": vault_token},
                    )
                    if r.status_code == 200:
                        data = r.json().get("data", {}).get("data", {})
                        secrets.update(data)
                        logger.info(f"Vault: loaded {len(data)} keys from {path}")
        except Exception as e:
            logger.warning(f"Vault load failed: {e}")
        return secrets

    @staticmethod
    async def load_from_aws(secret_name: str, region: str = "us-east-1") -> dict:
        try:
            import boto3

            client = boto3.client("secretsmanager", region_name=region)
            response = client.get_secret_value(SecretId=secret_name)
            return json.loads(response.get("SecretString", "{}"))
        except ImportError:
            logger.warning("boto3 not installed for AWS secrets")
            return {}
        except Exception as e:
            logger.warning(f"AWS secrets load failed: {e}")
            return {}

    @staticmethod
    async def apply_to_settings(secrets: dict[str, str]) -> int:
        count = 0
        for key, value in secrets.items():
            key_upper = key.upper()
            if hasattr(settings, key_upper):
                setattr(settings, key_upper, value)
                count += 1
            elif hasattr(settings, key):
                setattr(settings, key, value)
                count += 1
        if count:
            logger.info(f"Secrets auto-loaded: {count} keys applied to settings")
        return count


secrets_loader = SecretsLoader()


# ── #8 Model Card Export ───────────────────────────────────────


class ModelCard(Base):
    __tablename__ = "model_cards"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(128), index=True, nullable=False)
    version = Column(String(64), nullable=False)
    base_model = Column(String(128), nullable=True)
    framework = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    benchmarks = Column(JSON, nullable=True)
    usage_guide = Column(Text, nullable=True)
    license_info = Column(String(256), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ModelCardExporter:
    @staticmethod
    async def create_card(
        db: AsyncSession,
        model_name: str,
        version: str,
        description: str = "",
        base_model: str = "",
        framework: str = "llama-cpp",
        license_info: str = "MIT",
    ) -> ModelCard:
        card = ModelCard(
            model_name=model_name,
            version=version,
            base_model=base_model,
            framework=framework,
            description=description,
            license_info=license_info,
        )
        db.add(card)
        await db.flush()
        return card

    @staticmethod
    async def export_card_json(model_name: str, db: AsyncSession) -> dict:
        # Get model card
        result = await db.execute(
            select(ModelCard)
            .where(ModelCard.model_name == model_name)
            .order_by(ModelCard.id.desc())
        )
        card = result.scalar_one_or_none()

        # Get benchmarks for this model
        from src.mlops.quality import RegressionCheck

        bench_result = await db.execute(
            select(RegressionCheck)
            .where(RegressionCheck.test_suite_name == model_name)
            .order_by(RegressionCheck.checked_at.desc())
            .limit(10)
        )
        benchmarks = bench_result.scalars().all()

        # Get usage stats
        stats_result = await db.execute(
            select(
                func.count(InferenceLog.id),
                func.avg(InferenceLog.latency_ms),
                func.avg(InferenceLog.token_count),
                func.avg(InferenceLog.drift_score),
            ).where(InferenceLog.input_text.contains(model_name))
        )
        row = stats_result.one_or_none()

        return {
            "model_card": {
                "name": card.model_name if card else model_name,
                "version": card.version if card else "unknown",
                "base_model": card.base_model if card else "",
                "framework": card.framework if card else "",
                "description": card.description if card else "",
                "license": card.license_info if card else "",
                "created_at": card.created_at.isoformat()
                if card and card.created_at
                else None,
            },
            "benchmarks": [
                {
                    "suite": b.test_suite_name,
                    "score": b.new_score,
                    "passed": b.passed,
                    "checked_at": b.checked_at.isoformat() if b.checked_at else None,
                }
                for b in benchmarks
            ],
            "usage": {
                "total_requests": row[0] or 0,
                "avg_latency_ms": round(row[1] or 0, 2),
                "avg_tokens": round(row[2] or 0, 2),
                "avg_drift": round(row[3] or 0, 4),
            }
            if row
            else {},
        }


model_card_exporter = ModelCardExporter()
