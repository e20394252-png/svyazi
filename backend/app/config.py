from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "google/gemini-flash-1.5-8b"
    POLLINATIONS_API_KEY: Optional[str] = None
    N8N_MATCHING_WEBHOOK_URL: Optional[str] = None
    N8N_MATCHING_WEBHOOK_URL_NEW: Optional[str] = "https://assistenty-kassandr.amvera.io/webhook/37cdffe0-da60-493b-b0e0-80b4658119c6"
    N8N_PROFILE_WEBHOOK_URL: Optional[str] = "https://assistenty-kassandr.amvera.io/webhook/a032dab3-0f5f-4b78-b8b7-01a86ec24f67"
    BACKEND_URL: str = "https://backend-production-d855.up.railway.app"
    ACTIVE_DATABASE: str = "networkers"  # "networkers" or "new"
    GEMINI_API_KEYS: str = ""  # comma-separated list of fallback Gemini API keys
    CORS_ORIGINS: str = "http://localhost:3000"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "matchig_auth_bot"

    class Config:
        env_file = ".env"


settings = Settings()
