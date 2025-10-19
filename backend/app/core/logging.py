"""Structured logging configuration."""

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class SanitizingFormatter(jsonlogger.JsonFormatter):
    """JSON formatter that sanitizes PII from logs."""

    PII_FIELDS = {
        "password",
        "token",
        "secret",
        "api_key",
        "access_token",
        "refresh_token",
        "patient_name",
        "phone",
        "email",
        "ssn",
        "inn",
        "snils",
    }

    def process_log_record(self, log_record: dict[str, Any]) -> dict[str, Any]:
        """Process log record and sanitize PII fields."""
        for key in list(log_record.keys()):
            if any(pii_field in key.lower() for pii_field in self.PII_FIELDS):
                log_record[key] = "***REDACTED***"

        # Add standard fields
        log_record["service"] = settings.APP_NAME
        log_record["environment"] = settings.APP_ENV
        log_record["version"] = settings.APP_VERSION

        return log_record


def setup_logging() -> logging.Logger:
    """Set up structured logging with PII sanitization."""

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if settings.APP_DEBUG else logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    formatter = SanitizingFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return logger
