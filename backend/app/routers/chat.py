from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Message
from app.schemas import MessageCreate, MessageOut
from app.auth import get_current_user
from typing import List

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/{user_id}", response_model=List[MessageOut])
def get_messages(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(Message)
        .filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id))
            | ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
        )
        .order_by(Message.created_at.asc())
        .all()
    )
    # Mark received messages as read
    for msg in messages:
        if msg.receiver_id == current_user.id and msg.status == "sent":
            msg.status = "read"
    db.commit()
    return messages


@router.post("/{user_id}", response_model=MessageOut)
def send_message(
    user_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    receiver = db.query(User).filter(User.id == user_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    message = Message(
        sender_id=current_user.id,
        receiver_id=user_id,
        content=data.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/conversations/list")
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of all conversations"""
    # Get unique conversation partners
    from sqlalchemy import or_, distinct
    messages = db.query(Message).filter(
        or_(
            Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id,
        )
    ).all()

    partner_ids = set()
    for msg in messages:
        if msg.sender_id != current_user.id:
            partner_ids.add(msg.sender_id)
        if msg.receiver_id != current_user.id:
            partner_ids.add(msg.receiver_id)

    conversations = []
    for pid in partner_ids:
        partner = db.query(User).filter(User.id == pid).first()
        if not partner:
            continue
        last_msg = (
            db.query(Message)
            .filter(
                or_(
                    (Message.sender_id == current_user.id) & (Message.receiver_id == pid),
                    (Message.sender_id == pid) & (Message.receiver_id == current_user.id),
                )
            )
            .order_by(Message.created_at.desc())
            .first()
        )
        unread = db.query(Message).filter(
            Message.sender_id == pid,
            Message.receiver_id == current_user.id,
            Message.status == "sent",
        ).count()

        conversations.append({
            "user_id": pid,
            "user_name": partner.name,
            "user_telegram": partner.telegram,
            "last_message": last_msg.content if last_msg else "",
            "last_message_time": last_msg.created_at if last_msg else None,
            "unread_count": unread,
        })

    conversations.sort(key=lambda x: x["last_message_time"] or "", reverse=True)
    return conversations
