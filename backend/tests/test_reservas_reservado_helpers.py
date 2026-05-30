"""Paso 1 — Helpers de reserva compartidos (`_reservado_directo` / `_reservado_via_kit`).

Extraídos para que el gate (`_check_stock`) y el chequeo hipotético del portal
(`_check_stock_hipotetico`) usen UNA sola definición de la subquery de reserva
directa (antes byte-idéntica y copiada en dos módulos). Estos tests fijan la
conducta de los helpers (devuelven el escalar COALESCE, params bound en orden) y
que ambos chequeos efectivamente comparten el helper.
"""
import ast
import inspect
from types import SimpleNamespace

import pytest

from reservas import reservado_directo as _reservado_directo
from reservas import reservado_via_kit as _reservado_via_kit

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
    """Guard estructural: el gate y el chequeo hipotético usan el helper de
    reserva compartido (`reservado_directo`, con o sin alias `_`) en vez de
    re-copiar la subquery (evita que vuelvan a divergir). El gate vive en
    `reservas.gate.validar_stock` (usa el nombre del paquete); el hipotético en
    `cliente_portal` lo importa con alias `_reservado_directo` — ambos cuentan."""
    from reservas import validar_stock
    from routes.cliente_portal import _check_stock_hipotetico

    for fn in (validar_stock, _check_stock_hipotetico):
        src = inspect.getsource(fn)
        names = {n.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Name)}
        usa_helper = "reservado_directo" in names or "_reservado_directo" in names
        assert usa_helper, f"{fn.__name__} no usa el helper compartido de reserva"
        # Y no re-inlinea la subquery cruda de reserva directa.
        assert "FROM alquiler_items pi2" not in src, (
            f"{fn.__name__} re-copia la subquery en vez de usar el helper"
        )


# ── _check_stock_hipotetico — conducta (cuenta directo + vía-kit) ────────────

class _HipoteticoConn:
    """FakeConn para `_check_stock_hipotetico`: stubea el lookup de equipo, el
    lock FOR UPDATE, el buffer y las dos subqueries de reserva."""

    def __init__(self, stock, directo=0, via_kit=0, buffer_horas=0):
        self.stock = stock
        self.directo = directo
        self.via_kit = via_kit
        self.buffer_horas = buffer_horas

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM APP_SETTINGS WHERE KEY = ?" in s:
            return FakeCursor([FakeRow(value=str(self.buffer_horas))])
        if "FROM EQUIPO_MANTENIMIENTO" in s:
            return FakeCursor([FakeRow({0: 0})])
        if "SELECT NOMBRE, CANTIDAD FROM EQUIPOS WHERE ID = ?" in s:
            return FakeCursor([FakeRow(nombre="Cámara", cantidad=self.stock)])
        if "SELECT CANTIDAD FROM EQUIPOS WHERE ID = ? FOR UPDATE" in s:
            return FakeCursor([FakeRow(cantidad=self.stock)])
        if "JOIN KIT_COMPONENTES KC ON KC.EQUIPO_ID = PI2.EQUIPO_ID WHERE KC.COMPONENTE_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.via_kit})])
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.directo})])
        return FakeCursor([])

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _item(equipo_id, cantidad):
    return SimpleNamespace(equipo_id=equipo_id, cantidad=cantidad)


def test_hipotetico_cuenta_reserva_via_kit():
    """Conducta corregida (cambio deliberado, aprobado por el dueño): si la única
    unidad está reservada vía un kit, una propuesta directa por esa unidad se
    rechaza — igual que el gate real. Antes era un undercount (no la contaba)."""
    from routes.cliente_portal import _check_stock_hipotetico

    conn = _HipoteticoConn(stock=1, directo=0, via_kit=1)
    problemas = _check_stock_hipotetico(conn, 99, "2026-06-01", "2026-06-05", [_item(20, 1)])
    assert len(problemas) == 1
    assert "Cámara" in problemas[0]


def test_hipotetico_con_stock_libre_acepta():
    """Caso normal con stock de sobra: la propuesta pasa (no regresión)."""
    from routes.cliente_portal import _check_stock_hipotetico

    conn = _HipoteticoConn(stock=3, directo=0, via_kit=0)
    problemas = _check_stock_hipotetico(conn, 99, "2026-06-01", "2026-06-05", [_item(20, 1)])
    assert problemas == []
