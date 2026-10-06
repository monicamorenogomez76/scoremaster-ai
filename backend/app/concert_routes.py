"""Concerts of the signed-in user: programme, rehearsal pattern and the rehearsals that prepare it.
Every query is scoped to the owner: another user's concert answers 404."""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.application.accounts import User
from backend.application.concerts import Concert, ConcertDraft, ConcertRepository, RehearsalPattern
from backend.application.rehearsals import RehearsalRepository, UnknownWork
from backend.app.dependencies import authenticated_user, get_concert_repository, get_rehearsal_repository

router = APIRouter()
NOT_FOUND = "El concierto no existe."
TIME = r"^([01]\d|2[0-3]):[0-5]\d$"


class PatternIn(BaseModel):
    weekdays: list[int] = Field(min_length=1, max_length=7)
    time: str = Field(pattern=TIME)
    duration_minutes: int = Field(ge=10, le=600)
    start_date: date

    def pattern(self) -> RehearsalPattern:
        if any(day not in range(7) for day in self.weekdays):
            raise HTTPException(status_code=422, detail="Los días de ensayo van de 0 (lunes) a 6 (domingo).")
        return RehearsalPattern(tuple(sorted(set(self.weekdays))), self.time, self.duration_minutes, self.start_date)


class ConcertIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: date
    time: Optional[str] = Field(None, pattern=TIME)
    place: Optional[str] = Field(None, max_length=200)
    notes: str = Field("", max_length=2000)
    work_ids: list[UUID] = Field(default_factory=list, max_length=30)
    schedule: Optional[PatternIn] = None

    def draft(self) -> ConcertDraft:
        return ConcertDraft(self.title.strip(), self.date, self.time, self.place or None, self.notes,
                            tuple(dict.fromkeys(self.work_ids)), self.schedule.pattern() if self.schedule else None)


def _concert_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _public(concert: Concert, rehearsals: RehearsalRepository, user: User) -> dict:
    draft, pattern = concert.draft, concert.draft.schedule
    return {"id": str(concert.id), "title": draft.title, "date": draft.date.isoformat(), "time": draft.time,
            "place": draft.place, "notes": draft.notes,
            "works": [{"id": str(work), "title": title} for work, title in concert.works],
            "schedule": None if pattern is None else {"weekdays": list(pattern.weekdays), "time": pattern.time,
                                                      "duration_minutes": pattern.duration_minutes,
                                                      "start_date": pattern.start_date.isoformat()},
            "rehearsals": [{"id": str(item.id), "date": item.draft.date.isoformat(), "time": item.draft.time,
                            "phase": item.draft.phase, "fixed": item.draft.fixed, "reviewed": item.reviewed_at is not None}
                           for item in rehearsals.list_rehearsals(user.id, concert.id)]}


@router.get("/concerts")
def list_concerts(user: User = Depends(authenticated_user), concerts: ConcertRepository = Depends(get_concert_repository),
                  rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    return {"concerts": [_public(item, rehearsals, user) for item in concerts.list_concerts(user.id)]}


@router.post("/concerts", status_code=201)
def create_concert(body: ConcertIn, user: User = Depends(authenticated_user),
                   concerts: ConcertRepository = Depends(get_concert_repository),
                   rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    try:
        return _public(concerts.create_concert(user.id, body.draft()), rehearsals, user)
    except UnknownWork:
        raise HTTPException(status_code=422, detail="Alguna obra del programa no existe.") from None


@router.get("/concerts/{concert_id}")
def get_concert(concert_id: str, user: User = Depends(authenticated_user),
                concerts: ConcertRepository = Depends(get_concert_repository),
                rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    found = concerts.get_concert(user.id, _concert_id(concert_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(found, rehearsals, user)


@router.put("/concerts/{concert_id}")
def update_concert(concert_id: str, body: ConcertIn, user: User = Depends(authenticated_user),
                   concerts: ConcertRepository = Depends(get_concert_repository),
                   rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    try:
        updated = concerts.update_concert(user.id, _concert_id(concert_id), body.draft())
    except UnknownWork:
        raise HTTPException(status_code=422, detail="Alguna obra del programa no existe.") from None
    if updated is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(updated, rehearsals, user)


@router.delete("/concerts/{concert_id}", status_code=204)
def delete_concert(concert_id: str, user: User = Depends(authenticated_user),
                   concerts: ConcertRepository = Depends(get_concert_repository)):
    if not concerts.delete_concert(user.id, _concert_id(concert_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
