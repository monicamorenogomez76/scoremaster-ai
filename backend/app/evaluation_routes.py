"""Evaluation campaigns (steps 16-18). The owner manages passages, invitations and status and exports
the results; an invited musician (by the email of their account) rates the passages without seeing
ScoreLint's prediction. Anyone else gets 404, the same as a campaign that does not exist."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from backend.analyzers.evaluation_sample import WorkSample, propose_passages
from backend.application.accounts import User
from backend.application.evaluations import (EXPERIENCE_LEVELS, Campaign, CampaignLocked, EvaluationRepository,
                                             Rating)
from backend.application.library import LibraryRepository
from backend.app.dependencies import authenticated_user, get_evaluation_repository, get_library_repository
from backend.app.stored_scores import stored_score

router = APIRouter()
NOT_FOUND = "La campaña no existe."


class CampaignIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field("", max_length=2000)
    work_ids: list[UUID] = Field(min_length=1, max_length=20)
    size: int = Field(50, ge=10, le=80)


class InvitationsIn(BaseModel):
    emails: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("emails")
    @classmethod
    def addresses(cls, value: list[str]) -> list[str]:
        if any(len(item) > 254 or "@" not in item for item in value if item.strip()):
            raise ValueError("Indica emails válidos.")
        return value


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def known(cls, value: str) -> str:
        if value not in ("open", "closed"):
            raise ValueError("La campaña solo se abre o se cierra.")
        return value


class ProfileIn(BaseModel):
    experience_level: str
    main_instrument: str = Field(min_length=1, max_length=100)

    @field_validator("experience_level")
    @classmethod
    def level(cls, value: str) -> str:
        if value not in EXPERIENCE_LEVELS:
            raise ValueError("Nivel de experiencia desconocido.")
        return value


class RatingIn(BaseModel):
    difficulty: int = Field(ge=1, le=6)
    critical: bool
    priority: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=500)


def _id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _summary(campaign: Campaign, role: str) -> dict:
    done = len(campaign.ratings) if role == "evaluator" else sum(item.rated for item in campaign.invitations)
    return {"id": str(campaign.id), "title": campaign.title, "status": campaign.status, "role": role,
            "passages": len(campaign.passages), "rated": done, "invitations": len(campaign.invitations)}


def _owner_view(campaign: Campaign) -> dict:
    return {**_summary(campaign, "owner"), "instructions": campaign.instructions,
            "passages": [{"id": str(item.id), "work_id": str(item.work_id), "work_title": item.work_title,
                          "parts": list(item.parts), "measure_range": item.measure_range, "label": item.label,
                          "snapshot": item.snapshot} for item in campaign.passages],
            "invitations": [{"email": item.email, "rated": item.rated, "profile_done": item.experience_level is not None}
                            for item in campaign.invitations]}


def _evaluator_view(campaign: Campaign) -> dict:
    """Never the snapshot: the musician rates without ScoreLint's prediction."""
    rating = lambda item: (None if item is None else
                           {"difficulty": item.difficulty, "critical": item.critical, "priority": item.priority,
                            "comment": item.comment})
    return {**_summary(campaign, "evaluator"), "instructions": campaign.instructions,
            "profile": {"experience_level": campaign.own.experience_level, "main_instrument": campaign.own.main_instrument},
            "passages": [{"id": str(item.id), "work_id": str(item.work_id), "work_title": item.work_title,
                          "parts": list(item.parts), "measure_range": item.measure_range, "label": item.label,
                          "rating": rating(campaign.ratings.get(item.id))} for item in campaign.passages]}


def _owned(evaluations: EvaluationRepository, user: User, campaign_id: str) -> Campaign:
    found = evaluations.for_owner(user.id, _id(campaign_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return found


@router.post("/evaluations", status_code=201)
def create_campaign(body: CampaignIn, user: User = Depends(authenticated_user),
                    evaluations: EvaluationRepository = Depends(get_evaluation_repository),
                    library: LibraryRepository = Depends(get_library_repository)):
    """Proposes the passages of the chosen works from their stored analysis; the director reviews them."""
    samples = []
    for work_id in dict.fromkeys(body.work_ids):
        found, latest = stored_score(library, user.id, work_id), library.latest_analysis(user.id, work_id)
        if found is None or latest is None:
            raise HTTPException(status_code=422, detail="Alguna obra no existe o no tiene análisis.")
        title, score = found
        samples.append(WorkSample(str(work_id), title, score, latest.result.get("difficulty", {})))
    passages = propose_passages(samples, body.size)
    return _owner_view(evaluations.create_campaign(user.id, body.title.strip(), body.instructions.strip(), passages))


@router.get("/evaluations")
def list_campaigns(user: User = Depends(authenticated_user),
                   evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    return {"owned": [_summary(item, "owner") for item in evaluations.owned(user.id)],
            "invited": [_summary(item, "evaluator") for item in evaluations.invited(user.email)]}


@router.get("/evaluations/{campaign_id}")
def get_campaign(campaign_id: str, user: User = Depends(authenticated_user),
                 evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    owned = evaluations.for_owner(user.id, _id(campaign_id))
    if owned is not None:
        return _owner_view(owned)
    invited = evaluations.for_evaluator(user.email, _id(campaign_id))
    if invited is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _evaluator_view(invited)


@router.delete("/evaluations/{campaign_id}/passages/{passage_id}", status_code=204)
def delete_passage(campaign_id: str, passage_id: str, user: User = Depends(authenticated_user),
                   evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    try:
        deleted = evaluations.delete_passage(user.id, _id(campaign_id), _id(passage_id))
    except CampaignLocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if not deleted:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)


@router.put("/evaluations/{campaign_id}/invitations")
def set_invitations(campaign_id: str, body: InvitationsIn, user: User = Depends(authenticated_user),
                    evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    updated = evaluations.set_invitations(user.id, _id(campaign_id), body.emails)
    if updated is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _owner_view(updated)


@router.post("/evaluations/{campaign_id}/status")
def set_status(campaign_id: str, body: StatusIn, user: User = Depends(authenticated_user),
               evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    updated = evaluations.set_status(user.id, _id(campaign_id), body.status)
    if updated is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _owner_view(updated)


@router.put("/evaluations/{campaign_id}/profile")
def set_profile(campaign_id: str, body: ProfileIn, user: User = Depends(authenticated_user),
                evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    if not evaluations.set_profile(user.email, _id(campaign_id), body.experience_level, body.main_instrument.strip()):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return {"experience_level": body.experience_level, "main_instrument": body.main_instrument.strip()}


@router.put("/evaluations/{campaign_id}/passages/{passage_id}/rating")
def rate(campaign_id: str, passage_id: str, body: RatingIn, user: User = Depends(authenticated_user),
         evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    try:
        saved = evaluations.rate(user.email, _id(campaign_id), _id(passage_id),
                                 Rating(body.difficulty, body.critical, body.priority, body.comment.strip()))
    except CampaignLocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if not saved:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return body.model_dump()


@router.get("/evaluations/{campaign_id}/works/{work_id}/file")
def work_file(campaign_id: str, work_id: str, user: User = Depends(authenticated_user),
              evaluations: EvaluationRepository = Depends(get_evaluation_repository),
              library: LibraryRepository = Depends(get_library_repository)):
    """The whole work (author's decision): for the owner, from the library; for an invited musician, of a passage."""
    found = library.work_file(user.id, _id(work_id)) or evaluations.evaluator_work_file(user.email, _id(campaign_id), _id(work_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content, file_name = found
    safe_name = "".join(character for character in file_name if character.isalnum() or character in "._- ") or "obra.musicxml"
    return Response(content=content, media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="{}"'.format(safe_name)})


@router.get("/evaluations/{campaign_id}/export")
def export(campaign_id: str, user: User = Depends(authenticated_user),
           evaluations: EvaluationRepository = Depends(get_evaluation_repository)):
    exported = evaluations.export(user.id, _id(campaign_id))
    if exported is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return exported
