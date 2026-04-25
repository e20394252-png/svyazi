from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

if not settings.DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Add new columns to existing tables safely (idempotent, ALTER TABLE IF NOT EXISTS)"""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_imported BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_id BIGINT UNIQUE",
        "ALTER TABLE match_profiles ADD COLUMN IF NOT EXISTS wants_tags JSONB DEFAULT '[]'::jsonb",
        "ALTER TABLE match_profiles ADD COLUMN IF NOT EXISTS cans_tags JSONB DEFAULT '[]'::jsonb",
        "ALTER TABLE match_profiles ADD COLUMN IF NOT EXISTS has_tags JSONB DEFAULT '[]'::jsonb",
        "ALTER TABLE match_profiles ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE match_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
        """CREATE TABLE IF NOT EXISTS telegram_auth_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE NOT NULL,
            telegram_id BIGINT,
            telegram_username VARCHAR(200),
            telegram_name VARCHAR(200),
            confirmed BOOLEAN DEFAULT FALSE,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_telegram_auth_codes_code ON telegram_auth_codes(code)",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass  # Skip if column already exists or non-critical error
        conn.commit()


def init_db():
    """Create all tables and run migrations"""
    Base.metadata.create_all(bind=engine)
    run_migrations()
