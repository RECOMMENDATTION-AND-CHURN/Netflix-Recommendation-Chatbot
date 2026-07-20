# Module 1 — Website Frontend

A standalone, Netflix-inspired website (separate from the Streamlit app)
with Login, Signup, Chat, Profile, and Settings pages. It talks to a small
Flask JSON API that reuses the **existing** `chatbot/`, `recommendation/`,
and `database/` packages — the same orchestration logic `app.py` already
uses — so behavior stays identical, just delivered over HTTP + a proper
web UI instead of Streamlit reruns.

## Run it

```bash
cd Netflix-Recommendation-Chatbot
pip install flask
python webapp/server.py
```

Then open **http://localhost:5000/login.html**. Sign up, then log in.

This does not touch `app.py` (Streamlit chatbot) or `dashboard.py`
(provider dashboard) — both keep running exactly as before, on their own
`streamlit run` commands. All three surfaces share the same `chatbot.db`
SQLite file, so signing up or chatting in one is visible in the others.

## What's here

```
webapp/
  server.py              Flask app: auth, chat, favorites, ratings, profile, settings
  frontend/
    login.html            Login page
    signup.html            Signup page
    chat.html               Chat page (ChatGPT-style bubbles + movie cards)
    profile.html             Profile page (stats, preferences, favorites, ratings)
    settings.html              Settings page (password, UI prefs, feedback)
    css/style.css                Shared Netflix-dark glassmorphism theme
    js/api.js                     Tiny fetch() wrapper
    js/toast.js                    Toast notifications
    js/shell.js                     Sidebar + auth guard shared by logged-in pages
    js/chat.js                       Chat page logic
    js/profile.js                     Profile page logic
    js/settings.js                     Settings page logic
```

## Two small additive functions

To support "Clear chat" and "Change password" without altering any
existing function's behavior, two new functions were added:

- `database/chat_store.py` → `clear_chat_history(user_id)`
- `database/auth_store.py` → `update_password(user_id, current, new)`

Both are pure additions — every existing function in those files is
untouched, and nothing that already imports from them can break.

## Environment variables (optional)

- `NETFLIX_SECRET_KEY` — Flask session signing key. If unset, a random
  key is generated at startup (fine for local dev; sessions won't survive
  a server restart — set this explicitly for anything persistent).
- `PORT` — defaults to 5000.
- `FLASK_DEBUG` — defaults to `1` (auto-reload). Set to `0` for production.

## Known limitation carried over from app.py

`chatbot/chatbot.py`'s `extract_preferences()` requires the Gemini API
(`GEMINI_API_KEY` env var, wired in `chatbot/gemini_api.py`). Without it
configured, chat replies fall back to "Unable to connect to Gemini API" —
identical to what happens in the existing Streamlit app today.
