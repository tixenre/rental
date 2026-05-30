"""Paso 1 — Helpers de reserva compartidos (`_reservado_directo` / `_reservado_via_kit`).

Extraídos para que el gate (`_check_stock`) y el chequeo hipotético del portal
(`_check_stock_hipotetico`) usen UNA sola definición de la subquery de reserva
directa (antes byte-idéntica y copiada en dos módulos). Estos tests fijan la
conducta de los helpers (devuelven el escalar COALESCE, params bound en orden) y
que ambos chequeos efectivamente comparten el helper.
"""
import ast
import inspect

import pytest

from routes.alquileres import _reservado_directo, _reservado_via_kit

pytestmark = pytest.mark.unit


class FakeRow(dict):
    pass


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, directo=0, via_kit=0):
        self.directo = directo
        self.via_kit = via_kit
        self.calls = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        self.calls.append((s, params))
        if "JOIN KIT_COMPONENTES KC ON KC.EQUIPO_ID = PI2.EQUIPO_ID WHERE KC.COMPONENTE_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.via_kit})])
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.directo})])
        return FakeCursor([])


def test_reservado_directo_devuelve_escalar():
    assert _reservado_directo(_Conn(directo=3), 42, 7, "fh", "fd") == 3


def test_reservado_via_kit_devuelve_escalar():
    assert _reservado_via_kit(_Conn(via_kit=5), 42, 7, "fh", "fd") == 5


def test_params_van_como_bound_y_en_orden():
    c = _Conn(directo=0)
    _reservado_directo(c, 42, 7, "FH", "FD")
    sql, params = c.calls[-1]
    # equipo_id, excl_pedido_id, fh_buf, fd_buf — en ese orden, como bound params.
    assert params == (42, 7, "FH", "FD")
    # SQL parametrizado: placeholders ? presentes y sin {…} sin sustituir.
    assert "?" in sql and "{" not in sql


def test_gate_e_hipotetico_comparten_el_helper():
    """Guard estructural: ambos chequeos referencian `_reservado_directo` en vez
    de re-copiar la subquery (evita que vuelvan a divergir)."""
    from routes.alquileres import _check_stock
    from routes.cliente_portal import _check_stock_hipotetico

    for fn in (_check_stock, _check_stock_hipotetico):
        names = {
            n.id for n in ast.walk(ast.parse(inspect.getsource(fn)))
            if isinstance(n, ast.Name)
        }
        assert "_reservado_directo" in names, f"{fn.__name__} no usa el helper compartido"
