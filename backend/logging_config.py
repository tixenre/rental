"""
Configuración de logging estructurado.

En producción (Railway o LOG_FORMAT=json) emite JSON por línea, ideal para
sistemas de log search (Railway Logs, Datadog, etc).

En desarrollo local emite texto con colores y formato corto, fácil de leer.

Niveles configurables con LOG_LEVEL (default INFO en prod, DEBUG en dev).

Cada log incluye automáticamente un `request_id` si el handler corre dentro
de una request HTTP (inyectado por el middleware).
"""

from __future__ import annotations

import contextvars
import logging
import os
import sys
from logging.config import dictConfig

from pythonjsonlogger.json import JsonFormatter

# Context var seteado por el middleware en cada request. Si no hay request en
# curso (p. ej. init_db en background), queda None y no se incluye en el log.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class RequestIdFilter(logging.Filter):
    """Inyecta request_id (si existe) como atributo del LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = request_id_var.get()
        if rid:
            record.request_id = rid
        return True


class CustomJsonFormatter(JsonFormatter):
    """JSON formatter con campos estándar + request_id opcional."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        # request_id solo si fue inyectado por el filter
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


def _is_prod() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT")) or os.getenv("LOG_FORMAT") == "json"


def setup_logging() -> None:
    """Configura el root logger. Idempotente — llamar una vez al arrancar la app."""
    level = os.getenv("LOG_LEVEL", "INFO" if _is_prod() else "DEBUG").upper()
    use_json = _is_prod()

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "filters": ["request_id"],
            "formatter": "json" if use_json else "text",
        }
    }

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": RequestIdFilter},
        },
        "formatters": {
            "json": {"()": CustomJsonFormatter},
            "text": {
                "format": "%(asctime)s %(levelname)-7s %(name)s — %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": handlers,
        "root": {"level": level, "handlers": ["console"]},
        "loggers": {
            # Bajar el ruido de libs verbosas en INFO/DEBUG
            "uvicorn.access": {"level": "WARNING", "propagate": True},
            "httpx": {"level": "WARNING", "propagate": True},
            "botocore": {"level": "WARNING", "propagate": True},
            "boto3": {"level": "WARNING", "propagate": True},
            "urllib3": {"level": "WARNING", "propagate": True},
        },
    })
