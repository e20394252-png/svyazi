from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from app.database import get_db
from app.models import User, MatchProfile, Match
from app.auth import get_current_user
from app.ai_service import (
    cosine_similarity, generate_match_reasoning,
    get_embedding, build_profile_text, analyze_occupation, extract_tags,
    rerank_matches
)
from typing import List
import json
import asyncio
import re
import math
from collections import Counter

router = APIRouter(prefix="/api/matches", tags=["matches"])


def text_similarity(a: str, b: str) -> float:
    """Russian keyword similarity with basic root/substring matching"""
    def get_roots(text: str) -> set:
        tokens = re.findall(r'[а-яёa-z0-9]+', (text or "").lower())
        # Basic stemming: take first 6 chars for long words
        return set(w[:6] if len(w) > 5 else w for w in tokens if len(w) > 3)

    a_roots = get_roots(a)
    b_roots = get_roots(b)
    
    if not a_roots or not b_roots:
        return 0.0
        
    intersection = a_roots.intersection(b_roots)
    union = a_roots.union(b_roots)
    
    # Jaccard index for roots
    score = len(intersection) / len(union) if union else 0.0
    
    # Boost if there is an exact keyword match for short important words
    a_tokens = set(re.findall(r'[а-яёa-z0-9]+', (a or "").lower()))
    b_tokens = set(re.findall(r'[а-яёa-z0-9]+', (b or "").lower()))
    if a_tokens.intersection(b_tokens):
        score += 0.1 # 10% bonus for exact word match
        
    return min(score, 1.0)


def build_profile_text_local(profile: MatchProfile, user: User) -> str:
    parts = list(filter(None, [
        profile.wants if profile else "",
        profile.cans if profile else "",
        profile.has_items if profile else "",
        user.occupation or "",
        user.bio or "",
    ]))
    return " ".join(parts)


def clean_field(text) -> str:
    """Return None if text is garbled (encoding issue from CSV import)"""
    if not text:
        return None
    text = str(text)
    q_ratio = text.count('?') / max(len(text), 1)
    return None if q_ratio > 0.2 else text


def get_profile_out(user: User) -> dict:
    profile = user.profile
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "telegram": user.telegram,
        "phone": user.phone,
        "occupation": clean_field(user.occupation),
        "bio": clean_field(user.bio),
        "city": user.city,
        "wants": profile.wants if profile else None,
        "cans": profile.cans if profile else None,
        "has_items": profile.has_items if profile else None,
        "wants_tags": profile.wants_tags if profile else [],
        "cans_tags": profile.cans_tags if profile else [],
        "has_tags": profile.has_tags if profile else [],
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/find")
async def find_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Триггер для запуска поиска мэтчей в n8n (Асинхронно)"""
    from app.config import settings
    import httpx

    # Ensure profile exists
    profile = current_user.profile
    if not profile:
        profile = MatchProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()

    if not settings.N8N_MATCHING_WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="Webhook URL n8n не настроен в конфигурации (N8N_MATCHING_WEBHOOK_URL)")

    # Очищаем старые мэтчи СРАЗУ при запуске нового поиска
    db.query(Match).filter(Match.user1_id == current_user.id).delete()
    db.commit()

    payload = {
        "user": get_profile_out(current_user),
        "callback_url": f"{settings.BACKEND_URL}/api/matches/callback?user_id={current_user.id}"
    }

    async def trigger_n8n():
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                await client.post(settings.N8N_MATCHING_WEBHOOK_URL, json=payload)
            except Exception as e:
                print(f"DEBUG: Failed to trigger n8n: {e}")

    asyncio.create_task(trigger_n8n())

    return {"message": "Поиск запущен! Старые мэтчи удалены. Новые появятся здесь в течение 1-2 минут."}


@router.post("/callback")
async def matching_callback(
    user_id: int,
    data: Any = Body(...),
    db: Session = Depends(get_db),
):
    """Прием результатов от n8n"""
    # ── Процесс парсинга ────────────────────────────────────────
    import json
    matches_data = []
    
    def extract_matches(item):
        if not isinstance(item, dict): return []
        if "telegram" in item: return [item]
        if "user_id" in item and "score" in item: return [item]
        if "choices" in item:
            try:
                content = item["choices"][0]["message"]["content"]
                clean_content = content.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_content)
                if isinstance(parsed, dict):
                    res = parsed.get("matches", [])
                    return res if isinstance(res, list) else [res]
                elif isinstance(parsed, list):
                    return parsed
            except Exception: pass
        return []

    if isinstance(data, list):
        for entry in data: matches_data.extend(extract_matches(entry))
    elif isinstance(data, dict):
        matches_data = data.get("matches", []) if "matches" in data else extract_matches(data)

    # ── Сохранение ──────────────────────────────────────────────
    processed_count = 0
    for item in matches_data:
        tg_handle = item.get("telegram", "").replace("@", "").strip()
        score = float(item.get("score", 0))
        reasoning = item.get("reasoning", "")
        
        target_user = None
        if tg_handle:
            target_user = db.query(User).filter(User.telegram.ilike(f"%{tg_handle}%")).first()
        
        if not target_user or target_user.id == user_id:
            continue
            
        # Добавляем мэтч (без удаления, так как удалили в /find)
        new_match = Match(
            user1_id=user_id,
            user2_id=target_user.id,
            score=score,
            reasoning=reasoning,
            status="pending"
        )
        db.add(new_match)
        processed_count += 1
    
    db.commit()
    print(f"DEBUG CALLBACK: Added {processed_count} matches for user {user_id}")
    return {"status": "success", "added": processed_count}


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
        raise HTTPException(status_code=404, detail="Мэтч не найден")
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
        raise HTTPException(status_code=404, detail="Мэтч не найден")
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
