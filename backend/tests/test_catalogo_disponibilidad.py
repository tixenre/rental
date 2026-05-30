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
    """Stubea las queries de `reservas.calcular_disponibilidad`.

    - equipos: dict[id, {cantidad}]   (stock total)
    - reservas_directas: dict[id, int]
    - reservas_via_kit: dict[componente_id, int]
    - mantenimiento: dict[id, int]    (unidades fuera de servicio, bloquea_stock)
    - buffer_horas: int
    """

    def __init__(self, equipos, reservas_directas=None, reservas_via_kit=None,
                 mantenimiento=None, buffer_horas=0):
        self.equipos = equipos
        self.reservas_directas = reservas_directas or {}
        self.reservas_via_kit = reservas_via_kit or {}
        self.mantenimiento = mantenimiento or {}
        self.buffer_horas = buffer_horas

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()

        # Buffer global (setting).
        if "FROM APP_SETTINGS WHERE KEY = ?" in s:
            return FakeCursor([FakeRow(value=str(self.buffer_horas))])

        # Disponibilidad directa: SELECT e.id, e.cantidad, ... reservado FROM equipos e
        if "FROM EQUIPOS E" in s and "AS RESERVADO" in s:
            return FakeCursor([
                FakeRow(id=eid, cantidad=data["cantidad"],
                        reservado=self.reservas_directas.get(eid, 0))
                for eid, data in self.equipos.items()
            ])

        # Reservas vía kit.
        if "FROM KIT_COMPONENTES KC" in s and "AS EXTRA" in s:
            return FakeCursor([
                FakeRow(componente_id=cid, extra=extra)
                for cid, extra in self.reservas_via_kit.items()
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
        reservas_directas={1: 2},
    )
    equipos = [{"id": 1, "cantidad": 5}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 3


def test_disponible_resta_mantenimiento_fix_619():
    """EL FIX #619: un equipo en mantenimiento ahora baja la disponibilidad del
    catálogo. Antes esta resta se ignoraba y el catálogo inflaba el número."""
    conn = DispFakeConn(
        equipos={1: {"cantidad": 3}},
        reservas_directas={1: 0},
        mantenimiento={1: 2},  # 2 unidades fuera de servicio
    )
    equipos = [{"id": 1, "cantidad": 3}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 1  # 3 - 0 - 2


def test_disponible_resta_via_kit():
    conn = DispFakeConn(
        equipos={20: {"cantidad": 2}},
        reservas_via_kit={20: 1},  # 1 unidad comprometida dentro de un kit
    )
    equipos = [{"id": 20, "cantidad": 2}]
    out = _attach_disponibilidad(conn, equipos, D, H)
    assert out[0]["disponible"] == 1


def test_disponible_nunca_negativo():
    conn = DispFakeConn(
        equipos={1: {"cantidad": 1}},
        reservas_directas={1: 1},
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
