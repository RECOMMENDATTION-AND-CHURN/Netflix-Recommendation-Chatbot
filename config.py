"""
config.py
----------
Central configuration for the whole project (Streamlit app, Flask web
API, and provider dashboard). All environment-variable reads should go
through here instead of being scattered across modules with `os.getenv`
calls and inconsistent defaults — this is the single place to look when
tuning limits, rotating keys, or deploying to a new environment.

Existing `load_dotenv()` calls in chatbot/gemini_api.py and
recommendation/tmdb_api.py / movie_service.py are untouched and still
work — this module additionally loads the same .env files (idempotent;
python-dotenv doesn't overwrite already-set variables) so anything new
that imports config.py doesn't have to also remember to call
load_dotenv() itself.

Usage:
    from config import settings
    settings.TMDB_API_KEY
    settings.CHAT_MESSAGE_MAX_LENGTH
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load every .env file in the project (root, chatbot/, recommendation/)
# so a key defined in any one of them is visible everywhere. Existing
# per-module load_dotenv() calls still work fine alongside this — python-
# dotenv only sets a variable if it isn't already in the environment.
for _env_path in (
    BASE_DIR / ".env",
    BASE_DIR / "chatbot" / ".env",
    BASE_DIR / "recommendation" / ".env",
):
    if _env_path.exists():
        load_dotenv(_env_path)


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        logging.getLogger(__name__).warning(
            "Env var %s=%r is not a valid integer, using default %s", name, val, default
        )
        return default


@dataclass(frozen=True)
class Settings:
    # ---- Paths ----
    base_dir: Path = BASE_DIR
    data_path: Path = field(default_factory=lambda: BASE_DIR / "data" / "tmdb_Preprocessed_dataset.csv")
    embedding_path: Path = field(default_factory=lambda: BASE_DIR / "models" / "movie_embeddings.pkl")
    db_path: Path = field(default_factory=lambda: BASE_DIR / "chatbot.db")
    backup_dir: Path = field(default_factory=lambda: BASE_DIR / "backups")
    log_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")

    # ---- External API keys (secrets — never log these) ----
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    TMDB_API_KEY: str = field(default_factory=lambda: os.getenv("TMDB_API_KEY", ""))

    # ---- Flask web app (Module 1) ----
    FLASK_SECRET_KEY: str = field(default_factory=lambda: os.getenv("NETFLIC_SECRET_KEY", ""))
    FLASK_PORT: int = field(default_factory=lambda: _int_env("PORT", 5000))
    FLASK_DEBUG: bool = field(default_factory=lambda: _bool_env("FLASK_DEBUG", True))

    # ---- Rate limiting ----
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = field(default_factory=lambda: _int_env("AUTH_RATE_LIMIT_WINDOW_SECONDS", 60))
    AUTH_RATE_LIMIT_MAX_ATTEMPTS: int = field(default_factory=lambda: _int_env("AUTH_RATE_LIMIT_MAX_ATTEMPTS", 8))
    CHAT_RATE_LIMIT_COOLDOWN_SECONDS: float = field(
        default_factory=lambda: float(os.getenv("CHAT_RATE_LIMIT_COOLDOWN_SECONDS", "1.5"))
    )

    # ---- Input validation ----
    CHAT_MESSAGE_MAX_LENGTH: int = field(default_factory=lambda: _int_env("CHAT_MESSAGE_MAX_LENGTH", 2000))
    USERNAME_MIN_LENGTH: int = field(default_factory=lambda: _int_env("USERNAME_MIN_LENGTH", 3))
    PASSWORD_MIN_LENGTH: int = field(default_factory=lambda: _int_env("PASSWORD_MIN_LENGTH", 6))

    # ---- Caching ----
    RECOMMENDATION_CACHE_TTL_SECONDS: int = field(
        default_factory=lambda: _int_env("RECOMMENDATION_CACHE_TTL_SECONDS", 900)
    )

    # ---- Automatic DB backup ----
    DB_BACKUP_ENABLED: bool = field(default_factory=lambda: _bool_env("DB_BACKUP_ENABLED", True))
    DB_BACKUP_MAX_KEEP: int = field(default_factory=lambda: _int_env("DB_BACKUP_MAX_KEEP", 14))
    DB_BACKUP_MIN_INTERVAL_HOURS: int = field(default_factory=lambda: _int_env("DB_BACKUP_MIN_INTERVAL_HOURS", 24))

    # ---- Logging ----
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    LOG_TO_FILE: bool = field(default_factory=lambda: _bool_env("LOG_TO_FILE", True))

    def validate(self) -> list:
        """Returns a list of human-readable warnings for anything that
        looks misconfigured. Never raises — a missing API key shouldn't
        crash the whole app on import, it should just degrade the one
        feature that needs it (exactly as chatbot/gemini_api.py and
        recommendation/tmdb_api.py already do on their own)."""
        warnings = []
        if not self.GEMINI_API_KEY:
            warnings.append(
                "GEMINI_API_KEY is not set — chat preference extraction will fail "
                "('Unable to connect to Gemini API')."
            )
        if not self.TMDB_API_KEY:
            warnings.append(
                "TMDB_API_KEY is not set — movie posters/trailers/cast will be blank."
            )
        if not self.FLASK_SECRET_KEY and self.LOG_LEVEL != "TEST":
            warnings.append(
                "NETFLIC_SECRET_KEY is not set — the Flask web app will generate a random "
                "key at startup, which invalidates all sessions on every restart. Set this "
                "explicitly for any deployment that should survive a restart."
            )
        return warnings


settings = Settings()

# Surface any misconfiguration once, at import time, via logging rather
# than print() — so it shows up wherever this process's logs already go.
for _warning in settings.validate():
    logging.getLogger(__name__).warning(_warning)
