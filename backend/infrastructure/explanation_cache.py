"""Valid AI explanations, by the key of backend/application/explanations.cache_key (step 23)."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.infrastructure.analysis_repository import Base


class StoredExplanation(Base):
    __tablename__ = 'ai_explanations'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    answer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PostgresExplanationCache:
    def __init__(self, engine: Engine):
        self.engine = engine

    def load(self, key: str) -> Optional[dict]:
        with Session(self.engine) as session:
            return session.scalar(select(StoredExplanation.answer).where(StoredExplanation.key == key))

    def save(self, key: str, answer: dict) -> None:
        statement = insert(StoredExplanation).values(key=key, answer=answer)
        with Session(self.engine) as session, session.begin():
            session.execute(statement.on_conflict_do_update(index_elements=[StoredExplanation.key],
                                                            set_={"answer": answer, "created_at": func.now()}))
