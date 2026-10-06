"""Concerts of the signed-in user: programme, rehearsal pattern and the rehearsals that prepare it.
Every query is scoped to the owner: another user's concert answers 404."""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.analyzers.concert_plan import ReviewedBlock, Slot, phases, plan_concert, rehearsal_dates
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_proposal import WorkToRehearse
from backend.application.accounts import User
from backend.application.bands import UnknownBand
from backend.application.concerts import Concert, ConcertDraft, ConcertRepository, RehearsalPattern
from backend.application.library import LibraryRepository
from backend.application.rehearsals import NotReplannable, RehearsalRepository, UnknownWork, replannable
from backend.app.dependencies import (authenticated_user, get_concert_repository, get_library_repository,
                                      get_rehearsal_repository)
from backend.app.rehearsal_routes import RehearsalIn, _public as rehearsal_public
from backend.app.stored_scores import stored_score

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
    band_id: Optional[UUID] = None

    def draft(self) -> ConcertDraft:
        return ConcertDraft(self.title.strip(), self.date, self.time, self.place or None, self.notes,
                            tuple(dict.fromkeys(self.work_ids)), self.schedule.pattern() if self.schedule else None,
                            self.band_id)


def _concert_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _public(concert: Concert, rehearsals: RehearsalRepository, user: User) -> dict:
    draft, pattern = concert.draft, concert.draft.schedule
    return {"id": str(concert.id), "title": draft.title, "date": draft.date.isoformat(), "time": draft.time,
            "place": draft.place, "notes": draft.notes,
            "band": {"id": str(concert.band[0]), "name": concert.band[1]} if concert.band else None,
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
    except UnknownBand:
        raise HTTPException(status_code=422, detail="La banda del concierto no existe.") from None


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
    except UnknownBand:
        raise HTTPException(status_code=422, detail="La banda del concierto no existe.") from None
    if updated is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(updated, rehearsals, user)


@router.delete("/concerts/{concert_id}", status_code=204)
def delete_concert(concert_id: str, user: User = Depends(authenticated_user),
                   concerts: ConcertRepository = Depends(get_concert_repository)):
    if not concerts.delete_concert(user.id, _concert_id(concert_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)


class PlanIn(BaseModel):
    # The director's day: rehearsals before it are not planned again.
    today: date


class PlannedRehearsalIn(RehearsalIn):
    id: Optional[UUID] = None


class ConcertPlanIn(PlanIn):
    rehearsals: list[PlannedRehearsalIn] = Field(default_factory=list, max_length=60)


def _owned_concert(concerts: ConcertRepository, user: User, concert_id: str) -> Concert:
    found = concerts.get_concert(user.id, _concert_id(concert_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return found


@router.post("/concerts/{concert_id}/plan")
def propose_concert_plan(concert_id: str, body: PlanIn, user: User = Depends(authenticated_user),
                         concerts: ConcertRepository = Depends(get_concert_repository),
                         rehearsals: RehearsalRepository = Depends(get_rehearsal_repository),
                         library: LibraryRepository = Depends(get_library_repository)):
    """The series up to the concert, or the rest of it after a review. Nothing is saved."""
    concert = _owned_concert(concerts, user, concert_id)
    series = rehearsals.list_rehearsals(user.id, concert.id)
    if series:
        series_phases = phases(len(series))
        slots = [(item.id, Slot(item.draft.date, item.draft.time, item.draft.duration_minutes, phase))
                 for item, phase in zip(series, series_phases) if replannable(item, body.today)]
    else:
        pattern = concert.draft.schedule
        if pattern is None:
            raise HTTPException(status_code=422, detail="Indica los días de ensayo del concierto para proponer la planificación.")
        dates = rehearsal_dates(max(pattern.start_date, body.today), concert.draft.date, pattern.weekdays)
        slots = [(None, Slot(day, pattern.time, pattern.duration_minutes, phase)) for day, phase in zip(dates, phases(len(dates)))]
    programme = []
    for work_id, _ in concert.works:
        found = stored_score(library, user.id, work_id)
        if found is not None:
            title, score = found
            programme.append(WorkToRehearse(str(work_id), title, score, compute_difficulty_score(score)))
    reviews = [ReviewedBlock(str(block.work_id), block.measures, block.review.status)
               for item in series if item.reviewed_at for block in item.draft.blocks if block.review and block.work_id]
    plans = plan_concert(programme, [slot for _, slot in slots], reviews)
    planned_ids = {rehearsal_id for rehearsal_id, _ in slots if rehearsal_id}
    return {"rehearsals": [{"id": str(rehearsal_id) if rehearsal_id else None, **plan} for (rehearsal_id, _), plan in zip(slots, plans)],
            "kept": [str(item.id) for item in series if item.id not in planned_ids]}


@router.put("/concerts/{concert_id}/rehearsals")
def save_concert_plan(concert_id: str, body: ConcertPlanIn, user: User = Depends(authenticated_user),
                      concerts: ConcertRepository = Depends(get_concert_repository),
                      rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    """Saves the reviewed series: new rehearsals, or the replannable ones replaced, all or nothing."""
    concert = _owned_concert(concerts, user, concert_id)
    try:
        saved = rehearsals.save_concert_plan(user.id, concert.id, [(item.id, item.draft()) for item in body.rehearsals], body.today)
    except UnknownWork:
        raise HTTPException(status_code=422, detail="Alguna obra del ensayo no existe.") from None
    except NotReplannable:
        raise HTTPException(status_code=422, detail="Un ensayo ya revisado, pasado o fijo no se replanifica.") from None
    return {"rehearsals": [rehearsal_public(item) for item in saved]}
