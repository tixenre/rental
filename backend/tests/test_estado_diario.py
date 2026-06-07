"""Estado por día del calendario de disponibilidad (#808) — parte PURA.

`_estado_diario` clasifica cada día como libre / parcial / reservado a partir de
los segmentos de ocupación (reservas + mantenimiento) de UN equipo, vía un barrido
temporal. Estos tests fijan los dos sentidos de 'parcial' (por stock y por hora) y
los extremos, sin DB.
"""
from datetime import datetime

import pytest

from reservas.disponibilidad import _estado_diario

pytestmark = pytest.mark.unit


def _dt(s):
    return datetime.fromisoformat(s)


D0, D1 = _dt("2026-07-01T00:00:00"), _dt("2026-07-01T00:00:00")  # un solo día


def _estado_de_dia(stock, segs, mant=None):
    res = _estado_diario(stock, segs, mant or [], D0, D1)
    return res["2026-07-01"]


def test_sin_segmentos_es_libre():
    assert _estado_de_dia(1, []) == "libre"


def test_una_unidad_ocupada_todo_el_dia_es_reservado():
    segs = [(_dt("2026-06-30T08:00:00"), _dt("2026-07-02T08:00:00"), 1)]
    assert _estado_de_dia(1, segs) == "reservado"


def test_parcial_por_stock_3_de_6_ocupadas_todo_el_dia():
    # 6 unidades, 3 ocupadas todo el día → quedan 3 → parcial (ni libre ni reservado).
    segs = [(_dt("2026-06-30T08:00:00"), _dt("2026-07-02T08:00:00"), 3)]
    assert _estado_de_dia(6, segs) == "parcial"


def test_parcial_por_hora_devolucion_media_manana():
    # stock 1, ocupado hasta las 10am de ese día → libre a la tarde → parcial.
    segs = [(_dt("2026-06-29T08:00:00"), _dt("2026-07-01T10:00:00"), 1)]
    assert _estado_de_dia(1, segs) == "parcial"


def test_reservado_solo_si_todo_el_dia_sin_libres():
    # stock 2, dos segmentos concurrentes todo el día → 0 libres → reservado.
    segs = [
        (_dt("2026-06-30T08:00:00"), _dt("2026-07-02T08:00:00"), 1),
        (_dt("2026-06-30T09:00:00"), _dt("2026-07-02T09:00:00"), 1),
    ]
    assert _estado_de_dia(2, segs) == "reservado"


def test_mantenimiento_ocupa_igual_que_reserva():
    mant = [(_dt("2026-06-30T00:00:00"), _dt("2026-07-02T00:00:00"), 1)]
    assert _estado_de_dia(1, [], mant) == "reservado"


def test_rango_multiple_dias_mezcla_estados():
    # Día 1 reservado (ocupado todo), día 2 libre, día 3 parcial (libera 10am).
    stock = 1
    segs = [
        (_dt("2026-07-01T00:00:00"), _dt("2026-07-02T00:00:00"), 1),   # día 1 entero
        (_dt("2026-07-02T23:00:00"), _dt("2026-07-03T10:00:00"), 1),   # cruza al día 3, libera 10am
    ]
    res = _estado_diario(stock, segs, [], _dt("2026-07-01T00:00:00"), _dt("2026-07-03T00:00:00"))
    assert res["2026-07-01"] == "reservado"
    assert res["2026-07-02"] == "parcial"   # ocupado 23:00→fin del día
    assert res["2026-07-03"] == "parcial"   # ocupado hasta 10am, libre después
