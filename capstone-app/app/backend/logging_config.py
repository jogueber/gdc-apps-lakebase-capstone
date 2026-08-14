"""Structured (JSON) logging for the app.

One JSON object per line: ``timestamp, level, logger, message`` plus
``request_id`` (when set by the request-id middleware) and ``exception`` (when
a record carries ``exc_info``). Installing it on the *root* logger means the
app and uvicorn both emit JSON, so logs are queryable as structured data — and
the ``request_id`` matches the ``X-Request-Id`` stamped on the OTel span, so a
log line and its trace share one key.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from contextvars import ContextVar

# Set per request in the request-id middleware; None outside a request.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": dt.datetime.fromtimestamp(record.created, dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Route the root logger (and uvicorn's) through the JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn attaches its own handlers; drop them and let records propagate to
    # the root JSON handler instead of being double-printed in plain text.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
