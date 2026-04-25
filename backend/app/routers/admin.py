from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.models import User
from app.config import settings
from app.database import get_db

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


@router.get("/users")
def get_admin_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all registered users for admin panel"""
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        # Check if profile was actually filled (has occupation or bio)
        profile_filled = bool(u.occupation or u.bio)
        profile_saved_at = u.updated_at.isoformat() if u.updated_at else None

        result.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "telegram": u.telegram,
            "telegram_id": u.telegram_id if hasattr(u, 'telegram_id') else None,
            "phone": u.phone,
            "city": u.city,
            "auth_method": "telegram" if (hasattr(u, 'telegram_id') and u.telegram_id) else "email",
            "is_admin": u.is_admin,
            "profile_filled": profile_filled,
            "profile_saved_at": profile_saved_at,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if (hasattr(u, 'last_login_at') and u.last_login_at) else None,
        })
    return result
