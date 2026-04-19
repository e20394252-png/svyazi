from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    telegram: Optional[str] = None
    phone: Optional[str] = None
    occupation: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Profile ───────────────────────────────────────────
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    telegram: Optional[str] = None
    phone: Optional[str] = None
    occupation: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    wants: Optional[str] = None
    cans: Optional[str] = None
    has_items: Optional[str] = None


class ProfileOut(BaseModel):
    id: int
    name: str
    email: str
    telegram: Optional[str]
    phone: Optional[str]
    occupation: Optional[str]
    bio: Optional[str]
    city: Optional[str]
    wants: Optional[str] = None
    cans: Optional[str] = None
    has_items: Optional[str] = None
    wants_tags: Optional[List[str]] = []
    cans_tags: Optional[List[str]] = []
    has_tags: Optional[List[str]] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ── Match ─────────────────────────────────────────────
class MatchOut(BaseModel):
    id: int
    user: ProfileOut
    score: Optional[float]
    reasoning: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Message ───────────────────────────────────────────
class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Stats ─────────────────────────────────────────────
class StatsOut(BaseModel):
    total_users: int
    total_matches: int
    your_matches: int
