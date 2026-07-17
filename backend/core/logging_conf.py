"""Centralised logging configuration.

Every module imports `logger` from here instead of calling
`logging.getLogger(__name__)` directly. This guarantees:

1. A rotating file handler at logs/wfreport.log (10 MB x 3 files).
2. A console handler for local dev / Docker stdout.
3. A consistent format: timestamp, level, module, message.
4. Sensitive values (API keys) are never logged — callers must
   redact before passing strings to logger.

Usage in any module:

    from backend.core.logging_conf import logger
    logger.info("computing KPIs for %s", week_id)
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialised = False


def setup_logging(level: str | None = None):
    """Idempotent: safe to call multiple times (tests, restarts).

    - File handler → logs/wfreport.log  (rotates at 10 MB, keeps 3)
    - Console handler → stderr  (always visible in Docker / terminal)
    """
    global _initialised
    if _initialised:
        return
    _initialised = True

    root = logging.getLogger()
    root.setLevel(level or os.environ.get("LOG_LEVEL", "INFO"))

    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — visible in Docker logs and local terminal.
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler — persisted to logs/ directory (mapped to host
    # in docker-compose). Create dir lazily so tests that don't
    # need file logging can skip it.
    log_dir = Path("logs")
    try:
        log_dir.mkdir(exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "wfreport.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except (OSError, PermissionError):
        # Read-only filesystem or no write permission —
        # fall back to console-only (Docker captures stdout).
        pass


def get_logger(name: str) -> logging.Logger:
    """Module-level logger getter. Call setup_logging() once at
    app startup (done in main.py), then use get_logger everywhere."""
    return logging.getLogger(name)


# Module-level shortcut for simple cases.
logger = get_logger("wfreport")
