# Test suite

88 tests covering every database module, the recommendation engine, the
chatbot's memory/conversation logic, config/logging/backup (Module 6),
and a full Flask API user journey (Module 1).

## Run it

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Design

- **`conftest.py`** provides `isolated_db` (every test gets a brand-new,
  throwaway SQLite file — the suite never touches your real `chatbot.db`)
  and `make_user` (a one-line factory for a signed-up test user).
- **No real network calls, anywhere.** TMDB and Gemini are both stubbed:
  - `test_recommendation_engine_integration.py` and
    `test_webapp_integration.py` replace `TMDBClient`'s HTTP session with
    a fake one that returns canned JSON.
  - `test_webapp_integration.py` monkeypatches `extract_preferences`
    directly, so it never needs a `GEMINI_API_KEY` to test the full
    chat -> recommend pipeline.
- **Unit tests** (`test_auth_store.py`, `test_chat_store.py`,
  `test_favorites_ratings_feedback.py`, `test_interaction_store.py`,
  `test_analytics_store.py`, `test_memory.py`, `test_conversation.py`,
  `test_config.py`, `test_backup.py`) each exercise one module in
  isolation.
- **Integration tests** (`test_recommendation_engine_integration.py`,
  `test_webapp_integration.py`) exercise the real pipelines end-to-end —
  a synthetic dataset through the actual hybrid-scoring `recommend()`
  method, and a full signup → login → chat → favorite → rate → profile →
  password-change → logout journey through the real Flask test client.

## Adding a new test

Request the `isolated_db` fixture (or `make_user`, which implies it) and
you're isolated automatically — no manual setup/teardown needed.
