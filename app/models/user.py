from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    line_user_id = Column(String, unique=True, index=True, nullable=False)
    nickname = Column(String, nullable=True)
    line_contact = Column(String, nullable=True)   # Line ID หรือ URL
    facebook_url = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    total_score = Column(Integer, default=0)
    is_registered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
