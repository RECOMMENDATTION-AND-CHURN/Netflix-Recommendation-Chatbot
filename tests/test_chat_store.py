"""Unit tests for database/chat_store.py (chat history + preference memory)."""

from database.chat_store import (
    save_chat,
    get_chat_history,
    get_chat_history_with_timestamps,
    get_recent_chat,
    load_preferences,
    save_preferences,
    clear_preferences,
    clear_chat_history,
    delete_last_assistant_message,
    delete_last_user_message,
    delete_trailing_assistant_messages,
    DEFAULT_PREFERENCES,
)


def test_save_and_get_chat_history_order(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "hello")
    save_chat(uid, "assistant", "hi there")
    save_chat(uid, "user", "recommend action movies")

    history = get_chat_history(uid)
    assert history == [
        ("user", "hello"),
        ("assistant", "hi there"),
        ("user", "recommend action movies"),
    ]


def test_chat_history_scoped_per_user(isolated_db, make_user):
    uid1 = make_user()
    uid2 = make_user()
    save_chat(uid1, "user", "user 1 message")
    save_chat(uid2, "user", "user 2 message")

    assert get_chat_history(uid1) == [("user", "user 1 message")]
    assert get_chat_history(uid2) == [("user", "user 2 message")]


def test_get_chat_history_with_timestamps_includes_timestamp(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "hello")
    rows = get_chat_history_with_timestamps(uid)
    assert len(rows) == 1
    role, message, ts = rows[0]
    assert role == "user"
    assert message == "hello"
    assert ts  # non-empty timestamp string


def test_get_recent_chat_respects_limit_and_order(isolated_db, make_user):
    uid = make_user()
    for i in range(5):
        save_chat(uid, "user", f"message {i}")

    recent = get_recent_chat(uid, limit=3)
    # Should be the last 3, in chronological (not reverse) order
    assert recent == [("user", "message 2"), ("user", "message 3"), ("user", "message 4")]


def test_load_preferences_defaults_for_new_user(isolated_db, make_user):
    uid = make_user()
    prefs = load_preferences(uid)
    assert prefs == DEFAULT_PREFERENCES


def test_save_and_load_preferences_roundtrip(isolated_db, make_user):
    uid = make_user()
    save_preferences(uid, {
        "intent": "preference", "movie_name": None, "mood": "happy",
        "genre": "Comedy", "language": "English", "watch_time": 120, "audience": "Friends",
    })
    prefs = load_preferences(uid)
    assert prefs["genre"] == "Comedy"
    assert prefs["language"] == "English"
    assert prefs["watch_time"] == 120


def test_save_preferences_overwrites_previous(isolated_db, make_user):
    uid = make_user()
    save_preferences(uid, {**DEFAULT_PREFERENCES, "genre": "Action"})
    save_preferences(uid, {**DEFAULT_PREFERENCES, "genre": "Horror"})
    assert load_preferences(uid)["genre"] == "Horror"


def test_clear_preferences_resets_to_default(isolated_db, make_user):
    uid = make_user()
    save_preferences(uid, {**DEFAULT_PREFERENCES, "genre": "Action"})
    clear_preferences(uid)
    assert load_preferences(uid) == DEFAULT_PREFERENCES


def test_clear_chat_history_removes_all_messages_only_for_that_user(isolated_db, make_user):
    uid1 = make_user()
    uid2 = make_user()
    save_chat(uid1, "user", "hello")
    save_chat(uid2, "user", "hello from user 2")

    clear_chat_history(uid1)

    assert get_chat_history(uid1) == []
    assert get_chat_history(uid2) == [("user", "hello from user 2")]


def test_delete_last_assistant_message_only_removes_most_recent(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "hi")
    save_chat(uid, "assistant", "reply 1")
    save_chat(uid, "assistant", "reply 2")

    delete_last_assistant_message(uid)

    assert get_chat_history(uid) == [("user", "hi"), ("assistant", "reply 1")]


def test_delete_last_assistant_message_noop_when_none_exist(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "hi")
    delete_last_assistant_message(uid)  # should not raise
    assert get_chat_history(uid) == [("user", "hi")]


def test_delete_last_user_message_only_removes_most_recent_user_row(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "first")
    save_chat(uid, "assistant", "reply")
    save_chat(uid, "user", "second")

    delete_last_user_message(uid)

    assert get_chat_history(uid) == [("user", "first"), ("assistant", "reply")]


def test_delete_trailing_assistant_messages_stops_at_user_row(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "hi")
    save_chat(uid, "assistant", "reply 1")
    save_chat(uid, "user", "recommend action")
    save_chat(uid, "assistant", "change note")
    save_chat(uid, "assistant", "recommendation summary")

    delete_trailing_assistant_messages(uid)

    # Only the two trailing assistant messages after the LAST user row
    # should be removed — the earlier user/assistant pair stays intact.
    assert get_chat_history(uid) == [
        ("user", "hi"),
        ("assistant", "reply 1"),
        ("user", "recommend action"),
    ]


def test_delete_trailing_assistant_messages_noop_when_last_row_is_user(isolated_db, make_user):
    uid = make_user()
    save_chat(uid, "user", "hi")
    delete_trailing_assistant_messages(uid)
    assert get_chat_history(uid) == [("user", "hi")]
