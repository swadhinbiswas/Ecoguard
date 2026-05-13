"""Prompt template library, analytics engine, alert rules, deployment timeline."""

from datetime import datetime, timedelta, timezone
from typing import Optional

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

from src.db.database import Base
from src.mlops.models import Deployment, ModelRegistry
from src.models.inference import InferenceLog

# ── Prompt Template Library ────────────────────────────────────


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    category = Column(String(64), index=True, nullable=False)
    description = Column(Text, nullable=True)
    template = Column(Text, nullable=False)
    variables = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    usage_count = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(String, nullable=True)

    _BUILTIN_TEMPLATES = [
        {
            "name": "Code Review",
            "category": "engineering",
            "template": "Review this {language} code for bugs, style, and performance:\n\n```{language}\n{code}\n```",
            "variables": ["language", "code"],
            "tags": ["code", "review"],
        },
        {
            "name": "Summarize",
            "category": "text",
            "template": "Summarize the following text in {style} style, in approximately {words} words:\n\n{text}",
            "variables": ["text", "words", "style"],
            "tags": ["summarize", "text"],
        },
        {
            "name": "Translate",
            "category": "language",
            "template": "Translate the following from {source_lang} to {target_lang}:\n\n{text}",
            "variables": ["text", "source_lang", "target_lang"],
            "tags": ["translate", "language"],
        },
        {
            "name": "Explain Concept",
            "category": "education",
            "template": "Explain {concept} to a {audience}. Keep it {tone} and use analogies.",
            "variables": ["concept", "audience", "tone"],
            "tags": ["explain", "education"],
        },
        {
            "name": "Write Email",
            "category": "communication",
            "template": "Write a {tone} email about {topic}. Key points:\n{points}\n\nFrom: {sender}\nTo: {recipient}",
            "variables": ["topic", "tone", "points", "sender", "recipient"],
            "tags": ["email", "communication"],
        },
        {
            "name": "SQL Query",
            "category": "engineering",
            "template": "Write a SQL query for {database} that {task}.\n\nTables:\n{schema}\n\nRequirements: {requirements}",
            "variables": ["task", "database", "schema", "requirements"],
            "tags": ["sql", "database"],
        },
        {
            "name": "Bug Report",
            "category": "engineering",
            "template": "Analyze this bug report and suggest a fix:\n\nError: {error}\nStack trace: {stacktrace}\nEnvironment: {env}\n\nProvide: root cause, fix, and prevention.",
            "variables": ["error", "stacktrace", "env"],
            "tags": ["debug", "engineering"],
        },
        {
            "name": "Product Description",
            "category": "marketing",
            "template": "Write a compelling product description for {product}. Highlight: {features}. Target audience: {audience}. Tone: {tone}.",
            "variables": ["product", "features", "audience", "tone"],
            "tags": ["marketing", "product"],
        },
        {
            "name": "Lesson Plan",
            "category": "education",
            "template": "Create a lesson plan on {topic} for {grade_level}. Duration: {duration}. Include: objectives, materials, activities, and assessment.",
            "variables": ["topic", "grade_level", "duration"],
            "tags": ["education", "planning"],
        },
        {
            "name": "API Documentation",
            "category": "engineering",
            "template": "Write API documentation for the following endpoint:\n\nEndpoint: {method} {path}\nDescription: {description}\nRequest body: {request_body}\nResponse: {response}\n\nInclude: description, parameters, examples, and error codes.",
            "variables": ["method", "path", "description", "request_body", "response"],
            "tags": ["api", "docs", "engineering"],
        },
    ]

    @classmethod
    async def seed_builtins(cls, db: AsyncSession) -> int:
        count = 0
        for tmpl in cls._BUILTIN_TEMPLATES:
            existing = await db.execute(
                select(PromptTemplate).where(PromptTemplate.name == tmpl["name"])
            )
            if existing.scalar_one_or_none():
                continue
            db.add(PromptTemplate(**tmpl, created_by="system"))
            count += 1
        await db.flush()
        return count


# ── Analytics Engine ───────────────────────────────────────────


class AnalyticsEngine:
    @staticmethod
    async def get_usage_over_time(
        db: AsyncSession, hours: int = 168, interval_minutes: int = 60
    ) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await db.execute(
            select(InferenceLog)
            .where(InferenceLog.timestamp >= cutoff)
            .order_by(InferenceLog.timestamp)
        )
        logs = result.scalars().all()

        buckets: dict[str, dict] = {}
        for log in logs:
            if not log.timestamp:
                continue
            ts = log.timestamp
            bucket_key = ts.replace(
                minute=(ts.minute // interval_minutes) * interval_minutes,
                second=0,
                microsecond=0,
            ).isoformat()
            if bucket_key not in buckets:
                buckets[bucket_key] = {
                    "count": 0,
                    "total_latency": 0,
                    "total_tokens": 0,
                    "errors": 0,
                }
            buckets[bucket_key]["count"] += 1
            buckets[bucket_key]["total_latency"] += log.latency_ms or 0
            buckets[bucket_key]["total_tokens"] += log.token_count or 0

        series = []
        for key in sorted(buckets.keys()):
            b = buckets[key]
            n = max(b["count"], 1)
            series.append(
                {
                    "timestamp": key,
                    "requests": b["count"],
                    "avg_latency_ms": round(b["total_latency"] / n, 2),
                    "total_tokens": b["total_tokens"],
                }
            )

        return {
            "period_hours": hours,
            "interval_minutes": interval_minutes,
            "series": series,
        }

    @staticmethod
    async def get_top_prompts(db: AsyncSession, limit: int = 10) -> list[dict]:
        result = await db.execute(
            select(
                InferenceLog.input_text,
                func.count(InferenceLog.id).label("count"),
                func.avg(InferenceLog.latency_ms).label("avg_latency"),
                func.avg(InferenceLog.token_count).label("avg_tokens"),
            )
            .group_by(InferenceLog.input_text)
            .order_by(desc("count"))
            .limit(limit)
        )
        return [
            {
                "prompt": row[0][:200],
                "count": row[1],
                "avg_latency_ms": round(row[2] or 0, 2),
                "avg_tokens": round(row[3] or 0, 2),
            }
            for row in result
        ]

    @staticmethod
    async def get_summary(db: AsyncSession, hours: int = 24) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await db.execute(
            select(
                func.count(InferenceLog.id).label("total"),
                func.avg(InferenceLog.latency_ms).label("avg_lat"),
                func.avg(InferenceLog.token_count).label("avg_tok"),
                func.max(InferenceLog.latency_ms).label("max_lat"),
                func.min(InferenceLog.latency_ms).label("min_lat"),
                func.count(InferenceLog.id)
                .filter(InferenceLog.drift_score >= 0.8)
                .label("drift_count"),
            ).where(InferenceLog.timestamp >= cutoff)
        )
        row = result.one_or_none()
        if not row or not row[0]:
            return {"status": "no_data"}

        return {
            "period_hours": hours,
            "total_requests": row[0],
            "avg_latency_ms": round(row[1] or 0, 2),
            "avg_tokens": round(row[2] or 0, 2),
            "max_latency_ms": round(row[3] or 0, 2),
            "min_latency_ms": round(row[4] or 0, 2),
            "drift_events": row[5] or 0,
        }


analytics_engine = AnalyticsEngine()


# ── Alert Rules ─────────────────────────────────────────────────


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    metric = Column(
        String(64), nullable=False
    )  # latency_p95, drift_score, error_rate, request_rate, token_usage
    condition = Column(String(8), nullable=False)  # gt, lt, gte, lte
    threshold = Column(Float, nullable=False)
    window_minutes = Column(Integer, default=15)
    cooldown_minutes = Column(Integer, default=30)
    webhook_url = Column(String(512), nullable=True)
    email_alert = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AlertRuleEngine:
    @staticmethod
    async def evaluate_rules(db: AsyncSession) -> list[dict]:
        result = await db.execute(select(AlertRule).where(AlertRule.enabled))
        rules = result.scalars().all()

        triggered: list[dict] = []
        now = datetime.now(timezone.utc)

        for rule in rules:
            if rule.last_triggered_at:
                cooldown_end = rule.last_triggered_at + timedelta(
                    minutes=rule.cooldown_minutes
                )
                if now < cooldown_end:
                    continue

            value = await AlertRuleEngine._get_metric_value(
                db, rule.metric, rule.window_minutes
            )
            if value is None:
                continue

            should_trigger = False
            if rule.condition == "gt" and value > rule.threshold:
                should_trigger = True
            elif rule.condition == "lt" and value < rule.threshold:
                should_trigger = True
            elif rule.condition == "gte" and value >= rule.threshold:
                should_trigger = True
            elif rule.condition == "lte" and value <= rule.threshold:
                should_trigger = True

            if should_trigger:
                rule.last_triggered_at = now
                triggered.append(
                    {
                        "rule": rule.name,
                        "metric": rule.metric,
                        "value": round(value, 4),
                        "threshold": rule.threshold,
                        "condition": rule.condition,
                    }
                )

        if triggered:
            await db.flush()
        return triggered

    @staticmethod
    async def _get_metric_value(
        db: AsyncSession, metric: str, window_minutes: int
    ) -> Optional[float]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        if metric == "latency_p95":
            result = await db.execute(
                select(InferenceLog.latency_ms).where(InferenceLog.timestamp >= cutoff)
            )
            vals = sorted([r[0] for r in result if r[0] is not None])
            if not vals:
                return None
            return vals[int(len(vals) * 0.95)]

        elif metric == "drift_score":
            result = await db.execute(
                select(func.avg(InferenceLog.drift_score)).where(
                    InferenceLog.timestamp >= cutoff
                )
            )
            row = result.scalar()
            return float(row) if row else None

        elif metric == "error_rate":
            total_result = await db.execute(
                select(func.count(InferenceLog.id)).where(
                    InferenceLog.timestamp >= cutoff
                )
            )
            total = total_result.scalar() or 0
            if total == 0:
                return 0.0
            return 0.0  # placeholder — track actual errors in future

        elif metric == "request_rate":
            result = await db.execute(
                select(func.count(InferenceLog.id)).where(
                    InferenceLog.timestamp >= cutoff
                )
            )
            count = result.scalar() or 0
            return count / max(window_minutes, 1)

        return None


alert_engine = AlertRuleEngine()


# ── Deployment Timeline ────────────────────────────────────────


class DeploymentTimeline:
    @staticmethod
    async def get_timeline(db: AsyncSession, limit: int = 50) -> dict:
        result = await db.execute(
            select(Deployment).order_by(Deployment.deployed_at.desc()).limit(limit)
        )
        deployments = result.scalars().all()

        events: list[dict] = []
        for dep in deployments:
            model_result = await db.execute(
                select(ModelRegistry).where(ModelRegistry.id == dep.model_id)
            )
            model = model_result.scalar_one_or_none()

            events.append(
                {
                    "id": dep.id,
                    "type": "deployment",
                    "model": model.name if model else f"id:{dep.model_id}",
                    "strategy": dep.strategy,
                    "traffic_pct": dep.traffic_percent,
                    "status": dep.status,
                    "deployed_by": dep.deployed_by,
                    "deployed_at": dep.deployed_at.isoformat()
                    if dep.deployed_at
                    else None,
                    "message": f"Deployed {model.name if model else 'unknown'} "
                    f"via {dep.strategy} at {dep.traffic_percent}% traffic",
                }
            )

        return {"events": events, "total": len(events)}


deployment_timeline = DeploymentTimeline()
