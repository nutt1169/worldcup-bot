from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import engine, Base, SessionLocal
from app.routers.webhook import router as webhook_router
from app.services.match_service import sync_matches, update_scores_and_points
import app.models  # noqa: F401 — register models
import logging

logger = logging.getLogger(__name__)


def auto_sync():
    """รันทุก 1 ชั่วโมง — sync แมตช์ + คำนวณคะแนน"""
    try:
        db = SessionLocal()
        sync_matches(db)
        update_scores_and_points(db)
        db.close()
        logger.info("Auto-sync completed")
    except Exception as e:
        logger.error(f"Auto-sync error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_sync, "interval", hours=1, id="auto_sync")
    scheduler.start()
    logger.info("Scheduler started — auto-sync every 1 hour")

    yield

    scheduler.shutdown()


app = FastAPI(title="WorldCup Bot", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/")
def health():
    return {"status": "ok", "service": "worldcup-bot"}
