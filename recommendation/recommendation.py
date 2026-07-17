# recommendation.py
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import numpy as np
from recommendation.tmdb_api import TMDBClient


class RecommendationEngine:

    def __init__(self, dataset_path, embedding_path):
        # Load dataset
        self.df = pd.read_csv(dataset_path)

        # Load embeddings
        with open(embedding_path, "rb") as f:
            self.embeddings = pickle.load(f)

        # Create similarity matrix
        self.similarity = cosine_similarity(self.embeddings)

        # Initialize TMDB client (auto-detects v3/v4 key from .env)
        self.tmdb = TMDBClient()

    def recommend(self, preferences, top_n=5):
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
    "kannada": "kn"
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

        # Similarity Ranking
        candidate_indices = filtered_df.index.tolist()
        candidate_scores = self.similarity[candidate_indices].mean(axis=1)
        sorted_indices = np.argsort(candidate_scores)[::-1][:top_n]

        recommendations = []

        for idx in sorted_indices:
            movie = self.df.iloc[candidate_indices[idx]]

            # Get TMDB information (poster/trailer/cast/director etc.)
            tmdb_details = self.tmdb.get_movie_details(movie["title"])

            print("\n====================================")
            print("Movie:", movie["title"])
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
                "similarity_score": float(candidate_scores[idx]),

                # TMDB details — fall back to "Unknown" instead of blank (bug fix)
                "poster": tmdb_details["poster"] if tmdb_details and tmdb_details.get("poster") else "",
                "trailer": tmdb_details["trailer"] if tmdb_details and tmdb_details.get("trailer") else "",
                "director": tmdb_details["director"] if tmdb_details and tmdb_details.get("director") else "Unknown",
                "cast": tmdb_details["cast"] if tmdb_details and tmdb_details.get("cast") else [],
                "release_date": tmdb_details["release_date"] if tmdb_details and tmdb_details.get("release_date") else "Unknown",
                "imdb_id": tmdb_details["imdb_id"] if tmdb_details and tmdb_details.get("imdb_id") else "Unknown",
            })

        return recommendations


# -------------------------
# Testing Only
# -------------------------
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