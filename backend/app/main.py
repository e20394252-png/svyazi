from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import auth, profiles, matching, chat, admin

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


@app.get("/health")
def health():
    return {"status": "ok", "service": "Связи API"}
