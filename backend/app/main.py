from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import auth, profiles, matching, chat, admin, telegram

app = FastAPI(title="Связи API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(matching.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(telegram.router)


@app.on_event("startup")
def on_startup():
    init_db()
    # Auto-migrate: add is_admin column if it doesn't exist
    from app.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE
        """))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Migration note: {e}")
    finally:
        db.close()

    # Auto-set Telegram webhook on startup (survives redeploys)
    if settings.TELEGRAM_BOT_TOKEN and settings.BACKEND_URL:
        import threading
        def _set_webhook():
            import httpx
            webhook_url = f"{settings.BACKEND_URL}/api/auth/telegram/webhook"
            api_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(api_url, json={"url": webhook_url})
                    print(f"TELEGRAM WEBHOOK: {resp.json()}")
            except Exception as e:
                print(f"TELEGRAM WEBHOOK ERROR: {e}")
        threading.Thread(target=_set_webhook, daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok", "service": "Связи API"}
