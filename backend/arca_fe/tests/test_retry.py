"""Tests de arca_fe.retry.with_retry — puros, sin red (fn falsas + time.sleep mockeado)."""
from __future__ import annotations

import pytest

from arca_fe.errores import ArcaBusinessError, ArcaNetworkError
from arca_fe.retry import with_retry

pytestmark = pytest.mark.unit


def test_exito_al_primer_intento_no_reintenta(monkeypatch):
    sleeps = []
    monkeypatch.setattr("arca_fe.retry.time.sleep", lambda s: sleeps.append(s))

    llamadas = []

    def fn():
        llamadas.append(1)
        return "ok"

    assert with_retry(fn) == "ok"
    assert len(llamadas) == 1
    assert sleeps == []


def test_reintenta_arca_network_error_hasta_exito(monkeypatch):
    monkeypatch.setattr("arca_fe.retry.time.sleep", lambda s: None)

    intentos = {"n": 0}

    def fn():
        intentos["n"] += 1
        if intentos["n"] < 3:
            raise ArcaNetworkError("timeout")
        return "recuperado"

    assert with_retry(fn, intentos=5) == "recuperado"
    assert intentos["n"] == 3


def test_agota_intentos_y_propaga_la_excepcion(monkeypatch):
    monkeypatch.setattr("arca_fe.retry.time.sleep", lambda s: None)

    def fn():
        raise ArcaNetworkError("siempre falla")

    with pytest.raises(ArcaNetworkError, match="siempre falla"):
        with_retry(fn, intentos=3)


def test_no_reintenta_excepcion_no_incluida_en_la_lista(monkeypatch):
    """`ArcaBusinessError` (AFIP rechazó por regla de negocio) NUNCA se reintenta por
    default — reintentar sin cambiar nada da el mismo resultado. Rompe el guardrail a
    propósito (comentado abajo) para confirmar que el test lo detectaría."""
    monkeypatch.setattr("arca_fe.retry.time.sleep", lambda s: None)

    llamadas = []

    def fn():
        llamadas.append(1)
        raise ArcaBusinessError("rechazado")

    with pytest.raises(ArcaBusinessError):
        with_retry(fn, intentos=3)
    assert len(llamadas) == 1, "no debe reintentar una excepción fuera de `excepciones`"


def test_backoff_exponencial(monkeypatch):
    sleeps = []
    monkeypatch.setattr("arca_fe.retry.time.sleep", lambda s: sleeps.append(s))

    def fn():
        raise ArcaNetworkError("x")

    with pytest.raises(ArcaNetworkError):
        with_retry(fn, intentos=4, backoff_inicial=1.0)

    assert sleeps == [1.0, 2.0, 4.0]
