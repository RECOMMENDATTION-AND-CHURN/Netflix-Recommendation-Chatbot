"""Unit tests for chatbot/conversation.py — pure logic, no DB needed."""

from chatbot.conversation import is_ready_to_recommend, next_question, describe_preference_change


def test_is_ready_to_recommend_true_with_genre_and_language():
    prefs = {"intent": "preference", "genre": "Comedy", "language": "English"}
    assert is_ready_to_recommend(prefs) is True


def test_is_ready_to_recommend_true_with_mood_and_language():
    prefs = {"intent": "preference", "mood": "happy", "language": "English"}
    assert is_ready_to_recommend(prefs) is True


def test_is_ready_to_recommend_false_missing_language():
    prefs = {"intent": "preference", "genre": "Comedy", "language": None}
    assert is_ready_to_recommend(prefs) is False


def test_is_ready_to_recommend_false_missing_genre_and_mood():
    prefs = {"intent": "preference", "genre": None, "mood": None, "language": "English"}
    assert is_ready_to_recommend(prefs) is False


def test_is_ready_to_recommend_true_for_similar_movie_intent():
    prefs = {"intent": "similar_movie", "movie_name": "Interstellar", "language": None, "genre": None}
    assert is_ready_to_recommend(prefs) is True


def test_is_ready_to_recommend_false_similar_movie_without_name():
    prefs = {"intent": "similar_movie", "movie_name": None}
    assert is_ready_to_recommend(prefs) is False


def test_next_question_asks_for_language_first():
    prefs = {"intent": "preference", "genre": "Comedy", "language": None}
    q = next_question(prefs)
    assert "language" in q.lower()


def test_next_question_asks_for_genre_when_language_known():
    prefs = {"intent": "preference", "genre": None, "mood": None, "language": "English"}
    q = next_question(prefs)
    assert "genre" in q.lower()


def test_next_question_none_when_ready():
    prefs = {"intent": "preference", "genre": "Comedy", "language": "English"}
    assert next_question(prefs) is None


def test_describe_preference_change_none_on_first_message():
    before = {"genre": None, "language": None, "mood": None, "audience": None, "watch_time": None}
    after = {"genre": "Comedy", "language": None, "mood": None, "audience": None, "watch_time": None}
    # Nothing was "changed" (there was no old value to switch from) — only
    # newly set for the first time. describe_preference_change should not
    # comment on brand-new information, only on an actual switch.
    assert describe_preference_change(before, after) is None


def test_describe_preference_change_detects_a_switch():
    before = {"genre": "Comedy", "language": "Tamil", "mood": None, "audience": None, "watch_time": None}
    after = {"genre": "Comedy", "language": "English", "mood": None, "audience": None, "watch_time": None}
    result = describe_preference_change(before, after)
    assert result is not None
    assert "language" in result.lower()
    assert "english" in result.lower()


def test_describe_preference_change_mentions_kept_values():
    before = {"genre": "Comedy", "language": "Tamil", "mood": None, "audience": None, "watch_time": None}
    after = {"genre": "Comedy", "language": "English", "mood": None, "audience": None, "watch_time": None}
    result = describe_preference_change(before, after)
    assert "genre" in result.lower()  # kept genre should be mentioned too
