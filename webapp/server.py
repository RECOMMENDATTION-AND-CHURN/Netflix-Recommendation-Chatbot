"""
webapp/server.py
------------------
Flask backend for MODULE 1 — the standalone Netflix-inspired website
frontend (separate from the Streamlit app in app.py / Module 2).

Design principles:
  * Zero changes to existing behavior. This file only *imports* the
    existing chatbot/, recommendation/, database/ packages — it does not
    modify how app.py or dashboard.py work, and both keep running exactly
    as before.
  * Session-based auth using Flask's signed cookie sessions (no new
    external dependency beyond Flask itself).
  * The conversation orchestration (greeting/farewell detection, slot
    filling, preference merging, change-explanation, recommendations) is
    the same pipeline app.py uses — re-implemented here as a plain
    request/response instead of a Streamlit rerun loop.

Run with:
    cd Netflix-Recommendation-Chatbot
    pip install flask
    python webapp/server.py
Then open http://localhost:5000/login.html
"""

from __future__ import annotations

import os
import re
import time
import logging
import secrets
from functools import wraps
from typing import Optional

from flask import Flask, request, jsonify, session, redirect, send_from_directory

# ---------------------------------------------------------------------
# Make the project root importable regardless of cwd (webapp/ is nested
# one level below the project root where chatbot/, database/, etc. live).
# ---------------------------------------------------------------------
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)  # so the SQLite DB_NAME ("chatbot.db") resolves to the existing file

from config import settings
from logging_config import configure_logging

from recommendation.movie_service import MovieRecommendationService
from chatbot.chatbot import extract_preferences
from chatbot.memory import merge_preferences
from chatbot.conversation import is_ready_to_recommend, next_question, describe_preference_change
from database.auth_store import signup, login, get_user_by_id, update_password
from database.chat_store import (
    save_chat,
    get_chat_history_with_timestamps,
    load_preferences,
    delete_last_assistant_message,
    clear_chat_history,
)
from database.activity_store import (
    touch_login,
    touch_logout,
    increment_activity,
    add_rating as track_rating_activity,
    set_preferred_genre,
    set_session_duration,
)
from database.favorites_store import add_favorite, is_favorited, get_favorites
from database.ratings_store import add_or_update_rating, get_user_rating_for_movie, get_ratings, average_rating
from database.interaction_store import log_click
from database.feedback_store import add_feedback

logger = configure_logging(component="webapp")

# ---------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.secret_key = settings.FLASK_SECRET_KEY or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,  # 30 days for "remember me"
)

GREETING_PATTERN = re.compile(
    r"^\s*(hi|hii+|hey+|hello+|yo|sup|good\s?(morning|afternoon|evening))\s*[!.?]*\s*$",
    re.IGNORECASE,
)
FAREWELL_PATTERN = re.compile(
    r"^\s*(exit|quit|bye|goodbye|good\s?bye|see\s?you|thanks?|thank\s?you|thanks?\s?bye|thank\s?you\s?bye)\s*[!.?]*\s*$",
    re.IGNORECASE,
)
GREETING_REPLY = "\U0001F44B Hey! Tell me what kind of movie you're in the mood for \u2014 genre, language, mood, or even 'something like Interstellar'."
FAREWELL_REPLY = "Thanks for using Netflix AI.\nHave a great day."

# Simple in-memory rate limiter for auth endpoints: {key: [timestamps]}
_auth_attempts: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
_RATE_LIMIT_MAX = settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS


def _rate_limited(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _auth_attempts.get(key, []) if now - t < _RATE_LIMIT_WINDOW]
    attempts.append(now)
    _auth_attempts[key] = attempts
    return len(attempts) > _RATE_LIMIT_MAX


# Lazily built — loading embeddings/dataset is somewhat expensive, and we
# don't want it to slow down `python webapp/server.py --help` etc.
_service: Optional[MovieRecommendationService] = None


def get_service() -> MovieRecommendationService:
    global _service
    if _service is None:
        logger.info("Loading recommendation dataset + embeddings (one-time, cached)...")
        _service = MovieRecommendationService(
            dataset_path=str(settings.data_path),
            embedding_path=str(settings.embedding_path),
        )
    return _service


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"ok": False, "error": "Not authenticated."}), 401
        return fn(*args, **kwargs)
    return wrapper


def classify_locally(text: str) -> Optional[str]:
    if GREETING_PATTERN.match(text):
        return "greeting"
    if FAREWELL_PATTERN.match(text):
        return "farewell"
    return None


def format_genres(genre_string) -> str:
    parts = [g.strip() for g in str(genre_string or "").split(",") if g.strip()]
    return " \u2022 ".join(parts) if parts else "Unknown"


def star_rating(score) -> str:
    try:
        n = max(0, min(5, round(float(score) / 2)))
    except (TypeError, ValueError):
        n = 0
    return "\u2b50" * n + "\u2606" * (5 - n)


def build_reasons(movie: dict, preferences: dict) -> list:
    reasons = []
    if preferences.get("genre") and preferences["genre"].lower() in str(movie.get("genre", "")).lower():
        reasons.append(f"Matches your {preferences['genre']} preference")
    if preferences.get("language"):
        reasons.append(f"Matches your {preferences['language']} language preference")
    if preferences.get("mood"):
        reasons.append(f"Fits your {preferences['mood']} mood")
    if movie.get("similarity_score", 0) > 0.5:
        reasons.append("Similar to your previous interests")
    if not reasons:
        reasons.append("Highly rated pick from the catalog")
    return reasons


def serialize_movie(movie: dict, user_id: int, preferences: dict) -> dict:
    return {
        "title": movie.get("title"),
        "genre": format_genres(movie.get("genre")),
        "rating": movie.get("rating"),
        "starRating": star_rating(movie.get("rating")),
        "runtime": movie.get("runtime"),
        "director": movie.get("director") or "Unknown",
        "overview": movie.get("overview"),
        "poster": movie.get("poster"),
        "trailer": movie.get("trailer"),
        "cast": movie.get("cast") or [],
        "reasons": build_reasons(movie, preferences),
        "isFavorited": is_favorited(user_id, movie["title"]),
        "userRating": get_user_rating_for_movie(user_id, movie["title"]),
    }


# =======================================================================
# Static frontend
# =======================================================================
@app.route("/")
def root():
    return redirect("/chat.html" if session.get("user_id") else "/login.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# =======================================================================
# Auth
# =======================================================================
@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm = data.get("confirm") or ""

    if _rate_limited(f"signup:{request.remote_addr}"):
        return jsonify({"ok": False, "error": "Too many attempts. Please wait a minute and try again."}), 429

    if not username or len(username) < settings.USERNAME_MIN_LENGTH:
        return jsonify({"ok": False, "error": f"Username must be at least {settings.USERNAME_MIN_LENGTH} characters."}), 400
    if password != confirm:
        return jsonify({"ok": False, "error": "Passwords don't match."}), 400
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return jsonify({"ok": False, "error": f"Password should be at least {settings.PASSWORD_MIN_LENGTH} characters."}), 400

    user_id = signup(username, password)
    if user_id is None:
        return jsonify({"ok": False, "error": "That username is already taken."}), 409

    return jsonify({"ok": True, "message": "Account created! Please log in."})


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    remember = bool(data.get("remember", True))

    if _rate_limited(f"login:{request.remote_addr}:{username.lower()}"):
        return jsonify({"ok": False, "error": "Too many attempts. Please wait a minute and try again."}), 429

    user = login(username, password)
    if not user:
        return jsonify({"ok": False, "error": "Invalid username or password."}), 401

    session.clear()
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session.permanent = remember

    touch_login(user["user_id"])
    return jsonify({"ok": True, "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    user_id = session.get("user_id")
    if user_id:
        touch_logout(user_id)
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False})
    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": user})


# =======================================================================
# Chat
# =======================================================================
@app.route("/api/chat/history", methods=["GET"])
@login_required
def api_chat_history():
    user_id = session["user_id"]
    rows = get_chat_history_with_timestamps(user_id)
    return jsonify({
        "ok": True,
        "messages": [{"role": r, "content": m, "timestamp": ts} for r, m, ts in rows],
    })


def _run_turn(user_id: int, prompt: str) -> dict:
    """Shared pipeline for /send and /regenerate. Returns a JSON-able dict:
    {messages: [...new assistant/system messages...], movies: [...] | None}
    Mirrors app.py's logic turn-for-turn."""
    local_intent = classify_locally(prompt)
    new_messages = []

    if local_intent == "greeting":
        save_chat(user_id, "assistant", GREETING_REPLY)
        new_messages.append({"role": "assistant", "content": GREETING_REPLY})
        return {"messages": new_messages, "movies": None}

    if local_intent == "farewell":
        save_chat(user_id, "assistant", FAREWELL_REPLY)
        new_messages.append({"role": "assistant", "content": FAREWELL_REPLY})
        touch_logout(user_id)
        return {"messages": new_messages, "movies": None}

    increment_activity(user_id, "search_count")
    extracted = extract_preferences(prompt, user_id)

    if extracted is None:
        reply = "\u274c Unable to connect to Gemini API. Please try again in a moment."
        save_chat(user_id, "assistant", reply)
        new_messages.append({"role": "assistant", "content": reply})
        return {"messages": new_messages, "movies": None}

    intent = extracted.get("intent")
    if intent in ("greeting", "farewell", "other"):
        reply = (
            GREETING_REPLY if intent == "greeting"
            else FAREWELL_REPLY if intent == "farewell"
            else "Got it! Let me know what kind of movie you're looking for."
        )
        save_chat(user_id, "assistant", reply)
        new_messages.append({"role": "assistant", "content": reply})
        if intent == "farewell":
            touch_logout(user_id)
        return {"messages": new_messages, "movies": None}

    before_prefs = load_preferences(user_id)
    preferences = merge_preferences(user_id, extracted)
    change_note = describe_preference_change(before_prefs, preferences)

    if preferences.get("genre"):
        set_preferred_genre(user_id, preferences["genre"])

    follow_up = next_question(preferences)

    if follow_up and not is_ready_to_recommend(preferences):
        reply = f"{change_note} {follow_up}" if change_note else follow_up
        save_chat(user_id, "assistant", reply)
        new_messages.append({"role": "assistant", "content": reply})
        return {"messages": new_messages, "movies": None}

    movies = get_service().get_recommendations_with_details(preferences, top_n=5, user_id=user_id)
    increment_activity(user_id, "recommendation_requests")

    if change_note:
        save_chat(user_id, "assistant", change_note)
        new_messages.append({"role": "assistant", "content": change_note})

    if not movies:
        summary = "No movies matched the given preferences."
        save_chat(user_id, "assistant", summary)
        new_messages.append({"role": "assistant", "content": summary})
        return {"messages": new_messages, "movies": None}

    summary = "Recommended: " + ", ".join(m["title"] for m in movies)
    save_chat(user_id, "assistant", summary)
    new_messages.append({"role": "assistant", "content": summary})

    serialized = [serialize_movie(m, user_id, preferences) for m in movies]
    return {"messages": new_messages, "movies": serialized}


@app.route("/api/chat/send", methods=["POST"])
@login_required
def api_chat_send():
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    prompt = (data.get("message") or "").strip()

    if not prompt:
        return jsonify({"ok": False, "error": "Message cannot be empty."}), 400
    if len(prompt) > settings.CHAT_MESSAGE_MAX_LENGTH:
        return jsonify({
            "ok": False,
            "error": f"Message is too long (max {settings.CHAT_MESSAGE_MAX_LENGTH} characters).",
        }), 400

    save_chat(user_id, "user", prompt)

    elapsed_minutes = 0.0
    set_session_duration(user_id, round(elapsed_minutes, 2))  # kept for parity with app.py's per-turn write

    try:
        result = _run_turn(user_id, prompt)
    except Exception:
        logger.exception("Chat turn failed for user_id=%s", user_id)
        return jsonify({"ok": False, "error": "Something went wrong generating a reply. Please try again."}), 500

    return jsonify({"ok": True, **result})


@app.route("/api/chat/regenerate", methods=["POST"])
@login_required
def api_chat_regenerate():
    user_id = session["user_id"]
    rows = get_chat_history_with_timestamps(user_id)
    last_user_msg = next((m for r, m, _ in reversed(rows) if r == "user"), None)

    if not last_user_msg:
        return jsonify({"ok": False, "error": "Nothing to regenerate yet."}), 400

    delete_last_assistant_message(user_id)

    try:
        result = _run_turn(user_id, last_user_msg)
    except Exception:
        logger.exception("Regenerate failed for user_id=%s", user_id)
        return jsonify({"ok": False, "error": "Something went wrong regenerating. Please try again."}), 500

    return jsonify({"ok": True, **result})


@app.route("/api/chat/clear", methods=["POST"])
@login_required
def api_chat_clear():
    clear_chat_history(session["user_id"])
    return jsonify({"ok": True})


@app.route("/api/chat/edit-last-user-message", methods=["POST"])
@login_required
def api_edit_last_user_message():
    """Edits the most recent user message and re-runs the pipeline on the
    edited text (drops the stale assistant reply first, same pattern as
    Regenerate)."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    new_text = (data.get("message") or "").strip()
    if not new_text:
        return jsonify({"ok": False, "error": "Message cannot be empty."}), 400

    rows = get_chat_history_with_timestamps(user_id)
    if not rows or rows[-1][0] != "assistant" or len(rows) < 2 or rows[-2][0] != "user":
        return jsonify({"ok": False, "error": "No editable message found."}), 400

    delete_last_assistant_message(user_id)
    # Edit the underlying user row's text isn't exposed by chat_store, so we
    # append a fresh user turn instead \u2014 keeps chat_store's API untouched.
    save_chat(user_id, "user", new_text)

    try:
        result = _run_turn(user_id, new_text)
    except Exception:
        logger.exception("Edit-and-resend failed for user_id=%s", user_id)
        return jsonify({"ok": False, "error": "Something went wrong. Please try again."}), 500

    return jsonify({"ok": True, **result})


# =======================================================================
# Favorites / Ratings / Feedback
# =======================================================================
@app.route("/api/favorites", methods=["GET"])
@login_required
def api_get_favorites():
    return jsonify({"ok": True, "favorites": get_favorites(session["user_id"])})


@app.route("/api/favorites", methods=["POST"])
@login_required
def api_add_favorite():
    data = request.get_json(silent=True) or {}
    title = (data.get("movie_title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "movie_title is required."}), 400
    add_favorite(session["user_id"], title, data.get("genre", ""))
    increment_activity(session["user_id"], "favorites_added")
    log_click(session["user_id"], title, "favorited")
    return jsonify({"ok": True})


@app.route("/api/ratings", methods=["POST"])
@login_required
def api_add_rating():
    data = request.get_json(silent=True) or {}
    title = (data.get("movie_title") or "").strip()
    rating = data.get("rating")
    if not title or rating not in (1, 2, 3, 4, 5):
        return jsonify({"ok": False, "error": "movie_title and rating (1-5) are required."}), 400
    user_id = session["user_id"]
    add_or_update_rating(user_id, title, int(rating))
    track_rating_activity(user_id, int(rating))
    increment_activity(user_id, "movies_clicked")
    log_click(user_id, title, "rated")
    return jsonify({"ok": True})


@app.route("/api/feedback", methods=["POST"])
@login_required
def api_add_feedback():
    data = request.get_json(silent=True) or {}
    score = data.get("satisfaction")
    if score not in (1, 2, 3, 4, 5):
        return jsonify({"ok": False, "error": "satisfaction (1-5) is required."}), 400
    add_feedback(session["user_id"], int(score), data.get("comment", ""))
    return jsonify({"ok": True})


@app.route("/api/trailer-click", methods=["POST"])
@login_required
def api_trailer_click():
    data = request.get_json(silent=True) or {}
    title = (data.get("movie_title") or "").strip()
    increment_activity(session["user_id"], "trailer_clicked")
    if title:
        log_click(session["user_id"], title, "trailer")
    return jsonify({"ok": True})


# =======================================================================
# Profile / Settings
# =======================================================================
@app.route("/api/profile", methods=["GET"])
@login_required
def api_profile():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    return jsonify({
        "ok": True,
        "user": user,
        "favorites": get_favorites(user_id),
        "ratings": get_ratings(user_id),
        "averageRating": average_rating(user_id),
        "preferences": load_preferences(user_id),
    })


@app.route("/api/settings/password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    confirm = data.get("confirm_password") or ""

    if new != confirm:
        return jsonify({"ok": False, "error": "New passwords don't match."}), 400
    if len(new) < settings.PASSWORD_MIN_LENGTH:
        return jsonify({"ok": False, "error": f"New password should be at least {settings.PASSWORD_MIN_LENGTH} characters."}), 400

    if not update_password(session["user_id"], current, new):
        return jsonify({"ok": False, "error": "Current password is incorrect."}), 400

    return jsonify({"ok": True, "message": "Password updated."})


# =======================================================================
# Error handling
# =======================================================================
@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found."}), 404
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.errorhandler(500)
def server_error(e):
    logger.exception("Unhandled server error: %s", e)
    return jsonify({"ok": False, "error": "Internal server error."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.FLASK_PORT, debug=settings.FLASK_DEBUG)
