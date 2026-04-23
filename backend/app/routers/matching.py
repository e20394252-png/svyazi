from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
        "created_at": user.created_at,
    }


@router.post("/find")
async def find_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run matching for current user (vector similarity or text fallback)"""
    profile = current_user.profile

    # ── Step 1: ensure profile exists ──────────────────────────────
    if not profile:
        profile = MatchProfile(user_id=current_user.id)
        db.add(profile)
        db.flush()

    # ── Step 2: AI analysis (optional — proceed even if it fails) ──
    if not profile.wants and not profile.cans:
        text = current_user.bio or current_user.occupation or ""
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Заполните профиль: укажите чем занимаетесь и что ищете"
            )
        try:
            parsed = await analyze_occupation(text)
            profile.wants = parsed["wants"]
            profile.cans = parsed["cans"]
            profile.has_items = parsed["has"]
            try:
                profile.wants_tags = await extract_tags(parsed["wants"])
                profile.cans_tags = await extract_tags(parsed["cans"])
                profile.has_tags = await extract_tags(parsed["has"])
            except Exception:
                pass  # tags are optional
            db.commit()
            db.refresh(current_user)
            profile = current_user.profile
        except Exception:
            db.rollback()
            # AI failed — do text matching on raw occupation text
            profile.wants = ""
            profile.cans = current_user.occupation or current_user.bio or ""

    # ── Step 3: get all candidate profiles ─────────────────────────
    all_profiles = (
        db.query(MatchProfile)
        .filter(MatchProfile.user_id != current_user.id)
        .options(joinedload(MatchProfile.user))
        .all()
    )

    # ── Step 4: calculate similarity (vector if possible, text fallback) ──
    current_text = build_profile_text_local(profile, current_user)
    use_vectors = bool(profile.embedding)

    candidates = []
    for p in all_profiles:
        if not p.user or not p.user.is_active:
            continue
        # Try vector similarity first
        if use_vectors and p.embedding:
            try:
                emb_a = json.loads(profile.embedding)
                emb_b = json.loads(p.embedding)
                sim = cosine_similarity(emb_a, emb_b)
                candidates.append((sim, p.user))
                continue
            except Exception:
                pass
        # Fallback: pure text similarity
        other_text = build_profile_text_local(p, p.user)
        sim = text_similarity(current_text, other_text)
        candidates.append((sim, p.user))

    # ── Step 5: sort & take top 20 ─────────────────────────────────
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = candidates[:20]

    # ── Step 6: AI Reranking («Склеивание») ────────────────────────
    # Format candidates for the reranker
    rerank_list = []
    for sim, candidate_user in top_candidates:
        rerank_list.append({
            "user": get_profile_out(candidate_user),
            "orig_sim": sim
        })
    
    user_profile = get_profile_out(current_user)
    reranked = await rerank_matches(user_profile, rerank_list)
    
    # ── Step 7: Filter & Create Matches ────────────────────────────
    existing_match_ids = {
        m.user2_id
        for m in db.query(Match).filter(Match.user1_id == current_user.id).all()
    }

    created_matches = []
    for i, item in enumerate(reranked):
        candidate_user = top_candidates[i][1]
        if candidate_user.id in existing_match_ids:
            continue

        score = item["score"]
        # Threshold: 30% after AI reranking
        if score < 30:
            continue

        match = Match(
            user1_id=current_user.id,
            user2_id=candidate_user.id,
            score=score,
            reasoning=item["reasoning"],
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
