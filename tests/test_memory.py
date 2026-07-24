"""Unit tests for chatbot/memory.py (merge_preferences)."""

from chatbot.memory import merge_preferences
from database.chat_store import DEFAULT_PREFERENCES


def test_merge_preferences_fills_in_new_user(isolated_db, make_user):
    uid = make_user()
    new_prefs = {**DEFAULT_PREFERENCES, "intent": "preference", "genre": "Comedy"}
    result = merge_preferences(uid, new_prefs)
    assert result["genre"] == "Comedy"
    assert result["intent"] == "preference"


def test_merge_preferences_keeps_old_values_when_new_is_null(isolated_db, make_user):
    uid = make_user()
    merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": "preference", "language": "Tamil"})
    result = merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": "preference", "genre": "Comedy"})
    # language from the first turn should still be present after the second
    assert result["language"] == "Tamil"
    assert result["genre"] == "Comedy"


def test_merge_preferences_resets_everything_on_intent_change(isolated_db, make_user):
    uid = make_user()
    merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": "preference", "genre": "Comedy", "language": "Tamil"})
    result = merge_preferences(uid, {
        **DEFAULT_PREFERENCES, "intent": "similar_movie", "movie_name": "Interstellar",
    })
    # Old genre/language should be wiped since the intent changed
    assert result["genre"] is None
    assert result["language"] is None
    assert result["movie_name"] == "Interstellar"
    assert result["intent"] == "similar_movie"


def test_merge_preferences_no_reset_when_intent_unchanged(isolated_db, make_user):
    uid = make_user()
    merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": "preference", "genre": "Comedy"})
    result = merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": "preference", "language": "English"})
    # Same intent both times -> genre from turn 1 should survive
    assert result["genre"] == "Comedy"
    assert result["language"] == "English"


def test_merge_preferences_no_reset_when_first_intent_is_none(isolated_db, make_user):
    uid = make_user()
    # First turn has no intent at all (e.g. a bare "Tamil") — the second
    # turn's intent shouldn't trigger a reset since there was nothing to
    # compare against.
    merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": None, "language": "Tamil"})
    result = merge_preferences(uid, {**DEFAULT_PREFERENCES, "intent": "preference", "genre": "Comedy"})
    assert result["language"] == "Tamil"
    assert result["genre"] == "Comedy"
