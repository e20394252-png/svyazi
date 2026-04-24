from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
import enum
from app.database import Base


class MatchStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    dismissed = "dismissed"


class MessageStatus(str, enum.Enum):
    sent = "sent"
    read = "read"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    telegram = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    occupation = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_imported = Column(Boolean, default=False)  # импортирован из CSV
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    profile = relationship("MatchProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sent_matches = relationship("Match", foreign_keys="Match.user1_id", back_populates="user1")
    received_matches = relationship("Match", foreign_keys="Match.user2_id", back_populates="user2")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")


class MatchProfile(Base):
    __tablename__ = "match_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Три измерения
    wants = Column(Text, nullable=True)       # Хочу
    cans = Column(Text, nullable=True)        # Могу
    has_items = Column(Text, nullable=True)   # Имею

    # Теги (массив JSON)
    wants_tags = Column(JSONB, default=list)
    cans_tags = Column(JSONB, default=list)
    has_tags = Column(JSONB, default=list)

    # Embedding как TEXT (JSON-encoded float array) - без pgvector для простоты
    embedding = Column(Text, nullable=True)

    embedding_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profile")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # кто инициировал поиск
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # кого нашли

    score = Column(Float, nullable=True)           # % совпадения (0-100)
    reasoning = Column(Text, nullable=True)         # объяснение ИИ
    status = Column(String(20), default="pending")  # pending/accepted/dismissed

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user1 = relationship("User", foreign_keys=[user1_id], back_populates="sent_matches")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="received_matches")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="sent")  # sent/read
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
