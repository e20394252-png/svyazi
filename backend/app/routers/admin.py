from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.models import User
from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только для администратора")
    return current_user


@router.get("/settings")
def get_admin_settings(admin: User = Depends(require_admin)):
    return {
        "active_database": settings.ACTIVE_DATABASE,
        "n8n_matching_webhook": settings.N8N_MATCHING_WEBHOOK_URL or "",
        "n8n_matching_webhook_new": settings.N8N_MATCHING_WEBHOOK_URL_NEW or "",
        "n8n_profile_webhook": settings.N8N_PROFILE_WEBHOOK_URL or "",
    }


@router.post("/settings")
def update_admin_settings(
    data: dict,
    admin: User = Depends(require_admin),
):
    if "active_database" in data:
        value = data["active_database"]
        if value not in ("networkers", "new"):
            raise HTTPException(status_code=400, detail="Допустимые значения: networkers, new")
        settings.ACTIVE_DATABASE = value

    return {
        "message": f"Настройки обновлены. Активная база: {settings.ACTIVE_DATABASE}",
        "active_database": settings.ACTIVE_DATABASE,
    }
