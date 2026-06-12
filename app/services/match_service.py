from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.user import User
from app.services import football_api


STAGE_TH = {
    "GROUP_STAGE": "รอบแบ่งกลุ่ม",
    "ROUND_OF_32": "รอบ 32 ทีม",
    "ROUND_OF_16": "รอบ 16 ทีม",
    "QUARTER_FINALS": "รอบ 8 ทีม",
    "SEMI_FINALS": "รอบรองชนะเลิศ",
    "THIRD_PLACE": "ชิงที่ 3",
    "FINAL": "รอบชิงชนะเลิศ",
}


def sync_matches(db: Session):
    """ดึงแมตช์จาก API แล้วบันทึก/อัปเดตใน DB"""
    matches = football_api.fetch_matches()
    for m in matches:
        # ข้ามแมตช์ที่ยังไม่รู้ทีม (รอบน็อคเอาท์ที่ยังไม่ได้เล่น)
        if not m["home_team"] or not m["away_team"]:
            continue
        existing = db.query(Match).filter(Match.api_match_id == m["api_match_id"]).first()
        kickoff = datetime.fromisoformat(m["kickoff_time"].replace("Z", "+00:00"))
        if existing:
            existing.home_score = m["home_score"]
            existing.away_score = m["away_score"]
            existing.status = m["status"]
        else:
            db.add(Match(
                api_match_id=m["api_match_id"],
                home_team=m["home_team"],
                away_team=m["away_team"],
                kickoff_time=kickoff,
                stage=m["stage"],
                group_name=m["group_name"],
                home_score=m["home_score"],
                away_score=m["away_score"],
                status=m["status"],
            ))
    db.commit()


def get_upcoming_matches(db: Session, limit: int = 5) -> List[Match]:
    now = datetime.now(timezone.utc)
    return (
        db.query(Match)
        .filter(and_(Match.kickoff_time > now, Match.status == "TIMED"))
        .order_by(Match.kickoff_time)
        .limit(limit)
        .all()
    )


def get_match(db: Session, match_id: int) -> Optional[Match]:
    return db.query(Match).filter(Match.id == match_id).first()


def save_prediction(
    db: Session, user: User, match: Match, home_score: int, away_score: int
) -> Prediction:
    existing = (
        db.query(Prediction)
        .filter(and_(Prediction.user_id == user.id, Prediction.match_id == match.id))
        .first()
    )
    if existing:
        existing.predicted_home_score = home_score
        existing.predicted_away_score = away_score
        db.commit()
        db.refresh(existing)
        return existing

    pred = Prediction(
        user_id=user.id,
        match_id=match.id,
        predicted_home_score=home_score,
        predicted_away_score=away_score,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


def calculate_points(
    pred_home: int, pred_away: int, real_home: int, real_away: int
) -> int:
    if pred_home == real_home and pred_away == real_away:
        return 5  # ถูกสกอร์เป๊ะ
    pred_result = _result(pred_home, pred_away)
    real_result = _result(real_home, real_away)
    if pred_result != real_result:
        return 0
    if abs(pred_home - pred_away) == abs(real_home - real_away):
        return 3  # ถูกผู้ชนะ + ถูกผลต่าง
    return 1  # ถูกผู้ชนะอย่างเดียว


def _result(h: int, a: int) -> str:
    if h > a:
        return "H"
    if a > h:
        return "A"
    return "D"


def update_scores_and_points(db: Session):
    """อัปเดตสกอร์จริงและคำนวณคะแนนหลังแมตช์จบ"""
    live = football_api.fetch_live_scores()
    for m in live:
        match = db.query(Match).filter(Match.api_match_id == m["api_match_id"]).first()
        if not match:
            continue
        match.home_score = m["home_score"]
        match.away_score = m["away_score"]
        match.status = m["status"]

        if m["status"] == "FINISHED" and m["home_score"] is not None:
            preds = db.query(Prediction).filter(Prediction.match_id == match.id).all()
            for pred in preds:
                if pred.points_earned is None:
                    pts = calculate_points(
                        pred.predicted_home_score,
                        pred.predicted_away_score,
                        m["home_score"],
                        m["away_score"],
                    )
                    pred.points_earned = pts
                    user = db.query(User).filter(User.id == pred.user_id).first()
                    if user:
                        user.total_score += pts
    db.commit()
