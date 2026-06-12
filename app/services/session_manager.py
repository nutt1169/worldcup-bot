"""
In-memory session store สำหรับจัดการ multi-step registration flow
key: line_user_id, value: dict ของ state
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Dict

_sessions: Dict[str, dict] = {}


class RegStep(str, Enum):
    WAITING_NICKNAME = "waiting_nickname"
    WAITING_LINE_CONTACT = "waiting_line_contact"
    WAITING_FACEBOOK = "waiting_facebook"
    WAITING_PHONE = "waiting_phone"
    DONE = "done"


def get_session(line_user_id: str) -> Optional[dict]:
    return _sessions.get(line_user_id)


def start_registration(line_user_id: str):
    _sessions[line_user_id] = {
        "step": RegStep.WAITING_NICKNAME,
        "data": {},
    }


def update_session(line_user_id: str, key: str, value: str, next_step: RegStep):
    if line_user_id in _sessions:
        _sessions[line_user_id]["data"][key] = value
        _sessions[line_user_id]["step"] = next_step


def clear_session(line_user_id: str):
    _sessions.pop(line_user_id, None)
