"""
database/auth_store.py
------------------------
Signup / login / password hashing. Deliberately dependency-free (uses
stdlib hashlib + os.urandom for salt) so it doesn't add new pip packages.

Password storage: PBKDF2-HMAC-SHA256, 200k iterations, random 16-byte salt
per user — a reasonable, well-understood standard for a project like this
(not something you'd hand-roll for a real production bank, but solid for
a portfolio-grade multi-user app).
"""

import hashlib
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List

from database.connection import get_connection

logger = logging.getLogger(__name__)

_ITERATIONS = 200_000


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS).hex()


def signup(username: str, password: str) -> Optional[int]:
    """Creates a new user. Returns the new user_id, or None if username is taken."""
    username = username.strip().lower()
    if not username or not password:
        return None

    salt = os.urandom(16)
    password_hash = _hash_password(password, salt)

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO users (username, password_hash, salt, created_at)
                   VALUES (?, ?, ?, ?)""",
                (username, password_hash, salt.hex(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            return cursor.lastrowid
    except Exception as e:
        # Most likely a UNIQUE constraint violation (username taken)
        logger.info("Signup failed for '%s': %s", username, e)
        return None


def login(username: str, password: str) -> Optional[Dict]:
    """Returns {'user_id':..., 'username':...} on success, None on failure."""
    username = username.strip().lower()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, username, password_hash, salt FROM users WHERE username=?",
            (username,),
        ).fetchone()

    if row is None:
        return None

    salt = bytes.fromhex(row["salt"])
    candidate_hash = _hash_password(password, salt)

    if candidate_hash != row["password_hash"]:
        return None

    return {"user_id": row["user_id"], "username": row["username"]}


def get_all_users() -> list:
    """Used by the provider dashboard for total/new user counts."""
    with get_connection() as conn:
        rows = conn.execute("SELECT user_id, username, created_at FROM users").fetchall()
    return [dict(r) for r in rows]


def get_user_by_id(user_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, username FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None
