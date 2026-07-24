"""Unit tests for database/backup.py (automatic SQLite backup + retention)."""

import time
from pathlib import Path

from database.backup import backup_database
import config as config_module


def test_backup_creates_a_file(isolated_db):
    result = backup_database(force=True)
    assert result is not None
    assert Path(result).exists()


def test_backup_skipped_when_db_does_not_exist(isolated_db, patch_settings, tmp_path):
    patch_settings("db_path", tmp_path / "nonexistent.db")
    result = backup_database(force=True)
    assert result is None


def test_backup_respects_min_interval_without_force(isolated_db, patch_settings):
    patch_settings("DB_BACKUP_MIN_INTERVAL_HOURS", 24)
    first = backup_database(force=True)
    assert first is not None

    # Immediately calling again without force, with a 24h interval configured,
    # should be skipped since essentially no time has passed.
    second = backup_database(force=False)
    assert second is None


def test_backup_disabled_returns_none(isolated_db, patch_settings):
    patch_settings("DB_BACKUP_ENABLED", False)
    result = backup_database(force=False)
    assert result is None


def test_backup_pruning_keeps_only_max_keep(isolated_db, patch_settings):
    patch_settings("DB_BACKUP_MAX_KEEP", 2)

    paths = []
    for _ in range(4):
        p = backup_database(force=True)
        assert p is not None
        paths.append(p)
        time.sleep(1.1)  # ensure distinct timestamps in the filename

    remaining = sorted(config_module.settings.backup_dir.glob("chatbot_*.db"))
    assert len(remaining) == 2
    # The two most recent backups should be the ones kept.
    assert str(remaining[-1]) == paths[-1]
