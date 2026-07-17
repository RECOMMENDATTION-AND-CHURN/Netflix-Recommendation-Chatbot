"""database/feedback_store.py — satisfaction feedback history (not just latest score)."""

from datetime import datetime
from typing import List, Dict
from database.connection import get_connection


def add_feedback(user_id: int, score: int, comment: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO feedback (user_id, score, comment, submitted_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, score, comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def get_feedback(user_id: int) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE user_id=? ORDER BY submitted_at DESC", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]
