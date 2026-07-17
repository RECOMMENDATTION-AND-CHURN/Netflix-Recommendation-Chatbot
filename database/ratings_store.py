"""database/ratings_store.py — one row per movie a user rates."""

from datetime import datetime
from typing import List, Dict, Optional
from database.connection import get_connection


def add_or_update_rating(user_id: int, movie_title: str, rating: int) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT rating_id FROM ratings WHERE user_id=? AND movie_title=?",
            (user_id, movie_title),
        ).fetchone()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if existing:
            conn.execute(
                "UPDATE ratings SET rating=?, rated_at=? WHERE rating_id=?",
                (rating, now, existing["rating_id"]),
            )
        else:
            conn.execute(
                """INSERT INTO ratings (user_id, movie_title, rating, rated_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, movie_title, rating, now),
            )


def get_ratings(user_id: int) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ratings WHERE user_id=? ORDER BY rated_at DESC", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_user_rating_for_movie(user_id: int, movie_title: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT rating FROM ratings WHERE user_id=? AND movie_title=?",
            (user_id, movie_title),
        ).fetchone()
    return row["rating"] if row else None


def get_all_ratings() -> List[Dict]:
    """Used by the provider dashboard for platform-wide average rating."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM ratings").fetchall()
    return [dict(r) for r in rows]


def average_rating(user_id: int) -> float:
    ratings = get_ratings(user_id)
    if not ratings:
        return 0.0
    return round(sum(r["rating"] for r in ratings) / len(ratings), 2)
