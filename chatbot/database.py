import sqlite3
from datetime import datetime

DB_NAME = "chatbot.db"


# -------------------------
# Create Database & Tables
# -------------------------
def create_database():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Chat History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        message TEXT,
        timestamp TEXT
    )
    """)

    # User Preferences Table
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
        updated_at TEXT
    )
    """)

    conn.commit()
    conn.close()


# -------------------------
# Save Chat Message
# -------------------------
def save_chat(user_id, role, message):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO chat_history
    (user_id, role, message, timestamp)
    VALUES (?, ?, ?, ?)
    """,
    (
        user_id,
        role,
        message,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


# -------------------------
# Get Chat History
# -------------------------
def get_chat_history(user_id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role, message
    FROM chat_history
    WHERE user_id=?
    ORDER BY chat_id
    """, (user_id,))

    history = cursor.fetchall()

    conn.close()

    return history


# -------------------------
# Load User Preferences
# -------------------------
def load_preferences(user_id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT intent,
           movie_name,
           mood,
           genre,
           language,
           watch_time,
           audience
    FROM user_preferences
    WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    if row is None:

        return {
            "intent": None,
            "movie_name": None,
            "mood": None,
            "genre": None,
            "language": None,
            "watch_time": None,
            "audience": None
        }

    return {
        "intent": row[0],
        "movie_name": row[1],
        "mood": row[2],
        "genre": row[3],
        "language": row[4],
        "watch_time": row[5],
        "audience": row[6]
    }


# -------------------------
# Save / Update Preferences
# -------------------------
def save_preferences(user_id, preferences):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO user_preferences
    (
        user_id,
        intent,
        movie_name,
        mood,
        genre,
        language,
        watch_time,
        audience,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        user_id,
        preferences.get("intent"),
        preferences.get("movie_name"),
        preferences.get("mood"),
        preferences.get("genre"),
        preferences.get("language"),
        preferences.get("watch_time"),
        preferences.get("audience"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


# -------------------------
# Clear Preferences
# -------------------------
def clear_preferences(user_id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM user_preferences
    WHERE user_id=?
    """, (user_id,))

    conn.commit()
    conn.close()


# -------------------------
# Create tables automatically
# -------------------------
create_database()

def get_recent_chat(user_id, limit=10):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, message
        FROM chat_history
        WHERE user_id=?
        ORDER BY chat_id DESC
        LIMIT ?
    """, (user_id, limit))

    rows = cursor.fetchall()

    conn.close()

    rows.reverse()

    return rows