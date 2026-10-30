"""Email for password recovery (2026-10-29). Brevo's API sends from a sender address verified in Brevo, with no
domain of its own (free plan: 300 emails a day). In development, without Brevo, the message goes to the server's
log; in production, without Brevo or the public address the links point to, there is no recovery."""
from __future__ import annotations

import logging
import os
from email.utils import parseaddr
from typing import Optional

import httpx

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoMailer:
    def __init__(self, api_key: str, sender: str, client: Optional[httpx.Client] = None):
        name, email = parseaddr(sender)
        self.api_key, self.sender = api_key, {"name": name or "ScoreMaster", "email": email}
        self.client = client or httpx.Client(timeout=10)

    def send(self, to: str, subject: str, text: str) -> None:
        response = self.client.post(BREVO_URL, headers={"api-key": self.api_key, "accept": "application/json"},
                                    json={"sender": self.sender, "to": [{"email": to}], "subject": subject,
                                          "textContent": text})
        response.raise_for_status()


class LogMailer:
    """Development only: the message, link included, is written to the log instead of being sent."""

    def send(self, to: str, subject: str, text: str) -> None:
        logging.getLogger("uvicorn.error").info("Correo para %s (sin enviar, desarrollo): %s\n%s", to, subject, text)


def mailer_from_env():
    if os.environ.get("BREVO_API_KEY") and os.environ.get("MAIL_FROM") and os.environ.get("APP_BASE_URL"):
        return BrevoMailer(os.environ["BREVO_API_KEY"], os.environ["MAIL_FROM"])
    if os.environ.get("APP_ENV") != "production":
        return LogMailer()
    return None
