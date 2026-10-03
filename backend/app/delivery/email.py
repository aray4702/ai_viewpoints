import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()


def send_email(to: str, subject: str, html: str, text: str | None = None) -> None:
    """Send via Resend. Without an API key (local dev), log the message instead."""
    s = get_settings()
    if not s.resend_api_key:
        log.info("email_not_sent_no_key", to=to, subject=subject, text=text or html)
        return
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {s.resend_api_key}"},
        json={"from": s.email_from, "to": [to], "subject": subject, "html": html, "text": text},
        timeout=20,
    )
    resp.raise_for_status()
