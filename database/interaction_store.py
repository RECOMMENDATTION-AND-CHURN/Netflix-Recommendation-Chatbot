"""
DEVELOPED BY HARIHARASUDHAN(8208E23ASR022)
"""
"""
database/interaction_store.py
-------------------------------
Module 4 (Recommendation Engine upgrade) support tables:

  * search_history — an append-only log of what a user has searched for
    (genre/language/mood) across ALL their chat turns over time. This is
    different from user_preferences, which only holds the user's current
    snapshot (one row, overwritten every turn).

  * movie_clicks — a lightweight log of per-movie engagement (recommended
    / trailer clicked / rated / favorited), used as an additional signal
    alongside the favorites/ratings tables.

Both tables are purely additive (see database/connection.py) — nothing
here changes the shape or behavior of any existing table or function.
"""

from datetime import datetime
from collections import Counter
from typing import Dict, List, Optional

from database.connection import get_connection


# =====================================================================
# Search history
# =====================================================================
def log_search(user_id: int, genre: Optional[str], language: Optional[str], mood: Optional[str]) -> None:
    """Appends one row for this turn's extracted preferences. Safe to call
    every turn, even if all three fields are None (still useful to know
    the user searched at all) — callers may skip the call entirely if
    preferred, this is purely additive telemetry."""
    if not user_id or not any([genre, language, mood]):
        return
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO search_history (user_id, genre, language, mood, searched_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, genre, language, mood, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def get_top_genres(user_id: int, limit: int = 3) -> List[str]:
    """Most frequently searched genres for this user, most-common first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT genre FROM search_history WHERE user_id=? AND genre IS NOT NULL",
            (user_id,),
        ).fetchall()
    counts = Counter(r["genre"].strip().lower() for r in rows if r["genre"])
    return [genre for genre, _ in counts.most_common(limit)]


def get_top_languages(user_id: int, limit: int = 2) -> List[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT language FROM search_history WHERE user_id=? AND language IS NOT NULL",
            (user_id,),
        ).fetchall()
    counts = Counter(r["language"].strip().lower() for r in rows if r["language"])
    return [lang for lang, _ in counts.most_common(limit)]


# =====================================================================
# Click / engagement history
# =====================================================================
VALID_INTERACTION_TYPES = {"recommended", "trailer", "rated", "favorited"}


def log_click(user_id: int, movie_title: str, interaction_type: str) -> None:
    if not user_id or not movie_title or interaction_type not in VALID_INTERACTION_TYPES:
        return
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO movie_clicks (user_id, movie_title, interaction_type, clicked_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, movie_title, interaction_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def log_clicks_bulk(user_id: int, movie_titles: List[str], interaction_type: str = "recommended") -> None:
    """Convenience helper: logs the same interaction_type for a whole batch
    of movies in one connection (used to record "these N movies were
    shown to the user this turn" without N separate round-trips)."""
    if not user_id or not movie_titles or interaction_type not in VALID_INTERACTION_TYPES:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO movie_clicks (user_id, movie_title, interaction_type, clicked_at)
               VALUES (?, ?, ?, ?)""",
            [(user_id, title, interaction_type, now) for title in movie_titles],
        )


def get_engaged_titles(user_id: int, interaction_types: Optional[List[str]] = None, limit: int = 100) -> List[str]:
    """Titles the user has engaged with, most-recent first. By default
    excludes the passive "recommended" (shown-but-not-acted-on) type, so
    it reflects genuine engagement (trailer/rated/favorited) rather than
    everything that was ever displayed to them."""
    types = interaction_types or ["trailer", "rated", "favorited"]
    placeholders = ",".join("?" for _ in types)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT DISTINCT movie_title FROM movie_clicks
                WHERE user_id=? AND interaction_type IN ({placeholders})
                ORDER BY click_id DESC LIMIT ?""",
            (user_id, *types, limit),
        ).fetchall()
    return [r["movie_title"] for r in rows]


def get_all_shown_titles(user_id: int, limit: int = 500) -> List[str]:
    """Every title ever recommended to this user (any interaction_type),
    most-recent first. Used for duplicate prevention — don't recommend
    the same movie again and again across sessions."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT movie_title FROM movie_clicks
               WHERE user_id=? ORDER BY click_id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [r["movie_title"] for r in rows]
