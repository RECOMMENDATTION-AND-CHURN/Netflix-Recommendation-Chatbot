# movie_service.py
from typing import Dict, List, Optional, Any

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

    def __init__(self, dataset_path: str, embedding_path: str) -> None:
        self.engine = RecommendationEngine(dataset_path, embedding_path)

    def get_recommendations_with_details(
        self,
        preferences: Dict[str, Any],
        top_n: int = 5,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Returns up to `top_n` fully-detailed movie recommendations
        (poster/trailer/cast/director already resolved) for the given
        preferences dict. See RecommendationEngine.recommend() for the
        full hybrid-scoring behavior and the shape of each returned dict."""
        return self.engine.recommend(preferences, top_n, user_id=user_id)