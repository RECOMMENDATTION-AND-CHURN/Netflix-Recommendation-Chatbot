"""Unit tests for database/favorites_store.py, ratings_store.py, feedback_store.py."""

from database.favorites_store import add_favorite, get_favorites, is_favorited
from database.ratings_store import (
    add_or_update_rating, get_ratings, get_user_rating_for_movie,
    get_all_ratings, average_rating,
)
from database.feedback_store import add_feedback, get_feedback


def test_add_favorite_and_is_favorited(isolated_db, make_user):
    uid = make_user()
    assert is_favorited(uid, "Inception") is False
    add_favorite(uid, "Inception", "Sci-Fi")
    assert is_favorited(uid, "Inception") is True


def test_get_favorites_scoped_per_user(isolated_db, make_user):
    uid1 = make_user()
    uid2 = make_user()
    add_favorite(uid1, "Movie A", "Action")
    add_favorite(uid2, "Movie B", "Comedy")

    favs1 = get_favorites(uid1)
    assert len(favs1) == 1
    assert favs1[0]["movie_title"] == "Movie A"

    favs2 = get_favorites(uid2)
    assert len(favs2) == 1
    assert favs2[0]["movie_title"] == "Movie B"


def test_add_or_update_rating_inserts_then_updates(isolated_db, make_user):
    uid = make_user()
    add_or_update_rating(uid, "Interstellar", 4)
    assert get_user_rating_for_movie(uid, "Interstellar") == 4

    # Rating the same movie again should UPDATE, not create a second row.
    add_or_update_rating(uid, "Interstellar", 5)
    assert get_user_rating_for_movie(uid, "Interstellar") == 5
    assert len(get_ratings(uid)) == 1


def test_get_user_rating_for_movie_unrated_returns_none(isolated_db, make_user):
    uid = make_user()
    assert get_user_rating_for_movie(uid, "Never Rated") is None


def test_average_rating_computed_correctly(isolated_db, make_user):
    uid = make_user()
    add_or_update_rating(uid, "Movie A", 4)
    add_or_update_rating(uid, "Movie B", 2)
    assert average_rating(uid) == 3.0


def test_average_rating_zero_when_no_ratings(isolated_db, make_user):
    uid = make_user()
    assert average_rating(uid) == 0.0


def test_get_all_ratings_includes_every_user(isolated_db, make_user):
    uid1 = make_user()
    uid2 = make_user()
    add_or_update_rating(uid1, "Movie A", 5)
    add_or_update_rating(uid2, "Movie B", 3)

    all_ratings = get_all_ratings()
    assert len(all_ratings) == 2


def test_add_and_get_feedback(isolated_db, make_user):
    uid = make_user()
    add_feedback(uid, 4, "Pretty good recommendations")
    feedback = get_feedback(uid)
    assert len(feedback) == 1
    assert feedback[0]["score"] == 4
    assert feedback[0]["comment"] == "Pretty good recommendations"
