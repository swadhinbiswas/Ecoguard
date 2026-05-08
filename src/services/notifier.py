import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.core.logging import logger


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_email: str = "",
        to_emails: list[str] | None = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails or []

    @property
    def configured(self) -> bool:
        return bool(self.smtp_host and self.to_emails)

    async def send_drift_alert(
        self,
        drift_score: float,
        threshold: float,
        latency_ms: float,
        token_count: int,
    ) -> None:
        if not self.configured:
            return

        subject = f"[Eco-Guard] Drift Alert — Score: {drift_score:.4f}"
        body = f"""
        <h2>⚠ Drift Threshold Exceeded</h2>
        <table border="0" cellpadding="4">
            <tr><td><b>Drift Score:</b></td><td>{drift_score:.4f}</td></tr>
            <tr><td><b>Threshold:</b></td><td>{threshold:.2f}</td></tr>
            <tr><td><b>Latency:</b></td><td>{latency_ms:.2f}ms</td></tr>
            <tr><td><b>Tokens:</b></td><td>{token_count}</td></tr>
            <tr><td><b>Time:</b></td><td>{datetime.now(timezone.utc).isoformat()}</td></tr>
        </table>
        <p>Automated retraining pipeline may have been triggered. Check the dashboard.</p>
        """
        await self._send(subject, body)

    async def send_training_complete(
        self,
        job_name: str,
        status: str,
        model_name: str | None = None,
    ) -> None:
        if not self.configured:
            return

        emoji = "✅" if status == "completed" else "❌" if status == "failed" else "ℹ️"
        subject = f"[Eco-Guard] Training Job {status.upper()}: {job_name}"
        body = f"""
        <h2>{emoji} Training Job {status.title()}</h2>
        <table border="0" cellpadding="4">
            <tr><td><b>Job:</b></td><td>{job_name}</td></tr>
            <tr><td><b>Status:</b></td><td>{status}</td></tr>
            <tr><td><b>Model:</b></td><td>{model_name or "N/A"}</td></tr>
            <tr><td><b>Time:</b></td><td>{datetime.now(timezone.utc).isoformat()}</td></tr>
        </table>
        """
        await self._send(subject, body)

    async def send_weekly_report(self, stats: dict) -> None:
        if not self.configured:
            return

        subject = "[Eco-Guard] Weekly MLOps Report"
        body = f"""
        <h2>📊 Weekly Platform Report</h2>
        <table border="0" cellpadding="4">
            <tr><td><b>Total Requests:</b></td><td>{stats.get("total_requests", 0)}</td></tr>
            <tr><td><b>Avg Latency:</b></td><td>{stats.get("avg_latency_ms", 0)}ms</td></tr>
            <tr><td><b>Total Tokens:</b></td><td>{stats.get("total_tokens", 0)}</td></tr>
            <tr><td><b>Drift Score:</b></td><td>{stats.get("avg_drift", 0):.4f}</td></tr>
            <tr><td><b>Training Jobs:</b></td><td>{stats.get("jobs_total", 0)}</td></tr>
            <tr><td><b>Datasets:</b></td><td>{stats.get("datasets", 0)}</td></tr>
        </table>
        """
        await self._send(subject, body)

    async def _send(self, subject: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)
        msg.attach(MIMEText(html_body, "html"))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls(context=context)
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_email, self.to_emails, msg.as_string())
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")


_notifier: Optional[EmailNotifier] = None


def get_notifier(
    smtp_host: str = "",
    smtp_port: int = 587,
    username: str = "",
    password: str = "",
    from_email: str = "",
    to_emails: list[str] | None = None,
) -> EmailNotifier:
    global _notifier
    if _notifier is None:
        _notifier = EmailNotifier(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            from_email=from_email,
            to_emails=to_emails or [],
        )
    return _notifier
