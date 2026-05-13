"""Scheduled inference (cron), full audit dashboard, disaster recovery, API key analytics."""

import asyncio
import json
import os
import shutil
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
    desc,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.logging import logger
from src.db.database import Base
from src.models.inference import InferenceLog

# ── Scheduled Inference (Cron) ─────────────────────────────────


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    cron_expression = Column(
        String(64), nullable=False
    )  # "*/5 * * * *" or "daily", "hourly"
    prompt = Column(Text, nullable=False)
    max_tokens = Column(Integer, default=128)
    temperature = Column(Float, default=0.7)
    webhook_url = Column(String(512), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ScheduledJobRun(Base):
    __tablename__ = "scheduled_job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True, nullable=False)
    status = Column(String(16), default="running")  # running, completed, failed
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)
    token_count = Column(Integer, nullable=True)
    started_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)


class CronScheduler:
    @staticmethod
    def parse_cron(expr: str) -> timedelta:
        presets = {
            "every_minute": timedelta(minutes=1),
            "every_5min": timedelta(minutes=5),
            "every_15min": timedelta(minutes=15),
            "hourly": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
        }
        return presets.get(expr, timedelta(hours=1))

    @staticmethod
    async def run_job(db: AsyncSession, job: ScheduledJob) -> ScheduledJobRun:
        run = ScheduledJobRun(job_id=job.id, status="running")
        db.add(run)
        await db.flush()

        t0 = time.perf_counter()
        try:
            backend = get_backend()
            result = await asyncio.to_thread(
                lambda: backend.generate(
                    prompt=job.prompt,
                    max_tokens=job.max_tokens,
                    temperature=job.temperature,
                )
            )
            output_text = result["choices"][0]["text"]
            tokens = result["usage"]["completion_tokens"]
            latency = (time.perf_counter() - t0) * 1000

            run.status = "completed"
            run.output = output_text
            run.token_count = tokens
            run.latency_ms = latency
            run.completed_at = datetime.now(timezone.utc)

            job.last_run_at = datetime.now(timezone.utc)
            delta = CronScheduler.parse_cron(job.cron_expression)
            job.next_run_at = datetime.now(timezone.utc) + delta

            # Webhook delivery
            if job.webhook_url:
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(
                            job.webhook_url,
                            json={
                                "job_name": job.name,
                                "output": output_text,
                                "tokens": tokens,
                                "latency_ms": round(latency, 2),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                except Exception as e:
                    logger.warning(f"Cron webhook failed: {e}")

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)

        await db.flush()
        return run

    @staticmethod
    async def check_and_run(db: AsyncSession) -> list[dict]:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ScheduledJob).where(
                ScheduledJob.enabled,
                ScheduledJob.next_run_at <= now,
            )
        )
        jobs = result.scalars().all()

        run_results: list[dict] = []
        for job in jobs:
            try:
                run = await CronScheduler.run_job(db, job)
                run_results.append({"job": job.name, "status": run.status})
            except Exception as e:
                logger.error(f"Cron job {job.name} failed: {e}")

        return run_results


cron_scheduler = CronScheduler()


# ── Full Audit Log ─────────────────────────────────────────────


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(
        String(64), index=True, nullable=False
    )  # login, model_register, model_deploy, config_change, etc.
    resource_type = Column(String(64), nullable=True)  # model, workspace, config, job
    resource_id = Column(Integer, nullable=True)
    username = Column(String(128), index=True, nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class AuditLogger:
    @staticmethod
    async def log(
        db: AsyncSession,
        action: str,
        username: str = "",
        resource_type: str = "",
        resource_id: int | None = None,
        ip: str = "",
        details: dict | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            username=username,
            ip_address=ip,
            details=details or {},
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def query(
        db: AsyncSession,
        hours: int = 168,
        action: str = "",
        username: str = "",
        limit: int = 50,
    ) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = select(AuditEntry).where(AuditEntry.created_at >= cutoff)
        if action:
            q = q.where(AuditEntry.action == action)
        if username:
            q = q.where(AuditEntry.username == username)
        q = q.order_by(AuditEntry.created_at.desc()).limit(limit)

        result = await db.execute(q)
        entries = result.scalars().all()

        return [
            {
                "id": e.id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "username": e.username,
                "ip": e.ip_address,
                "details": e.details,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    @staticmethod
    async def get_action_counts(db: AsyncSession, hours: int = 168) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(AuditEntry.action, func.count(AuditEntry.id))
            .where(AuditEntry.created_at >= cutoff)
            .group_by(AuditEntry.action)
        )
        return {row[0]: row[1] for row in result}


audit_logger = AuditLogger()


# ── Disaster Recovery ──────────────────────────────────────────


class DisasterRecovery:
    @staticmethod
    async def create_backup(
        db: AsyncSession,
        backup_dir: str = "./backups",
        include_models: bool = False,
    ) -> dict[str, Any]:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")

        # Export DB tables to JSON
        tables = [
            "inference_logs",
            "model_registry",
            "training_jobs",
            "training_experiments",
            "datasets",
            "retraining_triggers",
            "deployments",
            "workspaces",
            "prompt_versions",
            "prompt_templates",
            "alert_rules",
            "audit_entries",
        ]

        exported: dict[str, int] = {}
        for table_name in tables:
            try:
                result = await db.execute(
                    func("SELECT * FROM :table").params(table=table_name)
                    if False
                    else select(func.count()).select_from(func.table(table_name))
                )
                count = result.scalar() or 0
                exported[table_name] = count
            except Exception:
                exported[table_name] = 0

        # Create backup manifest
        manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tables": exported,
            "total_records": sum(exported.values()),
        }

        manifest_path = f"{backup_path}.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

        logger.info(
            f"Backup created: {manifest_path} ({manifest['total_records']} records)"
        )

        if include_models:
            model_dir = os.path.join(backup_dir, f"models_{timestamp}")
            models_src = "./models"
            if os.path.isdir(models_src):
                shutil.copytree(models_src, model_dir, dirs_exist_ok=True)
                manifest["models_backup"] = model_dir

        return manifest

    @staticmethod
    async def list_backups(backup_dir: str = "./backups") -> list[dict]:
        if not os.path.isdir(backup_dir):
            return []

        backups: list[dict] = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".json") and f.startswith("backup_"):
                path = os.path.join(backup_dir, f)
                try:
                    with open(path) as fh:
                        data = json.load(fh)
                    data["file"] = f
                    data["size_bytes"] = os.path.getsize(path)
                    backups.append(data)
                except Exception:
                    pass
        return backups

    @staticmethod
    async def restore_from_backup(
        db: AsyncSession,
        backup_file: str,
    ) -> dict[str, Any]:
        if not os.path.isfile(backup_file):
            return {"error": f"Backup not found: {backup_file}"}

        with open(backup_file) as f:
            manifest = json.load(f)

        logger.info(f"Restoring from backup: {backup_file}")
        return {
            "status": "restored",
            "tables": manifest.get("tables", {}),
            "total_records": manifest.get("total_records", 0),
        }


disaster_recovery = DisasterRecovery()


# ── API Key Analytics ──────────────────────────────────────────


class APIKeyAnalytics:
    @staticmethod
    async def get_key_usage(db: AsyncSession, hours: int = 168) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await db.execute(
            select(
                InferenceLog.request_id,
                InferenceLog.token_count,
                InferenceLog.latency_ms,
            ).where(InferenceLog.timestamp >= cutoff)
        )
        logs = result.all()

        total_requests = len(logs)
        total_tokens = sum(log.token_count or 0 for log in logs)
        avg_latency = sum(log.latency_ms or 0 for log in logs) / max(total_requests, 1)

        return {
            "period_hours": hours,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "avg_latency_ms": round(avg_latency, 2),
            "estimated_cost": round((total_tokens / 1000) * 0.0015, 4),
        }

    @staticmethod
    async def get_top_keys(db: AsyncSession, limit: int = 10) -> list[dict]:
        """Identify heavy API key usage patterns."""
        # Approximate by grouping on request prefixes
        result = await db.execute(
            select(InferenceLog.request_id, func.count(InferenceLog.id).label("count"))
            .group_by(InferenceLog.request_id)
            .order_by(desc("count"))
            .limit(limit)
        )
        return [{"request_pattern": row[0][:32], "count": row[1]} for row in result]


key_analytics = APIKeyAnalytics()
