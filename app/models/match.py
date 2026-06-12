from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    api_match_id = Column(Integer, unique=True, index=True)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    home_team_flag = Column(String, nullable=True)
    away_team_flag = Column(String, nullable=True)
    kickoff_time = Column(DateTime(timezone=True), nullable=False)
    stage = Column(String, nullable=True)       # GROUP_STAGE / ROUND_OF_16 / etc
    group_name = Column(String, nullable=True)  # Group A / Group B / etc
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    status = Column(String, default="TIMED")    # TIMED / IN_PLAY / FINISHED
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
