from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "google/gemini-flash-1.5-8b"
    POLLINATIONS_API_KEY: Optional[str] = None
    N8N_MATCHING_WEBHOOK_URL: Optional[str] = None
    GEMINI_API_KEYS: str = ""  # comma-separated list of fallback Gemini API keys
    CORS_ORIGINS: str = "http://localhost:3000"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"


settings = Settings()
