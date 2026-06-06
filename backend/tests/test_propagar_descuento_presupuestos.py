"""El descuento del cliente se propaga a sus PRESUPUESTOS (pedidos no
confirmados) y los recotiza; los pedidos confirmados/cerrados conservan su
snapshot (lock de precio).

Bug del dueño (2026-06-06): "le modifiqué el descuento a un cliente y al entrar
en su pedido no se actualizó". Decisión: presupuestos en vivo, confirmados
congelados.
"""

import pytest

from routes.alquileres import (
    propagar_descuento_a_presupuestos,
    _recalcular_total_pedido,
)


pytestmark = pytest.mark.unit


class FakeConn:
    """Simula los SELECT/UPDATE que tocan propagación + recálculo.

    Modela varios pedidos por id (row + ítems). El SELECT de presupuestos
    devuelve SOLO los ids que le pasamos → representa el filtro
    `estado='presupuesto'` (los confirmados ni aparecen).
    """

    def __init__(self, presupuesto_ids, pedido_rows, items_by_pedido, descuentos_jornada):
        self.presupuesto_ids = presupuesto_ids
        self.pedido_rows = pedido_rows
        self.items_by_pedido = items_by_pedido
        self.descuentos_jornada = descuentos_jornada
        self.descuento_updates = []  # (id, pct)
        self.total_updates = []      # (id, monto_total, descuento_jornadas_pct)
        self._sql = ""
        self._params = ()

    def execute(self, sql, params=()):
        self._sql = sql
        self._params = params or ()
        s = sql.strip().upper()
        if s.startswith("UPDATE ALQUILERES SET DESCUENTO_PCT"):
            pct, pid = params
            self.descuento_updates.append((pid, pct))
            if pid in self.pedido_rows:
                self.pedido_rows[pid]["descuento_pct"] = pct  # el recálculo lo lee fresco
        elif s.startswith("UPDATE ALQUILERES SET MONTO_TOTAL"):
            monto, descj, pid = params
            self.total_updates.append((pid, monto, descj))
        return self

    def executemany(self, sql, seq):
        return self

    def fetchone(self):
        if "FROM alquileres WHERE id" in self._sql:
            return self.pedido_rows.get(self._params[0])
        return None

    def fetchall(self):
        sql = self._sql
        if "estado='presupuesto'" in sql:
            return [{"id": i} for i in self.presupuesto_ids]
        if "FROM alquiler_items WHERE pedido_id" in sql:
            return self.items_by_pedido.get(self._params[0], [])
        if "FROM descuentos_jornada" in sql:
            return [{"jornadas": j, "pct": p} for j, p in self.descuentos_jornada]
        return []

    def commit(self):
        pass

    def close(self):
        pass


def _pedido(id, descuento_pct=0):
    return {
        "id": id,
        "fecha_desde": "2026-07-01T10:00:00",
        "fecha_hasta": "2026-07-08T10:00:00",  # 7 jornadas
        "descuento_pct": descuento_pct,
        "descuento_jornadas_pct": 0,
    }


def test_propaga_a_presupuestos_y_recotiza():
    # Dos presupuestos del cliente (id 10 y 11), cada uno 1 ítem 10.000 x 7 = 70.000.
    rows = {10: _pedido(10, descuento_pct=0), 11: _pedido(11, descuento_pct=0)}
    items = {
        10: [{"id": 100, "equipo_id": 42, "cantidad": 1, "precio_jornada": 10000}],
        11: [{"id": 101, "equipo_id": 42, "cantidad": 1, "precio_jornada": 10000}],
    }
    conn = FakeConn([10, 11], rows, items, descuentos_jornada=[(1, 0.0)])

    n = propagar_descuento_a_presupuestos(conn, cliente_id=5, nuevo_pct=20)

    assert n == 2
    # Ambos presupuestos recibieron el nuevo descuento.
    assert sorted(conn.descuento_updates) == [(10, 20), (11, 20)]
    # Y se recotizaron: 70.000 bruto − 20% = 56.000 neto.
    montos = {pid: monto for pid, monto, _ in conn.total_updates}
    assert montos == {10: 56000, 11: 56000}


def test_sin_presupuestos_no_hace_nada():
    conn = FakeConn([], {}, {}, descuentos_jornada=[(1, 0.0)])
    n = propagar_descuento_a_presupuestos(conn, cliente_id=5, nuevo_pct=30)
    assert n == 0
    assert conn.descuento_updates == []
    assert conn.total_updates == []


def test_recalcular_usa_el_descuento_mayor():
    # descuento cliente 5% vs jornadas 10% → gana el mayor (no acumulativo).
    rows = {7: _pedido(7, descuento_pct=5)}
    items = {7: [{"id": 70, "equipo_id": 1, "cantidad": 2, "precio_jornada": 5000}]}
    # 2 x 5000 x 7 = 70.000 bruto. A 7 jornadas → 10%. → 63.000 neto.
    conn = FakeConn([7], rows, items, descuentos_jornada=[(1, 0.0), (7, 10.0)])
    _recalcular_total_pedido(conn, 7)
    assert conn.total_updates == [(7, 63000, 10.0)]
