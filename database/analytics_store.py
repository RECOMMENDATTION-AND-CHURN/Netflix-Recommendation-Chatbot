"""
database/analytics_store.py
-----------------------------
Module 5 (Dashboard Improvements) — provider-dashboard-only aggregate
queries. Nothing here is imported by app.py or webapp/server.py (the
user-facing chatbot); this is deliberately kept separate, the same way
churn/model.py already is, so provider analytics never leak into the
user-facing surfaces.

Built on top of the tables that already exist (users, chat_history,
favorites, ratings) plus the two Module 4 additions (search_history,
movie_clicks) — no schema changes needed here.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

from database.connection import get_connection


# =====================================================================
# Live activity feed
# =====================================================================
def get_recent_activity_feed(limit: int = 30) -> List[Dict]:
    """Merges the last N events across ALL users from chat_history,
    movie_clicks, favorites, and ratings into one time-ordered feed for
    the provider dashboard's "what's happening right now" view."""
    with get_connection() as conn:
        chat_rows = conn.execute(
            """SELECT u.username, c.role, c.message, c.timestamp AS ts
               FROM chat_history c JOIN users u ON u.user_id = c.user_id
               WHERE c.role='user'
               ORDER BY c.chat_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()

        click_rows = conn.execute(
            """SELECT u.username, m.movie_title, m.interaction_type, m.clicked_at AS ts
               FROM movie_clicks m JOIN users u ON u.user_id = m.user_id
               WHERE m.interaction_type != 'recommended'
               ORDER BY m.click_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    events = []
    for r in chat_rows:
        events.append({
            "username": r["username"],
            "icon": "💬",
            "text": f"searched: \u201c{r['message'][:60]}\u201d",
            "timestamp": r["ts"],
        })
    icon_map = {"favorited": "⭐", "trailer": "▶", "rated": "🌟"}
    verb_map = {"favorited": "favorited", "trailer": "watched the trailer for", "rated": "rated"}
    for r in click_rows:
        events.append({
            "username": r["username"],
            "icon": icon_map.get(r["interaction_type"], "🎬"),
            "text": f"{verb_map.get(r['interaction_type'], r['interaction_type'])} \u201c{r['movie_title']}\u201d",
            "timestamp": r["ts"],
        })

    events.sort(key=lambda e: e["timestamp"] or "", reverse=True)
    return events[:limit]


# =====================================================================
# Weekly / monthly trends
# =====================================================================
def _bucketed_counts(timestamps: List[str], freq: str, periods: int) -> pd.DataFrame:
    """Buckets a list of 'YYYY-MM-DD HH:MM:SS' strings into weekly ('W')
    or monthly ('M') counts, for the last `periods` buckets, filling in
    zero-count buckets so trend lines don't have misleading gaps."""
    if not timestamps:
        idx = pd.period_range(end=datetime.now(), periods=periods, freq=freq)
        return pd.DataFrame({"period": idx.astype(str), "count": [0] * periods})

    s = pd.to_datetime(pd.Series(timestamps), errors="coerce").dropna()
    counts = s.dt.to_period(freq).value_counts().sort_index()
    idx = pd.period_range(end=datetime.now(), periods=periods, freq=freq)
    counts = counts.reindex(idx, fill_value=0)
    return pd.DataFrame({"period": counts.index.astype(str), "count": counts.values})


def get_signup_trend(freq: str = "W", periods: int = 8) -> pd.DataFrame:
    with get_connection() as conn:
        rows = conn.execute("SELECT created_at FROM users").fetchall()
    return _bucketed_counts([r["created_at"] for r in rows if r["created_at"]], freq, periods)


def get_recommendation_trend(freq: str = "W", periods: int = 8) -> pd.DataFrame:
    """Recommendation *requests* over time — every "recommended" impression
    logged in movie_clicks is one movie shown, so we count distinct
    (user, clicked_at) turns rather than individual movies."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT clicked_at FROM movie_clicks WHERE interaction_type='recommended'"
        ).fetchall()
    return _bucketed_counts([r["clicked_at"] for r in rows if r["clicked_at"]], freq, periods)


# =====================================================================
# Recommendation acceptance analytics
# =====================================================================
def get_recommendation_acceptance_rate() -> Dict:
    """Of all (user, movie) pairs that were ever recommended, what
    fraction were then favorited, rated, or had their trailer watched?
    A simple, honest proxy for "did the user like what we suggested"."""
    with get_connection() as conn:
        rows = conn.execute("SELECT user_id, movie_title, interaction_type FROM movie_clicks").fetchall()

    recommended_pairs = set()
    accepted_pairs = set()
    for r in rows:
        pair = (r["user_id"], r["movie_title"])
        if r["interaction_type"] == "recommended":
            recommended_pairs.add(pair)
        else:
            accepted_pairs.add(pair)

    accepted_of_recommended = recommended_pairs & accepted_pairs
    total = len(recommended_pairs)
    accepted = len(accepted_of_recommended)
    rate = round(100 * accepted / total, 1) if total else 0.0

    return {
        "total_recommended": total,
        "accepted": accepted,
        "acceptance_rate_pct": rate,
    }


# =====================================================================
# Movie popularity analytics
# =====================================================================
def get_movie_popularity(limit: int = 10) -> pd.DataFrame:
    """Most-recommended and most-favorited movies platform-wide, from
    movie_clicks. Returns one row per movie with counts per interaction
    type, sorted by total interactions."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT movie_title, interaction_type FROM movie_clicks"
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=["movie_title", "recommended", "favorited", "trailer", "rated", "total"])

    df = pd.DataFrame([dict(r) for r in rows])
    pivot = df.pivot_table(index="movie_title", columns="interaction_type", aggfunc=len, fill_value=0)
    for col in ("recommended", "favorited", "trailer", "rated"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["total"] = pivot[["recommended", "favorited", "trailer", "rated"]].sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False).head(limit).reset_index()
    return pivot[["movie_title", "recommended", "favorited", "trailer", "rated", "total"]]
