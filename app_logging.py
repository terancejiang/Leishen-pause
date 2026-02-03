from __future__ import annotations

import logging as std_logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DEFAULT_RETENTION_DAYS = 30
DEFAULT_LOG_DIRNAME = "log"
LOGGER_NAME = "leishen_auto"


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def get_log_dir() -> Path:
    env_dir = os.getenv("LOG_DIR")
    if env_dir:
        return Path(env_dir)
    return _project_root() / DEFAULT_LOG_DIRNAME


def get_retention_days() -> int:
    raw = os.getenv("LOG_RETENTION_DAYS")
    if not raw:
        return DEFAULT_RETENTION_DAYS

    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETENTION_DAYS

    return value if value > 0 else DEFAULT_RETENTION_DAYS


def cleanup_old_logs(log_dir: Path, retention_days: int) -> None:
    cutoff = time.time() - (retention_days * 86400)

    for path in log_dir.glob("*.log*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def setup_logging() -> std_logging.Logger:
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    retention_days = get_retention_days()
    logger = std_logging.getLogger(LOGGER_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(std_logging.INFO)
    formatter = std_logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = TimedRotatingFileHandler(
        log_dir / "leishen-auto.log",
        when="D",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = std_logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    cleanup_old_logs(log_dir, retention_days)
    return logger


def get_logger() -> std_logging.Logger:
    return std_logging.getLogger(LOGGER_NAME)
