#!/usr/bin/env python3
"""
Import script for Networkers.csv
Run: python scripts/import_networkers.py
"""
import sys
import os
import asyncio
import json
import csv
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import User, MatchProfile
from app.auth import hash_password
from app.ai_service import analyze_occupation, extract_tags, build_profile_text, get_embedding


CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "Networkers.csv")


async def process_user(user: User, occupation: str, db) -> None:
    """Analyze occupation and generate embedding for a user"""
    if not occupation or not occupation.strip():
        return

    try:
        parsed = await analyze_occupation(occupation)

        profile = db.query(MatchProfile).filter(MatchProfile.user_id == user.id).first()
        if not profile:
            profile = MatchProfile(user_id=user.id)
            db.add(profile)

        profile.wants = parsed["wants"]
        profile.cans = parsed["cans"]
        profile.has_items = parsed["has"]

        profile.wants_tags = await extract_tags(parsed["wants"])
        profile.cans_tags = await extract_tags(parsed["cans"])
        profile.has_tags = await extract_tags(parsed["has"])

        profile_text = await build_profile_text(parsed["wants"], parsed["cans"], parsed["has"], occupation)
        embedding = await get_embedding(profile_text)
        profile.embedding = json.dumps(embedding)
        profile.embedding_updated_at = datetime.now(timezone.utc)

        db.commit()
        print(f"  ✓ {user.name} — обработан")
    except Exception as e:
        print(f"  ✗ {user.name} — ошибка: {e}")
        db.rollback()


async def main():
    print("🚀 Инициализация БД...")
    init_db()

    db = SessionLocal()
    imported = 0
    skipped = 0

    print(f"📂 Читаю CSV: {CSV_PATH}")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"📊 Всего строк: {len(rows)}")

    users_to_process = []

    for row in rows:
        name = (row.get("FIO") or "").strip()
        phone = (row.get("number") or "").strip()
        telegram = (row.get("Telegram") or "").strip()
        occupation = (row.get("Occupation") or "").strip()

        # Skip empty rows
        if not name and not phone:
            continue

        # Build fake email from telegram or phone
        if telegram:
            email = f"{telegram.lower().lstrip('@')}@networkers.import"
        elif phone:
            email = f"user_{phone}@networkers.import"
        else:
            continue

        # Check if already imported
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            skipped += 1
            continue

        # Build phone string
        phone_str = None
        if phone and phone.isdigit() and len(phone) >= 10:
            phone_str = f"+{phone}"

        user = User(
            name=name or telegram or f"Пользователь {phone}",
            email=email,
            password_hash=hash_password("networker2024"),  # default password
            telegram=telegram if telegram else None,
            phone=phone_str,
            occupation=occupation,
            is_imported=True,
        )
        db.add(user)
        db.flush()

        profile = MatchProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)

        imported += 1
        users_to_process.append((user.id, user.name, occupation))
        print(f"  + {user.name}")

    print(f"\n✅ Импортировано: {imported}, пропущено (дубли): {skipped}")
    print(f"\n🤖 Запускаю ИИ-анализ для {len(users_to_process)} пользователей...")
    print("   (Это займёт несколько минут)")

    for i, (user_id, name, occupation) in enumerate(users_to_process, 1):
        print(f"\n[{i}/{len(users_to_process)}] Анализирую: {name}")
        db2 = SessionLocal()
        try:
            user = db2.query(User).filter(User.id == user_id).first()
            await process_user(user, occupation, db2)
        finally:
            db2.close()

        # Small delay to avoid rate limiting
        if i % 10 == 0:
            print("   ⏳ Пауза 2 секунды...")
            await asyncio.sleep(2)

    print("\n🎉 Готово! База нетворкеров импортирована и проанализирована.")


if __name__ == "__main__":
    asyncio.run(main())
