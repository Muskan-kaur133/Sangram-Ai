"""Structured JSON Logging and Redaction Infrastructure for Sangram AI.

Formats application and access logs as machine-parseable JSON.
Redacts all sensitive headers, credentials, tokens, and secrets.
Injects contextual Request ID from contextvars into all log lines.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

# Request ID context variable shared across async task execution
request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Headers and fields that must NEVER appear in logs
SENSITIVE_FIELD_NAMES: Set[str] = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "client_secret",
    "stripe_secret_key",
    "stripe_webhook_secret",
    "openai_api_key",
    "anthropic_api_key",
    "google_api_key",
    "mistral_api_key",
    "xai_api_key",
}

# Regex pattern for key=value or "key": "value" matching
SENSITIVE_PATTERN = re.compile(
    r"(?i)(password|token|secret|key|authorization|bearer)[\"']?\s*[:=]\s*[\"']?([^\"'\s,]+)",
)


def redact_sensitive_data(val: Any) -> Any:
    """Recursively redacts sensitive values from dictionaries, lists, or strings."""
    if isinstance(val, dict):
        return {
            k: ("[REDACTED]" if str(k).lower() in SENSITIVE_FIELD_NAMES else redact_sensitive_data(v))
            for k, v in val.items()
        }
    elif isinstance(val, list):
        return [redact_sensitive_data(i) for i in val]
    elif isinstance(val, str):
        # Prevent leaking Authorization: Bearer <token> in raw strings
        return SENSITIVE_PATTERN.sub(r'\1="[REDACTED]"', val)
    return val


class JSONLogFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON with sanitized fields."""

    def format(self, record: logging.LogRecord) -> str:
        # Base log object
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
        }

        # Request ID from contextvar or record attribute
        req_id = request_id_ctx_var.get() or getattr(record, "request_id", None)
        if req_id:
            log_entry["requestId"] = req_id

        # Attach HTTP context if available
        for attr in ("method", "path", "status_code", "duration_ms", "client_ip"):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)

        # Attach exception info if present (without sensitive arguments)
        if record.exc_info and record.exc_text:
            log_entry["exception"] = record.exc_text
        elif record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", use_json: bool = True) -> None:
    """Configures the root and uvicorn loggers with the structured JSON formatter."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    if use_json:
        stream_handler.setFormatter(JSONLogFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(stream_handler)

    # Align uvicorn and app loggers
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sangram_ai"):
        target_logger = logging.getLogger(logger_name)
        target_logger.handlers = [stream_handler]
        target_logger.propagate = False
        target_logger.setLevel(level)
