from __future__ import annotations
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from sqlalchemy.orm import Session
from datetime import timezone, timedelta
import os
import re

from app.services import user_service, session_manager, match_service
from app.services.session_manager import RegStep
from app.services.match_service import STAGE_TH

BKK = timezone(timedelta(hours=7))


def get_line_api() -> MessagingApi:
    config = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
    return MessagingApi(ApiClient(config))


def reply(reply_token: str, messages: list):
    api = get_line_api()
    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))


def text(msg: str) -> TextMessage:
    return TextMessage(text=msg)


# ── Follow Event ──────────────────────────────────────────────────────────────

def handle_follow(event: FollowEvent, db: Session):
    uid = event.source.user_id
    user = user_service.get_user(db, uid)
    if not user:
        user_service.create_user(db, uid)

    reply(
        event.reply_token,
        [text(
            "👋 สวัสดีครับ! ยินดีต้อนรับสู่ระบบทายผลบอลโลก 2026 ⚽\n\n"
            "📝 /register — สมัครสมาชิก\n"
            "📅 /matches — ดูตารางแมตช์\n"
            "⚽ /predict — ทายผลแมตช์\n"
            "🏆 /leaderboard — ดูอันดับ\n"
            "ℹ️ /help — ดูคำสั่งทั้งหมด"
        )],
    )


# ── Message Event ─────────────────────────────────────────────────────────────

def handle_message(event: MessageEvent, db: Session):
    if not isinstance(event.message, TextMessageContent):
        return

    uid = event.source.user_id
    text_input = event.message.text.strip()

    session = session_manager.get_session(uid)
    if session:
        step = session["step"]
        if step in (RegStep.WAITING_NICKNAME, RegStep.WAITING_LINE_CONTACT,
                    RegStep.WAITING_FACEBOOK, RegStep.WAITING_PHONE):
            _handle_registration_step(event, uid, text_input, session, db)
            return
        if step == "waiting_predict_score":
            _handle_predict_score(event, uid, text_input, session, db)
            return

    cmd = text_input.lower().split()[0] if text_input else ""

    if cmd in ("/register", "สมัคร"):
        _start_register(event, uid, db)
    elif cmd in ("/matches", "ตาราง"):
        _show_matches(event, db)
    elif cmd in ("/predict", "ทาย"):
        _start_predict(event, uid, text_input, db)
    elif cmd in ("/leaderboard", "อันดับ"):
        _show_leaderboard(event, db)
    elif cmd in ("/profile", "โปรไฟล์"):
        _show_profile(event, uid, db)
    elif cmd in ("/help", "ช่วยเหลือ"):
        _show_help(event)
    elif cmd == "/sync":
        match_service.sync_matches(db)
        _show_matches(event, db)
    else:
        reply(event.reply_token, [text("พิมพ์ /help เพื่อดูคำสั่งที่ใช้ได้ครับ 😊")])


# ── Registration Flow ─────────────────────────────────────────────────────────

def _start_register(event: MessageEvent, uid: str, db: Session):
    user = user_service.get_user(db, uid)
    if not user:
        user_service.create_user(db, uid)
        user = user_service.get_user(db, uid)

    if user and user.is_registered:
        reply(event.reply_token, [text(
            f"✅ คุณสมัครแล้วในชื่อ '{user.nickname}'\nพิมพ์ /profile เพื่อดูข้อมูล"
        )])
        return

    session_manager.start_registration(uid)
    reply(event.reply_token, [text(
        "📝 เริ่มสมัครสมาชิก!\n\nขั้นที่ 1/4\nกรุณาพิมพ์ชื่อที่ต้องการแสดงในตารางอันดับ:"
    )])


def _handle_registration_step(event, uid, text_input, session, db):
    step = session["step"]

    if step == RegStep.WAITING_NICKNAME:
        if len(text_input) < 2 or len(text_input) > 30:
            reply(event.reply_token, [text("⚠️ ชื่อต้องมี 2–30 ตัวอักษรครับ ลองใหม่:")])
            return
        session_manager.update_session(uid, "nickname", text_input, RegStep.WAITING_LINE_CONTACT)
        reply(event.reply_token, [text(
            f"✅ ชื่อ: {text_input}\n\nขั้นที่ 2/4\n"
            "กรุณาพิมพ์ Line ID หรือ URL Line ของคุณ\n(พิมพ์ - ถ้าไม่ต้องการระบุ)"
        )])

    elif step == RegStep.WAITING_LINE_CONTACT:
        value = None if text_input == "-" else text_input
        session_manager.update_session(uid, "line_contact", value, RegStep.WAITING_FACEBOOK)
        reply(event.reply_token, [text(
            "ขั้นที่ 3/4\nกรุณาพิมพ์ URL Facebook ของคุณ\n(พิมพ์ - ถ้าไม่ต้องการระบุ)"
        )])

    elif step == RegStep.WAITING_FACEBOOK:
        value = None if text_input == "-" else text_input
        session_manager.update_session(uid, "facebook_url", value, RegStep.WAITING_PHONE)
        reply(event.reply_token, [text(
            "ขั้นที่ 4/4\nกรุณาพิมพ์เบอร์โทรศัพท์ของคุณ\n(พิมพ์ - ถ้าไม่ต้องการระบุ)"
        )])

    elif step == RegStep.WAITING_PHONE:
        value = None if text_input == "-" else text_input
        session_manager.update_session(uid, "phone", value, RegStep.DONE)
        data = session_manager.get_session(uid)["data"]
        session_manager.clear_session(uid)

        user_service.update_user_registration(
            db=db,
            line_user_id=uid,
            nickname=data["nickname"],
            line_contact=data.get("line_contact"),
            facebook_url=data.get("facebook_url"),
            phone=data.get("phone"),
        )

        reply(event.reply_token, [text(
            "🎉 สมัครสมาชิกสำเร็จ!\n\n"
            f"👤 ชื่อ: {data['nickname']}\n"
            f"💬 Line: {data.get('line_contact') or '—'}\n"
            f"📘 Facebook: {data.get('facebook_url') or '—'}\n"
            f"📞 โทร: {data.get('phone') or '—'}\n\n"
            "พิมพ์ /predict เพื่อเริ่มทายผลได้เลยครับ ⚽"
        )])


# ── Matches ───────────────────────────────────────────────────────────────────

def _show_matches(event: MessageEvent, db: Session):
    matches = match_service.get_upcoming_matches(db, limit=8)
    if not matches:
        reply(event.reply_token, [text(
            "ไม่พบแมตช์ที่กำลังจะมาถึงครับ\n"
            "ลองพิมพ์ /sync เพื่อโหลดข้อมูลแมตช์ก่อนนะครับ"
        )])
        return

    lines = ["📅 แมตช์ที่กำลังจะมาถึง\n"]
    for i, m in enumerate(matches, 1):
        bkk_time = m.kickoff_time.astimezone(BKK)
        time_str = bkk_time.strftime("%d/%m %H:%M")
        stage = STAGE_TH.get(m.stage, m.stage)
        lines.append(f"{i}. {m.home_team} vs {m.away_team}")
        lines.append(f"   📍 {stage} | 🕐 {time_str} น.\n")

    lines.append("พิมพ์ /predict <เลขแมตช์> <สกอร์> เพื่อทายครับ\nเช่น /predict 1 3-0")
    reply(event.reply_token, [text("\n".join(lines))])


# ── Predict Flow ──────────────────────────────────────────────────────────────

def _start_predict(event: MessageEvent, uid: str, text_input: str, db: Session):
    user = user_service.get_user(db, uid)
    if not user or not user.is_registered:
        reply(event.reply_token, [text("กรุณาสมัครสมาชิกก่อนครับ พิมพ์ /register")])
        return

    parts = text_input.split()
    if len(parts) < 2:
        # แสดงรายการแมตช์ให้เลือก
        _show_matches(event, db)
        return

    try:
        match_index = int(parts[1])
    except ValueError:
        reply(event.reply_token, [text("พิมพ์เลขแมตช์ครับ เช่น /predict 1")])
        return

    matches = match_service.get_upcoming_matches(db, limit=8)
    if match_index < 1 or match_index > len(matches):
        reply(event.reply_token, [text(f"ไม่มีแมตช์หมายเลข {match_index} ครับ")])
        return

    match = matches[match_index - 1]
    bkk_time = match.kickoff_time.astimezone(BKK)
    time_str = bkk_time.strftime("%d/%m/%Y %H:%M")

    session_manager._sessions[uid] = {
        "step": "waiting_predict_score",
        "data": {"match_id": match.id, "match_index": match_index},
    }

    reply(event.reply_token, [text(
        f"⚽ ทายผลแมตช์\n\n"
        f"🏠 {match.home_team}\n"
        f"✈️  {match.away_team}\n"
        f"🕐 {time_str} น.\n\n"
        f"พิมพ์สกอร์ที่ทายในรูปแบบ\n"
        f"<ทีมเจ้าบ้าน>-<ทีมเยือน>\n"
        f"เช่น 2-1 หรือ 0-0"
    )])


def _handle_predict_score(event, uid, text_input, session, db):
    match_obj = re.match(r"^(\d+)-(\d+)$", text_input)
    if not match_obj:
        reply(event.reply_token, [text("รูปแบบไม่ถูกต้องครับ ใส่เป็น เช่น 2-1 หรือ 0-0")])
        return

    home_score = int(match_obj.group(1))
    away_score = int(match_obj.group(2))
    match_id = session["data"]["match_id"]

    user = user_service.get_user(db, uid)
    match = match_service.get_match(db, match_id)

    if not match:
        session_manager.clear_session(uid)
        reply(event.reply_token, [text("ไม่พบแมตช์ครับ")])
        return

    match_service.save_prediction(db, user, match, home_score, away_score)
    session_manager.clear_session(uid)

    bkk_time = match.kickoff_time.astimezone(BKK)
    time_str = bkk_time.strftime("%d/%m/%Y %H:%M")

    reply(event.reply_token, [text(
        f"✅ บันทึกการทายแล้ว!\n\n"
        f"⚽ {match.home_team} {home_score} - {away_score} {match.away_team}\n"
        f"🕐 เตะ {time_str} น.\n\n"
        f"พิมพ์ /predict เพื่อทายแมตช์อื่น"
    )])


# ── Leaderboard & Profile ──────────────────────────────────────────────────────

def _show_leaderboard(event: MessageEvent, db: Session):
    users = user_service.get_leaderboard(db)
    if not users:
        reply(event.reply_token, [text("ยังไม่มีผู้สมัครในระบบครับ")])
        return

    lines = ["🏆 ตารางอันดับ Top 10\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {u.nickname} — {u.total_score} แต้ม")

    reply(event.reply_token, [text("\n".join(lines))])


def _show_profile(event: MessageEvent, uid: str, db: Session):
    user = user_service.get_user(db, uid)
    if not user or not user.is_registered:
        reply(event.reply_token, [text("คุณยังไม่ได้สมัครครับ พิมพ์ /register")])
        return

    reply(event.reply_token, [text(
        f"👤 โปรไฟล์ของคุณ\n\n"
        f"ชื่อ: {user.nickname}\n"
        f"Line: {user.line_contact or '—'}\n"
        f"Facebook: {user.facebook_url or '—'}\n"
        f"โทร: {user.phone or '—'}\n"
        f"คะแนนรวม: {user.total_score} แต้ม"
    )])


def _show_help(event: MessageEvent):
    reply(event.reply_token, [text(
        "📋 คำสั่งที่ใช้ได้\n\n"
        "📝 /register — สมัครสมาชิก\n"
        "📅 /matches — ดูตารางแมตช์\n"
        "⚽ /predict <เลข> — ทายผลแมตช์\n"
        "👤 /profile — ดูโปรไฟล์\n"
        "🏆 /leaderboard — ตารางอันดับ\n"
        "🔄 /sync — โหลดข้อมูลแมตช์ใหม่\n"
        "ℹ️ /help — ดูคำสั่งทั้งหมด"
    )])
