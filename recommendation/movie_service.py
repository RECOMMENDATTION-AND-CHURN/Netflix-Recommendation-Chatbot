# movie_service.py
from recommendation.recommendation import RecommendationEngine
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


