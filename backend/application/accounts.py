"""Accounts and sessions: records and the repository port (no database code here)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID


class DuplicateEmail(Exception):
    pass


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    display_name: str
    password_hash: Optional[str] = None
    google_sub: Optional[str] = None
    email_verified: bool = False


@dataclass(frozen=True)
class StoredSession:
    """Server-side session: the browser holds the token, the database only its SHA-256."""
    user_id: UUID
    token_hash: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class EmailVerification:
    """A link that confirms the email of an account: the email carries the token, the database only its SHA-256."""
    user_id: UUID
    token_hash: str
    expires_at: datetime


@dataclass(frozen=True)
class PasswordReset:
    """A password recovery link: the email carries the token, the database only its SHA-256."""
    user_id: UUID
    token_hash: str
    expires_at: datetime


class AccountRepository(Protocol):
    def add_user(self, user: User) -> None: ...
    def user_by_email(self, email: str) -> Optional[User]: ...
    def user_by_id(self, user_id: UUID) -> Optional[User]: ...
    def user_by_google_sub(self, sub: str) -> Optional[User]: ...
    def link_google(self, user_id: UUID, sub: str) -> None: ...
    def rename_user(self, user_id: UUID, display_name: str) -> None: ...
    def set_password_hash(self, user_id: UUID, password_hash: str) -> None: ...
    def delete_user_sessions(self, user_id: UUID) -> None: ...
    def add_session(self, session: StoredSession) -> None: ...
    def session_by_token_hash(self, token_hash: str) -> Optional[StoredSession]: ...
    def delete_session(self, token_hash: str) -> None: ...
    def add_password_reset(self, reset: PasswordReset) -> None: ...
    def password_reset_by_hash(self, token_hash: str) -> Optional[PasswordReset]: ...
    def delete_password_resets(self, user_id: UUID) -> None: ...
    def mark_email_verified(self, user_id: UUID) -> None: ...
    def add_email_verification(self, verification: EmailVerification) -> None: ...
    def email_verification_by_hash(self, token_hash: str) -> Optional[EmailVerification]: ...
    def delete_email_verifications(self, user_id: UUID) -> None: ...
    def record_event(self, user_id: Optional[UUID], event: str, ip: str) -> None: ...
