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


@dataclass(frozen=True)
class StoredSession:
    """Server-side session: the browser holds the token, the database only its SHA-256."""
    user_id: UUID
    token_hash: str
    csrf_token: str
    expires_at: datetime


class AccountRepository(Protocol):
    def add_user(self, user: User) -> None: ...
    def user_by_email(self, email: str) -> Optional[User]: ...
    def user_by_id(self, user_id: UUID) -> Optional[User]: ...
    def user_by_google_sub(self, sub: str) -> Optional[User]: ...
    def link_google(self, user_id: UUID, sub: str) -> None: ...
    def rename_user(self, user_id: UUID, display_name: str) -> None: ...
    def add_session(self, session: StoredSession) -> None: ...
    def session_by_token_hash(self, token_hash: str) -> Optional[StoredSession]: ...
    def delete_session(self, token_hash: str) -> None: ...
    def record_event(self, user_id: Optional[UUID], event: str, ip: str) -> None: ...
