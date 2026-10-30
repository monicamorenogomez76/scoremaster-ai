"""PostgreSQL record of the AI usage (M5, 2026-10-30) and its summary for the administration."""
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Identity, Integer, String, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.ai_usage import UsageEvent
from backend.infrastructure.analysis_repository import Base


class AiUsageRow(Base):
    __tablename__ = 'ai_usage'
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                                                 index=True)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


def _price(name: str) -> Optional[float]:
    """Dollars per million tokens, from GEMINI_PRICE_INPUT_PER_MTOK / GEMINI_PRICE_OUTPUT_PER_MTOK (the free tier
    costs nothing; a paid plan sets its prices)."""
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return None


def _p95(values: list[int]) -> Optional[int]:
    """Nearest rank: the value 95 % of the calls do not exceed."""
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None


class PostgresAiUsageRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def record(self, event: UsageEvent) -> None:
        fields = dict(event.__dict__)
        if fields["created_at"] is None:
            del fields["created_at"]   # the database's time
        with Session(self.engine) as session, session.begin():
            session.add(AiUsageRow(**fields))

    def summary(self, days: int = 30) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with Session(self.engine) as session:
            rows = session.scalars(select(AiUsageRow).where(AiUsageRow.created_at >= since)).all()
        prices = _price("GEMINI_PRICE_INPUT_PER_MTOK"), _price("GEMINI_PRICE_OUTPUT_PER_MTOK")
        priced = None not in prices
        calls = [row for row in rows if row.event == "call"]
        models = []
        for model in sorted({row.model for row in calls}):
            mine = [row for row in calls if row.model == model]
            tokens_in = sum(row.input_tokens or 0 for row in mine)
            tokens_out = sum(row.output_tokens or 0 for row in mine)
            latencies = [row.latency_ms for row in mine if row.latency_ms is not None]
            models.append({
                "model": model, "calls": len(mine), "failed": sum(row.outcome != "ok" for row in mine),
                "input_tokens": tokens_in, "output_tokens": tokens_out,
                "latency_ms": {"average": round(sum(latencies) / len(latencies)) if latencies else None, "p95": _p95(latencies)},
                "estimated_cost": tokens_in * prices[0] / 1e6 + tokens_out * prices[1] / 1e6 if priced else None,
            })
        count = lambda items, key: {value: sum(getattr(item, key) == value for item in items)
                                    for value in sorted({getattr(item, key) for item in items})}
        return {
            "days": days, "priced": priced, "models": models,
            "purposes": [{"purpose": purpose, "calls": total} for purpose, total in count(calls, "purpose").items()],
            "failures": count([row for row in calls if row.outcome != "ok"], "outcome"),
            "cache_hits": sum(row.event == "cache_hit" for row in rows),
            "rejected": count([row for row in rows if row.event == "rejected"], "outcome"),
        }
