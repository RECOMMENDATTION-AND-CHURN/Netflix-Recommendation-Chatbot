# movie_service.py
from recommendation import RecommendationEngine
from dotenv import load_dotenv

load_dotenv()


class MovieRecommendationService:
    """
    Thin wrapper around RecommendationEngine.

    NOTE: RecommendationEngine.recommend() already calls TMDB internally
    for every movie it returns (poster, trailer, cast, director, etc).
    This service used to call TMDB a *second* time for the same movies,
    which doubled your API usage for no benefit and made failures harder
    to trace. That duplicate step has been removed here.
    """

    def __init__(self, dataset_path, embedding_path):
        self.engine = RecommendationEngine(dataset_path, embedding_path)

    def get_recommendations_with_details(self, preferences, top_n=5):
        return self.engine.recommend(preferences, top_n)


# -------------------------
# Testing only
# -------------------------
if __name__ == "__main__":
    service = MovieRecommendationService
    (
       dataset_path = r"data\tmdb_Preprocessed_dataset.csv"

       embedding_path = r"models\movie_embeddings.pkl"
    )
    preferences = {
        "genre": "Action",
        "mood": "excited",
        "language": "en",
        "duration": 150,
        "min_rating": 7.0,
    }

    results = service.get_recommendations_with_details(preferences, top_n=5)

    for movie in results:
        print("\n🎬", movie["title"])
        print("⭐ Rating:", movie["rating"])
        print("🎭 Director:", movie.get("director"))
        print("📅 Release:", movie.get("release_date"))
        print("📸 Poster:", movie.get("poster"))
        print("🎥 Trailer:", movie.get("trailer"))
        if movie.get("cast"):
            print("👥 Cast:", ", ".join(movie["cast"][:3]))
        print("-" * 50)