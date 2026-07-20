# recommendation.py
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import numpy as np
from collections import Counter
from recommendation.tmdb_api import TMDBClient

# Optional — used only to build the "user history" signal in the hybrid
# score (favorites + highly-rated movies). Imported lazily/defensively so
# the engine still works standalone (e.g. the __main__ test block below)
# even if the database package or its sqlite file isn't set up yet.
try:
    from database.favorites_store import get_favorites
    from database.ratings_store import get_ratings
    from database.interaction_store import (
        get_top_genres as _get_top_searched_genres,
        get_top_languages as _get_top_searched_languages,
        get_engaged_titles,
        get_all_shown_titles,
    )
except Exception:  # pragma: no cover - defensive only
    get_favorites = None
    get_ratings = None
    _get_top_searched_genres = None
    _get_top_searched_languages = None
    get_engaged_titles = None
    get_all_shown_titles = None


def _min_max_normalize(values: np.ndarray) -> np.ndarray:
    """Scales an array to 0-1. Flat/empty arrays return all-zeros instead
    of dividing by zero, so a single-candidate result doesn't blow up."""
    if values.size == 0:
        return values
    lo, hi = values.min(), values.max()
    if hi - lo < 1e-9:
        return np.zeros_like(values, dtype=float)
    return (values - lo) / (hi - lo)


class RecommendationEngine:

    # Hybrid score weights — content similarity still dominates (this is a
    # recommendation engine, not a popularity chart), with popularity/
    # rating/history/behavioral signals as supporting weights. All six
    # weights sum to 1.0. Kept as class constants so a future tuning pass
    # has one obvious place to change them.
    W_CONTENT = 0.35
    W_POPULARITY = 0.10
    W_RATING = 0.10
    W_HISTORY = 0.20        # embedding similarity to favorited/rated/clicked movies
    W_FAVORITE_GENRE = 0.10  # boost for genres the user favorites/rates highly, most often
    W_SEARCH_HISTORY = 0.15  # boost for genres/languages the user has searched for most, over time

    # Soft penalty applied per prior "recommended" impression of a movie,
    # so the same handful of titles don't dominate every session (duplicate
    # prevention across turns/sessions, not just within one result list).
    REPEAT_IMPRESSION_PENALTY = 0.06
    MAX_REPEAT_PENALTY = 0.30

    # Diversity cap: at most this many of the final top_n may share the
    # same primary genre, so results aren't 5 near-identical Action movies.
    MAX_PER_PRIMARY_GENRE_RATIO = 0.6

    def __init__(self, dataset_path, embedding_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)

        # Load embeddings
        with open(embedding_path, "rb") as f:
            self.embeddings = pickle.load(f)

        # Create similarity matrix
        self.similarity = cosine_similarity(self.embeddings)

        # Title -> first-matching-row-index, used to look up a user's
        # favorited/rated movies against our own embeddings for the
        # "user history" signal in the hybrid score.
        self.title_to_index = {}
        for i, title in enumerate(self.df["title"]):
            key = str(title).strip().lower()
            if key not in self.title_to_index:
                self.title_to_index[key] = i

        # Initialize TMDB client (auto-detects v3/v4 key from .env)
        self.tmdb = TMDBClient()

    # ------------------------------------------------------------------
    # Hybrid scoring signals
    # ------------------------------------------------------------------
    def _user_history_vector(self, user_id):
        """Mean embedding of a user's favorited + highly-rated (>=4) +
        engaged-with (trailer watched / rated / favorited via movie_clicks)
        movies. Returns None if there's no usable history (new user, DB
        unavailable, or none of their titles matched our dataset)."""
        if not user_id or get_favorites is None or get_ratings is None:
            return None

        liked_titles = set()
        try:
            for fav in get_favorites(user_id):
                liked_titles.add(str(fav.get("movie_title", "")).strip().lower())
            for r in get_ratings(user_id):
                if r.get("rating", 0) >= 4:
                    liked_titles.add(str(r.get("movie_title", "")).strip().lower())
            if get_engaged_titles is not None:
                for title in get_engaged_titles(user_id):
                    liked_titles.add(str(title).strip().lower())
        except Exception:
            return None  # DB hiccup — degrade gracefully, no history boost

        indices = [self.title_to_index[t] for t in liked_titles if t in self.title_to_index]
        if not indices:
            return None

        return self.embeddings[indices].mean(axis=0)

    def _favorite_genre_scores(self, filtered_df, user_id):
        """Boosts candidates whose primary genre matches the genres the
        user favorites/rates highly most often — distinct from the
        explicit genre FILTER above, which only fires when genre was
        stated in the current turn. This is a soft preference signal that
        applies even on generic asks ("recommend me something")."""
        if not user_id or get_favorites is None or get_ratings is None:
            return np.zeros(len(filtered_df))

        genre_counts = Counter()
        try:
            for fav in get_favorites(user_id):
                for g in str(fav.get("genre", "")).split(","):
                    g = g.strip().lower()
                    if g:
                        genre_counts[g] += 1
            for r in get_ratings(user_id):
                if r.get("rating", 0) >= 4:
                    idx = self.title_to_index.get(str(r.get("movie_title", "")).strip().lower())
                    if idx is not None:
                        for g in str(self.df.loc[idx, "genres"]).split(","):
                            g = g.strip().lower()
                            if g:
                                genre_counts[g] += 1
        except Exception:
            return np.zeros(len(filtered_df))

        if not genre_counts:
            return np.zeros(len(filtered_df))

        top_genre_set = {g for g, _ in genre_counts.most_common(3)}
        scores = filtered_df["genres"].fillna("").apply(
            lambda g: 1.0 if any(tg in g.lower() for tg in top_genre_set) else 0.0
        ).to_numpy(dtype=float)
        return scores

    def _search_history_scores(self, filtered_df, user_id):
        """Boosts candidates matching the genres/languages this user has
        searched for most often over ALL their past chat turns (not just
        this one), using the search_history log."""
        if not user_id or _get_top_searched_genres is None:
            return np.zeros(len(filtered_df))

        try:
            top_genres = set(_get_top_searched_genres(user_id, limit=3))
            top_languages = set(_get_top_searched_languages(user_id, limit=2))
        except Exception:
            return np.zeros(len(filtered_df))

        if not top_genres and not top_languages:
            return np.zeros(len(filtered_df))

        def _score(row):
            score = 0.0
            genres_lower = str(row.get("genres", "")).lower()
            if any(g in genres_lower for g in top_genres):
                score += 0.6
            if str(row.get("original_language", "")).lower() in top_languages:
                score += 0.4
            return score

        return filtered_df.apply(_score, axis=1).to_numpy(dtype=float)

    def _novelty_penalty(self, filtered_df, user_id):
        """Soft penalty proportional to how many times a movie has already
        been shown to this user ("recommended" impressions in movie_clicks),
        capped at MAX_REPEAT_PENALTY. This is duplicate prevention ACROSS
        sessions/turns — on top of the existing within-list de-dup below —
        so the engine doesn't keep resurfacing the same handful of titles
        every time a user chats with it."""
        if not user_id or get_all_shown_titles is None:
            return np.zeros(len(filtered_df))

        try:
            shown = get_all_shown_titles(user_id, limit=500)
        except Exception:
            return np.zeros(len(filtered_df))

        if not shown:
            return np.zeros(len(filtered_df))

        shown_counts = Counter(t.strip().lower() for t in shown)
        penalties = filtered_df["title"].apply(
            lambda t: min(
                shown_counts.get(str(t).strip().lower(), 0) * self.REPEAT_IMPRESSION_PENALTY,
                self.MAX_REPEAT_PENALTY,
            )
        ).to_numpy(dtype=float)
        return penalties

    def _history_scores(self, candidate_indices, user_id):
        profile_vec = self._user_history_vector(user_id)
        if profile_vec is None:
            return np.zeros(len(candidate_indices))
        candidate_vecs = self.embeddings[candidate_indices]
        sims = cosine_similarity(candidate_vecs, profile_vec.reshape(1, -1)).flatten()
        return _min_max_normalize(sims)

    def _diversify(self, ranked_rows, top_n):
        """Greedy re-rank: walk the hybrid-score-sorted list and skip a
        candidate if its primary genre has already hit the diversity cap,
        coming back for it later only if we can't otherwise fill top_n."""
        max_per_genre = max(1, int(np.ceil(top_n * self.MAX_PER_PRIMARY_GENRE_RATIO)))
        genre_counts = {}
        selected, deferred = [], []

        for row in ranked_rows:
            primary_genre = str(row["genres"]).split(",")[0].strip().lower() or "unknown"
            if genre_counts.get(primary_genre, 0) < max_per_genre:
                selected.append(row)
                genre_counts[primary_genre] = genre_counts.get(primary_genre, 0) + 1
            else:
                deferred.append(row)
            if len(selected) == top_n:
                return selected

        # Not enough diverse candidates to fill top_n — top up from deferred.
        selected.extend(deferred[: top_n - len(selected)])
        return selected

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def recommend(self, preferences, top_n=5, user_id=None):
        filtered_df = self.df.copy()

        # Genre Filter
        if preferences.get("genre"):
            filtered_df = filtered_df[
                filtered_df["genres"].str.contains(
                    preferences["genre"], case=False, na=False
                )
            ]

        # Language Filter
        language_map = {
            "english": "en",
            "tamil": "ta",
            "hindi": "hi",
            "telugu": "te",
            "malayalam": "ml",
            "kannada": "kn",
        }

        if preferences.get("language"):
            lang = preferences["language"].lower()
            lang = language_map.get(lang, lang)
            filtered_df = filtered_df[
                filtered_df["original_language"].str.lower() == lang
            ]

        # Runtime Filter
        if preferences.get("watch_time"):
            filtered_df = filtered_df[
                filtered_df["runtime"] <= preferences["watch_time"]
            ]

        # Rating Filter
        if preferences.get("min_rating"):
            filtered_df = filtered_df[filtered_df["vote_average"] >= preferences["min_rating"]]

        # Mood Mapping
        mood_map = {
            "happy": ["Comedy", "Animation", "Family"],
            "sad": ["Drama", "Romance"],
            "excited": ["Action", "Adventure", "Thriller"],
            "relaxed": ["Family", "Fantasy"],
            "stressed": ["Comedy", "Animation"],
            "romantic": ["Romance"],
            "scared": ["Horror", "Thriller"],
        }

        mood = preferences.get("mood")
        if mood and mood.lower() in mood_map:
            genres = mood_map[mood.lower()]
            pattern = "|".join(genres)
            filtered_df = filtered_df[
                filtered_df["genres"].str.contains(pattern, case=False, na=False)
            ]

        if filtered_df.empty:
            print("[RecommendationEngine] No movies matched these preferences.")
            return []

        # De-duplicate by title BEFORE ranking (bug fix — the raw TMDB
        # dataset has repeat rows for some titles, which used to let the
        # same movie occupy two of the five recommendation slots).
        filtered_df = filtered_df.drop_duplicates(subset="title", keep="first")

        # Duplicate prevention, part 2: don't recommend a movie the user
        # has already explicitly favorited — that's a duplicate from the
        # user's point of view, not just the dataset's. Only applied if it
        # still leaves enough candidates to work with, so a small/heavily-
        # favorited catalog never ends up with zero results because of it.
        if user_id and get_favorites is not None:
            try:
                already_favorited = {
                    str(f.get("movie_title", "")).strip().lower() for f in get_favorites(user_id)
                }
                if already_favorited:
                    without_favorites = filtered_df[
                        ~filtered_df["title"].str.strip().str.lower().isin(already_favorited)
                    ]
                    if len(without_favorites) >= max(top_n, 3):
                        filtered_df = without_favorites
            except Exception:
                pass  # DB hiccup — fall back to the unfiltered candidate set

        # ---- Hybrid scoring ----
        candidate_indices = filtered_df.index.tolist()

        content_raw = self.similarity[candidate_indices].mean(axis=1)
        content_scores = _min_max_normalize(content_raw)

        popularity_scores = (
            _min_max_normalize(filtered_df["popularity"].fillna(0).to_numpy(dtype=float))
            if "popularity" in filtered_df.columns
            else np.zeros(len(candidate_indices))
        )

        rating_scores = (
            filtered_df["vote_average"].fillna(0).to_numpy(dtype=float) / 10.0
        )

        history_scores = self._history_scores(candidate_indices, user_id)
        favorite_genre_scores = self._favorite_genre_scores(filtered_df, user_id)
        search_history_scores = self._search_history_scores(filtered_df, user_id)
        novelty_penalty = self._novelty_penalty(filtered_df, user_id)

        hybrid_scores = (
            self.W_CONTENT * content_scores
            + self.W_POPULARITY * popularity_scores
            + self.W_RATING * rating_scores
            + self.W_HISTORY * history_scores
            + self.W_FAVORITE_GENRE * favorite_genre_scores
            + self.W_SEARCH_HISTORY * search_history_scores
            - novelty_penalty
        )

        # Rank by hybrid score, then re-rank for genre diversity, then cut to top_n.
        order = np.argsort(hybrid_scores)[::-1]
        ranked_rows = []
        for rank_pos in order:
            df_idx = candidate_indices[rank_pos]
            row = self.df.loc[df_idx].to_dict()
            row["_hybrid_score"] = float(hybrid_scores[rank_pos])
            row["_content_score"] = float(content_raw[rank_pos])
            ranked_rows.append(row)

        final_rows = self._diversify(ranked_rows, top_n)

        recommendations = []
        for movie in final_rows:
            # Get TMDB information (poster/trailer/cast/director etc.).
            # Prefer the dataset's own TMDB id (deterministic, no ambiguity).
            # Only fall back to fuzzy title search if the id is missing/bad —
            # title search can silently match the wrong movie for common
            # titles (e.g. "It", "Us", "Gun Shy").
            tmdb_details = None
            movie_id = movie.get("id")
            if pd.notna(movie_id):
                try:
                    tmdb_details = self.tmdb.get_movie_details_by_id(int(movie_id))
                except (ValueError, TypeError):
                    tmdb_details = None
            if tmdb_details is None:
                tmdb_details = self.tmdb.get_movie_details(movie["title"])

            print("\n====================================")
            print("Movie:", movie["title"], "| TMDB id:", movie_id,
                  "| hybrid_score:", round(movie["_hybrid_score"], 4))
            print("TMDB:", tmdb_details)
            print("====================================")
            recommendations.append({
                # Dataset details
                "title": movie["title"],
                "genre": movie["genres"],
                "language": movie["original_language"],
                "rating": movie["vote_average"],
                "runtime": movie["runtime"],
                "overview": movie["overview"] if movie["overview"] else "No overview available.",
                "similarity_score": movie["_content_score"],
                "hybrid_score": movie["_hybrid_score"],

                # TMDB details — fall back to "Unknown" instead of blank (bug fix)
                "poster": tmdb_details["poster"] if tmdb_details and tmdb_details.get("poster") else "",
                "trailer": tmdb_details["trailer"] if tmdb_details and tmdb_details.get("trailer") else "",
                "director": tmdb_details["director"] if tmdb_details and tmdb_details.get("director") else "Unknown",
                "cast": tmdb_details["cast"] if tmdb_details and tmdb_details.get("cast") else [],
                "release_date": tmdb_details["release_date"] if tmdb_details and tmdb_details.get("release_date") else "Unknown",
                "imdb_id": tmdb_details["imdb_id"] if tmdb_details and tmdb_details.get("imdb_id") else "Unknown",
            })

        if user_id and recommendations:
            try:
                from database.interaction_store import log_clicks_bulk, log_search
                log_clicks_bulk(user_id, [m["title"] for m in recommendations], "recommended")
                log_search(user_id, preferences.get("genre"), preferences.get("language"), preferences.get("mood"))
            except Exception:
                pass  # telemetry only — never let a logging hiccup break a recommendation response

        return recommendations


# -------------------------
# Testing Only
# Remove this section after chatbot integration
# -------------------------

if __name__ == "__main__":

    dataset_path = r"data\tmdb_Preprocessed_dataset.csv"

    embedding_path = r"models\movie_embeddings.pkl"

    engine = RecommendationEngine(
        dataset_path,
        embedding_path
    )

    # Test Preferences
    preferences = {
        "genre": "Action",
        "language": "en",
        "duration": 150,
        "min_rating": 7.0,
        "mood": "excited"
    }

    results = engine.recommend(
        preferences,
        top_n=5
    )

    print("\n" + "=" * 80)
    print("🎬 MOVIE RECOMMENDATIONS")
    print("=" * 80)

    if not results:
        print("No movies found.")

    else:
        for i, movie in enumerate(results, start=1):

            print(f"\nMovie #{i}")
            print("-" * 80)
            print(f"Title            : {movie['title']}")
            print(f"Genre            : {movie['genre']}")
            print(f"Language         : {movie['language']}")
            print(f"Rating           : {movie['rating']}")
            print(f"Runtime          : {movie['runtime']} minutes")
            print(f"Similarity Score : {movie['similarity_score']:.4f}")
            print(f"Hybrid Score     : {movie['hybrid_score']:.4f}")
            print(f"Overview         : {movie['overview']}")
            print(f"Director         : {movie['director']}")
            print(f"Release Date     : {movie['release_date']}")
            print(f"IMDb ID          : {movie['imdb_id']}")

            if movie["cast"]:
                print("Cast             :", ", ".join(movie["cast"]))
            else:
                print("Cast             : N/A")

            print("Poster           :", movie["poster"])
            print("Trailer          :", movie["trailer"])
            print("-" * 80)