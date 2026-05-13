"""Routes for prompt templates, analytics, alert rules, deployment timeline, and system config."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.session import get_db
from src.mlops.dashboard_data import (
    AlertRule,
    PromptTemplate,
    analytics_engine,
    deployment_timeline,
)

dashboard_data_router = APIRouter(prefix="/api/v1", tags=["Dashboard Data"])


# ── Prompt Template Library ────────────────────────────────────


class TemplateCreate(BaseModel):
    name: str
    category: str = "custom"
    description: str = ""
    template: str
    variables: list[str] = []
    tags: list[str] = []


@dashboard_data_router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PromptTemplate).order_by(PromptTemplate.category, PromptTemplate.name)
    )
    templates = result.scalars().all()
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category,
                "description": t.description,
                "template": t.template,
                "variables": t.variables,
                "tags": t.tags,
                "usage_count": t.usage_count,
            }
            for t in templates
        ]
    }


@dashboard_data_router.post("/templates")
async def create_template(
    body: TemplateCreate, request: Request, db: AsyncSession = Depends(get_db)
):
    tmpl = PromptTemplate(
        name=body.name,
        category=body.category,
        description=body.description,
        template=body.template,
        variables=body.variables,
        tags=body.tags,
        created_by="api",
    )
    db.add(tmpl)
    await db.flush()
    return {"id": tmpl.id, "name": tmpl.name}


@dashboard_data_router.delete("/templates/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(404, "Template not found")
    await db.delete(tmpl)
    await db.flush()
    return {"deleted": template_id}


@dashboard_data_router.post("/templates/seed")
async def seed_builtin_templates(db: AsyncSession = Depends(get_db)):
    count = await PromptTemplate.seed_builtins(db)
    return {"seeded": count}


# ── Analytics ──────────────────────────────────────────────────


@dashboard_data_router.get("/analytics/usage")
async def usage_over_time(
    hours: int = Query(default=168, ge=1, le=720),
    interval: int = Query(default=60, ge=5, le=360),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_engine.get_usage_over_time(db, hours, interval)


@dashboard_data_router.get("/analytics/top-prompts")
async def top_prompts(
    limit: int = Query(default=10, le=50), db: AsyncSession = Depends(get_db)
):
    return {"prompts": await analytics_engine.get_top_prompts(db, limit)}


@dashboard_data_router.get("/analytics/summary")
async def analytics_summary(
    hours: int = Query(default=24), db: AsyncSession = Depends(get_db)
):
    return await analytics_engine.get_summary(db, hours)


# ── Alert Rules ────────────────────────────────────────────────


class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    condition: str = "gt"
    threshold: float
    window_minutes: int = 15
    cooldown_minutes: int = 30
    webhook_url: str = ""
    email_alert: bool = False


@dashboard_data_router.get("/alerts/rules")
async def list_alert_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRule).order_by(AlertRule.name))
    rules = result.scalars().all()
    return {
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "metric": r.metric,
                "condition": r.condition,
                "threshold": r.threshold,
                "enabled": r.enabled,
                "window_minutes": r.window_minutes,
            }
            for r in rules
        ]
    }


@dashboard_data_router.post("/alerts/rules")
async def create_alert_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AlertRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    return {"id": rule.id, "name": rule.name}


@dashboard_data_router.put("/alerts/rules/{rule_id}/toggle")
async def toggle_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    rule.enabled = not rule.enabled
    await db.flush()
    return {"id": rule.id, "enabled": rule.enabled}


@dashboard_data_router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    await db.delete(rule)
    await db.flush()
    return {"deleted": rule_id}


# ── Deployment Timeline ────────────────────────────────────────


@dashboard_data_router.get("/deployments/timeline")
async def get_deployment_timeline(
    limit: int = Query(default=50), db: AsyncSession = Depends(get_db)
):
    return await deployment_timeline.get_timeline(db, limit)


# ── System Configuration ──────────────────────────────────────


@dashboard_data_router.get("/system/config")
async def get_system_config():
    return {
        "environment": settings.environment,
        "log_level": settings.log_level,
        "auth_enabled": settings.auth_enabled,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_requests": settings.rate_limit_requests,
        "rate_limit_window_seconds": settings.rate_limit_window_seconds,
        "cache_enabled": settings.cache_enabled,
        "cache_ttl_seconds": settings.cache_ttl_seconds,
        "metrics_enabled": settings.metrics_enabled,
        "guardrails_enabled": settings.guardrails_enabled,
        "max_concurrent_inference": settings.max_concurrent_inference,
        "request_timeout_seconds": settings.request_timeout_seconds,
        "drift_alert_threshold": settings.drift_alert_threshold,
        "model_warmup_enabled": settings.model_warmup_enabled,
        "demo_mode": settings.demo_mode,
        "auto_migrate": settings.auto_migrate,
        "cors_origins": settings.cors_origins,
        "ip_allowlist": settings.ip_allowlist,
    }


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str


@dashboard_data_router.put("/system/config")
async def update_system_config(body: ConfigUpdateRequest):
    allowed_keys = {
        "log_level",
        "rate_limit_requests",
        "rate_limit_window_seconds",
        "cache_ttl_seconds",
        "drift_alert_threshold",
        "request_timeout_seconds",
        "guardrails_enabled",
        "max_concurrent_inference",
    }
    if body.key not in allowed_keys:
        raise HTTPException(
            400,
            f"Cannot update '{body.key}'. Allowed: {', '.join(sorted(allowed_keys))}",
        )

    if hasattr(settings, body.key):
        current = getattr(settings, body.key)
        if isinstance(current, bool):
            setattr(settings, body.key, body.value.lower() in ("true", "1", "yes"))
        elif isinstance(current, int):
            setattr(settings, body.key, int(body.value))
        elif isinstance(current, float):
            setattr(settings, body.key, float(body.value))
        else:
            setattr(settings, body.key, body.value)

    return {"key": body.key, "value": body.value}
