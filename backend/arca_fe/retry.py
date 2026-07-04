"""arca_fe.retry — retry/backoff opcional. PORTABLE (solo stdlib).

`with_retry` es un helper genérico, NO se aplica automáticamente adentro de `WsfeClient`/
`PadronClient` — es opt-in explícito del consumidor, para no esconder latencia/reintentos detrás
de una llamada que hoy es predecible en tiempo.

Solo tiene sentido reintentar `ArcaNetworkError` (falla de transporte — timeout/HTTP/TLS): un
`ArcaBusinessError` (AFIP rechazó por regla de negocio) o un `ArcaAuthError` (cert/relación mal)
dan el mismo resultado si se reintentan sin cambiar nada — reintentarlos por default sería
esconder un error real detrás de reintentos inútiles.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from .errores import ArcaNetworkError

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    intentos: int = 3,
    backoff_inicial: float = 0.5,
    excepciones: tuple[type[BaseException], ...] = (ArcaNetworkError,),
) -> T:
    """Ejecuta `fn()` reintentando con backoff exponencial simple si levanta alguna de
    `excepciones` (default: solo `ArcaNetworkError`). `intentos` es el total de intentos
    (no de reintentos) — `intentos=3` corre `fn()` hasta 3 veces. Backoff:
    `backoff_inicial * 2**intento` entre cada intento fallido.

    Ejemplo: `with_retry(lambda: client.solicitar_cae(req, numero))`.

    Si el último intento también falla, la excepción se propaga tal cual (sin envolver)."""
    ultimo_exc: BaseException | None = None
    for intento in range(intentos):
        try:
            return fn()
        except excepciones as exc:
            ultimo_exc = exc
            if intento < intentos - 1:
                time.sleep(backoff_inicial * (2**intento))
    assert ultimo_exc is not None
    raise ultimo_exc
