from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.user import User
from typing import Optional, List


def get_user(db: Session, line_user_id: str) -> Optional[User]:
    return db.query(User).filter(User.line_user_id == line_user_id).first()


def create_user(db: Session, line_user_id: str) -> User:
    user = User(line_user_id=line_user_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_registration(
    db: Session,
    line_user_id: str,
    nickname: str,
    line_contact: str | None,
    facebook_url: str | None,
    phone: str | None,
) -> User:
    user = get_user(db, line_user_id)
    user.nickname = nickname
    user.line_contact = line_contact
    user.facebook_url = facebook_url
    user.phone = phone
    user.is_registered = True
    db.commit()
    db.refresh(user)
    return user


def get_leaderboard(db: Session, limit: int = 10) -> List[User]:
    return (
        db.query(User)
        .filter(User.is_registered == True)
        .order_by(User.total_score.desc())
        .limit(limit)
        .all()
    )
