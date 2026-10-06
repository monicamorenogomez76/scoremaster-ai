"""Bands of the signed-in director: several fixed templates, one active. Every query is scoped to the
owner: another user's band answers 404."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from backend.application.accounts import User
from backend.application.bands import SECTION_GROUPS, Band, BandDraft, BandRepository
from backend.app.dependencies import authenticated_user, get_band_repository
from backend.app.library_routes import valid_band_profile

router = APIRouter()
NOT_FOUND = "La banda no existe."


class BandIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    locality: Optional[str] = Field(None, max_length=200)
    place: Optional[str] = Field(None, max_length=200)
    rehearsal_weekdays: list[int] = Field(default_factory=list, max_length=7)
    rehearsal_time: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    rehearsal_minutes: Optional[int] = Field(None, ge=10, le=600)
    profile: dict = Field(default_factory=dict)
    section_levels: dict = Field(default_factory=dict)

    @field_validator("rehearsal_weekdays")
    @classmethod
    def weekdays(cls, value: list[int]) -> list[int]:
        if any(day not in range(7) for day in value):
            raise ValueError("Los días de ensayo van de 0 (lunes) a 6 (domingo).")
        return sorted(set(value))

    @field_validator("profile")
    @classmethod
    def template(cls, value: dict) -> dict:
        if not valid_band_profile(value):
            raise ValueError("La plantilla debe indicar músicos (0–1000) por instrumento.")
        return value

    @field_validator("section_levels")
    @classmethod
    def levels(cls, value: dict) -> dict:
        if any(key not in SECTION_GROUPS or type(level) is not int or not 1 <= level <= 6 for key, level in value.items()):
            raise ValueError("El nivel de cada sección va de 1 a 6.")
        return value

    def draft(self) -> BandDraft:
        return BandDraft(self.name.strip(), self.locality or None, self.place or None, tuple(self.rehearsal_weekdays),
                         self.rehearsal_time, self.rehearsal_minutes, self.profile, self.section_levels)


def _band_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _public(band: Band) -> dict:
    draft = band.draft
    return {"id": str(band.id), "name": draft.name, "locality": draft.locality, "place": draft.place,
            "rehearsal_weekdays": list(draft.rehearsal_weekdays), "rehearsal_time": draft.rehearsal_time,
            "rehearsal_minutes": draft.rehearsal_minutes, "profile": draft.profile, "section_levels": draft.section_levels,
            "active": band.active}


def _found(band: Optional[Band]) -> dict:
    if band is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(band)


@router.get("/bands")
def list_bands(user: User = Depends(authenticated_user), bands: BandRepository = Depends(get_band_repository)):
    return {"bands": [_public(band) for band in bands.list_bands(user.id)]}


@router.post("/bands", status_code=201)
def create_band(body: BandIn, user: User = Depends(authenticated_user), bands: BandRepository = Depends(get_band_repository)):
    return _public(bands.create_band(user.id, body.draft()))


@router.get("/bands/{band_id}")
def get_band(band_id: str, user: User = Depends(authenticated_user), bands: BandRepository = Depends(get_band_repository)):
    return _found(bands.get_band(user.id, _band_id(band_id)))


@router.put("/bands/{band_id}")
def update_band(band_id: str, body: BandIn, user: User = Depends(authenticated_user),
                bands: BandRepository = Depends(get_band_repository)):
    return _found(bands.update_band(user.id, _band_id(band_id), body.draft()))


@router.post("/bands/{band_id}/activate")
def activate_band(band_id: str, user: User = Depends(authenticated_user), bands: BandRepository = Depends(get_band_repository)):
    """The active band is the template of the analyses and BandFit."""
    return _found(bands.activate_band(user.id, _band_id(band_id)))


@router.delete("/bands/{band_id}", status_code=204)
def delete_band(band_id: str, user: User = Depends(authenticated_user), bands: BandRepository = Depends(get_band_repository)):
    if not bands.delete_band(user.id, _band_id(band_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
