"""Saved rehearsals of the signed-in user. Every query is scoped to the owner: another user's
rehearsal answers 404, the same as one that does not exist."""
from datetime import date
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_proposal import WorkToRehearse, propose_rehearsal
from backend.application.accounts import User
from backend.application.library import LibraryRepository
from backend.application.rehearsals import (Rehearsal, RehearsalBlock, RehearsalDraft, RehearsalRepository,
                                            UnknownWork)
from backend.app.dependencies import authenticated_user, get_library_repository, get_rehearsal_repository
from backend.app.stored_scores import stored_score

router = APIRouter()
NOT_FOUND = "El ensayo no existe."
UNKNOWN_WORK = "Alguna obra del ensayo no existe."

Short = Annotated[str, Field(min_length=1, max_length=80)]


class BlockIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    minutes: int = Field(ge=1, le=600)
    objective: str = Field("", max_length=500)
    work_id: Optional[UUID] = None
    measures: str = Field("", max_length=40)
    sections: list[Short] = Field(default_factory=list, max_length=20)


class RehearsalIn(BaseModel):
    date: date
    time: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: int = Field(ge=10, le=600)
    place: Optional[str] = Field(None, max_length=200)
    objectives: str = Field("", max_length=2000)
    work_ids: list[UUID] = Field(default_factory=list, max_length=50)
    blocks: list[BlockIn] = Field(default_factory=list, max_length=50)

    def draft(self) -> RehearsalDraft:
        if any(block.work_id and block.work_id not in self.work_ids for block in self.blocks):
            raise HTTPException(status_code=422, detail="Cada bloque solo puede usar obras del ensayo.")
        return RehearsalDraft(self.date, self.time, self.duration_minutes, self.place or None, self.objectives,
                              tuple(dict.fromkeys(self.work_ids)),
                              tuple(RehearsalBlock(block.title, block.minutes, block.objective, block.work_id,
                                                   block.measures, tuple(block.sections)) for block in self.blocks))


class ProposalIn(BaseModel):
    work_ids: list[UUID] = Field(default_factory=list, max_length=12)
    duration_minutes: int = Field(ge=10, le=600)


def _rehearsal_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _public(rehearsal: Rehearsal) -> dict:
    draft, titles = rehearsal.draft, dict(rehearsal.works)
    return {"id": str(rehearsal.id), "date": draft.date.isoformat(), "time": draft.time,
            "duration_minutes": draft.duration_minutes, "place": draft.place, "objectives": draft.objectives,
            "works": [{"id": str(work), "title": title} for work, title in rehearsal.works],
            "blocks": [{"title": block.title, "minutes": block.minutes, "objective": block.objective,
                        "work_id": str(block.work_id) if block.work_id else None,
                        "work_title": titles.get(block.work_id), "measures": block.measures,
                        "sections": list(block.sections)} for block in draft.blocks]}


@router.get("/rehearsals")
def list_rehearsals(user: User = Depends(authenticated_user),
                    rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    return {"rehearsals": [_public(item) for item in rehearsals.list_rehearsals(user.id)]}


@router.post("/rehearsals", status_code=201)
def create_rehearsal(body: RehearsalIn, user: User = Depends(authenticated_user),
                     rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    try:
        return _public(rehearsals.create_rehearsal(user.id, body.draft()))
    except UnknownWork:
        raise HTTPException(status_code=422, detail=UNKNOWN_WORK) from None


# Declared before /rehearsals/{rehearsal_id}. Nothing is saved: the director reviews the proposal.
@router.post("/rehearsals/proposal")
def propose(body: ProposalIn, user: User = Depends(authenticated_user),
            library: LibraryRepository = Depends(get_library_repository)):
    works = []
    for work_id in dict.fromkeys(body.work_ids):
        found = stored_score(library, user.id, work_id)
        if found is None:
            raise HTTPException(status_code=422, detail=UNKNOWN_WORK)
        title, score = found
        works.append(WorkToRehearse(str(work_id), title, score, compute_difficulty_score(score)))
    return propose_rehearsal(works, body.duration_minutes)


@router.get("/rehearsals/{rehearsal_id}")
def get_rehearsal(rehearsal_id: str, user: User = Depends(authenticated_user),
                  rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    found = rehearsals.get_rehearsal(user.id, _rehearsal_id(rehearsal_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(found)


@router.put("/rehearsals/{rehearsal_id}")
def update_rehearsal(rehearsal_id: str, body: RehearsalIn, user: User = Depends(authenticated_user),
                     rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    try:
        updated = rehearsals.update_rehearsal(user.id, _rehearsal_id(rehearsal_id), body.draft())
    except UnknownWork:
        raise HTTPException(status_code=422, detail=UNKNOWN_WORK) from None
    if updated is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(updated)


@router.delete("/rehearsals/{rehearsal_id}", status_code=204)
def delete_rehearsal(rehearsal_id: str, user: User = Depends(authenticated_user),
                     rehearsals: RehearsalRepository = Depends(get_rehearsal_repository)):
    if not rehearsals.delete_rehearsal(user.id, _rehearsal_id(rehearsal_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
