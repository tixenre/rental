"""Caracterización de `dias_no_disponibles`: la versión optimizada (diff-array
event-based) debe dar EXACTAMENTE la misma salida que la implementación original
(loop día-por-día), sobre cientos de escenarios aleatorios + bordes explícitos.

Por qué un test diferencial: `dias_no_disponibles` alimenta el calendario del
cliente y comparte la semántica de overlap con el gate sagrado. La optimización
NO puede cambiar ni un día bloqueado. El oráculo de abajo es una copia congelada
del algoritmo original (loop O(días×segmentos)); el test exige que el nuevo
cómputo puro coincida byte a byte.
"""
import datetime
import random

import pytest

from reservas.disponibilidad import _dias_bloqueados

pytestmark = pytest.mark.unit


# ── Oráculo: copia CONGELADA del algoritmo original (loop día-por-día) ────────
# (Era el cuerpo inline de `dias_no_disponibles` antes de la optimización.)
def _oraculo(stock, segs, mant, items, d_desde, d_hasta, buf):
    bloqueados: list[str] = []
    dia = d_desde.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = d_hasta.replace(hour=0, minute=0, second=0, microsecond=0)
    while dia <= fin:
        dia_next = dia + datetime.timedelta(days=1)
        lo = dia - buf
        hi = dia_next + buf
        for eid, qty in items.items():
            reservado = sum(
                c for (sd, sh, c) in segs.get(eid, [])
                if sd is not None and sh is not None and sd < hi and sh > lo
            )
            en_mant = sum(
                c for (sd, sh, c) in mant.get(eid, [])
                if sd is not None and sh is not None and sd < dia_next and sh > dia
            )
            disp = stock.get(eid, 0) - reservado - en_mant
            if disp < max(1, qty):
                bloqueados.append(dia.date().isoformat())
                break
        dia = dia_next
    return bloqueados


# ── Generador de escenarios aleatorios ───────────────────────────────────────
def _rand_dt(rng, base, span_dias):
    """Datetime dentro de [base, base+span_dias], con hora/minuto variados para
    ejercitar bordes de medianoche y fracciones."""
    segundos = rng.randint(0, span_dias * 86400)
    return base + datetime.timedelta(seconds=segundos)


def _rand_segmento(rng, base, span_dias):
    """Segmento (sd, sh, cant) con sd < sh (invariante real de las reservas)."""
    a = _rand_dt(rng, base, span_dias)
    dur = datetime.timedelta(seconds=rng.randint(1, 5 * 86400))
    return (a, a + dur, rng.randint(1, 3))


@pytest.mark.parametrize("semilla", range(60))
def test_optimizado_igual_al_oraculo_aleatorio(semilla):
    rng = random.Random(semilla)
    base = datetime.datetime(2026, 6, 1)
    span = 20

    n_eq = rng.randint(1, 4)
    ids = list(range(1, n_eq + 1))
    items = {eid: rng.randint(1, 3) for eid in ids}
    stock = {eid: rng.randint(0, 4) for eid in ids}

    segs = {eid: [_rand_segmento(rng, base, span) for _ in range(rng.randint(0, 5))] for eid in ids}
    mant = {eid: [_rand_segmento(rng, base, span) for _ in range(rng.randint(0, 2))] for eid in ids}

    # Buffer variado: 0, horas sueltas, y múltiplos de día.
    buf = datetime.timedelta(hours=rng.choice([0, 1, 2, 6, 24, 48]))

    d_desde = _rand_dt(rng, base, span)
    d_hasta = d_desde + datetime.timedelta(days=rng.randint(0, 15))

    esperado = _oraculo(stock, segs, mant, items, d_desde, d_hasta, buf)
    obtenido = _dias_bloqueados(stock, segs, mant, items, d_desde, d_hasta, buf)
    assert obtenido == esperado, (
        f"semilla={semilla} buf={buf}\nesperado={esperado}\nobtenido={obtenido}"
    )


# ── Bordes explícitos (medianoche exacta, buffer que cruza el día) ───────────
def _dt(y, m, d, h=0):
    return datetime.datetime(y, m, d, h)


def test_segmento_termina_a_medianoche_exacta():
    # Reserva [01 00:00, 03 00:00): half-open → bloquea 01 y 02, NO el 03.
    stock = {1: 1}
    segs = {1: [(_dt(2026, 6, 1), _dt(2026, 6, 3), 1)]}
    mant = {1: []}
    items = {1: 1}
    buf = datetime.timedelta(0)
    esperado = _oraculo(stock, segs, mant, items, _dt(2026, 6, 1), _dt(2026, 6, 5), buf)
    obtenido = _dias_bloqueados(stock, segs, mant, items, _dt(2026, 6, 1), _dt(2026, 6, 5), buf)
    assert obtenido == esperado == ["2026-06-01", "2026-06-02"]


def test_buffer_extiende_a_dias_adyacentes():
    # Reserva de un rato el día 03, buffer 24h → bloquea 02, 03 y 04.
    stock = {1: 1}
    segs = {1: [(_dt(2026, 6, 3, 10), _dt(2026, 6, 3, 14), 1)]}
    mant = {1: []}
    items = {1: 1}
    buf = datetime.timedelta(hours=24)
    esperado = _oraculo(stock, segs, mant, items, _dt(2026, 6, 1), _dt(2026, 6, 6), buf)
    obtenido = _dias_bloqueados(stock, segs, mant, items, _dt(2026, 6, 1), _dt(2026, 6, 6), buf)
    assert obtenido == esperado == ["2026-06-02", "2026-06-03", "2026-06-04"]


def test_mantenimiento_no_usa_buffer():
    # Mantenimiento NO se expande por buffer aunque el buffer sea grande.
    stock = {1: 1}
    segs = {1: []}
    mant = {1: [(_dt(2026, 6, 3), _dt(2026, 6, 4), 1)]}
    items = {1: 1}
    buf = datetime.timedelta(hours=48)
    esperado = _oraculo(stock, segs, mant, items, _dt(2026, 6, 1), _dt(2026, 6, 6), buf)
    obtenido = _dias_bloqueados(stock, segs, mant, items, _dt(2026, 6, 1), _dt(2026, 6, 6), buf)
    assert obtenido == esperado == ["2026-06-03"]


def test_rango_de_un_solo_dia():
    stock = {1: 1}
    segs = {1: [(_dt(2026, 6, 2), _dt(2026, 6, 3), 1)]}
    mant = {1: []}
    items = {1: 1}
    buf = datetime.timedelta(0)
    esperado = _oraculo(stock, segs, mant, items, _dt(2026, 6, 2), _dt(2026, 6, 2), buf)
    obtenido = _dias_bloqueados(stock, segs, mant, items, _dt(2026, 6, 2), _dt(2026, 6, 2), buf)
    assert obtenido == esperado == ["2026-06-02"]


def test_sin_segmentos_no_bloquea_nada():
    stock = {1: 2}
    items = {1: 1}
    buf = datetime.timedelta(hours=12)
    esperado = _oraculo(stock, {1: []}, {1: []}, items, _dt(2026, 6, 1), _dt(2026, 6, 10), buf)
    obtenido = _dias_bloqueados(stock, {1: []}, {1: []}, items, _dt(2026, 6, 1), _dt(2026, 6, 10), buf)
    assert obtenido == esperado == []
