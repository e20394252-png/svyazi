"""
Telegram Bot Auth Router
─────────────────────────
Flow:
1. Frontend calls POST /api/auth/telegram/init  → gets {code, bot_url}
2. User opens bot link (t.me/matchig_auth_bot?start=CODE)
3. Bot receives /start CODE via webhook → confirms the code with telegram data
4. Frontend polls GET /api/auth/telegram/check?code=CODE → gets {access_token}
"""

import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, MatchProfile, TelegramAuthCode
from app.auth import create_access_token, hash_password
from app.config import settings

router = APIRouter(prefix="/api/auth/telegram", tags=["telegram-auth"])

# Codes expire after 10 minutes
CODE_TTL_MINUTES = 10


def _generate_code() -> str:
    """Generate a 6-char alphanumeric code"""
    return secrets.token_urlsafe(4)[:6].upper()


@router.post("/init")
def telegram_auth_init(db: Session = Depends(get_db)):
    """Generate a one-time code for Telegram auth"""
    code = _generate_code()

    # Make sure code is unique
    while db.query(TelegramAuthCode).filter(TelegramAuthCode.code == code).first():
        code = _generate_code()

    auth_code = TelegramAuthCode(code=code)
    db.add(auth_code)
    db.commit()

    bot_username = settings.TELEGRAM_BOT_USERNAME
    bot_url = f"https://t.me/{bot_username}?start={code}"

    return {"code": code, "bot_url": bot_url}


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Telegram Bot Webhook — receives updates from Telegram.
    Parses /start CODE messages and confirms the auth code.
    """
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    # Extract message
    message = data.get("message", {})
    text = message.get("text", "")
    from_user = message.get("from", {})

    telegram_id = from_user.get("id")
    first_name = from_user.get("first_name", "")
    last_name = from_user.get("last_name", "")
    username = from_user.get("username", "")

    full_name = f"{first_name} {last_name}".strip() or username or str(telegram_id)

    print(f"TG WEBHOOK: text={text!r}, user={full_name} (@{username}), id={telegram_id}")

    # Handle /start CODE
    if text and text.startswith("/start "):
        code = text.split(" ", 1)[1].strip()

        auth_entry = db.query(TelegramAuthCode).filter(
            TelegramAuthCode.code == code,
            TelegramAuthCode.confirmed == False,
            TelegramAuthCode.used == False,
        ).first()

        if auth_entry:
            # Check TTL
            created = auth_entry.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)

            if (now - created) < timedelta(minutes=CODE_TTL_MINUTES):
                auth_entry.telegram_id = telegram_id
                auth_entry.telegram_username = username
                auth_entry.telegram_name = full_name
                auth_entry.confirmed = True
                db.commit()
                print(f"TG WEBHOOK: Code {code} confirmed for @{username}")

                # Send confirmation message to user
                await _send_telegram_message(
                    telegram_id,
                    f"✅ Код подтверждён!\n\nВозвращайтесь на сайт — вход выполнен автоматически."
                )
            else:
                print(f"TG WEBHOOK: Code {code} expired")
                await _send_telegram_message(
                    telegram_id,
                    "⏰ Код истёк. Вернитесь на сайт и нажмите «Войти через Telegram» заново."
                )
        else:
            print(f"TG WEBHOOK: Code {code} not found or already used")
            await _send_telegram_message(
                telegram_id,
                "❌ Код не найден или уже использован. Попробуйте ещё раз на сайте."
            )
    elif text and text.strip() == "/start":
        # User clicked Start without a code
        await _send_telegram_message(
            telegram_id,
            "👋 Привет! Чтобы войти, нажмите «Войти через Telegram» на сайте Связи."
        )

    return {"ok": True}


@router.get("/check")
def telegram_auth_check(code: str, db: Session = Depends(get_db)):
    """
    Frontend polls this endpoint to check if the Telegram bot confirmed the code.
    If confirmed — find/create user and return JWT token.
    """
    auth_entry = db.query(TelegramAuthCode).filter(
        TelegramAuthCode.code == code
    ).first()

    if not auth_entry:
        raise HTTPException(status_code=404, detail="Код не найден")

    # Check TTL
    created = auth_entry.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    if (now - created) > timedelta(minutes=CODE_TTL_MINUTES):
        raise HTTPException(status_code=410, detail="Код истёк")

    if auth_entry.used:
        raise HTTPException(status_code=410, detail="Код уже использован")

    if not auth_entry.confirmed:
        # Not yet confirmed — frontend should keep polling
        return {"status": "waiting"}

    # ── Confirmed! Find or create user ──────────────────
    auth_entry.used = True

    tg_id = auth_entry.telegram_id
    tg_username = auth_entry.telegram_username or ""
    tg_name = auth_entry.telegram_name or "Telegram User"

    # 1. Try to find by telegram_id
    user = db.query(User).filter(User.telegram_id == tg_id).first()

    # 2. Try to find by @username match
    if not user and tg_username:
        user = db.query(User).filter(
            User.telegram.ilike(f"%{tg_username}%")
        ).first()
        if user:
            user.telegram_id = tg_id  # link the telegram_id

    # 3. Create new user
    if not user:
        # Generate a unique placeholder email
        placeholder_email = f"tg_{tg_id}@telegram.local"
        user = User(
            name=tg_name,
            email=placeholder_email,
            password_hash=hash_password(secrets.token_urlsafe(16)),  # random password
            telegram=f"@{tg_username}" if tg_username else None,
            telegram_id=tg_id,
        )
        db.add(user)
        db.flush()

        # Create empty match profile
        profile = MatchProfile(user_id=user.id)
        db.add(profile)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return {"status": "ok", "access_token": token, "token_type": "bearer"}


async def _send_telegram_message(chat_id: int, text: str):
    """Send a message via Telegram Bot API"""
    if not settings.TELEGRAM_BOT_TOKEN:
        print(f"TG SEND: No bot token, skipping message to {chat_id}")
        return

    import httpx

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
            print(f"TG SEND: status={resp.status_code}")
    except Exception as e:
        print(f"TG SEND: Error sending message: {e}")


@router.get("/setup-webhook")
async def setup_webhook():
    """Manually (re)set the Telegram webhook — useful after redeploys"""
    if not settings.TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set"}

    import httpx
    webhook_url = f"{settings.BACKEND_URL}/api/auth/telegram/webhook"
    api_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(api_url, json={"url": webhook_url})
        result = resp.json()

    # Also check current info
    info_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    async with httpx.AsyncClient(timeout=15.0) as client:
        info_resp = await client.get(info_url)
        info = info_resp.json()

    return {"set_result": result, "webhook_info": info}
