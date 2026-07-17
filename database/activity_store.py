"""
database/activity_store.py
----------------------------
Everything the CHURN/ANALYTICS side needs. The chatbot UI (app.py) calls
into this module to record behavior, but the chatbot's own logic
(chatbot/chatbot.py, chatbot/memory.py) never imports this — keeping the
two modules cleanly separated per the project spec.
"""

from datetime import datetime
from typing import Dict, List, Optional

from database.connection import get_connection

_ALLOWED_COUNTERS = {
    "search_count",
    "recommendation_requests",
    "movies_clicked",
    "poster_clicked",
    "trailer_clicked",
    "favorites_added",
}

_NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_user_activity(user_id: int) -> None:
    """Ensures a row exists so every other function can safely UPDATE."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_activity (user_id, updated_at) VALUES (?, ?)",
            (user_id, _NOW()),
        )


def touch_login(user_id: int) -> None:
    """Call once per new session. Bumps login_frequency, sets login_time, recalculates recency."""
    init_user_activity(user_id)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_login FROM user_activity WHERE user_id=?", (user_id,)
        ).fetchone()

        now = datetime.now()
        days_since = 0
        if row and row["last_login"]:
            last_login = datetime.strptime(row["last_login"], "%Y-%m-%d %H:%M:%S")
            days_since = (now - last_login).days

        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """UPDATE user_activity
               SET login_frequency = login_frequency + 1,
                   login_time = ?,
                   days_since_last_login = ?,
                   last_login = ?,
                   last_activity = ?,
                   updated_at = ?
               WHERE user_id = ?""",
            (now_str, days_since, now_str, now_str, now_str, user_id),
        )


def touch_logout(user_id: int) -> None:
    """Records logout_time — call this on an explicit exit/logout action."""
    init_user_activity(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE user_activity SET logout_time = ?, updated_at = ? WHERE user_id = ?",
            (_NOW(), _NOW(), user_id),
        )


def increment_activity(user_id: int, field: str, amount: int = 1) -> None:
    """Generic +N increment for a whitelisted set of integer counters."""
    if field not in _ALLOWED_COUNTERS:
        raise ValueError(f"'{field}' is not a trackable counter. Allowed: {_ALLOWED_COUNTERS}")

    init_user_activity(user_id)

    with get_connection() as conn:
        conn.execute(
            f"""UPDATE user_activity
                SET {field} = {field} + ?, last_activity = ?, updated_at = ?
                WHERE user_id = ?""",
            (amount, _NOW(), _NOW(), user_id),
        )


def set_session_duration(user_id: int, minutes: float) -> None:
    """OVERWRITES session_duration (safe to call every Streamlit rerun)."""
    init_user_activity(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE user_activity SET session_duration = ?, updated_at = ? WHERE user_id = ?",
            (minutes, _NOW(), user_id),
        )


def add_rating(user_id: int, rating: int) -> None:
    init_user_activity(user_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ratings_given, rating_sum FROM user_activity WHERE user_id=?", (user_id,)
        ).fetchone()

        ratings_given = (row["ratings_given"] or 0) + 1
        rating_sum = (row["rating_sum"] or 0) + rating
        avg_rating = rating_sum / ratings_given

        conn.execute(
            """UPDATE user_activity
               SET ratings_given = ?, rating_sum = ?, avg_rating_given = ?,
                   last_activity = ?, updated_at = ?
               WHERE user_id = ?""",
            (ratings_given, rating_sum, avg_rating, _NOW(), _NOW(), user_id),
        )


def set_satisfaction_score(user_id: int, score: int) -> None:
    init_user_activity(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE user_activity SET satisfaction_score = ?, updated_at = ? WHERE user_id = ?",
            (score, _NOW(), user_id),
        )


def set_preferred_genre(user_id: int, genre: Optional[str]) -> None:
    if not genre:
        return
    init_user_activity(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE user_activity SET preferred_genre = ?, updated_at = ? WHERE user_id = ?",
            (genre, _NOW(), user_id),
        )


def get_user_activity(user_id: int) -> Dict:
    init_user_activity(user_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_activity WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else {}


def get_all_user_activity() -> List[Dict]:
    """Used exclusively by the provider dashboard — never called from the chatbot."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM user_activity").fetchall()
    return [dict(row) for row in rows]
