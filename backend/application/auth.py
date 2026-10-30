"""Registration, login, sessions (plan phase 1) and password recovery by email (2026-10-29).

Passwords are hashed with Argon2id. A session is a random token held by the browser in an HttpOnly
cookie; the database keeps only its SHA-256, so a leaked table does not open sessions. Unknown
emails and wrong passwords fail the same way, and repeated failures from one address for one email
are throttled. Every session carries its own CSRF token for state-changing requests. A recovery link is a one-time
token kept, like sessions, only as its SHA-256; it expires in 30 minutes and only the last one of an account works.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from backend.application.accounts import AccountRepository, DuplicateEmail, PasswordReset, StoredSession, User

MIN_PASSWORD = 10
MAX_PASSWORD = 256
SESSION_DAYS = 7
RESET_MINUTES = 30
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
INVALID_CREDENTIALS = "Email o contraseña incorrectos."


class InvalidCredentials(Exception):
    pass


class InvalidRegistration(Exception):
    pass


class TooManyAttempts(Exception):
    pass


class InvalidResetLink(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class SignedIn:
    user: User
    token: str
    csrf_token: str
    expires_at: datetime


class LoginLimiter:
    """At most `max_failures` failed logins per email and address within `window` (in memory: one
    process; a shared store would be needed with several workers)."""

    def __init__(self, max_failures: int = 5, window: timedelta = timedelta(minutes=15),
                 clock: Callable[[], datetime] = utcnow):
        self.max_failures, self.window, self.clock = max_failures, window, clock
        self.failures: dict[tuple[str, str], list[datetime]] = defaultdict(list)

    def _recent(self, key):
        limit = self.clock() - self.window
        self.failures[key] = [moment for moment in self.failures[key] if moment > limit]
        return self.failures[key]

    def blocked(self, email: str, ip: str) -> bool:
        return len(self._recent((email, ip))) >= self.max_failures

    def failed(self, email: str, ip: str) -> None:
        self._recent((email, ip)).append(self.clock())

    def succeeded(self, email: str, ip: str) -> None:
        self.failures.pop((email, ip), None)

    def reset(self) -> None:
        self.failures.clear()


class AuthService:
    def __init__(self, accounts: AccountRepository, clock: Callable[[], datetime] = utcnow,
                 limiter: Optional[LoginLimiter] = None, hasher: Optional[PasswordHasher] = None,
                 reset_limiter: Optional[LoginLimiter] = None):
        self.accounts, self.clock = accounts, clock
        self.limiter = limiter or LoginLimiter(clock=clock)
        self.reset_limiter = reset_limiter or LoginLimiter(3, timedelta(hours=1), clock=clock)
        self.hasher = hasher or PasswordHasher()

    def _open_session(self, user: User, event: str, ip: str) -> SignedIn:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = self.clock() + timedelta(days=SESSION_DAYS)
        self.accounts.add_session(StoredSession(user.id, token_hash(token), csrf, expires))
        self.accounts.record_event(user.id, event, ip)
        return SignedIn(user, token, csrf, expires)

    def register(self, email: str, password: str, display_name: str, ip: str) -> SignedIn:
        email = email.strip().lower()
        if not EMAIL.match(email) or not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise InvalidRegistration("Revisa el email y usa una contraseña de al menos 10 caracteres.")
        user = User(uuid4(), email, (display_name or "").strip()[:100] or email.split("@")[0],
                    password_hash=self.hasher.hash(password))
        try:
            self.accounts.add_user(user)
        except DuplicateEmail as exc:
            raise InvalidRegistration("No se pudo crear la cuenta con ese email.") from exc
        return self._open_session(user, "registered", ip)

    def matches(self, user: User, password: str) -> bool:
        try:
            return user.password_hash is not None and self.hasher.verify(user.password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def set_password(self, user: User, password: str, ip: str) -> None:
        """A new password closes every session opened with the previous one."""
        if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise InvalidRegistration("Usa una contraseña de al menos 10 caracteres.")
        self.accounts.set_password_hash(user.id, self.hasher.hash(password))
        self.accounts.delete_user_sessions(user.id)
        self.accounts.record_event(user.id, "password_changed", ip)

    def login(self, email: str, password: str, ip: str) -> SignedIn:
        email = (email or "").strip().lower()
        if self.limiter.blocked(email, ip):
            raise TooManyAttempts("Demasiados intentos. Espera unos minutos.")
        user = self.accounts.user_by_email(email)
        try:
            if user is None or user.password_hash is None:
                # Same work as a real check, so timing does not reveal unknown emails.
                self.hasher.hash(password or "-")
                raise VerificationError()
            self.hasher.verify(user.password_hash, password or "")
        except (VerificationError, InvalidHashError):
            self.limiter.failed(email, ip)
            self.accounts.record_event(user.id if user else None, "login_failed", ip)
            raise InvalidCredentials(INVALID_CREDENTIALS) from None
        self.limiter.succeeded(email, ip)
        return self._open_session(user, "login", ip)

    def request_password_reset(self, email: str, ip: str) -> Optional[tuple[User, str]]:
        """The account and the link's token, or None (unknown email, or three links this hour for that email);
        the caller answers the same either way."""
        email = (email or "").strip().lower()
        if self.reset_limiter.blocked(email, ""):
            return None
        self.reset_limiter.failed(email, "")
        user = self.accounts.user_by_email(email)
        if user is None:
            return None
        token = secrets.token_urlsafe(32)
        self.accounts.add_password_reset(PasswordReset(user.id, token_hash(token),
                                                       self.clock() + timedelta(minutes=RESET_MINUTES)))
        self.accounts.record_event(user.id, "password_reset_requested", ip)
        return user, token

    def reset_password(self, token: str, password: str, ip: str) -> SignedIn:
        reset = self.accounts.password_reset_by_hash(token_hash(token or ""))
        user = self.accounts.user_by_id(reset.user_id) if reset and reset.expires_at > self.clock() else None
        if user is None:
            raise InvalidResetLink("El enlace no es válido o ha caducado. Pide otro.")
        self.set_password(user, password, ip)
        self.accounts.delete_password_resets(user.id)
        return self._open_session(user, "password_reset", ip)

    def google(self, sub: str, email: str, email_verified: bool, name: str, ip: str) -> SignedIn:
        user = self.accounts.user_by_google_sub(sub)
        if user is None:
            email = (email or "").strip().lower()
            existing = self.accounts.user_by_email(email)
            if existing is not None:
                if not email_verified:
                    raise InvalidCredentials("La cuenta de Google no tiene el email verificado.")
                self.accounts.link_google(existing.id, sub)
                user = replace(existing, google_sub=sub)
            else:
                user = User(uuid4(), email, (name or email.split("@")[0])[:100], google_sub=sub)
                self.accounts.add_user(user)
        return self._open_session(user, "login_google", ip)

    def current(self, token: str) -> Optional[tuple[User, StoredSession]]:
        if not token:
            return None
        session = self.accounts.session_by_token_hash(token_hash(token))
        if session is None or session.expires_at <= self.clock():
            return None
        user = self.accounts.user_by_id(session.user_id)
        return (user, session) if user else None

    def logout(self, token: str) -> None:
        current = self.current(token)
        self.accounts.delete_session(token_hash(token))
        if current:
            self.accounts.record_event(current[0].id, "logout", "")
