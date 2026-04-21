from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from app.database import get_db
from app.models import User, MatchProfile, Match
from app.auth import get_current_user
from app.ai_service import (
    cosine_similarity, generate_match_reasoning,
    get_embedding, build_profile_text, analyze_occupation, extract_tags
)
from typing import List
import json
import asyncio

router = APIRouter(prefix="/api/matches", tags=["matches"])


def get_profile_out(user: User) -> dict:
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


@router.post("/find")
async def find_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run AI matching for current user"""
    profile = current_user.profile

    # If no embedding, auto-analyze first
    if not profile or not profile.embedding:
        text = current_user.bio or current_user.occupation or ""
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Заполните профиль: расскажите о себе, что умеете и что ищете"
            )

        if not profile:
            profile = MatchProfile(user_id=current_user.id)
            db.add(profile)

        try:
            parsed = await analyze_occupation(text)
            profile.wants = parsed["wants"]
            profile.cans = parsed["cans"]
            profile.has_items = parsed["has"]
            profile.wants_tags = await extract_tags(parsed["wants"])
            profile.cans_tags = await extract_tags(parsed["cans"])
            profile.has_tags = await extract_tags(parsed["has"])

            profile_text = await build_profile_text(parsed["wants"], parsed["cans"], parsed["has"], text)
            embedding = await get_embedding(profile_text)
            profile.embedding = json.dumps(embedding)
            db.commit()
            db.refresh(current_user)
            profile = current_user.profile
        except Exception as ai_err:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="AI-сервис временно недоступен. Пополните баланс OpenRouter или повторите позже."
            )

    current_embedding = json.loads(profile.embedding)

    # Get all other users with embeddings
    all_profiles = (
        db.query(MatchProfile)
        .filter(
            MatchProfile.user_id != current_user.id,
            MatchProfile.embedding.isnot(None),
        )
        .options(joinedload(MatchProfile.user))
        .all()
    )

    # Calculate similarities
    candidates = []
    for p in all_profiles:
        if not p.user or not p.user.is_active:
            continue
        try:
            emb = json.loads(p.embedding)
            sim = cosine_similarity(current_embedding, emb)
            candidates.append((sim, p.user))
        except Exception:
            continue

    # Sort by similarity, take top 20
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = candidates[:20]

    # Get existing matches to avoid duplicates
    existing_match_ids = {
        m.user2_id
        for m in db.query(Match).filter(Match.user1_id == current_user.id).all()
    }

    created_matches = []
    for sim, candidate_user in top_candidates:
        if candidate_user.id in existing_match_ids:
            continue

        score = round(sim * 100, 1)
        if score < 30:
            continue

        # Generate reasoning for top matches
        reasoning = ""
        if score >= 50:
            try:
                cp = candidate_user.profile
                reasoning = await generate_match_reasoning(
                    current_user.name,
                    profile.wants or "",
                    profile.cans or "",
                    candidate_user.name,
                    cp.wants if cp else "",
                    cp.cans if cp else "",
                )
            except Exception:
                reasoning = f"Высокое совпадение интересов и направлений деятельности."

        match = Match(
            user1_id=current_user.id,
            user2_id=candidate_user.id,
            score=score,
            reasoning=reasoning,
            status="pending",
        )
        db.add(match)
        created_matches.append(match)

    db.commit()
    return {"message": f"Найдено {len(created_matches)} новых совпадений"}


@router.get("/top")
def get_top_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    matches = (
        db.query(Match)
        .filter(
            Match.user1_id == current_user.id,
            Match.status == "pending",
        )
        .options(joinedload(Match.user2).joinedload(User.profile))
        .order_by(Match.score.desc())
        .limit(50)
        .all()
    )

    result = []
    for m in matches:
        if not m.user2:
            continue
        result.append({
            "id": m.id,
            "user": get_profile_out(m.user2),
            "score": m.score,
            "reasoning": m.reasoning,
            "status": m.status,
            "created_at": m.created_at,
        })
    return result


@router.get("/accepted")
def get_accepted_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mutual accepted matches"""
    my_accepted_ids = {
        m.user2_id
        for m in db.query(Match).filter(
            Match.user1_id == current_user.id,
            Match.status == "accepted"
        ).all()
    }
    their_accepted_ids = {
        m.user1_id
        for m in db.query(Match).filter(
            Match.user2_id == current_user.id,
            Match.status == "accepted"
        ).all()
    }
    mutual_ids = my_accepted_ids & their_accepted_ids

    # Also include one-sided accepted (I accepted them)
    all_accepted_ids = my_accepted_ids

    result = []
    for uid in all_accepted_ids:
        user = db.query(User).options(joinedload(User.profile)).filter(User.id == uid).first()
        if not user:
            continue
        match = db.query(Match).filter(
            Match.user1_id == current_user.id,
            Match.user2_id == uid
        ).first()
        result.append({
            "id": match.id if match else 0,
            "user": get_profile_out(user),
            "score": match.score if match else None,
            "reasoning": match.reasoning if match else None,
            "status": "accepted",
            "is_mutual": uid in mutual_ids,
            "created_at": match.created_at if match else user.created_at,
        })
    return result


@router.get("/incoming")
def get_incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Matches where others accepted me"""
    matches = (
        db.query(Match)
        .filter(
            Match.user2_id == current_user.id,
            Match.status == "accepted",
        )
        .options(joinedload(Match.user1).joinedload(User.profile))
        .order_by(Match.score.desc())
        .all()
    )
    result = []
    for m in matches:
        if not m.user1:
            continue
        result.append({
            "id": m.id,
            "user": get_profile_out(m.user1),
            "score": m.score,
            "reasoning": m.reasoning,
            "status": m.status,
            "created_at": m.created_at,
        })
    return result


@router.get("/awaiting")
def get_awaiting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Matches I accepted but they haven't responded"""
    matches = (
        db.query(Match)
        .filter(
            Match.user1_id == current_user.id,
            Match.status == "accepted",
        )
        .options(joinedload(Match.user2).joinedload(User.profile))
        .order_by(Match.created_at.desc())
        .all()
    )
    result = []
    for m in matches:
        if not m.user2:
            continue
        result.append({
            "id": m.id,
            "user": get_profile_out(m.user2),
            "score": m.score,
            "reasoning": m.reasoning,
            "status": m.status,
            "created_at": m.created_at,
        })
    return result


@router.post("/{match_id}/accept")
def accept_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.user1_id == current_user.id,
    ).first()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    match.status = "accepted"
    db.commit()
    return {"message": "Запрос на знакомство отправлен"}


@router.post("/{match_id}/dismiss")
def dismiss_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    match = db.query(Match).filter(
        Match.id == match_id,
        Match.user1_id == current_user.id,
    ).first()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    match.status = "dismissed"
    db.commit()
    return {"message": "Пропущено"}


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_users = db.query(User).filter(User.is_active == True).count()
    my_matches = db.query(Match).filter(
        Match.user1_id == current_user.id,
        Match.status == "accepted"
    ).count()
    return {
        "total_users": total_users,
        "my_accepted_matches": my_matches,
    }
