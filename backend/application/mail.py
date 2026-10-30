"""The port for sending email (password recovery, 2026-10-29); the providers live in infrastructure."""
from typing import Protocol


class Mailer(Protocol):
    def send(self, to: str, subject: str, text: str) -> None: ...
