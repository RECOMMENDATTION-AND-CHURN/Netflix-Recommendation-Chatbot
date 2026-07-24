"""Unit tests for database/analytics_store.py (Module 5 provider dashboard analytics)."""

from database.chat_store import save_chat
from database.interaction_store import log_click
from database.favorites_store import add_favorite
from database.ratings_store import add_or_update_rating
from database.analytics_store import (
    get_recent_activity_feed,
    get_recommendation_acceptance_rate,
    get_movie_popularity,
)


def test_activity_feed_includes_chat_and_click_events(isolated_db, make_user):
    uid = make_user("alice")
    save_chat(uid, "user", "recommend action movies")
    log_click(uid, "Movie A", "favorited")

    feed = get_recent_activity_feed(limit=10)
    texts = [e["text"] for e in feed]
    usernames = [e["username"] for e in feed]

    assert any("recommend action movies" in t for t in texts)
    assert any("favorited" in t and "Movie A" in t for t in texts)
    assert all(u == "alice" for u in usernames)


def test_activity_feed_excludes_passive_recommended_impressions(isolated_db, make_user):
    uid = make_user()
    log_click(uid, "Movie A", "recommended")  # passive impression, not a real "action"
    feed = get_recent_activity_feed(limit=10)
    assert feed == []


def test_activity_feed_respects_limit(isolated_db, make_user):
    uid = make_user()
    for i in range(5):
        save_chat(uid, "user", f"search {i}")
    feed = get_recent_activity_feed(limit=3)
    assert len(feed) == 3


def test_recommendation_acceptance_rate_with_no_data(isolated_db):
    result = get_recommendation_acceptance_rate()
    assert result == {"total_recommended": 0, "accepted": 0, "acceptance_rate_pct": 0.0}


def test_recommendation_acceptance_rate_computed_correctly(isolated_db, make_user):
    uid = make_user()
    # Two movies recommended; only one acted on (favorited).
    log_click(uid, "Movie A", "recommended")
    log_click(uid, "Movie B", "recommended")
    log_click(uid, "Movie A", "favorited")

    result = get_recommendation_acceptance_rate()
    assert result["total_recommended"] == 2
    assert result["accepted"] == 1
    assert result["acceptance_rate_pct"] == 50.0


def test_movie_popularity_ranks_by_total_interactions(isolated_db, make_user):
    uid = make_user()
    log_click(uid, "Popular Movie", "recommended")
    log_click(uid, "Popular Movie", "favorited")
    log_click(uid, "Popular Movie", "trailer")
    log_click(uid, "Less Popular Movie", "recommended")

    df = get_movie_popularity(limit=10)
    assert df.iloc[0]["movie_title"] == "Popular Movie"
    assert df.iloc[0]["total"] == 3


def test_movie_popularity_empty_when_no_interactions(isolated_db):
    df = get_movie_popularity()
    assert df.empty
    assert list(df.columns) == ["movie_title", "recommended", "favorited", "trailer", "rated", "total"]
