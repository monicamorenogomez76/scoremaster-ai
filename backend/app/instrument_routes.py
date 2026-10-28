"""The instrument catalog (2026-10-28): everyone reads it to confirm the instruments of a work; only the
administration (ADMIN_EMAILS) adds or removes the names an instrument is written with and adds common instruments.
The catalog lives in the database, is handed to the resolver at startup and after every change, and its new version
makes the works be analysed again at the next startup."""
import logging
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from backend.analyzers.band_fit import PERCUSSION
from backend.application.accounts import User
from backend.application.instruments import KEYS, REHEARSAL_GROUPS, SECTIONS, DuplicateName, InstrumentRepository
from backend.app.dependencies import authenticated_user, get_instrument_repository, is_admin
from backend.domain.instrument_catalog import (catalog_entries, catalog_version, match_instrument_name,
                                               normalize_instrument_name, seed_instruments, use_catalog)

router = APIRouter()
NOT_FOUND = "El instrumento no existe."
ADMIN_ONLY = "Solo una cuenta administradora puede cambiar el catálogo de instrumentos."
TAKEN = "Ese nombre ya corresponde a {}."
# The soundfont programs playback knows: those of the seed.
SOUNDS = sorted({item["sound"] for item in seed_instruments() if item.get("sound")})


def load_instrument_catalog(repository: InstrumentRepository) -> None:
    """The resolver uses the catalog of the database; without it, or if it cannot be read, the seed."""
    try:
        use_catalog(repository.common() or None)
    except (SQLAlchemyError, ValueError):
        logging.getLogger("uvicorn.error").warning("No se pudo leer el catálogo de instrumentos; se usa el inicial.",
                                                   exc_info=True)


def _admin(user: User):
    if not is_admin(user):
        raise HTTPException(status_code=403, detail=ADMIN_ONLY)


def _name_key(name: str) -> str:
    """The normalized name, refused when empty or when it already names an instrument."""
    key = normalize_instrument_name(name)
    if not re.search(r"[a-z]", key):
        raise HTTPException(status_code=422, detail="El nombre debe tener letras.")
    known = match_instrument_name(name).identity
    if known is not None:
        raise HTTPException(status_code=409, detail=TAKEN.format(known.label_es))
    return key


def _known_sound(value):
    if value is not None and value not in SOUNDS:
        raise ValueError("unknown sound")
    return value


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class InstrumentIn(BaseModel):
    label_es: str = Field(min_length=1, max_length=80)
    label_en: str = Field(min_length=1, max_length=80)
    section: Literal[SECTIONS]
    family: str = Field(pattern=r"^[a-z][a-z_]{0,39}$")
    transposition: Optional[Literal[KEYS]] = None
    sound: Optional[str] = None
    rehearsal_group: Literal[REHEARSAL_GROUPS]
    names: list[str] = Field(min_length=1, max_length=30)

    @field_validator("sound")
    @classmethod
    def known_sound(cls, value):
        return _known_sound(value)

    @field_validator("names")
    @classmethod
    def short_names(cls, value):
        if not all(0 < len(name.strip()) <= 120 for name in value):
            raise ValueError("names must have between 1 and 120 characters")
        return [name.strip() for name in value]


class InstrumentChange(BaseModel):
    label_es: Optional[str] = Field(None, min_length=1, max_length=80)
    label_en: Optional[str] = Field(None, min_length=1, max_length=80)
    sound: Optional[str] = None
    rehearsal_group: Optional[Literal[REHEARSAL_GROUPS]] = None

    @field_validator("sound")
    @classmethod
    def known_sound(cls, value):
        return _known_sound(value)


@router.get("/instruments/catalog")
def instrument_catalog():
    return {"instruments": [{"canonical_id": identity.canonical_id, "label_es": identity.label_es, "section": identity.section}
                            for identity in catalog_entries()],
            "percussion_key": PERCUSSION}


@router.get("/admin/instruments")
def admin_instruments(user: User = Depends(authenticated_user),
                      repository: InstrumentRepository = Depends(get_instrument_repository)):
    _admin(user)
    return {"instruments": [dict(item, canonical_id=item.pop("id")) for item in repository.listing()],
            "version": catalog_version(), "sounds": SOUNDS}


@router.post("/admin/instruments/{instrument_id}/names", status_code=201)
def add_name(body: NameIn, instrument_id: str = Path(..., max_length=80), user: User = Depends(authenticated_user),
             repository: InstrumentRepository = Depends(get_instrument_repository)):
    _admin(user)
    name = body.name.strip()
    try:
        added = repository.add_name(instrument_id, name, _name_key(name))
    except DuplicateName:
        raise HTTPException(status_code=409, detail="Ese nombre ya está en el catálogo.") from None
    if added is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    load_instrument_catalog(repository)
    return added


@router.delete("/admin/instruments/names/{name_id}", status_code=204)
def delete_name(name_id: int, user: User = Depends(authenticated_user),
                repository: InstrumentRepository = Depends(get_instrument_repository)):
    _admin(user)
    if not repository.delete_name(name_id):
        raise HTTPException(status_code=404, detail="El nombre no existe.")
    load_instrument_catalog(repository)
    return Response(status_code=204)


@router.post("/admin/instruments", status_code=201)
def create_instrument(body: InstrumentIn, user: User = Depends(authenticated_user),
                      repository: InstrumentRepository = Depends(get_instrument_repository)):
    _admin(user)
    keys = {}
    for name in body.names:
        keys.setdefault(_name_key(name), name)
    variant = body.transposition.lower() if body.transposition else None
    slug = re.sub(r"[^a-z0-9]+", "_", normalize_instrument_name(body.label_en)).strip("_")[:70] or body.family
    canonical_id = slug + ("." + variant if variant else "")
    fields = {"id": canonical_id, "section": body.section, "family": body.family, "variant": variant,
              "transposition": body.transposition, "label_es": body.label_es.strip(), "label_en": body.label_en.strip(),
              "sound": body.sound, "rehearsal_group": body.rehearsal_group}
    try:
        created = repository.create_instrument(fields, [(name, key) for key, name in keys.items()])
    except DuplicateName:
        raise HTTPException(status_code=409, detail="Ya hay un instrumento con ese nombre en inglés.") from None
    load_instrument_catalog(repository)
    return dict(created, canonical_id=created.pop("id"))


@router.patch("/admin/instruments/{instrument_id}")
def update_instrument(body: InstrumentChange, instrument_id: str = Path(..., max_length=80),
                      user: User = Depends(authenticated_user),
                      repository: InstrumentRepository = Depends(get_instrument_repository)):
    _admin(user)
    changed = repository.update_instrument(instrument_id, body.model_dump(exclude_unset=True))
    if changed is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    load_instrument_catalog(repository)
    return dict(changed, canonical_id=changed.pop("id"))
