import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


def send_external_notification(message: str, investigation_id: int, recipient_email: str | None) -> None:
    """Send configured assignment/status notices; leave delivery disabled by default."""
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if slack_webhook:
        try:
            payload = json.dumps({"text": message}).encode("utf-8")
            request = Request(
                slack_webhook,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=8) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Slack returned HTTP {response.status}")
        except Exception as error:
            logger.warning(
                "Could not deliver Slack notification for investigation %s (%s)",
                investigation_id,
                type(error).__name__,
            )

    smtp_host = os.getenv("NOTIFICATION_SMTP_HOST", "").strip()
    sender = os.getenv("NOTIFICATION_EMAIL_FROM", "").strip()
    if not (smtp_host and sender and recipient_email):
        return

    email = EmailMessage()
    email["Subject"] = f"Incident investigation update #{investigation_id}"
    email["From"] = sender
    email["To"] = recipient_email
    email.set_content(f"{message}\n\nOpen investigation #{investigation_id} in Incident Investigator.")
    try:
        port = int(os.getenv("NOTIFICATION_SMTP_PORT", "587"))
        if os.getenv("NOTIFICATION_SMTP_SSL", "false").lower() == "true":
            with smtplib.SMTP_SSL(smtp_host, port, timeout=8, context=ssl.create_default_context()) as client:
                _send_email(client, email)
        else:
            with smtplib.SMTP(smtp_host, port, timeout=8) as client:
                client.starttls(context=ssl.create_default_context())
                _send_email(client, email)
    except Exception as error:
        logger.warning(
            "Could not deliver email notification for investigation %s (%s)",
            investigation_id,
            type(error).__name__,
        )


def _send_email(client: smtplib.SMTP, email: EmailMessage) -> None:
    username = os.getenv("NOTIFICATION_SMTP_USERNAME", "")
    password = os.getenv("NOTIFICATION_SMTP_PASSWORD", "")
    if username:
        client.login(username, password)
    client.send_message(email)
