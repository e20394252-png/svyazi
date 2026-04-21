import csv
import io
import re
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, MatchProfile

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Pre-computed bcrypt hash for "imported_no_login" — imported users can't log in via password
IMPORTED_USER_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGZCNAPLkjGdg5K5dqUi3bKj3Ry"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "svyazi-admin-secret")


def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


def clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits
    if len(digits) == 10:
        return "+7" + digits
    return digits or None


def make_email(name: str, telegram: str, phone: str) -> str:
    """Generate a fake unique email for imported users"""
    if telegram and telegram.strip() and telegram.strip() not in ("-", ""):
        slug = re.sub(r"[^a-zA-Z0-9_]", "", telegram.strip().lstrip("@"))
        if slug:
            return f"{slug}@imported.svyazi.local"
    if phone:
        digits = re.sub(r"\D", "", phone)
        if digits:
            return f"phone{digits}@imported.svyazi.local"
    slug = re.sub(r"[^a-zA-Z0-9]", "_", name.strip().lower())[:30]
    return f"{slug}@imported.svyazi.local"


@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    """
    Import contacts from CSV file.
    Expected columns: FIO, number, Telegram, Occupation
    """
    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        name = (row.get("FIO") or "").strip()
        phone_raw = (row.get("number") or "").strip()
        telegram = (row.get("Telegram") or "").strip()
        occupation = (row.get("Occupation") or "").strip()

        # Skip empty rows
        if not name and not occupation:
            skipped += 1
            continue

        if not name:
            name = telegram or f"User_{i}"

        phone = clean_phone(phone_raw)
        email = make_email(name, telegram, phone)

        # Skip duplicates
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            skipped += 1
            continue

        try:
            user = User(
                name=name,
                email=email,
                password_hash=IMPORTED_USER_HASH,
                telegram=telegram if telegram and telegram not in ("-", "") else None,
                phone=phone,
                occupation=occupation or None,
                bio=occupation or None,  # use occupation as bio for matching
                is_imported=True,
                is_active=True,
            )
            db.add(user)
            db.flush()  # get user.id

            # Create empty match profile (will be filled by AI later)
            profile = MatchProfile(
                user_id=user.id,
                wants=None,
                cans=None,
                has_items=None,
            )
            db.add(profile)
            created += 1
        except Exception as e:
            errors.append(f"Row {i} ({name}): {str(e)}")
            db.rollback()
            continue

    db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors[:20],  # return first 20 errors max
        "total_errors": len(errors),
    }


@router.post("/generate-embeddings")
async def generate_embeddings(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    """
    Trigger AI analysis for all imported users without embeddings.
    Runs in background, returns count of users to process.
    """
    from app.ai_service import analyze_occupation, get_embedding, build_profile_text, extract_tags
    import json
    import asyncio

    users = (
        db.query(User)
        .join(MatchProfile, User.id == MatchProfile.user_id)
        .filter(
            User.is_imported == True,
            User.is_active == True,
            MatchProfile.embedding == None,
        )
        .all()
    )

    processed = 0
    failed = 0
    first_errors = []

    for i, user in enumerate(users):
        try:
            text = user.occupation or user.bio or ""
            if not text:
                continue

            parsed = await analyze_occupation(text)
            profile = user.profile

            profile.wants = parsed.get("wants", "")
            profile.cans = parsed.get("cans", "")
            profile.has_items = parsed.get("has", "")
            profile.wants_tags = await extract_tags(parsed.get("wants", ""))
            profile.cans_tags = await extract_tags(parsed.get("cans", ""))
            profile.has_tags = await extract_tags(parsed.get("has", ""))

            profile_text = await build_profile_text(
                parsed.get("wants", ""),
                parsed.get("cans", ""),
                parsed.get("has", ""),
                text,
            )
            embedding = await get_embedding(profile_text)
            profile.embedding = json.dumps(embedding)
            db.commit()
            processed += 1

            # Rate limit: Gemini free tier 15 RPM/key, 3 keys = 45 RPM
            # 5 calls per user, so sleep 1s per user to stay under limit
            if i % 10 == 9:
                await asyncio.sleep(2)  # brief pause every 10 users

        except Exception as e:
            failed += 1
            if len(first_errors) < 3:
                first_errors.append(f"user_id={user.id}: {type(e).__name__}: {str(e)[:200]}")
            continue

    return {"processed": processed, "failed": failed, "total": len(users), "first_errors": first_errors}


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    total_users = db.query(User).count()
    imported = db.query(User).filter(User.is_imported == True).count()
    with_embeddings = db.query(MatchProfile).filter(MatchProfile.embedding != None).count()
    return {
        "total_users": total_users,
        "imported_users": imported,
        "users_with_embeddings": with_embeddings,
    }


@router.post("/test-ai")
async def test_ai(
    _: None = Depends(verify_admin),
):
    """Diagnose which AI providers and models are functional"""
    import httpx
    from app.config import settings
    from app.ai_service import OPENROUTER_URL, OPENROUTER_MODELS, GEMINI_MODEL_URLS

    results = {}

    # Test OpenRouter models
    for model in OPENROUTER_MODELS:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://svyazi.app",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Say 'ok'"}],
                        "max_tokens": 5,
                    },
                )
                results[f"openrouter/{model}"] = f"{resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            results[f"openrouter/{model}"] = f"ERROR: {str(e)[:100]}"

    # Test Gemini direct
    gemini_keys = [k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",") if k.strip()]
    results["gemini_keys_count"] = len(gemini_keys)
    for i, key in enumerate(gemini_keys):
        for url_tpl in GEMINI_MODEL_URLS[:2]:
            label = f"gemini[key{i+1}]/{url_tpl.split('/')[-1]}"
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        f"{url_tpl}?key={key}",
                        json={"contents": [{"parts": [{"text": "Say ok"}]}], "generationConfig": {"maxOutputTokens": 5}},
                    )
                    results[label] = f"{resp.status_code}: {resp.text[:100]}"
            except Exception as e:
                results[label] = f"ERROR: {str(e)[:100]}"

    return results
