"""
Integration test for recommendation/recommendation.py's full recommend()
pipeline: dataset loading -> filtering -> hybrid scoring (content,
popularity, rating, history, favorite-genre, search-history) -> TMDB
detail lookup -> duplicate prevention.

Uses a small synthetic dataset + embeddings and a stubbed TMDB HTTP
session (no real network calls), so this runs anywhere, including CI,
without API keys.
"""

import pickle

import numpy as np
import pandas as pd
import pytest

import recommendation.tmdb_api as tmdb_mod
from recommendation.recommendation import RecommendationEngine
from database.auth_store import signup
from database.favorites_store import add_favorite
from database.ratings_store import add_or_update_rating
from database.interaction_store import log_search


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


class _FakeSession:
    """Stands in for requests.Session so no real network call is made."""

    def get(self, url, params=None, timeout=None):
        if url.endswith("/authentication"):
            return _FakeResponse({"success": True})
        if "/videos" in url:
            return _FakeResponse({"results": []})
        if "/credits" in url:
            return _FakeResponse({"cast": [], "crew": []})
        return _FakeResponse({
            "title": "X", "vote_average": 7.0, "release_date": "2020-01-01",
            "runtime": 100, "genres": [{"name": "Action"}], "overview": "overview",
            "poster_path": None, "imdb_id": "tt1",
        })


@pytest.fixture
def stub_tmdb(monkeypatch):
    """Replaces TMDBClient's real HTTP session with the fake one above for
    the duration of one test."""
    def fake_init(self, api_key=None):
        self.api_key = "fake-key"
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base = "https://image.tmdb.org/t/p/w500"
        self.timeout = 10
        self.is_v4_token = False
        self.session = _FakeSession()

    monkeypatch.setattr(tmdb_mod.TMDBClient, "__init__", fake_init)


@pytest.fixture
def synthetic_engine(tmp_path, stub_tmdb):
    """A RecommendationEngine over a small, deterministic synthetic
    dataset — 10 movies, mostly Action/Comedy, with random embeddings."""
    titles = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    genres = ["Action", "Action", "Comedy", "Drama", "Action",
              "Action", "Comedy", "Action", "Action", "Action"]
    df = pd.DataFrame({
        "id": list(range(1, 11)),
        "title": titles,
        "overview": ["overview text"] * 10,
        "genres": genres,
        "original_language": ["en"] * 10,
        "popularity": [10, 20, 5, 8, 15, 3, 12, 9, 11, 14],
        "runtime": [100, 90, 110, 95, 105, 120, 88, 100, 95, 90],
        "vote_average": [7, 8, 6, 7.5, 6.5, 8.2, 7.1, 7.3, 7.6, 7.9],
    })

    rng = np.random.default_rng(42)
    embeddings = rng.random((10, 8))

    csv_path = tmp_path / "data.csv"
    pkl_path = tmp_path / "emb.pkl"
    df.to_csv(csv_path, index=False)
    with open(pkl_path, "wb") as f:
        pickle.dump(embeddings, f)

    return RecommendationEngine(str(csv_path), str(pkl_path))


def test_recommend_returns_requested_top_n(isolated_db, synthetic_engine):
    results = synthetic_engine.recommend({"genre": "Action"}, top_n=3)
    assert len(results) == 3


def test_recommend_filters_by_genre(isolated_db, synthetic_engine):
    results = synthetic_engine.recommend({"genre": "Drama"}, top_n=5)
    assert all("drama" in r["genre"].lower() for r in results)


def test_recommend_no_duplicate_titles_within_one_result_list(isolated_db, synthetic_engine):
    results = synthetic_engine.recommend({"genre": "Action"}, top_n=5)
    titles = [r["title"] for r in results]
    assert len(titles) == len(set(titles))


def test_recommend_excludes_already_favorited_movies(isolated_db, synthetic_engine):
    uid = signup("rec_test_user", "pw123456")
    add_favorite(uid, "A", "Action")
    add_favorite(uid, "E", "Action")

    results = synthetic_engine.recommend({"genre": "Action"}, top_n=3, user_id=uid)
    result_titles = [r["title"] for r in results]

    assert "A" not in result_titles
    assert "E" not in result_titles


def test_recommend_falls_back_to_including_favorites_if_too_few_alternatives(isolated_db, tmp_path, stub_tmdb):
    # Tiny dataset where excluding favorites would leave too few candidates
    # -- the engine should fall back to including them rather than
    # returning an emptier-than-necessary result.
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "title": ["A", "B", "C"],
        "overview": ["o"] * 3,
        "genres": ["Action"] * 3,
        "original_language": ["en"] * 3,
        "popularity": [10, 20, 5],
        "runtime": [100, 90, 110],
        "vote_average": [7, 8, 6],
    })
    embeddings = np.random.default_rng(1).random((3, 8))
    csv_path = tmp_path / "tiny.csv"
    pkl_path = tmp_path / "tiny_emb.pkl"
    df.to_csv(csv_path, index=False)
    with open(pkl_path, "wb") as f:
        pickle.dump(embeddings, f)

    engine = RecommendationEngine(str(csv_path), str(pkl_path))
    uid = signup("rec_test_user2", "pw123456")
    add_favorite(uid, "A", "Action")

    results = engine.recommend({"genre": "Action"}, top_n=3, user_id=uid)
    assert len(results) == 3  # falls back to including "A" rather than returning fewer


def test_recommend_boosts_favorite_genre_even_without_explicit_genre_filter(isolated_db, synthetic_engine):
    uid = signup("rec_test_user3", "pw123456")
    add_favorite(uid, "A", "Action")
    add_or_update_rating(uid, "B", 5)

    # No genre stated this turn -- should still lean toward Action given
    # the user's favorite/highly-rated history.
    results = synthetic_engine.recommend({}, top_n=5, user_id=uid)
    action_count = sum(1 for r in results if "action" in r["genre"].lower())
    assert action_count >= 3  # majority should be Action-leaning


def test_recommend_logs_impressions_for_novelty_penalty(isolated_db, synthetic_engine):
    from database.interaction_store import get_all_shown_titles

    uid = signup("rec_test_user4", "pw123456")
    synthetic_engine.recommend({"genre": "Action"}, top_n=3, user_id=uid)

    shown = get_all_shown_titles(uid)
    assert len(shown) == 3


def test_recommend_empty_when_no_movies_match(isolated_db, synthetic_engine):
    results = synthetic_engine.recommend({"genre": "Nonexistent Genre XYZ"}, top_n=5)
    assert results == []
