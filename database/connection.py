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

    logger.info("Database schema verified/created.")


create_database()
