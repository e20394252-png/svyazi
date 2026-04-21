import csv
import io
import re
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, MatchProfile
from passlib.context import CryptContext

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

    for user in users:
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
        except Exception:
            failed += 1
            continue

    return {"processed": processed, "failed": failed, "total": len(users)}


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
