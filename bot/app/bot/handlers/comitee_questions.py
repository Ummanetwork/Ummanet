from __future__ import annotations

from typing import Dict, Optional

# In-memory buffer for "ask scholars" flow.
# Key: telegram user id; Value: question text to forward.
pending_questions: Dict[int, str] = {}


def set_pending_question(user_id: int, text: str) -> None:
    if not user_id:
        return
    cleaned = (text or "").strip()
    if not cleaned:
        return
    pending_questions[user_id] = cleaned


def pop_pending_question(user_id: int) -> Optional[str]:
    if not user_id:
        return None
    return pending_questions.pop(user_id, None)


def get_pending_question(user_id: int) -> Optional[str]:
    if not user_id:
        return None
    return pending_questions.get(user_id)

