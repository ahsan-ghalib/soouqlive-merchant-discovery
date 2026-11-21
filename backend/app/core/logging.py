"""Structured application logging configuration."""

import logging
import sys
from typing import Optional

from app.core.config import get_settings


def setup_logging(level: Optional[str] = None) -> None:
    settings = get_settings()
    log_level = level or ("DEBUG" if settings.debug else "INFO")

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if not settings.debug else logging.INFO
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
