"""
Email notification service for security incident alerts.

Uses smtplib to send HTML-formatted alert emails via Brevo SMTP.
Dispatched via FastAPI BackgroundTasks as an async task to never block the client.

Recipients are loaded dynamically from the 'users_notification' table on the main
async event loop, avoiding cross-thread pool issues with asyncpg.
Falls back to the static ALERT_RECIPIENT_EMAIL from .env if no active
recipients are found in the database.
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import NotificationRecipient
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Severity levels used to filter which events trigger an email alert.
_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Layer severity mapping: determines the alert level for each blocking layer.
_LAYER_SEVERITY = {
    "layer_1_heuristics": "LOW",
    "layer_2_vectorial": "LOW",
    "layer_3_intelligence": "MEDIUM",
    "layer_5_egress": "HIGH",
}


def _build_html_body(
    user_id: str,
    session_id: str,
    layer: str,
    reason: str,
    score: float | None,
    prompt_excerpt: str,
    timestamp: datetime,
) -> str:
    """
    Builds the HTML body for the security incident alert email.

    Args:
        user_id: The ID of the user who sent the blocked message.
        session_id: The session identifier of the request.
        layer: The pipeline layer that triggered the block.
        reason: Human-readable description of the security event.
        score: AI confidence score, if applicable.
        prompt_excerpt: First 300 characters of the blocked prompt.
        timestamp: UTC datetime when the incident occurred.

    Returns:
        A fully formed HTML string for the email body.
    """
    score_row = (
        f"<tr><td><strong>Confidence Score</strong></td><td>{score:.4f}</td></tr>"
        if score is not None
        else ""
    )
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
        .container {{ background: #fff; border-radius: 8px; padding: 30px; max-width: 600px; margin: auto; }}
        .header {{ background: #b91c1c; color: white; padding: 15px 20px; border-radius: 6px; }}
        .header h2 {{ margin: 0; font-size: 18px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; vertical-align: top; }}
        td:first-child {{ width: 40%; color: #555; font-size: 13px; }}
        .excerpt {{ background: #fef2f2; border-left: 4px solid #b91c1c; padding: 12px; font-size: 13px; color: #333; margin-top: 20px; border-radius: 4px; word-break: break-all; }}
        .footer {{ margin-top: 20px; font-size: 11px; color: #aaa; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header"><h2>SECURITY ALERT: Threat Intercepted by AI Gateway</h2></div>
        <table>
          <tr><td><strong>Timestamp (UTC)</strong></td><td>{timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
          <tr><td><strong>User ID</strong></td><td>{user_id}</td></tr>
          <tr><td><strong>Session ID</strong></td><td>{session_id}</td></tr>
          <tr><td><strong>Layer Activated</strong></td><td>{layer}</td></tr>
          <tr><td><strong>Reason</strong></td><td>{reason}</td></tr>
          {score_row}
        </table>
        <div class="excerpt">
          <strong>Blocked Prompt Excerpt:</strong><br><br>
          {prompt_excerpt}
        </div>
        <div class="footer">
          AI Gateway Perimetral | Automated Security Alert | Do not reply.
        </div>
      </div>
    </body>
    </html>
    """


async def _get_active_recipients(fallback_email: str) -> list[str]:
    """
    Fetches active recipient emails from the database asynchronously.

    Falls back to the static fallback_email if no active recipients exist
    or if the database is unavailable.

    Args:
        fallback_email: Static email from settings.alert_recipient_email.

    Returns:
        List of email addresses to notify.
    """
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(NotificationRecipient.email).where(
                    NotificationRecipient.is_active.is_(True)
                )
            )
            emails = list(result.scalars().all())
            if emails:
                return emails
    except Exception as exc:
        logger.warning(
            "Could not load recipients from DB, falling back to static email: %s", exc
        )

    # Fallback: use the static email configured in .env
    if fallback_email:
        return [fallback_email]
    return []


def _send_smtp_blocking(
    settings: Settings,
    recipients: list[str],
    message_str: str,
    layer: str,
) -> None:
    """
    Executes the blocking SMTP network handshake and send operations.
    Run inside an asyncio worker thread pool via asyncio.to_thread.
    """
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(
                settings.alert_sender_email,
                recipients,
                message_str,
            )
        logger.info(
            "Security alert email sent to %d recipient(s) for event in %s.",
            len(recipients),
            layer,
        )
    except Exception as exc:
        # Email failure must never crash the gateway or surface to the client.
        logger.error("Failed to send security alert email via SMTP: %s", str(exc))


async def send_security_alert(
    settings: Settings,
    user_id: str,
    session_id: str,
    layer: str,
    reason: str,
    prompt: str,
    score: float | None = None,
) -> None:
    """
    Asynchronous security alert email dispatcher via Brevo SMTP.

    Dispatched as a FastAPI BackgroundTask. Because it is an async coroutine,
    FastAPI executes it on the main asyncio event loop, enabling clean,
    thread-safe database queries against asyncpg. The blocking SMTP call is
    offloaded to a worker thread via asyncio.to_thread.

    Args:
        settings: Application configuration settings.
        user_id: User identifier from the request.
        session_id: Session identifier from the request.
        layer: The pipeline layer that blocked the request.
        reason: Description of the security event.
        prompt: The full blocked prompt (only an excerpt is included in the email).
        score: Optional AI classifier confidence score.
    """
    if not settings.smtp_enabled:
        logger.debug("SMTP notifications are disabled. Skipping alert.")
        return

    event_severity = _LAYER_SEVERITY.get(layer, "LOW")
    min_severity = settings.alert_min_severity.upper()

    if _SEVERITY_ORDER.get(event_severity, 0) < _SEVERITY_ORDER.get(min_severity, 0):
        logger.debug(
            "Alert severity %s below threshold %s. Skipping email.",
            event_severity,
            min_severity,
        )
        return

    timestamp = datetime.utcnow()
    prompt_excerpt = (prompt[:300] + "...") if len(prompt) > 300 else prompt
    html_body = _build_html_body(
        user_id, session_id, layer, reason, score, prompt_excerpt, timestamp
    )

    # 1. Fetch active recipient list on the async event loop
    recipients = await _get_active_recipients(settings.alert_recipient_email)

    if not recipients:
        logger.warning("No active notification recipients found. Skipping alert email.")
        return

    # 2. Build email payload
    message = MIMEMultipart("alternative")
    message["Subject"] = f"[SECURITY ALERT] AI Gateway: Threat Blocked by {layer}"
    message["From"] = settings.alert_sender_email
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html"))

    # 3. Offload blocking SMTP network call to a worker thread
    await asyncio.to_thread(
        _send_smtp_blocking,
        settings,
        recipients,
        message.as_string(),
        layer,
    )
