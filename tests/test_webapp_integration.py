"""
Integration test for webapp/server.py (Module 1's Flask API): a full
signup -> login -> chat -> favorite -> rate -> profile -> logout journey
through the real Flask test client and real database layer.

Gemini and TMDB are stubbed (no real network / API keys needed):
  - webapp.server.extract_preferences is monkeypatched to return a fixed
    preferences dict, exactly like a real Gemini reply would.
  - webapp.server.get_service is monkeypatched to return a
    MovieRecommendationService backed by a tiny synthetic dataset and a
    stubbed TMDB HTTP session (see test_recommendation_engine_integration.py
    for the same pattern).
"""

import pickle

import numpy as np
import pandas as pd
import pytest

import recommendation.tmdb_api as tmdb_mod
from recommendation.movie_service import MovieRecommendationService


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


class _FakeSession:
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
def webapp_client(isolated_db, tmp_path, monkeypatch):
    def fake_tmdb_init(self, api_key=None):
        self.api_key = "fake-key"
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base = "https://image.tmdb.org/t/p/w500"
        self.timeout = 10
        self.is_v4_token = False
        self.session = _FakeSession()

    monkeypatch.setattr(tmdb_mod.TMDBClient, "__init__", fake_tmdb_init)

    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "title": ["Action Movie One", "Action Movie Two", "Comedy Movie", "Drama Movie", "Action Movie Three"],
        "overview": ["overview"] * 5,
        "genres": ["Action", "Action", "Comedy", "Drama", "Action"],
        "original_language": ["en"] * 5,
        "popularity": [10, 20, 5, 8, 15],
        "runtime": [100, 90, 110, 95, 105],
        "vote_average": [7, 8, 6, 7.5, 6.5],
    })
    embeddings = np.random.default_rng(7).random((5, 8))
    csv_path = tmp_path / "data.csv"
    pkl_path = tmp_path / "emb.pkl"
    df.to_csv(csv_path, index=False)
    with open(pkl_path, "wb") as f:
        pickle.dump(embeddings, f)

    fake_service = MovieRecommendationService(str(csv_path), str(pkl_path))

    import webapp.server as server
    monkeypatch.setattr(server, "get_service", lambda: fake_service)
    monkeypatch.setattr(
        server,
        "extract_preferences",
        lambda prompt, user_id=None: {
            "intent": "preference", "movie_name": None, "mood": None,
            "genre": "Action", "language": "English", "watch_time": None, "audience": None,
        },
    )

    server.app.config.update(TESTING=True)
    with server.app.test_client() as client:
        yield client


def test_full_user_journey(webapp_client):
    client = webapp_client

    # Not authenticated yet
    r = client.get("/api/auth/me")
    assert r.get_json()["authenticated"] is False

    # Signup
    r = client.post("/api/auth/signup", json={
        "username": "integrationuser", "password": "pw123456", "confirm": "pw123456",
    })
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    # Login
    r = client.post("/api/auth/login", json={"username": "integrationuser", "password": "pw123456"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["user"]["username"] == "integrationuser"

    # Now authenticated
    r = client.get("/api/auth/me")
    assert r.get_json()["authenticated"] is True

    # Greeting doesn't need Gemini at all (caught by local regex first)
    r = client.post("/api/chat/send", json={"message": "hi"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    # A real preference message goes through the (stubbed) extract_preferences
    # -> merge -> recommend pipeline end-to-end
    r = client.post("/api/chat/send", json={"message": "recommend an action movie"})
    body = r.get_json()
    assert body["ok"] is True
    assert body["movies"] is not None
    assert len(body["movies"]) > 0
    first_movie = body["movies"][0]["title"]

    # Favorite it
    r = client.post("/api/favorites", json={"movie_title": first_movie, "genre": "Action"})
    assert r.get_json()["ok"] is True

    # Rate it
    r = client.post("/api/ratings", json={"movie_title": first_movie, "rating": 5})
    assert r.get_json()["ok"] is True

    # Profile should reflect both
    r = client.get("/api/profile")
    profile = r.get_json()
    assert profile["ok"] is True
    assert any(f["movie_title"] == first_movie for f in profile["favorites"])
    assert any(rt["movie_title"] == first_movie for rt in profile["ratings"])
    assert profile["preferences"]["genre"] == "Action"

    # Change password
    r = client.post("/api/settings/password", json={
        "current_password": "pw123456", "new_password": "newpw123456", "confirm_password": "newpw123456",
    })
    assert r.get_json()["ok"] is True

    # Logout
    r = client.post("/api/auth/logout")
    assert r.get_json()["ok"] is True
    r = client.get("/api/auth/me")
    assert r.get_json()["authenticated"] is False

    # Old password no longer works; new one does
    r = client.post("/api/auth/login", json={"username": "integrationuser", "password": "pw123456"})
    assert r.get_json()["ok"] is False
    r = client.post("/api/auth/login", json={"username": "integrationuser", "password": "newpw123456"})
    assert r.get_json()["ok"] is True


def test_message_too_long_is_rejected(webapp_client):
    client = webapp_client
    client.post("/api/auth/signup", json={"username": "longmsguser", "password": "pw123456", "confirm": "pw123456"})
    client.post("/api/auth/login", json={"username": "longmsguser", "password": "pw123456"})

    r = client.post("/api/chat/send", json={"message": "x" * 3000})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_chat_requires_authentication(webapp_client):
    client = webapp_client
    r = client.post("/api/chat/send", json={"message": "hi"})
    assert r.status_code == 401


def test_signup_rejects_mismatched_passwords(webapp_client):
    client = webapp_client
    r = client.post("/api/auth/signup", json={
        "username": "mismatcheduser", "password": "pw123456", "confirm": "differentpw",
    })
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_signup_rejects_duplicate_username(webapp_client):
    client = webapp_client
    client.post("/api/auth/signup", json={"username": "dupuser", "password": "pw123456", "confirm": "pw123456"})
    r = client.post("/api/auth/signup", json={"username": "dupuser", "password": "pw123456", "confirm": "pw123456"})
    assert r.status_code == 409
