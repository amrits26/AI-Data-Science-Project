"""Logging setup utilities for API runtime."""

from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: int = logging.INFO, json_output: bool = True) -> None:
    """Configure JSON-lines logging via structlog with safe stdlib fallback."""
    try:
        import structlog

        logging.basicConfig(level=level, format="%(message)s", force=True)

        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]
        if json_output:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    except Exception:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(level)

        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        handler.setFormatter(formatter)
        root.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger (structlog if available, else stdlib)."""
    try:
        import structlog

        return structlog.get_logger(name)
    except Exception:
        return logging.getLogger(name)
