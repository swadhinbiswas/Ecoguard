"""Routes for Slack/Discord, cost comparison, CSV export, daily digest, secrets."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.finishing import (
    chat_notifier,
    daily_digest,
    data_exporter,
    model_cost_comparator,
    secrets_manager,
)
from src.db.session import get_db

polish_router = APIRouter(prefix="/api/v1", tags=["Polish"])


# ── Slack/Discord Notifications ────────────────────────────────


class ChatNotifyRequest(BaseModel):
    message: str
    title: str = ""
    platform: str = "slack"  # slack or discord
    webhook_url: str


@polish_router.post("/notify/chat")
async def send_chat_notification(body: ChatNotifyRequest):
    if body.platform == "discord":
        ok = await chat_notifier.send_discord(
            body.webhook_url, body.message, body.title
        )
    else:
        ok = await chat_notifier.send_slack(body.webhook_url, body.message, body.title)
    return {"sent": ok, "platform": body.platform}


@polish_router.post("/notify/alert")
async def send_alert_notification(
    alert_type: str = Query(...),
    message: str = Query(...),
    slack_url: str = Query(default=""),
    discord_url: str = Query(default=""),
):
    results = await chat_notifier.send_alert(
        alert_type, message, slack_url, discord_url
    )
    return {"results": results}


# ── Model Cost Comparison ──────────────────────────────────────


class CostCompareRequest(BaseModel):
    prompt: str
    max_tokens: int = 128


@polish_router.post("/cost/compare")
async def compare_model_costs(body: CostCompareRequest):
    return model_cost_comparator.compare_providers(body.prompt, body.max_tokens)


# ── CSV/JSON Export ────────────────────────────────────────────


@polish_router.get("/export/logs/csv")
async def export_logs_csv(
    hours: int = Query(default=168), db: AsyncSession = Depends(get_db)
):
    csv_data = await data_exporter.export_logs_csv(db, hours)
    return PlainTextResponse(
        csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inference_logs.csv"},
    )


@polish_router.get("/export/feedback/csv")
async def export_feedback_csv(
    hours: int = Query(default=168), db: AsyncSession = Depends(get_db)
):
    csv_data = await data_exporter.export_feedback_csv(db, hours)
    return PlainTextResponse(
        csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=feedback.csv"},
    )


# ── Daily Digest ───────────────────────────────────────────────


@polish_router.get("/digest")
async def get_daily_digest(db: AsyncSession = Depends(get_db)):
    return await daily_digest.generate_digest(db)


class DigestSendRequest(BaseModel):
    to_email: str = ""
    slack_url: str = ""


@polish_router.post("/digest/send")
async def send_daily_digest(
    body: DigestSendRequest, db: AsyncSession = Depends(get_db)
):
    return await daily_digest.send_digest_email(
        db, body.to_email, slack_url=body.slack_url
    )


# ── Secrets Management ─────────────────────────────────────────


@polish_router.get("/secrets/test-vault")
async def test_vault_connection(
    vault_addr: str = Query(default="http://localhost:8200"),
    vault_token: str = Query(...),
    path: str = Query(default="secret/ecoguard"),
):
    secrets = await secrets_manager.load_from_vault(vault_addr, vault_token, path)
    return {"connected": bool(secrets), "keys_found": list(secrets.keys())}


@polish_router.get("/secrets/redact")
async def redact_value(value: str = Query(...), show_chars: int = Query(default=4)):
    return {
        "original_length": len(value),
        "redacted": secrets_manager.redact(value, show_chars),
    }


@polish_router.get("/secrets/load-env")
async def load_env_file(path: str = Query(default=".env")):
    secrets = await secrets_manager.load_from_env_file(path)
    return {
        "keys_found": len(secrets),
        "keys": [secrets_manager.redact(k) for k in secrets.keys()],
    }
