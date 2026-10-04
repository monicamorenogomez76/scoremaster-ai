from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, delete, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.accounts import DuplicateEmail, StoredSession, User
from backend.infrastructure.analysis_repository import Base


class StoredUser(Base):
    __tablename__ = 'users'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredSessionRow(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                                          nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'),
                                                    nullable=True)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _user(row: Optional[StoredUser]) -> Optional[User]:
    if row is None:
        return None
    return User(row.id, row.email, row.display_name, row.password_hash, row.google_sub)


class PostgresAccountRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def add_user(self, user: User) -> None:
        try:
            with Session(self.engine) as session, session.begin():
                session.add(StoredUser(id=user.id, email=user.email, display_name=user.display_name,
                                       password_hash=user.password_hash, google_sub=user.google_sub))
        except IntegrityError as exc:
            raise DuplicateEmail(user.email) from exc

    def _one_user(self, condition) -> Optional[User]:
        with Session(self.engine) as session:
            return _user(session.scalars(select(StoredUser).where(condition)).first())

    def user_by_email(self, email: str) -> Optional[User]:
        return self._one_user(StoredUser.email == email)

    def user_by_id(self, user_id: UUID) -> Optional[User]:
        return self._one_user(StoredUser.id == user_id)

    def user_by_google_sub(self, sub: str) -> Optional[User]:
        return self._one_user(StoredUser.google_sub == sub)

    def link_google(self, user_id: UUID, sub: str) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(update(StoredUser).where(StoredUser.id == user_id).values(google_sub=sub))

    def add_session(self, stored: StoredSession) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(StoredSessionRow(token_hash=stored.token_hash, user_id=stored.user_id,
                                         csrf_token=stored.csrf_token, expires_at=stored.expires_at))

    def session_by_token_hash(self, token_hash: str) -> Optional[StoredSession]:
        with Session(self.engine) as session:
            row = session.get(StoredSessionRow, token_hash)
            return StoredSession(row.user_id, row.token_hash, row.csrf_token, row.expires_at) if row else None

    def delete_session(self, token_hash: str) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(delete(StoredSessionRow).where(StoredSessionRow.token_hash == token_hash))

    def record_event(self, user_id: Optional[UUID], event: str, ip: str) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(AuditEvent(user_id=user_id, event=event, ip=(ip or "")[:64]))
