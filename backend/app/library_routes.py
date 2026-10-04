"""Works and band template of the signed-in user. Every query is scoped to the owner: another
user's work answers 404, the same as a work that does not exist."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from backend.application.accounts import User
from backend.application.library import LibraryRepository, Work
from backend.app.dependencies import authenticated_user, get_library_repository

router = APIRouter()
NOT_FOUND = "La obra no existe."
MAX_MUSICIANS = 1000
MAX_PROFILE_ENTRIES = 256


def valid_band_profile(profile) -> bool:
    """Instrument key → number of musicians."""
    return isinstance(profile, dict) and len(profile) <= MAX_PROFILE_ENTRIES and all(
        isinstance(key, str) and len(key) <= 200 and type(count) is int and 0 <= count <= MAX_MUSICIANS
        for key, count in profile.items())


class BandUpdate(BaseModel):
    profile: dict


def _work_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _public(work: Work) -> dict:
    return {"id": str(work.id), "title": work.title, "composer": work.composer, "file_name": work.file_name,
            "size": work.size, "updated_at": work.updated_at.isoformat() if work.updated_at else None,
            "summary": work.summary}


@router.get("/works")
def list_works(user: User = Depends(authenticated_user), library: LibraryRepository = Depends(get_library_repository)):
    return {"works": [_public(work) for work in library.list_works(user.id)]}


@router.get("/works/{work_id}")
def get_work(work_id: str, user: User = Depends(authenticated_user),
             library: LibraryRepository = Depends(get_library_repository)):
    record = library.latest_analysis(user.id, _work_id(work_id))
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return {**record.result, "analysis_id": str(record.analysis_id), "work_id": work_id}


@router.get("/works/{work_id}/file")
def work_file(work_id: str, user: User = Depends(authenticated_user),
              library: LibraryRepository = Depends(get_library_repository)):
    found = library.work_file(user.id, _work_id(work_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content, file_name = found
    safe_name = "".join(character for character in file_name if character.isalnum() or character in "._- ") or "obra.musicxml"
    return Response(content=content, media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="{}"'.format(safe_name)})


@router.delete("/works/{work_id}", status_code=204)
def delete_work(work_id: str, user: User = Depends(authenticated_user),
                library: LibraryRepository = Depends(get_library_repository)):
    if not library.delete_work(user.id, _work_id(work_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)


@router.get("/band")
def get_band(user: User = Depends(authenticated_user), library: LibraryRepository = Depends(get_library_repository)):
    return {"profile": library.band_profile(user.id)}


@router.patch("/band")
def update_band(update: BandUpdate, user: User = Depends(authenticated_user),
                library: LibraryRepository = Depends(get_library_repository)):
    if not valid_band_profile(update.profile):
        raise HTTPException(status_code=400, detail="La plantilla debe indicar músicos (0–1000) por instrumento.")
    return {"profile": library.update_band_profile(user.id, update.profile)}
