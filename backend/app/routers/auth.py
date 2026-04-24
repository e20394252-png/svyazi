from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, MatchProfile
from app.schemas import UserRegister, UserLogin, Token, ProfileOut
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token)
def register(data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        telegram=data.telegram,
        phone=data.phone,
        occupation=data.occupation,
    )
    db.add(user)
    db.flush()

    # Create empty match profile
    profile = MatchProfile(user_id=user.id)
    db.add(profile)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    # ── Админский логин ──────────────────────────────────────
    if data.email == "admin@admin.com" and data.password == "admin123":
        user = db.query(User).filter(User.email == "admin@admin.com").first()
        if not user:
            user = User(
                name="Администратор",
                email="admin@admin.com",
                password_hash=hash_password("admin123"),
                is_admin=True,
            )
            db.add(user)
            db.flush()
            profile = MatchProfile(user_id=user.id)
            db.add(profile)
            db.commit()
            db.refresh(user)
        elif not user.is_admin:
            user.is_admin = True
            db.commit()
        token = create_access_token(user.id)
        return Token(access_token=token)
    # ────────────────────────────────────────────────────────

    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = create_access_token(user.id)
    return Token(access_token=token)
