from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    predicted_home_score = Column(Integer, nullable=False)
    predicted_away_score = Column(Integer, nullable=False)
    points_earned = Column(Integer, nullable=True)
    is_locked = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
