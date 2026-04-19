from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, MatchProfile
from app.schemas import ProfileOut, ProfileUpdate
from app.auth import get_current_user
from app.ai_service import analyze_occupation, extract_tags, build_profile_text, get_embedding
import json
from datetime import datetime, timezone

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def build_profile_out(user: User) -> dict:
    profile = user.profile
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "telegram": user.telegram,
        "phone": user.phone,
        "occupation": user.occupation,
        "bio": user.bio,
        "city": user.city,
        "wants": profile.wants if profile else None,
        "cans": profile.cans if profile else None,
        "has_items": profile.has_items if profile else None,
        "wants_tags": profile.wants_tags if profile else [],
        "cans_tags": profile.cans_tags if profile else [],
        "has_tags": profile.has_tags if profile else [],
        "created_at": user.created_at,
    }


@router.get("/me", response_model=ProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return build_profile_out(current_user)


@router.get("/{user_id}", response_model=ProfileOut)
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return build_profile_out(user)


@router.put("/me", response_model=ProfileOut)
def update_my_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Update user fields
    for field in ["name", "telegram", "phone", "occupation", "bio", "city"]:
        value = getattr(data, field)
        if value is not None:
            setattr(current_user, field, value)

    # Update profile fields
    profile = current_user.profile
    if not profile:
        profile = MatchProfile(user_id=current_user.id)
        db.add(profile)

    for field in ["wants", "cans", "has_items"]:
        value = getattr(data, field)
        if value is not None:
            setattr(profile, field, value)

    db.commit()
    db.refresh(current_user)
    return build_profile_out(current_user)


@router.post("/me/analyze")
async def analyze_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Use AI to parse occupation into Wants/Cans/Has and generate embedding"""
    if not current_user.occupation and not current_user.bio:
        raise HTTPException(status_code=400, detail="Заполните описание деятельности")

    text = current_user.bio or current_user.occupation or ""

    # AI analysis
    parsed = await analyze_occupation(text)

    profile = current_user.profile
    if not profile:
        profile = MatchProfile(user_id=current_user.id)
        db.add(profile)

    profile.wants = parsed["wants"]
    profile.cans = parsed["cans"]
    profile.has_items = parsed["has"]

    # Extract tags
    profile.wants_tags = await extract_tags(parsed["wants"])
    profile.cans_tags = await extract_tags(parsed["cans"])
    profile.has_tags = await extract_tags(parsed["has"])

    # Generate embedding
    profile_text = await build_profile_text(
        parsed["wants"], parsed["cans"], parsed["has"], text
    )
    embedding = await get_embedding(profile_text)
    profile.embedding = json.dumps(embedding)
    profile.embedding_updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(current_user)
    return {"message": "Профиль обновлён", "profile": build_profile_out(current_user)}


@router.post("/me/update-embedding")
async def update_embedding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate embedding for current profile state"""
    profile = current_user.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Профиль не заполнен")

    profile_text = await build_profile_text(
        profile.wants or "", profile.cans or "", profile.has_items or "", current_user.occupation or ""
    )
    embedding = await get_embedding(profile_text)
    profile.embedding = json.dumps(embedding)
    profile.embedding_updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": "Embedding обновлён"}
