"""The AI usage panel (M5, 2026-10-30), only for the administration: calls per model, tokens, estimated cost,
cache hits, latency and rejections by reason, over the last days."""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.accounts import User
from backend.app.dependencies import authenticated_user, get_ai_usage_repository, is_admin

router = APIRouter()
ADMIN_ONLY = "Solo una cuenta administradora puede ver el uso de la IA."


@router.get("/admin/ai-usage")
def ai_usage(days: int = Query(30, ge=1, le=365), user: User = Depends(authenticated_user),
             usage=Depends(get_ai_usage_repository)):
    if not is_admin(user):
        raise HTTPException(status_code=403, detail=ADMIN_ONLY)
    return usage.summary(days)
