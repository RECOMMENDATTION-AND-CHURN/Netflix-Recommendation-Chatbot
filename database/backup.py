"""
database/backup.py
--------------------
Automatic backup for the SQLite database (chatbot.db). Uses sqlite3's
built-in `backup()` API (safe to run against a live, in-use database —
unlike a plain file copy, which can grab a half-written file mid-write)
rather than shutil.copy.

Two ways to use this:

1. Automatically, once per process start (already wired into
   database/connection.py's create_database(), which every entrypoint
   calls at import time) — respects DB_BACKUP_MIN_INTERVAL_HOURS so it
   won't spam a new backup file every single Streamlit rerun.

2. On demand / from cron:
       python -m database.backup

Backups are kept in backups/ as chatbot_YYYYMMDD_HHMMSS.db, with only
the most recent DB_BACKUP_MAX_KEEP files retained.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


def _last_backup_time() -> float | None:
    if not settings.backup_dir.exists():
        return None
    backups = sorted(settings.backup_dir.glob("chatbot_*.db"))
    if not backups:
        return None
    return backups[-1].stat().st_mtime


def _should_run_backup() -> bool:
    if not settings.DB_BACKUP_ENABLED:
        return False
    last = _last_backup_time()
    if last is None:
        return True
    hours_since = (time.time() - last) / 3600
    return hours_since >= settings.DB_BACKUP_MIN_INTERVAL_HOURS


def _prune_old_backups() -> None:
    backups = sorted(settings.backup_dir.glob("chatbot_*.db"))
    excess = len(backups) - settings.DB_BACKUP_MAX_KEEP
    for old_backup in backups[:max(excess, 0)]:
        try:
            old_backup.unlink()
            logger.info("Pruned old backup: %s", old_backup.name)
        except OSError as e:
            logger.warning("Could not delete old backup %s: %s", old_backup.name, e)


def backup_database(force: bool = False) -> str | None:
    """Creates a timestamped, consistent backup of the live database using
    sqlite3's online backup API. Returns the backup file path, or None if
    skipped (disabled, too soon since the last one, or DB doesn't exist
    yet — e.g. brand-new install). Never raises: a failed backup should
    never take down the app that's calling it."""
    db_path = Path(settings.db_path)
    if not db_path.exists():
        return None

    if not force and not _should_run_backup():
        return None

    try:
        os.makedirs(settings.backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = settings.backup_dir / f"chatbot_{timestamp}.db"

        source_conn = sqlite3.connect(str(db_path))
        dest_conn = sqlite3.connect(str(backup_path))
        with dest_conn:
            source_conn.backup(dest_conn)
        source_conn.close()
        dest_conn.close()

        logger.info("Database backed up to %s", backup_path)
        _prune_old_backups()
        return str(backup_path)

    except sqlite3.Error as e:
        logger.error("Database backup failed: %s", e)
        return None


if __name__ == "__main__":
    result = backup_database(force=True)
    if result:
        print(f"Backup created: {result}")
    else:
        print("Backup skipped (disabled, or no database found).")
