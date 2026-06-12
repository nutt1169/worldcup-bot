from __future__ import annotations
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import timezone, timedelta
import os

from app.database import get_db
from app.models.user import User
from app.models.match import Match
from app.models.prediction import Prediction
from app.services.match_service import sync_matches, update_scores_and_points, get_upcoming_matches, STAGE_TH
from app.services.user_service import get_leaderboard

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")
BKK = timezone(timedelta(hours=7))

ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin1234")


def is_logged_in(request: Request) -> bool:
    return request.cookies.get("admin_auth") == "ok"


def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/admin/login", status_code=302)
    return None


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        resp = RedirectResponse("/admin/dashboard", status_code=302)
        resp.set_cookie("admin_auth", "ok", max_age=86400 * 7)
        return resp
    return templates.TemplateResponse("login.html", {"request": request, "error": "Username หรือ Password ไม่ถูกต้อง"})


@router.get("/logout")
def logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("admin_auth")
    return resp


@router.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/admin/dashboard", status_code=302)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir

    total_players = db.query(User).filter(User.is_registered == True).count()
    total_matches = db.query(Match).count()
    finished_matches = db.query(Match).filter(Match.status == "FINISHED").count()
    total_predictions = db.query(Prediction).count()
    leaderboard = get_leaderboard(db, limit=10)
    upcoming = get_upcoming_matches(db, limit=5)

    # แปลงเวลาเป็น BKK
    for m in upcoming:
        if m.kickoff_time.tzinfo is None:
            m.kickoff_time = m.kickoff_time.replace(tzinfo=timezone.utc)
        m.kickoff_time = m.kickoff_time.astimezone(BKK)

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "active": "dashboard",
        "total_players": total_players,
        "total_matches": total_matches,
        "finished_matches": finished_matches,
        "total_predictions": total_predictions,
        "leaderboard": leaderboard,
        "upcoming": upcoming,
    })


# ── Players ───────────────────────────────────────────────────────────────────

@router.get("/players", response_class=HTMLResponse)
def players(request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    players = db.query(User).filter(User.is_registered == True).order_by(User.total_score.desc()).all()
    return templates.TemplateResponse("players.html", {"request": request, "active": "players", "players": players})


@router.get("/players/{user_id}", response_class=HTMLResponse)
def player_detail(user_id: int, request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    player = db.query(User).filter(User.id == user_id).first()
    preds = db.query(Prediction).filter(Prediction.user_id == user_id).all()
    items = []
    for p in preds:
        match = db.query(Match).filter(Match.id == p.match_id).first()
        if match:
            if match.kickoff_time.tzinfo is None:
                match.kickoff_time = match.kickoff_time.replace(tzinfo=timezone.utc)
            match.kickoff_time = match.kickoff_time.astimezone(BKK)
            items.append({"pred": p, "match": match})
    return templates.TemplateResponse("player_detail.html", {"request": request, "active": "players", "player": player, "predictions": items})


# ── Matches ───────────────────────────────────────────────────────────────────

@router.get("/matches", response_class=HTMLResponse)
def matches(request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    matches = db.query(Match).order_by(Match.kickoff_time).all()
    for m in matches:
        if m.kickoff_time.tzinfo is None:
            m.kickoff_time = m.kickoff_time.replace(tzinfo=timezone.utc)
        m.kickoff_time = m.kickoff_time.astimezone(BKK)
        m.pred_count = db.query(Prediction).filter(Prediction.match_id == m.id).count()
    return templates.TemplateResponse("matches.html", {"request": request, "active": "matches", "matches": matches})


@router.get("/matches/{match_id}", response_class=HTMLResponse)
def match_detail(match_id: int, request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    match = db.query(Match).filter(Match.id == match_id).first()
    if match.kickoff_time.tzinfo is None:
        match.kickoff_time = match.kickoff_time.replace(tzinfo=timezone.utc)
    match.kickoff_time = match.kickoff_time.astimezone(BKK)
    preds = db.query(Prediction).filter(Prediction.match_id == match_id).all()
    items = []
    for p in preds:
        user = db.query(User).filter(User.id == p.user_id).first()
        items.append({"pred": p, "user": user})
    return templates.TemplateResponse("match_detail.html", {"request": request, "active": "matches", "match": match, "predictions": items})


# ── Predictions ───────────────────────────────────────────────────────────────

@router.get("/predictions", response_class=HTMLResponse)
def predictions(request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    preds = db.query(Prediction).order_by(Prediction.submitted_at.desc()).all()
    items = []
    for p in preds:
        user = db.query(User).filter(User.id == p.user_id).first()
        match = db.query(Match).filter(Match.id == p.match_id).first()
        if user and match:
            items.append({"pred": p, "user": user, "match": match})
    return templates.TemplateResponse("predictions.html", {"request": request, "active": "predictions", "predictions": items})


# ── Sync ──────────────────────────────────────────────────────────────────────

@router.get("/sync")
def admin_sync(request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    sync_matches(db)
    update_scores_and_points(db)
    return RedirectResponse("/admin/dashboard", status_code=302)


# ── Reset Scores ──────────────────────────────────────────────────────────────

@router.get("/reset-scores")
def reset_scores(request: Request, db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir
    # reset คะแนนทุก prediction
    db.query(Prediction).update({"points_earned": None})
    # reset คะแนนรวมทุก user
    db.query(User).update({"total_score": 0})
    db.commit()
    return RedirectResponse("/admin/dashboard", status_code=302)


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.get("/broadcast", response_class=HTMLResponse)
def broadcast_page(request: Request):
    if redir := require_login(request):
        return redir
    return templates.TemplateResponse("broadcast.html", {"request": request, "active": "broadcast"})


@router.post("/broadcast", response_class=HTMLResponse)
def broadcast_send(request: Request, message: str = Form(...), db: Session = Depends(get_db)):
    if redir := require_login(request):
        return redir

    from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, BroadcastRequest, TextMessage
    config = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
    api = MessagingApi(ApiClient(config))
    users = db.query(User).filter(User.is_registered == True).all()
    count = 0
    for u in users:
        try:
            from linebot.v3.messaging import PushMessageRequest
            api.push_message(PushMessageRequest(to=u.line_user_id, messages=[TextMessage(text=message)]))
            count += 1
        except Exception:
            pass

    return templates.TemplateResponse("broadcast.html", {"request": request, "active": "broadcast", "success": True, "count": count})
