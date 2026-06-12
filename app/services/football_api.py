import httpx
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.football-data.org/v4"


def _headers():
    return {"X-Auth-Token": os.getenv("FOOTBALL_API_KEY")}


def fetch_matches(date_from: str = None, date_to: str = None) -> list[dict]:
    """ดึงแมตช์บอลโลก 2026 จาก API"""
    params = {"season": 2026}
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to

    with httpx.Client() as client:
        resp = client.get(
            f"{API_BASE}/competitions/WC/matches",
            headers=_headers(),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for m in data.get("matches", []):
        results.append({
            "api_match_id": m["id"],
            "home_team": m["homeTeam"]["name"],
            "away_team": m["awayTeam"]["name"],
            "kickoff_time": m["utcDate"],
            "stage": m.get("stage", ""),
            "group_name": m.get("group", ""),
            "home_score": m["score"]["fullTime"].get("home"),
            "away_score": m["score"]["fullTime"].get("away"),
            "status": m["status"],
        })
    return results


def fetch_live_scores() -> list[dict]:
    """ดึงแมตช์ที่กำลังเล่นอยู่"""
    with httpx.Client() as client:
        resp = client.get(
            f"{API_BASE}/competitions/WC/matches",
            headers=_headers(),
            params={"season": 2026, "status": "IN_PLAY,PAUSED,FINISHED"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for m in data.get("matches", []):
        results.append({
            "api_match_id": m["id"],
            "home_score": m["score"]["fullTime"].get("home"),
            "away_score": m["score"]["fullTime"].get("away"),
            "status": m["status"],
        })
    return results
