"""auth/ratelimit.py — rate-limit por IP, in-memory (estado único).

Lo usan los callbacks de OAuth (`google.py`) y el staging-login (`staging.py`):
un solo `_failures` para que el conteo sea compartido. Movido verbatim de
`routes/auth.py`.
"""
import time
from collections import defaultdict

from fastapi import HTTPException

_failures: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 600
_RATE_MAX = 10


def _check_rate(ip: str) -> None:
    now = time.time()
    recent = [t for t in _failures[ip] if now - t < _RATE_WINDOW]
    _failures[ip] = recent
    if len(recent) >= _RATE_MAX:
        raise HTTPException(429, "Demasiados intentos. Intentá en 10 minutos.")


def _record_fail(ip: str) -> None:
    _failures[ip].append(time.time())
