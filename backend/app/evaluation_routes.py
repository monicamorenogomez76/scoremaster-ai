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
from backend.app.dependencies import (authenticated_user, get_evaluation_repository, get_review_provider,
                                      get_library_repository, get_score_store)
from backend.analyzers.passage_features import FEATURES_VERSION, passage_features
from backend.application import llm_review_jobs
from backend.application.llm_review import PROMPT_VERSION as REVIEW_PROMPT_VERSION, review_passage
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


def _owner_view(campaign: Campaign, reviews: Optional[list] = None) -> dict:
    """The owner sees ScoreLint's prediction and, when it has run, the LLM's independent review (newest)."""
    latest = {}
    for review in reviews or []:
        latest.setdefault(review["passage_id"], review)
    return {**_summary(campaign, "owner"), "instructions": campaign.instructions,
            "passages": [{"id": str(item.id), "work_id": str(item.work_id), "work_title": item.work_title,
                          "parts": list(item.parts), "measure_range": item.measure_range, "label": item.label,
                          "snapshot": item.snapshot, "llm_review": latest.get(str(item.id))} for item in campaign.passages],
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
                    library: LibraryRepository = Depends(get_library_repository),
                    score_store=Depends(get_score_store)):
    """Proposes the passages of the chosen works from their stored analysis; the director reviews them."""
    samples = []
    for work_id in dict.fromkeys(body.work_ids):
        found, latest = stored_score(library, user.id, work_id, score_store), library.latest_analysis(user.id, work_id)
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
        return _owner_view(owned, evaluations.llm_reviews(user.id, owned.id))
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


def _reviewing(provider) -> bool:
    return provider.info.kind == "llm" and hasattr(provider, "review_passage")


def _current(review: dict, provider) -> bool:
    return (review["provider"], review["model"], review["prompt_version"], review["features_version"]) == \
        (provider.info.name, provider.info.model, REVIEW_PROMPT_VERSION, FEATURES_VERSION)


def _review_status(campaign: Campaign, reviews: list, provider) -> dict:
    available = _reviewing(provider)
    done = {item["passage_id"] for item in reviews if available and _current(item, provider)}
    running = llm_review_jobs.job(campaign.id)
    return {"available": available, "provider": provider.info.name if available else None,
            "model": provider.info.model if available else None, "prompt_version": REVIEW_PROMPT_VERSION,
            "features_version": FEATURES_VERSION, "state": running.state if running else "idle",
            "done": len(done & {str(item.id) for item in campaign.passages}), "total": len(campaign.passages),
            "failed": running.failed if running else 0, "last_error": running.last_error if running else None}


@router.get("/evaluations/{campaign_id}/llm-review")
def llm_review_status(campaign_id: str, user: User = Depends(authenticated_user),
                      evaluations: EvaluationRepository = Depends(get_evaluation_repository),
                      provider=Depends(get_review_provider)):
    """How far the independent review of the LLM (method B, step 22) has gone."""
    campaign = _owned(evaluations, user, campaign_id)
    return _review_status(campaign, evaluations.llm_reviews(user.id, campaign.id) or [], provider)


@router.post("/evaluations/{campaign_id}/llm-review", status_code=202)
def start_llm_review(campaign_id: str, user: User = Depends(authenticated_user),
                     evaluations: EvaluationRepository = Depends(get_evaluation_repository),
                     library: LibraryRepository = Depends(get_library_repository),
                     score_store=Depends(get_score_store), provider=Depends(get_review_provider)):
    """Asks the LLM about every passage still without a review with the current versions, in the background."""
    campaign = _owned(evaluations, user, campaign_id)
    if not _reviewing(provider):
        raise HTTPException(status_code=409, detail="La valoración con IA necesita configurar GEMINI_API_KEY en el servidor.")
    reviews = evaluations.llm_reviews(user.id, campaign.id) or []
    done = {item["passage_id"] for item in reviews if _current(item, provider)}
    todo = [item for item in campaign.passages if str(item.id) not in done]
    scores = {}

    def review(passage):
        if passage.work_id not in scores:
            found = stored_score(library, user.id, passage.work_id, score_store)
            if found is None:
                raise ValueError("La obra del pasaje ya no está en el repertorio.")
            scores[passage.work_id] = found[1]
        features = passage_features(scores[passage.work_id], passage.parts[0], passage.measure_range)
        return review_passage(features, provider), features

    def save(passage, reviewed, features):
        evaluations.save_llm_review(user.id, campaign.id, passage.id, reviewed, features)

    llm_review_jobs.start(campaign.id, todo, review, save)
    return _review_status(campaign, reviews, provider)
