# tmdb_api.py
import requests
import functools
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


class TMDBClient:
    """
    TMDB API client.

    IMPORTANT: TMDB gives you TWO different kinds of credentials on your
    account settings page:
      1. "API Key (v3 auth)"            -> short string, e.g. "a1b2c3d4..."
                                            sent as a query param: ?api_key=...
      2. "API Read Access Token (v4 auth)" -> long JWT-looking string
                                            sent as a header: Authorization: Bearer ...

    This client auto-detects which one you gave it (v4 tokens are long and
    contain dots, like a JWT) and uses the correct auth method automatically,
    so it works no matter which one is in your .env file.
    """

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.getenv("TMDB_API_KEY")
            if not api_key:
                raise ValueError(
                    "TMDB_API_KEY not found in environment variables! "
                    "Add TMDB_API_KEY=your_key_here to your .env file."
                )

        self.api_key = api_key.strip()
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base = "https://image.tmdb.org/t/p/w500"
        self.timeout = 10

        # v4 read-access tokens are long and contain two dots (JWT format).
        # v3 api keys are short (usually 32 chars, no dots).
        self.is_v4_token = self.api_key.count(".") >= 2 and len(self.api_key) > 60

        self.session = requests.Session()
        if self.is_v4_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "accept": "application/json",
            })

        # Validate the key once at startup so failures show up immediately,
        # not silently later as blank fields.
        self._validate_key()

    def _params(self, extra: dict = None) -> dict:
        """Build query params. v3 keys go here; v4 tokens go in the header."""
        params = {} if self.is_v4_token else {"api_key": self.api_key}
        if extra:
            params.update(extra)
        return params

    def _validate_key(self):
        try:
            resp = self.session.get(
                f"{self.base_url}/authentication",
                params=self._params(),
                timeout=self.timeout,
            )
            if resp.status_code == 401:
                raise ValueError(
                    "TMDB rejected your API key (401 Unauthorized). "
                    "Check that TMDB_API_KEY in your .env is correct and "
                    "matches the key type TMDBClient detected "
                    f"({'v4 Read Access Token' if self.is_v4_token else 'v3 API Key'})."
                )
            resp.raise_for_status()
            print(
                f"[TMDBClient] Key validated OK "
                f"({'v4 token' if self.is_v4_token else 'v3 key'})."
            )
        except requests.exceptions.RequestException as e:
            print(f"[TMDBClient] WARNING: could not validate key at startup: {e}")

    @functools.lru_cache(maxsize=200)
    def get_movie_details(self, movie_name: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive movie details from TMDB. Returns None on failure
        and prints a clear reason (no more silent blank fields)."""
        try:
            search_url = f"{self.base_url}/search/movie"
            response = self.session.get(
                search_url,
                params=self._params({"query": movie_name, "include_adult": False}),
                timeout=self.timeout,
            )
            if response.status_code == 401:
                print(f"[TMDBClient] 401 Unauthorized while searching '{movie_name}'. "
                      f"Your API key/token is invalid or expired.")
                return None
            response.raise_for_status()
            data = response.json()

            if not data.get("results"):
                print(f"[TMDBClient] No TMDB match found for '{movie_name}'.")
                return None

            movie = data["results"][0]
            movie_id = movie["id"]

            details = self.session.get(
                f"{self.base_url}/movie/{movie_id}",
                params=self._params(),
                timeout=self.timeout,
            ).json()

            videos = self.session.get(
                f"{self.base_url}/movie/{movie_id}/videos",
                params=self._params(),
                timeout=self.timeout,
            ).json()

            trailer = ""
            for video in videos.get("results", []):
                if video.get("site") == "YouTube":
                    if video.get("type") == "Trailer" or not trailer:
                        trailer = f"https://www.youtube.com/watch?v={video['key']}"
                        if video.get("type") == "Trailer":
                            break

            credits = self.session.get(
                f"{self.base_url}/movie/{movie_id}/credits",
                params=self._params(),
                timeout=self.timeout,
            ).json()

            poster = ""
            if details.get("poster_path"):
                poster = self.image_base + details["poster_path"]

            director = None
            for crew in credits.get("crew", []):
                if crew.get("job") == "Director":
                    director = crew.get("name")
                    break

            return {
                "title": details.get("title"),
                "rating": details.get("vote_average"),
                "release_date": details.get("release_date"),
                "runtime": details.get("runtime"),
                "genres": [g["name"] for g in details.get("genres", [])],
                "overview": details.get("overview"),
                "poster": poster,
                "trailer": trailer,
                "cast": [actor["name"] for actor in credits.get("cast", [])[:5]],
                "director": director,
                "imdb_id": details.get("imdb_id"),
            }

        except requests.exceptions.RequestException as e:
            print(f"[TMDBClient] API Error for '{movie_name}': {e}")
            return None
        except KeyError as e:
            print(f"[TMDBClient] Data parsing error for '{movie_name}': {e}")
            return None


if __name__ == "__main__":
    client = TMDBClient()
    movie = client.get_movie_details("Inception")
    print(movie)