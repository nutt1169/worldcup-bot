from fastapi import APIRouter, Request, HTTPException, Depends
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, FollowEvent, TextMessageContent
from sqlalchemy.orm import Session
import os

from app.database import get_db, SessionLocal
from app.services.line_handler import handle_message, handle_follow
from app.services import match_service

router = APIRouter()


def get_parser() -> WebhookParser:
    return WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    parser = get_parser()
    try:
        events = parser.parse(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, FollowEvent):
            handle_follow(event, db)
        elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_message(event, db)

    return {"status": "ok"}


@router.post("/sync")
def sync_matches(db: Session = Depends(get_db)):
    """Manual sync endpoint สำหรับ admin"""
    match_service.sync_matches(db)
    return {"status": "synced"}
