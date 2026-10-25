"""
Structured JSON logging configuration using structlog.
Provides consistent timestamped JSON logs with contextual request-ID binding.
"""

import logging
import sys
from typing import Any, cast

import structlog

from app.config import get_settings


def add_app_context(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject application name and environment to all log records."""
    settings = get_settings()
    event_dict["app"] = settings.app_name
    event_dict["env"] = settings.app_env
    return event_dict


def setup_logging() -> None:
    """Configure standard library logging and structlog processors."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Standard library root logger configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_app_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env.lower() == "development":
        # Pretty console logging for development
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # Structured JSON renderer for production & container logging
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog bound logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))

