"""database/favorites_store.py — one row per movie a user saves."""

from datetime import datetime
from typing import List, Dict
from database.connection import get_connection


def add_favorite(user_id: int, movie_title: str, genre: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO favorites (user_id, movie_title, genre, added_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, movie_title, genre, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def get_favorites(user_id: int) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM favorites WHERE user_id=? ORDER BY added_at DESC", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def is_favorited(user_id: int, movie_title: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND movie_title=?",
            (user_id, movie_title),
        ).fetchone()
    return row is not None
