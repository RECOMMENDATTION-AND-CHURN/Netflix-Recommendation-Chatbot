"""
logging_config.py
-------------------
Central logging setup, shared by app.py (Streamlit chatbot), dashboard.py
(provider dashboard), and webapp/server.py (Flask API). Call
`configure_logging()` once, near the top of each entrypoint, before doing
anything else that logs.

Writes to both:
  - console (so `streamlit run` / `python webapp/server.py` output still
    shows logs live, same as today)
  - a rotating file under logs/ (new — previously nothing was persisted,
    so a crash overnight left no trace once the terminal scrolled past it)

Safe to call more than once (e.g. if both app.py and a module it imports
call it) — subsequent calls are no-ops.
"""

from __future__ import annotations

import logging
import logging.handlers
import os

from config import settings

_configured = False


def configure_logging(component: str = "app") -> logging.Logger:
    """component is a short tag (e.g. 'streamlit', 'dashboard', 'webapp')
    used in the log filename, so the three surfaces don't interleave into
    one unreadable file."""
    global _configured

    root_logger = logging.getLogger()

    if _configured:
        return root_logger

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if settings.LOG_TO_FILE:
        try:
            os.makedirs(settings.log_dir, exist_ok=True)
            file_path = os.path.join(settings.log_dir, f"{component}.log")
            file_handler = logging.handlers.RotatingFileHandler(
                file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError as e:
            # Read-only filesystem, permissions issue, etc. — degrade to
            # console-only logging rather than crashing the app over it.
            root_logger.warning("Could not set up file logging (%s); continuing with console only.", e)

    # Quiet down noisy third-party libraries so our own log lines aren't
    # buried, without silencing warnings/errors from them.
    for noisy in ("urllib3", "httpx", "httpcore", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    root_logger.info("Logging configured (component=%s, level=%s, file=%s)",
                      component, settings.LOG_LEVEL, settings.LOG_TO_FILE)
    return root_logger
