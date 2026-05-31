"""Helpers de reserva compartidos (`reservado_directo` / `reservado_total`).

`reservado_directo` es la subquery única de reserva DIRECTA. `reservado_total`
(C4 #635) es el conteo de consumo RECURSIVO que reemplazó al par
`reservado_directo + reservado_via_kit` (1 nivel): sube por el grafo inverso de
composición (`parientes_de`) y suma la reserva directa de cada antecesor ponderada
por la multiplicidad del camino — así un combo→kit→hoja reservado por otro pedido
descuenta la hoja (a 1 nivel no lo hacía → overbooking en anidados).

Estos tests fijan: el escalar de `reservado_directo`, la recursión de
`reservado_total` (directo, vía-kit 1 nivel, anidado, multiplicación de
cantidades), que params van como bound, y que el gate y el chequeo hipotético del
portal comparten el MISMO helper (`reservado_total`) en vez de re-copiar la
subquery.
"""
import ast
import inspect
from types import SimpleNamespace

import pytest

from reservas import reservado_directo as _reservado_directo
from reservas import reservado_total as _reservado_total

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
    """FakeConn mínimo para `reservado_directo`: stubea la subquery directa."""

    def __init__(self, directo=0):
        self.directo = directo
        self.calls = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        self.calls.append((s, params))
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.directo})])
        return FakeCursor([])


class _RevConn:
    """FakeConn para `reservado_total`: grafo inverso (`parientes_de`) + reserva
    directa por equipo.

    parents:  dict[componente_id, list[(equipo_id, cantidad, esencial)]]
    directas: dict[equipo_id, int]  (lo que devuelve `reservado_directo` por equipo)
    """

    def __init__(self, parents=None, directas=None):
        self.parents = parents or {}
        self.directas = directas or {}

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        # parientes_de (grafo inverso completo).
        if s.startswith("SELECT EQUIPO_ID, COMPONENTE_ID, CANTIDAD") and "FROM KIT_COMPONENTES" in s:
            rows = [
                FakeRow(equipo_id=eq, componente_id=cid, cantidad=cant, esencial=ese)
                for cid, plist in self.parents.items()
                for (eq, cant, ese) in plist
            ]
            return FakeCursor(rows)
        # reservado_directo.
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.directas.get(params[0], 0)})])
        return FakeCursor([])


# ── reservado_directo ────────────────────────────────────────────────────────

def test_reservado_directo_devuelve_escalar():
    assert _reservado_directo(_Conn(directo=3), 42, 7, "fh", "fd") == 3


def test_params_van_como_bound_y_en_orden():
    c = _Conn(directo=0)
    _reservado_directo(c, 42, 7, "FH", "FD")
    sql, params = c.calls[-1]
    # equipo_id, excl_pedido_id, fh_buf, fd_buf — en ese orden, como bound params.
    assert params == (42, 7, "FH", "FD")
    # SQL parametrizado: placeholders ? presentes y sin {…} sin sustituir.
    assert "?" in sql and "{" not in sql


# ── reservado_total — conteo de consumo recursivo (C4) ───────────────────────

def test_reservado_total_solo_directo():
    # Sin compuestos: cuenta solo la reserva directa del propio equipo.
    assert _reservado_total(_RevConn(directas={42: 3}), 42, 7, "fh", "fd") == 3


def test_reservado_total_via_kit_un_nivel():
    # Equipo 20 es componente del kit 10 (q1); el kit 10 está reservado 1 vez.
    conn = _RevConn(parents={20: [(10, 1, True)]}, directas={10: 1})
    assert _reservado_total(conn, 20, 7, "fh", "fd") == 1


def test_reservado_total_anidado():
    # Combo 30 → Kit 10 → Hoja 20 (q1 cada arista); el combo 30 reservado 2 veces.
    # A 1 nivel daba 0 (el combo no es padre directo de la hoja) → overbooking.
    conn = _RevConn(parents={20: [(10, 1, True)], 10: [(30, 1, True)]}, directas={30: 2})
    assert _reservado_total(conn, 20, 7, "fh", "fd") == 2


def test_reservado_total_multiplica_cantidades():
    # Kit 10 contiene 3× hoja 20; el kit reservado 2 → consume 6 hojas.
    conn = _RevConn(parents={20: [(10, 3, True)]}, directas={10: 2})
    assert _reservado_total(conn, 20, 7, "fh", "fd") == 6


def test_reservado_total_suma_directo_y_via_compuesto():
    # 1 reserva directa de la hoja 20 + 1 vía kit 10 (q1) = 2.
    conn = _RevConn(parents={20: [(10, 1, True)]}, directas={20: 1, 10: 1})
    assert _reservado_total(conn, 20, 7, "fh", "fd") == 2


# ── Guard estructural: gate e hipotético comparten el helper ─────────────────

def test_gate_e_hipotetico_comparten_el_helper():
    """El gate y el chequeo hipotético usan el helper de consumo compartido
    (`reservado_total`, con o sin alias `_`) en vez de re-copiar la subquery (evita
    que vuelvan a divergir, ahora a cualquier profundidad). El gate vive en
    `reservas.gate.validar_stock`; el hipotético en `cliente_portal` lo importa con
    alias `_reservado_total` — ambos cuentan."""
    from reservas import validar_stock
    from routes.cliente_portal import _check_stock_hipotetico

    for fn in (validar_stock, _check_stock_hipotetico):
        src = inspect.getsource(fn)
        names = {n.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Name)}
        usa_helper = "reservado_total" in names or "_reservado_total" in names
        assert usa_helper, f"{fn.__name__} no usa el helper compartido de consumo"
        # Y no re-inlinea la subquery cruda de reserva directa.
        assert "FROM alquiler_items pi2" not in src, (
            f"{fn.__name__} re-copia la subquery en vez de usar el helper"
        )


# ── _check_stock_hipotetico — conducta (cuenta consumo recursivo) ────────────

class _HipoteticoConn:
    """FakeConn para `_check_stock_hipotetico` (espeja el gate: forward + backward).

    stock:    dict[id, cantidad]
    kit:      list[(equipo_id, componente_id, cantidad, esencial)]  (filas crudas de
              kit_componentes — sirven a la vez para componentes_de y parientes_de)
    directas: dict[equipo_id, int]   (lo que devuelve reservado_directo por equipo)
    nombres:  dict[id, nombre]       (opcional; default f"eq{id}")
    """

    def __init__(self, stock, kit=None, directas=None, nombres=None, buffer_horas=0):
        self.stock = stock
        self.kit = kit or []
        self.directas = directas or {}
        self.nombres = nombres or {}
        self.buffer_horas = buffer_horas

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM APP_SETTINGS WHERE KEY = ?" in s:
            return FakeCursor([FakeRow(value=str(self.buffer_horas))])
        if "FROM EQUIPO_MANTENIMIENTO" in s:
            return FakeCursor([FakeRow({0: 0})])
        if s.startswith("SELECT EQUIPO_ID, COMPONENTE_ID, CANTIDAD") and "FROM KIT_COMPONENTES" in s:
            return FakeCursor([
                FakeRow(equipo_id=e, componente_id=c, cantidad=q, esencial=es)
                for (e, c, q, es) in self.kit
            ])
        if s.startswith("SELECT ID, NOMBRE FROM EQUIPOS WHERE ID IN"):
            return FakeCursor([
                FakeRow(id=i, nombre=self.nombres.get(i, f"eq{i}")) for i in self.stock
            ])
        if "SELECT CANTIDAD FROM EQUIPOS WHERE ID = ? FOR UPDATE" in s:
            i = params[0]
            return FakeCursor([FakeRow(cantidad=self.stock[i])] if i in self.stock else [])
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s:
            return FakeCursor([FakeRow({0: self.directas.get(params[0], 0)})])
        return FakeCursor([])

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _item(equipo_id, cantidad):
    return SimpleNamespace(equipo_id=equipo_id, cantidad=cantidad)


def test_hipotetico_cuenta_reserva_via_compuesto():
    """Backward: si la única unidad de la hoja está tomada por un compuesto
    reservado, una propuesta directa por esa hoja se rechaza — igual que el gate."""
    from routes.cliente_portal import _check_stock_hipotetico

    conn = _HipoteticoConn(
        stock={20: 1},
        kit=[(10, 20, 1, True)],   # kit 10 contiene hoja 20
        directas={10: 1},          # kit 10 reservado
        nombres={20: "Cámara"},
    )
    problemas = _check_stock_hipotetico(conn, 99, "2026-06-01", "2026-06-05", [_item(20, 1)])
    assert len(problemas) == 1
    assert "Cámara" in problemas[0]


def test_hipotetico_con_stock_libre_acepta():
    """Caso normal con stock de sobra: la propuesta pasa (no regresión)."""
    from routes.cliente_portal import _check_stock_hipotetico

    conn = _HipoteticoConn(stock={20: 3})
    problemas = _check_stock_hipotetico(conn, 99, "2026-06-01", "2026-06-05", [_item(20, 1)])
    assert problemas == []


def test_hipotetico_rechaza_combo_anidado_con_hoja_escasa():
    """FORWARD: una propuesta de un COMBO ANIDADO (combo→kit→hoja, hoja stock 1 ya
    tomada) se rechaza ANTES de guardarla — el pre-chequeo expande la demanda hasta
    la hoja, igual que `validar_stock`. Antes solo miraba el stock del combo (alto)
    y aceptaba; el gate real después la rechazaba (mala UX)."""
    from routes.cliente_portal import _check_stock_hipotetico

    conn = _HipoteticoConn(
        stock={30: 9, 10: 9, 20: 1},
        kit=[(30, 10, 1, True), (10, 20, 1, True)],  # combo 30 → kit 10 → hoja 20
        directas={20: 1},                            # la hoja ya está tomada
        nombres={30: "Combo", 10: "Kit", 20: "Foco Z"},
    )
    problemas = _check_stock_hipotetico(conn, 99, "2026-06-01", "2026-06-05", [_item(30, 1)])
    assert len(problemas) == 1
    assert "Foco Z" in problemas[0]
