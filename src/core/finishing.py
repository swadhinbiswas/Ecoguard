"""Slack/Discord notifications, model cost comparison, CSV/PDF export, secrets management."""

import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import logger
from src.models.inference import InferenceLog

# ── Slack/Discord Notifications ────────────────────────────────


class ChatNotifier:
    @staticmethod
    async def send_slack(webhook_url: str, message: str, title: str = "") -> bool:
        payload = {
            "text": f"*{title}*\n{message}" if title else message,
            "username": "Eco-Guard",
            "icon_emoji": ":robot_face:",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(webhook_url, json=payload)
                return r.status_code == 200
        except Exception as e:
            logger.warning(f"Slack notification failed: {e}")
            return False

    @staticmethod
    async def send_discord(webhook_url: str, message: str, title: str = "") -> bool:
        payload = {
            "content": f"**{title}**\n{message}" if title else message,
            "username": "Eco-Guard",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(webhook_url, json=payload)
                return r.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"Discord notification failed: {e}")
            return False

    @staticmethod
    async def send_alert(
        alert_type: str,
        message: str,
        slack_url: str = "",
        discord_url: str = "",
    ) -> dict[str, bool]:
        results = {"slack": False, "discord": False}
        if slack_url:
            results["slack"] = await ChatNotifier.send_slack(
                slack_url, message, f"🚨 {alert_type}"
            )
        if discord_url:
            results["discord"] = await ChatNotifier.send_discord(
                discord_url, message, f"🚨 {alert_type}"
            )
        return results


chat_notifier = ChatNotifier()


# ── Model Cost Comparison ──────────────────────────────────────


class ModelCostComparator:
    @staticmethod
    def compare_providers(
        prompt: str,
        max_tokens: int = 128,
    ) -> dict[str, Any]:
        input_tokens = len(prompt.split()) * 2
        output_tokens = max_tokens

        providers = {
            "Llama-3-8B (self-hosted)": {
                "input_per_1k": 0.0,
                "output_per_1k": 0.0,
                "latency_factor": 1.0,
            },
            "Llama-3-70B (self-hosted)": {
                "input_per_1k": 0.0,
                "output_per_1k": 0.0,
                "latency_factor": 1.5,
            },
            "GPT-4o (API)": {
                "input_per_1k": 0.0025,
                "output_per_1k": 0.01,
                "latency_factor": 0.5,
            },
            "GPT-4 (API)": {
                "input_per_1k": 0.03,
                "output_per_1k": 0.06,
                "latency_factor": 1.0,
            },
            "Claude-3-Sonnet (API)": {
                "input_per_1k": 0.003,
                "output_per_1k": 0.015,
                "latency_factor": 0.8,
            },
            "Claude-3-Haiku (API)": {
                "input_per_1k": 0.00025,
                "output_per_1k": 0.00125,
                "latency_factor": 0.3,
            },
        }

        results: list[dict] = []
        for name, config in providers.items():
            input_cost = (input_tokens / 1000) * config["input_per_1k"]
            output_cost = (output_tokens / 1000) * config["output_per_1k"]
            total = input_cost + output_cost
            results.append(
                {
                    "provider": name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "input_cost": round(input_cost, 6),
                    "output_cost": round(output_cost, 6),
                    "total_cost": round(total, 6),
                    "self_hosted": config["input_per_1k"] == 0,
                }
            )

        results.sort(key=lambda x: x["total_cost"])
        return {
            "prompt_length": len(prompt),
            "estimated_input_tokens": input_tokens,
            "expected_output_tokens": output_tokens,
            "providers": results,
            "cheapest": results[0]["provider"],
            "savings_vs_most_expensive": round(
                results[-1]["total_cost"] - results[0]["total_cost"], 6
            ),
        }


model_cost_comparator = ModelCostComparator()


# ── CSV/PDF Export ─────────────────────────────────────────────


class DataExporter:
    @staticmethod
    async def export_logs_csv(
        db: AsyncSession, hours: int = 168, max_rows: int = 10000
    ) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(InferenceLog)
            .where(InferenceLog.timestamp >= cutoff)
            .order_by(InferenceLog.timestamp.desc())
            .limit(max_rows)
        )
        logs = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "request_id",
                "timestamp",
                "input_text",
                "output",
                "latency_ms",
                "token_count",
                "drift_score",
            ]
        )

        for log in logs:
            writer.writerow(
                [
                    log.request_id,
                    log.timestamp.isoformat() if log.timestamp else "",
                    log.input_text[:500],
                    (log.prediction_output or "")[:500],
                    log.latency_ms,
                    log.token_count,
                    log.drift_score,
                ]
            )

        return output.getvalue()

    @staticmethod
    async def export_feedback_csv(db: AsyncSession, hours: int = 168) -> str:
        from src.mlops.advanced import UserFeedback

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(UserFeedback)
            .where(UserFeedback.created_at >= cutoff)
            .order_by(UserFeedback.created_at.desc())
        )
        feedbacks = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["request_id", "rating", "feedback", "category", "username", "created_at"]
        )

        for fb in feedbacks:
            writer.writerow(
                [
                    fb.request_id,
                    fb.rating,
                    fb.feedback_text,
                    fb.category,
                    fb.username,
                    fb.created_at.isoformat() if fb.created_at else "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_json(data: list[dict], filename: str = "export.json") -> str:
        return json.dumps(data, indent=2, default=str)


data_exporter = DataExporter()


# ── Daily Digest ───────────────────────────────────────────────


class DailyDigest:
    @staticmethod
    async def generate_digest(db: AsyncSession) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        result = await db.execute(
            select(InferenceLog).where(InferenceLog.timestamp >= cutoff)
        )
        logs = result.scalars().all()

        total = len(logs)
        if total == 0:
            return {"period": "24h", "total_requests": 0, "message": "No activity"}

        latencies = [log.latency_ms for log in logs if log.latency_ms]
        tokens = [log.token_count for log in logs if log.token_count]
        drift_scores = [log.drift_score for log in logs if log.drift_score is not None]

        import statistics

        return {
            "period": "24h",
            "total_requests": total,
            "total_tokens": sum(tokens),
            "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2)
            if len(latencies) > 1
            else (latencies[0] if latencies else 0),
            "avg_drift": round(statistics.mean(drift_scores), 4) if drift_scores else 0,
            "drift_events": sum(1 for d in drift_scores if d >= 0.8),
            "estimated_cost": round((sum(tokens) / 1000) * 0.0015, 4),
        }

    @staticmethod
    async def send_digest_email(
        db: AsyncSession,
        to_email: str = "",
        smtp_host: str = "",
        slack_url: str = "",
    ) -> dict[str, bool]:
        digest = await DailyDigest.generate_digest(db)
        message = (
            f"📊 *Eco-Guard Daily Digest*\n"
            f"• Requests: {digest['total_requests']}\n"
            f"• Tokens: {digest['total_tokens']:,}\n"
            f"• Avg Latency: {digest['avg_latency_ms']}ms\n"
            f"• P95 Latency: {digest['p95_latency_ms']}ms\n"
            f"• Drift Events: {digest['drift_events']}\n"
            f"• Est. Cost: ${digest['estimated_cost']:.4f}"
        )

        results = {"email": False, "slack": False}

        if to_email:
            try:
                from src.services.notifier import get_notifier

                notifier = get_notifier(smtp_host=smtp_host)
                await notifier.send_email_alert("Daily Digest", message, [to_email])
                results["email"] = True
            except Exception as e:
                logger.warning(f"Digest email failed: {e}")

        if slack_url:
            results["slack"] = await chat_notifier.send_slack(
                slack_url, message, "Daily Digest"
            )

        return results


daily_digest = DailyDigest()


# ── Secrets Management ─────────────────────────────────────────


class SecretsManager:
    @staticmethod
    async def load_from_vault(
        vault_addr: str, vault_token: str, secret_path: str
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{vault_addr}/v1/{secret_path}",
                    headers={"X-Vault-Token": vault_token},
                )
                if r.status_code == 200:
                    data = r.json()
                    return data.get("data", {}).get("data", {})
        except Exception as e:
            logger.warning(f"Vault fetch failed: {e}")
        return {}

    @staticmethod
    async def load_from_env_file(path: str = ".env") -> dict[str, str]:
        if not os.path.isfile(path):
            return {}

        secrets: dict[str, str] = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                secrets[key.strip()] = value.strip().strip('"').strip("'")
        return secrets

    @staticmethod
    def redact(value: str, show_chars: int = 4) -> str:
        if len(value) <= show_chars:
            return "*" * len(value)
        return value[:show_chars] + "*" * (len(value) - show_chars)


secrets_manager = SecretsManager()
