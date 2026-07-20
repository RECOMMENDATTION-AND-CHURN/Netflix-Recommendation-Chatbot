"""
database/chat_store.py
------------------------
Everything the CHATBOT needs: chat history + user preference memory.
Deliberately has zero knowledge of churn/activity tracking.
"""

from datetime import datetime
from typing import List, Tuple, Dict, Optional

from database.connection import get_connection

DEFAULT_PREFERENCES = {
    "intent": None,
    "movie_name": None,
    "mood": None,
    "genre": None,
    "language": None,
    "watch_time": None,
    "audience": None,
}


def save_chat(user_id: int, role: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO chat_history (user_id, role, message, timestamp)
               VALUES (?, ?, ?, ?)""",
            (user_id, role, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def get_chat_history(user_id: int) -> List[Tuple[str, str]]:
    """Full chat history in chronological order — used to restore the UI on page reload."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, message FROM chat_history
               WHERE user_id=? ORDER BY chat_id""",
            (user_id,),
        ).fetchall()
    return [(row["role"], row["message"]) for row in rows]


def get_chat_history_with_timestamps(user_id: int) -> List[Tuple[str, str, str]]:
    """Same as get_chat_history() but also returns each message's stored
    timestamp — added for the chat UI's timestamp display. Kept as a
    separate function (rather than changing get_chat_history's return
    shape) so nothing that already unpacks (role, message) breaks."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, message, timestamp FROM chat_history
               WHERE user_id=? ORDER BY chat_id""",
            (user_id,),
        ).fetchall()
    return [(row["role"], row["message"], row["timestamp"]) for row in rows]


def delete_last_assistant_message(user_id: int) -> None:
    """Deletes only the single most-recent assistant row for this user.
    Used by the "Regenerate" button — never touches user messages or any
    other user's rows, so it's safe to call even if it no-ops."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT chat_id FROM chat_history
               WHERE user_id=? AND role='assistant'
               ORDER BY chat_id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        if row is not None:
            conn.execute("DELETE FROM chat_history WHERE chat_id=?", (row["chat_id"],))


def delete_last_user_message(user_id: int) -> None:
    """Deletes only the single most-recent user row for this user. Used by
    "Edit Last Message" right before re-inserting the edited text as a new
    row — never touches assistant messages or any other user's rows."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT chat_id FROM chat_history
               WHERE user_id=? AND role='user'
               ORDER BY chat_id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        if row is not None:
            conn.execute("DELETE FROM chat_history WHERE chat_id=?", (row["chat_id"],))


def delete_trailing_assistant_messages(user_id: int) -> None:
    """Deletes every assistant row that comes after the most recent user
    row (a single chat "turn" can produce more than one assistant message,
    e.g. a change-note followed by a recommendation summary). Used by
    "Edit Last Message" so editing cleanly removes the whole stale reply,
    not just the last row of it. Stops at the first non-assistant row it
    finds walking backwards, so it never touches user messages or older
    turns."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT chat_id, role FROM chat_history
               WHERE user_id=? ORDER BY chat_id DESC""",
            (user_id,),
        ).fetchall()
        to_delete = []
        for row in rows:
            if row["role"] == "assistant":
                to_delete.append(row["chat_id"])
            else:
                break
        for chat_id in to_delete:
            conn.execute("DELETE FROM chat_history WHERE chat_id=?", (chat_id,))


def get_recent_chat(user_id: int, limit: int = 10) -> List[Tuple[str, str]]:
    """Most recent N messages, chronological — used as LLM conversation context."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, message FROM chat_history
               WHERE user_id=? ORDER BY chat_id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [(row["role"], row["message"]) for row in reversed(rows)]


def load_preferences(user_id: int) -> Dict:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT intent, movie_name, mood, genre, language, watch_time, audience
               FROM user_preferences WHERE user_id=?""",
            (user_id,),
        ).fetchone()

    if row is None:
        return dict(DEFAULT_PREFERENCES)

    return {
        "intent": row["intent"],
        "movie_name": row["movie_name"],
        "mood": row["mood"],
        "genre": row["genre"],
        "language": row["language"],
        "watch_time": row["watch_time"],
        "audience": row["audience"],
    }


def save_preferences(user_id: int, preferences: Dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO user_preferences
               (user_id, intent, movie_name, mood, genre, language, watch_time, audience, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                preferences.get("intent"),
                preferences.get("movie_name"),
                preferences.get("mood"),
                preferences.get("genre"),
                preferences.get("language"),
                preferences.get("watch_time"),
                preferences.get("audience"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )


def clear_preferences(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM user_preferences WHERE user_id=?", (user_id,))


def clear_chat_history(user_id: int) -> None:
    """Deletes ALL chat_history rows for this user (does not touch
    user_preferences). Additive function for the new web frontend's
    "Clear chat" button — existing callers of get_chat_history() /
    save_chat() etc. are completely unaffected."""
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_history WHERE user_id=?", (user_id,))