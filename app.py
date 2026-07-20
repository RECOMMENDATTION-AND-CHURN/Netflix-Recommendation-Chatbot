"""
app.py
-------
User-facing Netflix AI Chatbot — multi-user version.

Owns: auth gate, UI (Netflix theme, cards, chat bubbles), conversation
orchestration (greeting/exit/slot-filling/change-explanation), and wiring
chatbot/* together with database/activity_store.py for silent behavioral
tracking. Does NOT import churn/model.py — churn prediction stays entirely
in dashboard.py (provider-only), per spec.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import re
import time
import logging

from recommendation.movie_service import MovieRecommendationService
from chatbot.chatbot import extract_preferences
from chatbot.memory import merge_preferences
from chatbot.conversation import is_ready_to_recommend, next_question, describe_preference_change
from database.auth_store import signup, login, get_user_by_id
from database.chat_store import (
    save_chat, get_chat_history, get_chat_history_with_timestamps,
    load_preferences, delete_last_assistant_message, delete_last_user_message,
    delete_trailing_assistant_messages, clear_chat_history,
)
from database.activity_store import (
    touch_login, touch_logout, increment_activity, add_rating as track_rating_activity,
    set_preferred_genre, set_session_duration, get_user_activity,
)
from database.favorites_store import add_favorite, is_favorited, get_favorites
from database.ratings_store import add_or_update_rating, get_user_rating_for_movie
from database.interaction_store import log_click
from database.feedback_store import add_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
ASSISTANT_AVATAR = None
USER_AVATAR = None

GREETING_PATTERN = re.compile(
    r"^\s*(hi|hii+|hey+|hello+|yo|sup|good\s?(morning|afternoon|evening))\s*[!.?]*\s*$",
    re.IGNORECASE,
)
FAREWELL_PATTERN = re.compile(
    r"^\s*(exit|quit|bye|goodbye|good\s?bye|see\s?you|thanks?|thank\s?you|thanks?\s?bye|thank\s?you\s?bye)\s*[!.?]*\s*$",
    re.IGNORECASE,
)
GREETING_REPLY = "👋 Hey! Tell me what kind of movie you're in the mood for — genre, language, mood, or even 'something like Interstellar'."
FAREWELL_REPLY = "Thanks for using Netflix AI.\nHave a great day."


# =====================================================
# Page setup + theme
# =====================================================
st.set_page_config(page_title="Netflix AI Chatbot", page_icon="🎬", layout="centered")

css_path = os.path.join(BASE_DIR, "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Ensure mobile browsers render at device width (not desktop-zoomed-out)
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">',
    unsafe_allow_html=True,
)

# Small progressive-enhancement JS layer (auto-scroll, tap-to-expand cards).
# Purely cosmetic — the app is fully functional without it.
js_path = os.path.join(BASE_DIR, "assets", "script.js")
if os.path.exists(js_path):
    with open(js_path) as f:
        components.html(f"<script>{f.read()}</script>", height=0, width=0)

service = MovieRecommendationService(
    dataset_path=os.path.join(BASE_DIR, "data", "tmdb_Preprocessed_dataset.csv"),
    embedding_path=os.path.join(BASE_DIR, "models", "movie_embeddings.pkl"),
)


# =====================================================
# Helpers
# =====================================================
def classify_locally(text: str):
    if GREETING_PATTERN.match(text):
        return "greeting"
    if FAREWELL_PATTERN.match(text):
        return "farewell"
    return None


def format_genres(genre_string: str) -> str:
    """Fixes the 'ComedyDramaRomance' bug — always renders with clear separators."""
    parts = [g.strip() for g in str(genre_string or "").split(",") if g.strip()]
    return " • ".join(parts) if parts else "Unknown"


def star_rating(score) -> str:
    try:
        n = max(0, min(5, round(float(score) / 2)))  # TMDB is 0-10, show out of 5 stars
    except (TypeError, ValueError):
        n = 0
    return "⭐" * n + "☆" * (5 - n)


def typing_effect(placeholder, text: str, delay: float = 0.012) -> None:
    """Lightweight typing animation for short bot replies (not full movie cards)."""
    shown = ""
    for ch in text:
        shown += ch
        placeholder.markdown(shown)
        time.sleep(delay)


def build_reasons(movie: dict, preferences: dict) -> list:
    """'Why recommended' bullet list."""
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


def render_movie_card(movie: dict, idx: int, user_id: int, preferences: dict) -> None:
    genre_display = format_genres(movie.get("genre"))
    poster_html = (
        f'<img src="{movie["poster"]}" class="nf-poster" loading="lazy" alt="{movie["title"]} poster">'
        if movie.get("poster") else '<div class="nf-poster-placeholder">🎬 No Poster</div>'
    )
    director = movie.get("director") or "Unknown"
    reasons_html = "".join(f"<li>✔ {r}</li>" for r in build_reasons(movie, preferences))
    # Small visual touch: each card fades in slightly later than the one
    # before it (capped so a long list doesn't feel sluggish to appear).
    stagger_delay = min(idx * 0.06, 0.3)

    st.markdown(
        f"""
        <div class="nf-movie-card" style="animation-delay:{stagger_delay}s">
            <div class="nf-poster-wrap">{poster_html}</div>
            <div class="nf-movie-title">{movie['title']}</div>
            <div class="nf-movie-meta">{star_rating(movie['rating'])} &nbsp;
                <span class="nf-badge">⭐ {movie['rating']}</span>
                <span class="nf-badge nf-badge-outline">🕒 {movie['runtime']} min</span>
            </div>
            <div class="nf-movie-meta">{genre_display}</div>
            <div class="nf-movie-meta">🎬 {director}</div>
            <div class="nf-overview">{movie['overview']}</div>
            <div class="nf-reasons"><b>Why recommended</b><ul>{reasons_html}</ul></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if movie.get("cast"):
        st.caption("👥 Top Cast: " + ", ".join(movie["cast"]))

    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        already_fav = is_favorited(user_id, movie["title"])
        label = "✅ Favorited" if already_fav else "👍 Save to Favorites"
        if st.button(label, key=f"fav_{idx}_{movie['title']}", disabled=already_fav):
            add_favorite(user_id, movie["title"], movie.get("genre", ""))
            increment_activity(user_id, "favorites_added")
            log_click(user_id, movie["title"], "favorited")
            st.toast(f"Added {movie['title']} to favorites!")
            st.rerun()

    with action_col2:
        if movie.get("trailer"):
            if st.button("▶ Watch Trailer", key=f"trailer_{idx}_{movie['title']}"):
                increment_activity(user_id, "trailer_clicked")
                log_click(user_id, movie["title"], "trailer")
                st.markdown(f"[Open trailer ↗]({movie['trailer']})")
        else:
            st.caption("Trailer: Unknown")

    with action_col3:
        current_rating = get_user_rating_for_movie(user_id, movie["title"]) or "-"
        options = ["-", 1, 2, 3, 4, 5]
        rating_choice = st.selectbox(
            "Rate", options, index=options.index(current_rating) if current_rating in options else 0,
            key=f"rate_{idx}_{movie['title']}", label_visibility="collapsed"
        )
        if rating_choice != "-" and rating_choice != current_rating:
            add_or_update_rating(user_id, movie["title"], int(rating_choice))
            track_rating_activity(user_id, int(rating_choice))
            increment_activity(user_id, "movies_clicked")
            log_click(user_id, movie["title"], "rated")

    st.write("")


def send_and_store(user_id: int, role: str, content: str) -> None:
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_chat(user_id, role, content)


# =====================================================
# AUTH GATE — Signup / Login / Remember Me
# =====================================================
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

# Try to restore a remembered session from the URL query param
if st.session_state.auth_user is None:
    remembered_uid = st.query_params.get("uid")
    if remembered_uid:
        user = get_user_by_id(int(remembered_uid))
        if user:
            st.session_state.auth_user = user

if st.session_state.auth_user is None:
    # Center a real bordered container (not a bare <div>, so Streamlit's
    # own widgets/tabs/forms actually render *inside* it as DOM children).
    left, mid, right = st.columns([1, 2.2, 1])
    with mid:
        with st.container(border=True, key="nf_auth_card"):
            st.markdown(
                """
                <div class="nf-auth-logo">🎬</div>
                <h2>Netflix AI</h2>
                <div class="nf-sub">Sign in to get personalized movie recommendations.</div>
                """,
                unsafe_allow_html=True,
            )

            tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

            with tab_login:
                with st.form("login_form"):
                    u = st.text_input("Username")
                    p = st.text_input("Password", type="password")
                    remember = st.checkbox("Remember me", value=True)
                    submitted = st.form_submit_button("Log In")

                if submitted:
                    user = login(u, p)
                    if user:
                        st.session_state.auth_user = user
                        if remember:
                            st.query_params["uid"] = str(user["user_id"])
                        touch_login(user["user_id"])
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

            with tab_signup:
                with st.form("signup_form"):
                    new_u = st.text_input("Choose a username")
                    new_p = st.text_input("Choose a password", type="password")
                    new_p2 = st.text_input("Confirm password", type="password")
                    signup_submitted = st.form_submit_button("Sign Up")

                if signup_submitted:
                    if new_p != new_p2:
                        st.error("Passwords don't match.")
                    elif len(new_p) < 6:
                        st.error("Password should be at least 6 characters.")
                    else:
                        uid = signup(new_u, new_p)
                        if uid:
                            st.success("Account created! Please log in.")
                        else:
                            st.error("That username is already taken.")

    st.stop()


# =====================================================
# LOGGED IN — main chatbot
# =====================================================
USER_ID = st.session_state.auth_user["user_id"]
USERNAME = st.session_state.auth_user["username"]

st.markdown(
    f"""
    <div class="nf-hero">
        <h1>🎬 Netflix AI Chatbot</h1>
        <p>Welcome back, {USERNAME.title()}! Tell me your mood, language, or genre.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Session bookkeeping (silent — feeds churn features later) ----
if "session_start" not in st.session_state:
    st.session_state.session_start = time.time()

elapsed_minutes = (time.time() - st.session_state.session_start) / 60.0
set_session_duration(USER_ID, round(elapsed_minutes, 2))

# ---- Persistent chat: restore from SQLite, formatted correctly ----
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": role, "content": message, "timestamp": ts}
        for role, message, ts in get_chat_history_with_timestamps(USER_ID)
    ]

if "prev_preferences_snapshot" not in st.session_state:
    st.session_state.prev_preferences_snapshot = load_preferences(USER_ID)

if "last_movies" not in st.session_state:
    st.session_state.last_movies = None
    st.session_state.last_preferences = {}

# =====================================================
# Sidebar — user-facing only, no churn data by design
# =====================================================
with st.sidebar:
    st.markdown(
        f"""
        <div class="nf-user-chip">
            <div class="nf-avatar-circle">{USERNAME[:1].upper()}</div>
            <div>{USERNAME.title()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🚪 Log Out"):
        touch_logout(USER_ID)
        st.session_state.auth_user = None
        st.session_state.pop("messages", None)
        if "uid" in st.query_params:
            del st.query_params["uid"]
        st.rerun()

    if st.button("🗑️ Clear Chat"):
        clear_chat_history(USER_ID)
        st.session_state.messages = []
        st.session_state.last_movies = None
        st.session_state.last_preferences = {}
        st.session_state.pop("_editing_message_index", None)
        st.toast("Chat cleared.")
        st.rerun()

    st.divider()
    st.subheader("⭐ Your Favorites")
    favs = get_favorites(USER_ID)
    if favs:
        for f in favs[:5]:
            st.caption(f"🎬 {f['movie_title']}")
    else:
        st.caption("No favorites saved yet.")

    st.divider()
    st.subheader("🎛️ Feedback")
    satisfaction = st.slider("How satisfied are you with recommendations?", 1, 5, 3)
    comment = st.text_input("Anything to add? (optional)")
    if st.button("Submit feedback"):
        add_feedback(USER_ID, satisfaction, comment)
        st.success("Thanks for the feedback!")

# =====================================================
# Render existing conversation
# =====================================================
last_user_idx = None
for _i, _m in enumerate(st.session_state.messages):
    if _m["role"] == "user":
        last_user_idx = _i

editing_idx = st.session_state.get("_editing_message_index")

for i, msg in enumerate(st.session_state.messages):
    avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else USER_AVATAR

    # The one message currently being edited renders as an editable form
    # instead of a static bubble.
    if msg["role"] == "user" and i == editing_idx:
        with st.chat_message("user", avatar=USER_AVATAR):
            with st.form(key=f"nf_edit_form_{i}"):
                edited_text = st.text_area("Edit your message", value=msg["content"], label_visibility="collapsed")
                save_col, cancel_col = st.columns(2)
                save_clicked = save_col.form_submit_button("💾 Save & Resend")
                cancel_clicked = cancel_col.form_submit_button("✖ Cancel")

            if cancel_clicked:
                st.session_state.pop("_editing_message_index", None)
                st.rerun()

            if save_clicked and edited_text.strip():
                # Drop this user message + every assistant reply that followed
                # it (both in the UI and in the DB), then treat the edited
                # text exactly like a fresh prompt the user just typed.
                del st.session_state.messages[i:]
                delete_trailing_assistant_messages(USER_ID)
                delete_last_user_message(USER_ID)
                st.session_state.pop("_editing_message_index", None)
                st.session_state["_edited_prompt"] = edited_text.strip()
                st.rerun()
        continue

    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        ts = msg.get("timestamp")
        if ts:
            # Show just the time (HH:MM) — the date is implicit for a live chat.
            st.caption(ts[-8:-3] if len(ts) >= 8 else ts)

        if msg["role"] == "user" and i == last_user_idx and editing_idx is None:
            if st.button("✏️ Edit", key=f"nf_edit_{i}"):
                st.session_state["_editing_message_index"] = i
                st.rerun()

    is_last_message = (i == len(st.session_state.messages) - 1)
    if is_last_message and msg["role"] == "assistant":
        last_user_msg = next(
            (m["content"] for m in reversed(st.session_state.messages[:i]) if m["role"] == "user"),
            None,
        )
        if last_user_msg and st.button("🔄 Regenerate", key="nf_regenerate"):
            # Drop the stale reply (UI + the single most-recent DB row only —
            # never touches the user's message or any other user's rows)
            # then re-run the exact same pipeline on the same prompt.
            st.session_state.messages.pop(i)
            delete_last_assistant_message(USER_ID)
            st.session_state["_regenerate_prompt"] = last_user_msg
            st.rerun()

# =====================================================
# Handle new input
# =====================================================
prompt = st.chat_input("Type your message...")
regenerate_prompt = st.session_state.pop("_regenerate_prompt", None)
edited_prompt = st.session_state.pop("_edited_prompt", None)
is_regenerate = prompt is None and regenerate_prompt is not None
if is_regenerate:
    prompt = regenerate_prompt
elif prompt is None and edited_prompt is not None:
    # An edited message behaves exactly like a brand-new prompt the user
    # just typed — it gets its own fresh chat bubble + DB row below,
    # rather than reusing the (already-deleted) old one.
    prompt = edited_prompt

if prompt:
    if not is_regenerate:
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)
        send_and_store(USER_ID, "user", prompt)

    local_intent = classify_locally(prompt)

    if local_intent == "greeting":
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            ph = st.empty()
            typing_effect(ph, GREETING_REPLY)
        send_and_store(USER_ID, "assistant", GREETING_REPLY)
        st.stop()

    if local_intent == "farewell":
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            ph = st.empty()
            typing_effect(ph, FAREWELL_REPLY)
        send_and_store(USER_ID, "assistant", FAREWELL_REPLY)
        touch_logout(USER_ID)
        st.stop()

    increment_activity(USER_ID, "search_count")

    with st.spinner("🎬 Thinking..."):
        extracted = extract_preferences(prompt, USER_ID)

    if extracted is None:
        reply = "❌ Unable to connect to Gemini API. Please try again in a moment."
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            st.markdown(reply)
        send_and_store(USER_ID, "assistant", reply)

    elif extracted.get("intent") in ("greeting", "farewell", "other"):
        reply = (
            GREETING_REPLY if extracted.get("intent") == "greeting"
            else FAREWELL_REPLY if extracted.get("intent") == "farewell"
            else "Got it! Let me know what kind of movie you're looking for."
        )
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            st.markdown(reply)
        send_and_store(USER_ID, "assistant", reply)
        if extracted.get("intent") == "farewell":
            touch_logout(USER_ID)

    else:
        before_prefs = st.session_state.prev_preferences_snapshot
        preferences = merge_preferences(USER_ID, extracted)
        change_note = describe_preference_change(before_prefs, preferences)
        st.session_state.prev_preferences_snapshot = preferences

        if preferences.get("genre"):
            set_preferred_genre(USER_ID, preferences["genre"])

        follow_up = next_question(preferences)

        if follow_up and not is_ready_to_recommend(preferences):
            reply = f"{change_note} {follow_up}" if change_note else follow_up
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                ph = st.empty()
                typing_effect(ph, reply)
            send_and_store(USER_ID, "assistant", reply)

        else:
            movies = service.get_recommendations_with_details(preferences, top_n=5, user_id=USER_ID)
            increment_activity(USER_ID, "recommendation_requests")

            if change_note:
                with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                    st.markdown(change_note)
                send_and_store(USER_ID, "assistant", change_note)

            if not movies:
                summary = "No movies matched the given preferences."
                with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                    st.warning("No movies matched your preferences. Try a different genre or language?")
                send_and_store(USER_ID, "assistant", summary)
                st.session_state.last_movies = None
            else:
                summary = "Recommended: " + ", ".join(m["title"] for m in movies)
                send_and_store(USER_ID, "assistant", summary)
                # FIX: persist recommendations across reruns (e.g. when a
                # Favorite/Trailer/Rate button is clicked) instead of only
                # rendering them inside this one-shot "new prompt" block.
                st.session_state.last_movies = movies
                st.session_state.last_preferences = preferences

# =====================================================
# Persistent recommendation cards — rendered on EVERY
# rerun (not just when a new prompt arrives), so clicking
# Favorite / Trailer / Rate doesn't make the cards vanish.
# =====================================================
if st.session_state.get("last_movies"):
    st.markdown('<div class="nf-section-title">🎥 Here\'s what I found for you</div>', unsafe_allow_html=True)
    movies = st.session_state.last_movies
    prefs = st.session_state.get("last_preferences", {})
    # Two-column responsive grid — Streamlit's own columns stack to a single
    # column automatically on narrow/mobile viewports, so this stays a real
    # grid on laptop and a clean single column on phones without CSS hacks.
    grid_cols = st.columns(2, gap="medium")
    for i, movie in enumerate(movies):
        with grid_cols[i % 2]:
            render_movie_card(movie, i, USER_ID, prefs)