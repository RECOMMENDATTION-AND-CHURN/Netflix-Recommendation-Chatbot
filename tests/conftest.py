"""
tests/conftest.py
-------------------
Shared fixtures for the whole test suite. The most important one is
`isolated_db`, which points every database/* module at a brand-new,
throwaway SQLite file for the duration of one test — so running the
test suite can NEVER touch, corrupt, or leave test data in the real
chatbot.db a developer is using locally.

Run with (from the project root):
    pip install pytest --break-system-packages   # if not already installed
    pytest tests/ -v
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    """Redirects database.connection.DB_NAME (and config.settings.db_path/
    backup_dir, for tests that touch backups) at a fresh temp file. Yields
    nothing useful directly — tests just import the database/* modules
    they need as usual after requesting this fixture.

    Settings is a frozen dataclass (by design — see config.py), so its
    fields can't go through monkeypatch.setattr directly. We bypass that
    via object.__setattr__ and restore the originals afterward ourselves.
    """
    import database.connection as connection
    import config as config_module

    db_path = tmp_path / "test_chatbot.db"
    backup_dir = tmp_path / "backups"

    monkeypatch.setattr(connection, "DB_NAME", str(db_path))

    original_db_path = config_module.settings.db_path
    original_backup_dir = config_module.settings.backup_dir
    object.__setattr__(config_module.settings, "db_path", db_path)
    object.__setattr__(config_module.settings, "backup_dir", backup_dir)

    connection.create_database()
    try:
        yield db_path
    finally:
        object.__setattr__(config_module.settings, "db_path", original_db_path)
        object.__setattr__(config_module.settings, "backup_dir", original_backup_dir)


@pytest.fixture
def patch_settings():
    """Returns a function `patch(attr, value)` that temporarily overrides a
    field on the frozen `config.settings` singleton (bypassing the
    dataclass's frozen=True via object.__setattr__) and restores the
    original value once the test ends. Needed because Settings is
    deliberately immutable in normal code — see config.py."""
    import config as config_module

    originals = {}

    def _patch(attr: str, value):
        if attr not in originals:
            originals[attr] = getattr(config_module.settings, attr)
        object.__setattr__(config_module.settings, attr, value)

    yield _patch

    for attr, original_value in originals.items():
        object.__setattr__(config_module.settings, attr, original_value)


@pytest.fixture
def make_user(isolated_db):
    """Factory fixture: make_user() -> user_id, creating a fresh signed-up
    user in the isolated test DB each call."""
    from database.auth_store import signup

    counter = {"n": 0}

    def _make(username: str = None, password: str = "pw123456") -> int:
        counter["n"] += 1
        uname = username or f"testuser{counter['n']}"
        user_id = signup(uname, password)
        assert user_id is not None, f"signup unexpectedly failed for {uname!r}"
        return user_id

    return _make
