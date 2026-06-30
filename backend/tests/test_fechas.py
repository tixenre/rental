"""Candados de la fuente única de validación de fechas (`services.fechas`).

Cubre el criterio de rango (orden / no-pasado / tope) y el lead-time configurable.
Tiempos en wall-clock AR (`now_ar()`), no `date.today()` (UTC en CI desfasa).
"""

import datetime

from database import now_ar
from services.fechas import (
    validar_rango_fechas,
    antelacion_minima_horas,
    antelacion_insuficiente,
    inicio_desde_fecha_hora,
)


# ── Fake conn (mismo molde que test_checkout_portero) ───────────────────────────


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, responses=None):
        self._resp = responses or {}

    def execute(self, sql, params=None):
        for key, val in self._resp.items():
            if key in sql:
                return _FakeCursor(val)
        return _FakeCursor(None)


def _d(delta_days: int) -> str:
    return (now_ar().date() + datetime.timedelta(days=delta_days)).isoformat()


# ── validar_rango_fechas ────────────────────────────────────────────────────────


def test_rango_ok():
    assert validar_rango_fechas(_d(1), _d(3)) is None


def test_rango_orden_invertido():
    msg = validar_rango_fechas(_d(3), _d(1))
    assert msg and "posterior" in msg


def test_rango_mismo_dia_sin_hora_invalido():
    # Sin hora (date puro) retiro==devolución → d0>=d1 → inválido (preserva el
    # comportamiento del portero, que compara por día).
    assert validar_rango_fechas(_d(2), _d(2)) is not None


def test_rango_pasado_cliente():
    msg = validar_rango_fechas(_d(-1), _d(2))
    assert msg and "pasado" in msg


def test_rango_pasado_permitido():
    # Admin / histórico (permitir_pasado=True) → la fecha pasada no bloquea.
    assert validar_rango_fechas(_d(-5), _d(-1), permitir_pasado=True) is None


def test_rango_tope_dias():
    msg = validar_rango_fechas(_d(1), _d(200), max_dias=120)
    assert msg and "120" in msg


def test_rango_dentro_del_tope():
    assert validar_rango_fechas(_d(1), _d(10), max_dias=120) is None


def test_rango_sin_ambas_fechas_no_valida():
    # "ambas o ninguna" lo decide el caller; sin ambas el helper no opina.
    assert validar_rango_fechas(None, _d(2)) is None
    assert validar_rango_fechas(_d(2), None) is None
    assert validar_rango_fechas(None, None) is None


# ── antelacion_minima_horas ─────────────────────────────────────────────────────


def test_antelacion_setting_valido():
    assert antelacion_minima_horas(_FakeConn({"app_settings": {"value": "12"}})) == 12


def test_antelacion_setting_ausente_es_cero():
    assert antelacion_minima_horas(_FakeConn()) == 0


def test_antelacion_setting_corrupto_falla_a_cero():
    assert antelacion_minima_horas(_FakeConn({"app_settings": {"value": "doce"}})) == 0


def test_antelacion_setting_negativo_clampea_a_cero():
    assert antelacion_minima_horas(_FakeConn({"app_settings": {"value": "-5"}})) == 0


# ── antelacion_insuficiente ─────────────────────────────────────────────────────


def test_insuficiente_apagado_nunca_bloquea():
    conn = _FakeConn({"app_settings": {"value": "0"}})
    assert antelacion_insuficiente(conn, now_ar() + datetime.timedelta(hours=1)) is None


def test_insuficiente_dentro_de_ventana():
    conn = _FakeConn({"app_settings": {"value": "12"}})
    horas = antelacion_insuficiente(conn, now_ar() + datetime.timedelta(hours=2))
    assert horas == 12


def test_insuficiente_fuera_de_ventana():
    conn = _FakeConn({"app_settings": {"value": "12"}})
    assert antelacion_insuficiente(conn, now_ar() + datetime.timedelta(hours=48)) is None


def test_insuficiente_inicio_none():
    conn = _FakeConn({"app_settings": {"value": "12"}})
    assert antelacion_insuficiente(conn, None) is None


# ── inicio_desde_fecha_hora ─────────────────────────────────────────────────────


def test_inicio_con_hora():
    dt = inicio_desde_fecha_hora("2026-07-01", "14:30")
    assert dt == datetime.datetime(2026, 7, 1, 14, 30)


def test_inicio_sin_hora_es_medianoche():
    dt = inicio_desde_fecha_hora("2026-07-01", None)
    assert dt == datetime.datetime(2026, 7, 1, 0, 0)


def test_inicio_hora_invalida_cae_a_medianoche():
    dt = inicio_desde_fecha_hora("2026-07-01", "no-es-hora")
    assert dt == datetime.datetime(2026, 7, 1, 0, 0)


def test_inicio_sin_fecha_es_none():
    assert inicio_desde_fecha_hora(None, "14:30") is None
