"""Unit tests for config.py (central settings + validation)."""

from config import Settings, settings


def test_settings_has_sensible_defaults():
    s = Settings()
    assert s.CHAT_MESSAGE_MAX_LENGTH == 2000
    assert s.USERNAME_MIN_LENGTH == 3
    assert s.PASSWORD_MIN_LENGTH == 6
    assert s.DB_BACKUP_MAX_KEEP == 14


def test_validate_warns_when_gemini_key_missing(monkeypatch):
    s = Settings(GEMINI_API_KEY="", TMDB_API_KEY="x", FLASK_SECRET_KEY="x")
    warnings = s.validate()
    assert any("GEMINI_API_KEY" in w for w in warnings)


def test_validate_warns_when_tmdb_key_missing():
    s = Settings(GEMINI_API_KEY="x", TMDB_API_KEY="", FLASK_SECRET_KEY="x")
    warnings = s.validate()
    assert any("TMDB_API_KEY" in w for w in warnings)


def test_validate_no_warnings_when_fully_configured():
    s = Settings(GEMINI_API_KEY="x", TMDB_API_KEY="x", FLASK_SECRET_KEY="x")
    assert s.validate() == []


def test_settings_singleton_is_importable():
    # The module-level `settings` instance should just work out of the box.
    assert isinstance(settings, Settings)
    assert settings.CHAT_MESSAGE_MAX_LENGTH > 0
