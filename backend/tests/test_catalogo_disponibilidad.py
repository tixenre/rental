"""Catálogo: `_attach_disponibilidad` usa la fuente única del motor.

Antes el catálogo (`routes/equipos._attach_disponibilidad`) tenía su propia query
de disponibilidad que NO restaba mantenimiento ni aplicaba buffer → mostraba
disponibilidad inflada respecto del gate de confirmación (bug #619). Ahora delega
en `reservas.calcular_disponibilidad`, así muestra exactamente lo mismo que el
chequeo real.

Estos tests fijan esa conducta con un fake conn que stubea las 3 queries de
`calcular_disponibilidad` (directas + vía kit + mantenimiento).
"""
import pytest

from routes.equipos import _attach_disponibilidad

pytestmark = pytest.mark.unit


class FakeRow(dict):
    pass


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class DispFakeConn:
    """Stubea las queries de `reservas.calcular_disponibilidad` (C4).

    - equipos: dict[id, {cantidad}]            (stock total)
    - reservados: dict[equipo_id, int]         (items reservados DIRECTOS por equipo)
    - kit: dict[equipo_id, [(cid, q, esencial)]]  (grafo de composición)
    - mantenimiento: dict[id, int]             (unidades fuera de servicio)
    - buffer_horas: int

    El consumo (lo que descuenta cada equipo) se DERIVA expandiendo `reservados`
    por el grafo `kit` — espeja la lógica real (un kit/combo reservado descuenta
    sus componentes, recursivamente).
    """

    def __init__(self, equipos, reservados=None, kit=None,
                 mantenimiento=None, buffer_horas=0):
        self.equipos = equipos
        self.reservados = reservados or {}
        self.kit = kit or {}
        self.mantenimiento = mantenimiento or {}
        self.buffer_horas = buffer_horas

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()

        # Buffer global (setting).
        if "FROM APP_SETTINGS WHERE KEY = %S" in s:
            return FakeCursor([FakeRow(value=str(self.buffer_horas))])

        # Stock propio de cada equipo.
        if s.startswith("SELECT ID, CANTIDAD FROM EQUIPOS"):
            return FakeCursor([
                FakeRow(id=eid, cantidad=data["cantidad"])
                for eid, data in self.equipos.items()
            ])

        # Items reservados (directos) agregados por equipo.
        if "FROM ALQUILER_ITEMS PI JOIN ALQUILERES P" in s and "GROUP BY PI.EQUIPO_ID" in s:
            return FakeCursor([
                FakeRow(eid=eid, cant=cant) for eid, cant in self.reservados.items()
            ])

        # Grafo de composición (componentes_de, completo).
        if s.startswith("SELECT EQUIPO_ID, COMPONENTE_ID, CANTIDAD") and "FROM KIT_COMPONENTES" in s:
            return FakeCursor([
                FakeRow(equipo_id=eid, componente_id=cid, cantidad=q, esencial=ese)
                for eid, comps in self.kit.items()
                for (cid, q, ese) in comps
            ])

        # Mantenimiento que bloquea stock.
        if "FROM EQUIPO_MANTENIMIENTO" in s and "AS BLOQUEADO" in s:
            return FakeCursor([
                FakeRow(equipo_id=eid, bloqueado=n)
                for eid, n in self.mantenimiento.items()
            ])

        return FakeCursor([])


D, H = "2026-06-01", "2026-06-05"


def test_disponible_resta_reservas_directas():
    conn = DispFakeConn(
        equipos={1: {"cantidad": 5}},
        reservados={1: 2},
    )
    equipos = [{"id": 1, "cantidad": 5}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 3


def test_disponible_resta_mantenimiento_fix_619():
    """EL FIX #619: un equipo en mantenimiento ahora baja la disponibilidad del
    catálogo. Antes esta resta se ignoraba y el catálogo inflaba el número."""
    conn = DispFakeConn(
        equipos={1: {"cantidad": 3}},
        reservados={1: 0},
        mantenimiento={1: 2},  # 2 unidades fuera de servicio
    )
    equipos = [{"id": 1, "cantidad": 3}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 1  # 3 - 0 - 2


def test_disponible_resta_via_kit():
    # 1 unidad de la hoja 20 comprometida dentro de un kit 10 reservado (q1).
    conn = DispFakeConn(
        equipos={10: {"cantidad": 5}, 20: {"cantidad": 2}},
        reservados={10: 1},
        kit={10: [(20, 1, True)]},
    )
    equipos = [{"id": 20, "cantidad": 2}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 1


def test_disponible_resta_via_combo_anidado():
    """C4: una hoja comprometida por un COMBO ANIDADO (combo→kit→hoja) baja su
    disponibilidad en el catálogo. A 1 nivel no se descontaba (optimista)."""
    conn = DispFakeConn(
        equipos={30: {"cantidad": 9}, 10: {"cantidad": 9}, 20: {"cantidad": 2}},
        reservados={30: 1},                       # 1 combo reservado
        kit={30: [(10, 1, True)], 10: [(20, 1, True)]},  # combo→kit→hoja
    )
    equipos = [{"id": 20, "cantidad": 2}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 1  # 2 - 1 (vía combo anidado)


def test_disponible_nunca_negativo():
    conn = DispFakeConn(
        equipos={1: {"cantidad": 1}},
        reservados={1: 1},
        mantenimiento={1: 2},  # sobre-comprometido
    )
    equipos = [{"id": 1, "cantidad": 1}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 0  # max(0, ...) — nunca negativo


def test_equipo_sin_filas_cae_a_su_stock():
    """Si el equipo no aparece en el cálculo (sin reservas/mant), usa su stock."""
    conn = DispFakeConn(equipos={})  # calcular_disponibilidad no lo devuelve
    equipos = [{"id": 99, "cantidad": 7}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 7
