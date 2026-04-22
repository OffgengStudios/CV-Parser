"""
logger.py — Structured logging configuration for the entire application.
"""
import logging
import sys
from pathlib import Path
from config import settings


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger with consistent formatting.
    Logs to both stdout (for containerized environments) and a rotating file.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    log_file = settings.LOG_DIR / "cv_system.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
