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

# In-memory job tracker (per user)
_matching_jobs = {}  # user_id -> {status, message, saved, log, ...}


@router.get("/status")
def get_matching_status(
    current_user: User = Depends(get_current_user),
):
    """Статус текущего процесса мэтчинга"""
    job = _matching_jobs.get(current_user.id)
    if not job:
        return {"status": "idle", "message": "Нет активного поиска"}
    return job


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
    """Запуск поиска мэтчей — мгновенный ответ, работа в фоне"""
    from app.config import settings

    # ── Проверяем заполненность профиля ───────────────────
    profile = current_user.profile
    has_profile = (
        (profile and profile.wants and profile.wants.strip())
        or (profile and profile.cans and profile.cans.strip())
        or (profile and profile.has_items and profile.has_items.strip())
        or (current_user.occupation and current_user.occupation.strip())
    )
    if not has_profile:
        raise HTTPException(
            status_code=400,
            detail="Сначала заполните профиль: укажите что вы хотите, можете или имеете"
        )

    if not profile:
        profile = MatchProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()

    # ── Выбираем вебхук в зависимости от активной базы ────
    if settings.ACTIVE_DATABASE == "new":
        webhook_url = settings.N8N_MATCHING_WEBHOOK_URL_NEW
    else:
        webhook_url = settings.N8N_MATCHING_WEBHOOK_URL

    if not webhook_url:
        raise HTTPException(status_code=500, detail="Webhook URL n8n не настроен для выбранной базы")

    # Очищаем старые мэтчи
    db.query(Match).filter(Match.user1_id == current_user.id).delete()
    db.commit()

    # Собираем данные для отправки
    user_id = current_user.id
    payload = {"user": get_profile_out(current_user)}

    # ── Фоновая задача: вызвать n8n → дождаться ответа → сохранить ──
    async def _background_matching():
        import httpx
        import json as json_lib
        from app.database import SessionLocal
        from datetime import datetime, timezone

        job = _matching_jobs[user_id]
        job["status"] = "sending"
        job["message"] = "Отправляем запрос в ИИ..."
        job["started_at"] = datetime.now(timezone.utc).isoformat()

        data = None
        last_error = None

        # Ретрай до 3 раз
        async with httpx.AsyncClient(timeout=300.0) as client:
            for attempt in range(1, 4):
                try:
                    job["message"] = f"Запрос в ИИ (попытка {attempt}/3)..."
                    print(f"MATCH [{user_id}]: n8n attempt {attempt}/3")
                    response = await client.post(webhook_url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    print(f"MATCH [{user_id}]: n8n responded OK, status={response.status_code}")
                    break
                except httpx.TimeoutException:
                    job["message"] = "Таймаут ИИ (300 сек)"
                    job["status"] = "error"
                    print(f"MATCH [{user_id}]: n8n timeout")
                    break
                except Exception as e:
                    last_error = str(e)
                    print(f"MATCH [{user_id}]: attempt {attempt} failed: {e}")
                    if attempt < 3:
                        job["message"] = f"Ошибка, повтор через {5*attempt} сек..."
                        await asyncio.sleep(5 * attempt)

        if data is None:
            job["status"] = "error"
            job["message"] = f"Ошибка n8n: {last_error or 'timeout'}"
            print(f"MATCH [{user_id}]: FAILED: {last_error}")
            return

        job["status"] = "parsing"
        job["message"] = "Получен ответ, парсим..."

        # ── Парсим ответ ──────────────────────────────────────
        matches_data = []

        def extract_matches(item):
            if not isinstance(item, dict): return []
            if "telegram" in item and "score" in item: return [item]
            if "user_id" in item and "score" in item: return [item]
            if "choices" in item:
                try:
                    content = item["choices"][0]["message"]["content"]
                    clean = content.replace("```json", "").replace("```", "").strip()
                    parsed = json_lib.loads(clean)
                    if isinstance(parsed, dict):
                        res = parsed.get("matches", [])
                        return res if isinstance(res, list) else [res]
                    elif isinstance(parsed, list):
                        return parsed
                except Exception as parse_err:
                    print(f"MATCH [{user_id}]: Parse error in choices: {parse_err}")
                    pass
            if "matches" in item:
                m = item["matches"]
                return m if isinstance(m, list) else [m]
            return []

        if isinstance(data, list):
            for entry in data:
                matches_data.extend(extract_matches(entry))
        elif isinstance(data, dict):
            matches_data = extract_matches(data)

        print(f"MATCH [{user_id}]: Extracted {len(matches_data)} raw match items")
        job["raw_found"] = len(matches_data)
        job["message"] = f"ИИ нашёл {len(matches_data)} кандидатов, сохраняем..."

        if not matches_data:
            job["status"] = "done"
            job["saved"] = 0
            job["message"] = "ИИ не нашёл подходящих мэтчей"
            return

        # ── Сохраняем в базу (новая сессия!) ─────────────────
        job["status"] = "saving"
        bg_db = SessionLocal()
        try:
            saved = 0
            skipped = 0
            not_found = 0
            log_details = []

            for item in matches_data:
                tg_handle = item.get("telegram", "").replace("@", "").strip()
                try:
                    score = float(item.get("score", 0))
                except (ValueError, TypeError):
                    score = 0
                reasoning = item.get("reasoning", "")

                # ── Фильтр качества: минимальный порог 30% ────
                if score < 30:
                    log_details.append(f"⛔ @{tg_handle} score={score} < 30 — отброшен")
                    skipped += 1
                    continue

                target_user = None
                if tg_handle:
                    target_user = bg_db.query(User).filter(User.telegram.ilike(f"%{tg_handle}%")).first()

                if not target_user:
                    log_details.append(f"❌ @{tg_handle} score={score} — НЕ НАЙДЕН в БД")
                    not_found += 1
                    continue

                if target_user.id == user_id:
                    log_details.append(f"⚠️ @{tg_handle} — это сам юзер, пропуск")
                    continue

                # ── Фильтр: пропускаем кандидатов с пустым профилем ──
                tp = target_user.profile
                has_content = (
                    (tp and tp.wants and tp.wants.strip())
                    or (tp and tp.cans and tp.cans.strip())
                    or (target_user.occupation and target_user.occupation.strip())
                )
                if not has_content:
                    log_details.append(f"⚠️ @{tg_handle} score={score} — пустой профиль, пропуск")
                    skipped += 1
                    continue

                new_match = Match(
                    user1_id=user_id,
                    user2_id=target_user.id,
                    score=score,
                    reasoning=reasoning,
                    status="pending"
                )
                bg_db.add(new_match)
                log_details.append(f"✅ @{tg_handle} score={score} — СОХРАНЁН (user_id={target_user.id})")
                saved += 1

            bg_db.commit()

            job["saved"] = saved
            job["skipped"] = skipped
            job["not_found"] = not_found
            job["log"] = log_details
            job["status"] = "done"
            job["message"] = f"Готово! Сохранено {saved} мэтчей" + (f", пропущено {skipped}" if skipped else "") + (f", не найдено {not_found}" if not_found else "")

            print(f"MATCH [{user_id}]: DONE — saved={saved}, skipped={skipped}, not_found={not_found}")
            for line in log_details:
                print(f"MATCH [{user_id}]: {line}")

        except Exception as e:
            bg_db.rollback()
            job["status"] = "error"
            job["message"] = f"Ошибка БД: {str(e)}"
            print(f"MATCH [{user_id}]: DB error: {e}")
        finally:
            bg_db.close()

    # Инициализируем трекер
    _matching_jobs[user_id] = {"status": "queued", "message": "Запрос в очереди..."}

    # Запускаем фоновую задачу и СРАЗУ отвечаем
    asyncio.create_task(_background_matching())
    return {"message": "Поиск запущен! Следите за статусом на странице."}


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
