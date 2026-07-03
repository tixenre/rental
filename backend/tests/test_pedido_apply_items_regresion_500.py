"""Regresión del bug #500.

Antes: `_apply_pedido_items` ignoraba el descuento por jornadas → editar
los ítems de un pedido perdía el descuento (el `monto_total` saltaba a más
caro solo por tocar los ítems).

Ahora: la función recalcula `descuento_jornadas_pct` desde `obtener_descuento_jornadas`
(`backend/descuentos/`), lo pasa al `calcular_total` canónico y persiste tanto
`monto_total` como `descuento_jornadas_pct` en `alquileres`.
"""

import pytest

from routes.alquileres import _apply_pedido_items, PedidoItem


pytestmark = pytest.mark.unit


# ── FakeConn ──────────────────────────────────────────────────────────────


class FakeConn:
    """Conn fake que captura los UPDATEs sobre `alquileres` y simula:
    - SELECT del pedido (devuelve los datos que le pasemos)
    - SELECT existencia de equipos (siempre existen)
    - SELECT puntos de descuento_jornada
    - INSERT/DELETE/UPDATE (capturados pero no persistidos)

    El `_get_alquiler_detail` al final lo mockeamos a nivel de import.
    """

    def __init__(self, pedido_data: dict, descuento_jornadas_puntos: list[tuple[int, float]]):
        self._pedido_data = pedido_data
        self._descuento_jornadas_puntos = descuento_jornadas_puntos
        self.updates_alquileres: list[tuple[str, tuple]] = []
        self._last_sql = ""
        self._last_params: tuple = ()

    def execute(self, sql, params=()):
        self._last_sql = sql
        self._last_params = params or ()
        if sql.strip().upper().startswith("UPDATE ALQUILERES"):
            self.updates_alquileres.append((sql, params or ()))
        return self

    def executemany(self, sql, seq):
        return self

    def fetchone(self):
        sql = self._last_sql
        if "FROM alquileres WHERE id" in sql:
            return self._pedido_data
        if "FROM equipos WHERE id" in sql:
            return {"id": self._last_params[0], "tipo": "simple"}
        return None

    def fetchall(self):
        sql = self._last_sql
        if "FROM descuentos_jornada" in sql:
            return [
                {"jornadas": j, "pct": p}
                for j, p in self._descuento_jornadas_puntos
            ]
        return []

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# ── Test de regresión ────────────────────────────────────────────────────


def test_apply_items_preserva_descuento_jornadas(monkeypatch):
    """Pedido a 7 jornadas con descuento por jornadas configurado.
    Al editar ítems, el `monto_total` resultante debe tener el descuento
    aplicado (no quedar en el bruto)."""

    # Pedido a 7 jornadas, sin cliente asignado ni override manual.
    pedido = {
        "id": 1,
        "cliente_id": None,
        "fecha_desde": "2026-06-01T10:00:00",
        "fecha_hasta": "2026-06-08T10:00:00",  # 7 jornadas
        "descuento_pct": 0,
        "descuento_jornadas_pct": 10.0,
        "descuento_manual_tipo": "pct",
        "descuento_manual_monto": 0,
    }
    # Descuentos por jornadas: a 7 jornadas → 10%.
    puntos = [(1, 0.0), (7, 10.0)]
    conn = FakeConn(pedido, puntos)

    # Evitamos resolver _get_alquiler_detail (depende de muchos JOINs).
    monkeypatch.setattr(
        "routes.alquileres._get_alquiler_detail",
        lambda conn, id: {"id": id, "monto_total": conn.updates_alquileres[-1][1][0]},
    )

    # 1 ítem × $10.000/jornada × 7 jornadas = 70.000 bruto.
    # Con 10% descuento → 63.000 neto.
    items = [PedidoItem(equipo_id=42, cantidad=1, precio_jornada=10000)]
    _apply_pedido_items(conn, id=1, items=items)

    # Tiene que haberse hecho un UPDATE de alquileres con monto_total Y
    # descuento_jornadas_pct (antes solo actualizaba monto_total).
    updates = conn.updates_alquileres
    assert len(updates) >= 1, "No se hizo UPDATE de alquileres"

    # Encontrar el UPDATE final del total (último UPDATE de alquileres).
    sql_final, params_final = updates[-1]
    assert "monto_total" in sql_final.lower(), (
        f"El UPDATE final no toca monto_total: {sql_final}"
    )
    assert "descuento_jornadas_pct" in sql_final.lower(), (
        "El UPDATE no persiste descuento_jornadas_pct — bug #500 vuelve si "
        "esta columna queda desactualizada. SQL: " + sql_final
    )

    # El monto_total persistido debe tener el descuento aplicado.
    monto_total_persistido = params_final[0]
    assert monto_total_persistido == 63000, (
        f"Esperaba 63.000 neto (10% off de 70.000), recibí "
        f"{monto_total_persistido}. El descuento por jornadas no se aplicó "
        f"al editar ítems (bug #500)."
    )

    # El descuento_jornadas_pct persistido debe ser 10.0.
    descuento_persistido = params_final[1]
    assert descuento_persistido == 10.0
