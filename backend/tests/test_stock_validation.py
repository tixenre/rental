"""Tests de validación de stock — foco en doble booking vía kits y
detección de ciclos en kits.

NO requieren BD real: usan un FakeConn que stubea las queries que
ejecutan `_check_stock` y `_crea_ciclo_kit`. Validan la LÓGICA de
agregación (suma directa + suma vía kit) y la BFS de detección de ciclos.

El bug de doble booking que motivó estos tests:

  Equipo Kit "Cinema básico" contiene 1× Cámara FX3.
  Stock FX3 = 1.
  Pedido A reserva el Kit (item.equipo_id = Kit).
  Pedido B reserva FX3 directamente (item.equipo_id = FX3).
  Ambos pasaban _check_stock antes del fix porque la query de "reservado"
  solo sumaba alquiler_items.equipo_id = FX3 (Pedido A apunta al Kit, no
  a FX3) y no inspeccionaba kit_componentes.
"""

import pytest

from routes.alquileres import _check_stock, ESTADOS_RESERVADO
from routes.equipos import _crea_ciclo_kit


pytestmark = pytest.mark.unit


# ── Fake DB ────────────────────────────────────────────────────────────────

class FakeRow(dict):
    """dict-row con __getitem__ como las rows reales del wrapper."""


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class StockFakeConn:
    """Conn que stubea las queries de _check_stock.

    Se le pasa el "estado del mundo":
      - equipos: dict[id, {nombre, cantidad}]
      - kit_componentes: dict[equipo_id, list[{componente_id, kc_cant, nombre, stock_total}]]
      - reservas_directas: dict[(equipo_id, excl_pedido_id), int]
      - reservas_via_kit:  dict[(componente_id, excl_pedido_id), int]
      - pedido_items: dict[pedido_id, list[{equipo_id, cantidad, nombre, stock_total}]]
    """

    def __init__(
        self,
        equipos,
        kit_componentes=None,
        reservas_directas=None,
        reservas_via_kit=None,
        pedido_items=None,
    ):
        self.equipos = equipos
        self.kit_componentes = kit_componentes or {}
        self.reservas_directas = reservas_directas or {}
        self.reservas_via_kit = reservas_via_kit or {}
        self.pedido_items = pedido_items or {}

    def execute(self, sql, params=()):
        s = " ".join(sql.split())  # normalizar whitespace
        s_up = s.upper()

        # Items del pedido (primera query de _check_stock).
        if s_up.startswith("SELECT PI.EQUIPO_ID, PI.CANTIDAD, E.NOMBRE, E.CANTIDAD AS STOCK_TOTAL"):
            pid = params[0]
            return FakeCursor([FakeRow(r) for r in self.pedido_items.get(pid, [])])

        # Componentes de un equipo (expansión de kits en _check_stock).
        if s_up.startswith("SELECT KC.COMPONENTE_ID, KC.CANTIDAD AS KC_CANT"):
            eq_id = params[0]
            return FakeCursor([FakeRow(r) for r in self.kit_componentes.get(eq_id, [])])

        # Lock + cantidad del equipo.
        if "SELECT CANTIDAD FROM EQUIPOS WHERE ID = ? FOR UPDATE" in s_up:
            eq = self.equipos.get(params[0])
            if not eq:
                return FakeCursor([])
            return FakeCursor([FakeRow(cantidad=eq["cantidad"])])

        # Reservas directas (suma de alquiler_items donde equipo_id == X).
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s_up:
            eq_id, excl, _fh, _fd = params
            total = self.reservas_directas.get((eq_id, excl), 0)
            return FakeCursor([FakeRow({0: total})])

        # Reservas vía kit (suma de alquiler_items que reservan un kit con
        # componente_id = X).
        if "JOIN KIT_COMPONENTES KC ON KC.EQUIPO_ID = PI2.EQUIPO_ID WHERE KC.COMPONENTE_ID = ?" in s_up:
            comp_id, excl, _fh, _fd = params
            total = self.reservas_via_kit.get((comp_id, excl), 0)
            return FakeCursor([FakeRow({0: total})])

        # Fallback: vacío.
        return FakeCursor([])

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# ── _check_stock — kits ───────────────────────────────────────────────────

class TestCheckStockKits:
    """Bug fix: doble booking vía kit + componente directo."""

    def test_kit_reserva_componente(self):
        """Pedido que reserva un kit debe consumir stock de sus componentes."""
        # Kit "Cine" (id=10) contiene 1× Cámara FX3 (id=20, stock=1)
        conn = StockFakeConn(
            equipos={
                10: {"nombre": "Kit Cine", "cantidad": 5},
                20: {"nombre": "Cámara FX3", "cantidad": 1},
            },
            kit_componentes={
                10: [{"componente_id": 20, "kc_cant": 1, "nombre": "Cámara FX3", "stock_total": 1}],
            },
            pedido_items={
                1: [{"equipo_id": 10, "cantidad": 1, "nombre": "Kit Cine", "stock_total": 5}],
            },
        )
        # Sin otras reservas, el pedido cabe.
        problemas = _check_stock(conn, 1, "2026-06-01", "2026-06-05")
        assert problemas == []

    def test_doble_booking_via_kit_y_directo(self):
        """REGRESIÓN: Pedido A reserva el Kit (que tiene FX3), Pedido B
        reserva FX3 directo. _check_stock(B) debe ver que A ya consumió
        la única FX3 vía el kit."""
        conn = StockFakeConn(
            equipos={
                10: {"nombre": "Kit Cine", "cantidad": 5},
                20: {"nombre": "Cámara FX3", "cantidad": 1},
            },
            kit_componentes={
                10: [{"componente_id": 20, "kc_cant": 1, "nombre": "Cámara FX3", "stock_total": 1}],
                # Componentes del equipo 20 (FX3) — ninguno.
            },
            # Pedido A=1 ya reservó el Kit (id=10) en las mismas fechas.
            # No hay reservas directas de FX3.
            reservas_directas={},
            # Pero sí hay reserva vía kit: 1 unidad de FX3 consumida por A.
            reservas_via_kit={(20, 2): 1},  # (componente=FX3, excl=pedido B)
            pedido_items={
                2: [{"equipo_id": 20, "cantidad": 1, "nombre": "Cámara FX3", "stock_total": 1}],
            },
        )
        problemas = _check_stock(conn, 2, "2026-06-01", "2026-06-05")
        # Stock FX3 = 1, reservado vía kit = 1, disponible = 0 < 1 → BLOQUEA
        assert len(problemas) == 1
        assert "Cámara FX3" in problemas[0]
        assert "disponible: 0" in problemas[0]

    def test_kit_consume_componente_que_otro_kit_tambien_necesita(self):
        """Dos pedidos reservan kits distintos que comparten el mismo
        componente. El stock del componente se debe sumar correctamente."""
        conn = StockFakeConn(
            equipos={
                10: {"nombre": "Kit A", "cantidad": 5},
                11: {"nombre": "Kit B", "cantidad": 5},
                20: {"nombre": "Trípode", "cantidad": 1},
            },
            kit_componentes={
                10: [{"componente_id": 20, "kc_cant": 1, "nombre": "Trípode", "stock_total": 1}],
                11: [{"componente_id": 20, "kc_cant": 1, "nombre": "Trípode", "stock_total": 1}],
            },
            # Pedido 1 (Kit A) ya reservó. _check_stock(2) calcula para Kit B.
            reservas_directas={},
            # Reserva vía kit del Trípode: 1 unidad consumida por pedido 1.
            reservas_via_kit={(20, 2): 1},
            pedido_items={
                2: [{"equipo_id": 11, "cantidad": 1, "nombre": "Kit B", "stock_total": 5}],
            },
        )
        problemas = _check_stock(conn, 2, "2026-06-01", "2026-06-05")
        assert len(problemas) == 1
        assert "Trípode" in problemas[0]

    def test_kit_con_cantidad_componente_mayor_a_1(self):
        """Kit que contiene 3× Pila AA. Pedido reserva 2 kits ⇒ exige 6 pilas."""
        conn = StockFakeConn(
            equipos={
                10: {"nombre": "Kit", "cantidad": 5},
                20: {"nombre": "Pila AA", "cantidad": 4},
            },
            kit_componentes={
                10: [{"componente_id": 20, "kc_cant": 3, "nombre": "Pila AA", "stock_total": 4}],
            },
            pedido_items={
                1: [{"equipo_id": 10, "cantidad": 2, "nombre": "Kit", "stock_total": 5}],
            },
        )
        problemas = _check_stock(conn, 1, "2026-06-01", "2026-06-05")
        # 2 kits × 3 pilas = 6, pero hay solo 4 → falla
        assert len(problemas) == 1
        assert "Pila AA" in problemas[0]
        assert "necesitás 6" in problemas[0]

    def test_directo_sin_kits_funciona_como_antes(self):
        """Caso simple — sin kits — debe seguir funcionando."""
        conn = StockFakeConn(
            equipos={20: {"nombre": "Cámara", "cantidad": 2}},
            pedido_items={
                1: [{"equipo_id": 20, "cantidad": 1, "nombre": "Cámara", "stock_total": 2}],
            },
        )
        assert _check_stock(conn, 1, "2026-06-01", "2026-06-05") == []


# ── _crea_ciclo_kit — detección de ciclos ────────────────────────────────

class CycleFakeConn:
    """Conn fake con grafo de kit_componentes en memoria."""

    def __init__(self, grafo):
        # grafo: dict[equipo_id, list[componente_id]]
        self.grafo = grafo

    def execute(self, sql, params=()):
        s_up = sql.upper()
        if "SELECT COMPONENTE_ID FROM KIT_COMPONENTES WHERE EQUIPO_ID = ?" in s_up:
            eq_id = params[0]
            return FakeCursor([
                FakeRow(componente_id=cid)
                for cid in self.grafo.get(eq_id, [])
            ])
        return FakeCursor([])


class TestCicloKit:
    def test_auto_referencia_es_ciclo(self):
        conn = CycleFakeConn({})
        assert _crea_ciclo_kit(conn, 1, 1) is True

    def test_sin_relacion_no_es_ciclo(self):
        conn = CycleFakeConn({2: []})
        assert _crea_ciclo_kit(conn, 1, 2) is False

    def test_ciclo_directo_a_b_y_b_a(self):
        # B ya contiene A. Agregar A → B crearía A → B → A.
        conn = CycleFakeConn({2: [1]})  # B(2) tiene a A(1) como componente
        assert _crea_ciclo_kit(conn, 1, 2) is True

    def test_ciclo_indirecto_largo(self):
        # D contiene C, C contiene B, B contiene A. Agregar A → D crearía
        # A → D → C → B → A.
        conn = CycleFakeConn({4: [3], 3: [2], 2: [1]})
        assert _crea_ciclo_kit(conn, 1, 4) is True

    def test_cadena_sin_volver_no_es_ciclo(self):
        # D → C → B → X (X != A). No vuelve a A.
        conn = CycleFakeConn({4: [3], 3: [2], 2: [99]})
        assert _crea_ciclo_kit(conn, 1, 4) is False

    def test_grafo_con_ciclo_existente_no_genera_loop_infinito(self):
        # B → C, C → B (ciclo preexistente entre B y C, sin involucrar a A).
        # Agregar A como hijo de B no debería loopear infinito.
        conn = CycleFakeConn({2: [3], 3: [2]})
        # No es ciclo desde A — solo el grafo B/C ya está en ciclo, pero
        # el BFS protege con `visitados` y eventualmente termina.
        assert _crea_ciclo_kit(conn, 1, 2) is False
