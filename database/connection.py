"""
database/connection.py
-----------------------
Single source of truth for the SQLite connection and full schema.
All other database/* modules build on top of this.
"""

import sqlite3
import logging
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = "chatbot.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Database operation failed, rolled back.")
        raise
    finally:
        conn.close()


def create_database() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()

        # ---- Users (Module: auth) ----
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT
        )
        """)

        # ---- Chatbot memory ----
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            message TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            intent TEXT,
            movie_name TEXT,
            mood TEXT,
            genre TEXT,
            language TEXT,
            watch_time INTEGER,
            audience TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # ---- Favorites (separate table, one row per saved movie) ----
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            favorite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_title TEXT,
            genre TEXT,
            added_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # ---- Ratings (separate table, one row per rated movie) ----
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_title TEXT,
            rating INTEGER,
            rated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # ---- Feedback (satisfaction comments/scores over time) ----
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER,
            comment TEXT,
            submitted_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # ---- User activity (churn feature source — silent, provider-only) ----
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_activity (
            user_id INTEGER PRIMARY KEY,
            login_frequency INTEGER DEFAULT 0,
            login_time TEXT,
            logout_time TEXT,
            session_duration REAL DEFAULT 0,
            search_count INTEGER DEFAULT 0,
            recommendation_requests INTEGER DEFAULT 0,
            movies_clicked INTEGER DEFAULT 0,
            poster_clicked INTEGER DEFAULT 0,
            trailer_clicked INTEGER DEFAULT 0,
            favorites_added INTEGER DEFAULT 0,
            ratings_given INTEGER DEFAULT 0,
            rating_sum REAL DEFAULT 0,
            avg_rating_given REAL DEFAULT 0,
            satisfaction_score INTEGER DEFAULT 3,
            preferred_genre TEXT,
            last_login TEXT,
            last_activity TEXT,
            days_since_last_login INTEGER DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # ---- Search history (Module 4 — recommendation engine) ----
        # One row per chat turn where preferences were extracted. Unlike
        # user_preferences (which only keeps the CURRENT snapshot, one row
        # per user), this is an append-only log, so the recommendation
        # engine can weight candidates by what a user has searched for
        # most *over time*, not just their latest ask.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            genre TEXT,
            language TEXT,
            mood TEXT,
            searched_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # ---- Movie click/engagement history (Module 4) ----
        # One row per movie a user interacted with (recommended / clicked
        # trailer / rated / favorited). Distinct from favorites/ratings
        # tables: this captures lighter-weight signals (e.g. "recommended
        # and shown" or "trailer clicked" even without an explicit rating)
        # for the recommendation engine's history-based scoring.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movie_clicks (
            click_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_title TEXT,
            interaction_type TEXT,
            clicked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

    logger.info("Database schema verified/created.")

    # ---- Performance indexes (Module 6) ----
    # Every hot-path query in this project (chat history lookup, favorites/
    # ratings lookup, dashboard analytics, recommendation history scoring)
    # filters by user_id. Without an index, each of those does a full
    # table scan — fine at demo scale, increasingly slow as chat_history
    # and movie_clicks grow. IF NOT EXISTS makes this a safe no-op on
    # databases that already have these indexes.
    with get_connection() as conn:
        cursor = conn.cursor()
        for index_name, table, column in [
            ("idx_chat_history_user_id", "chat_history", "user_id"),
            ("idx_user_preferences_user_id", "user_preferences", "user_id"),
            ("idx_favorites_user_id", "favorites", "user_id"),
            ("idx_ratings_user_id", "ratings", "user_id"),
            ("idx_feedback_user_id", "feedback", "user_id"),
            ("idx_user_activity_user_id", "user_activity", "user_id"),
            ("idx_search_history_user_id", "search_history", "user_id"),
            ("idx_movie_clicks_user_id", "movie_clicks", "user_id"),
            ("idx_movie_clicks_title", "movie_clicks", "movie_title"),
        ]:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")

    logger.info("Database indexes verified/created.")


create_database()

# Automatic database backup (Module 6). Respects DB_BACKUP_MIN_INTERVAL_HOURS
# internally, so this runs on every process start but only actually writes
# a new backup file once that interval has elapsed — cheap and safe to
# leave in the hot import path. Never blocks startup if it fails.
try:
    from database.backup import backup_database
    backup_database()
except Exception as _backup_err:  # pragma: no cover - defensive only
    logger.warning("Startup database backup skipped due to an error: %s", _backup_err)
