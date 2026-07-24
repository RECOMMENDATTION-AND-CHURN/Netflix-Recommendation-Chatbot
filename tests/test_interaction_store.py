"""Unit tests for database/interaction_store.py (search history + click/engagement history)."""

from database.interaction_store import (
    log_search, get_top_genres, get_top_languages,
    log_click, log_clicks_bulk, get_engaged_titles, get_all_shown_titles,
)


def test_log_search_and_get_top_genres_ranks_by_frequency(isolated_db, make_user):
    uid = make_user()
    log_search(uid, "Action", "en", "excited")
    log_search(uid, "Action", "en", None)
    log_search(uid, "Comedy", "en", None)

    top = get_top_genres(uid, limit=2)
    assert top[0] == "action"  # most frequent, lowercased
    assert "comedy" in top


def test_log_search_ignores_calls_with_no_signal(isolated_db, make_user):
    uid = make_user()
    log_search(uid, None, None, None)
    assert get_top_genres(uid) == []


def test_get_top_languages_ranks_by_frequency(isolated_db, make_user):
    uid = make_user()
    log_search(uid, "Action", "en", None)
    log_search(uid, "Action", "en", None)
    log_search(uid, "Drama", "ta", None)

    top = get_top_languages(uid, limit=2)
    assert top[0] == "en"


def test_log_click_and_get_engaged_titles(isolated_db, make_user):
    uid = make_user()
    log_click(uid, "Movie A", "recommended")
    log_click(uid, "Movie A", "trailer")
    log_click(uid, "Movie B", "rated")

    engaged = get_engaged_titles(uid)
    # "recommended" (passive impression) should be excluded by default
    assert "Movie A" in engaged
    assert "Movie B" in engaged


def test_log_click_rejects_invalid_interaction_type(isolated_db, make_user):
    uid = make_user()
    log_click(uid, "Movie A", "not_a_real_type")
    assert get_all_shown_titles(uid) == []


def test_log_clicks_bulk_logs_every_title(isolated_db, make_user):
    uid = make_user()
    log_clicks_bulk(uid, ["Movie A", "Movie B", "Movie C"], "recommended")
    shown = get_all_shown_titles(uid)
    assert set(shown) == {"Movie A", "Movie B", "Movie C"}


def test_get_all_shown_titles_includes_recommended(isolated_db, make_user):
    uid = make_user()
    log_click(uid, "Movie A", "recommended")
    assert "Movie A" in get_all_shown_titles(uid)


def test_interactions_scoped_per_user(isolated_db, make_user):
    uid1 = make_user()
    uid2 = make_user()
    log_click(uid1, "Movie A", "favorited")
    log_click(uid2, "Movie B", "favorited")

    assert get_engaged_titles(uid1) == ["Movie A"]
    assert get_engaged_titles(uid2) == ["Movie B"]
