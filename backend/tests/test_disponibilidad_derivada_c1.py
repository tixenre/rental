"""C1 #635 — disponibilidad derivada de componentes (camino de LECTURA).

Tests de corrección de la derivación pura (`_derivar_compuestos`) y de la
expansión de demanda (`expandir_demanda`, que espeja la del gate). El motor es
tipo-agnóstico: deriva cualquier equipo con componentes (kit o combo) igual que
el gate (propio + componentes, 1 nivel, todos los componentes). Best-effort = C2;
recursión = C4.
"""
import pytest

from reservas import expandir_demanda
from reservas.disponibilidad import _derivar_compuestos

pytestmark = pytest.mark.unit


# ── _derivar_compuestos — derivación pura ────────────────────────────────────
def test_hoja_sin_componentes_no_cambia():
    """Equipos sin componentes (hojas) quedan igual que su raw — diferencial."""
    raw = {1: 5, 2: 0, 3: 7}
    assert _derivar_compuestos(raw, {}) == {"1": 5, "2": 0, "3": 7}


def test_kit_limitado_por_stock_propio():
    # kit 10: propio 2; componente 4 libre 10, usa 2/u → min(2, 10//2=5) = 2
    assert _derivar_compuestos({10: 2, 4: 10}, {10: [(4, 2)]})["10"] == 2


def test_kit_limitado_por_componente():
    # kit 10: propio 5; componente 4 libre 2, usa 2/u → min(5, 2//2=1) = 1
    assert _derivar_compuestos({10: 5, 4: 2}, {10: [(4, 2)]})["10"] == 1


def test_componente_agotado_da_cero():
    assert _derivar_compuestos({10: 5, 4: 0}, {10: [(4, 2)]})["10"] == 0


def test_combo_sentinel_gobernado_por_componentes():
    # combo 20: cantidad propia sentinel alta; componentes 3 (libre 6, q2) y 4 (libre 5, q1)
    # → min(9999, 6//2=3, 5//1=5) = 3. El sentinel no constriñe → lo gobiernan los componentes.
    assert _derivar_compuestos({20: 9999, 3: 6, 4: 5}, {20: [(3, 2), (4, 1)]})["20"] == 3


def test_qty_cero_se_ignora():
    # componente con qty 0 no constriñe (guarda contra división por cero)
    assert _derivar_compuestos({10: 5, 4: 3}, {10: [(4, 0)]})["10"] == 5


def test_componente_inexistente_da_cero():
    # componente que no está en raw (equipo faltante) → 0 disponible
    assert _derivar_compuestos({10: 5}, {10: [(99, 2)]})["10"] == 0


def test_es_un_solo_nivel_no_recursivo():
    """C1 es 1 nivel: al derivar un compuesto usa el `raw` de sus componentes,
    NO su valor derivado. La recursión (combo que contiene un kit) es C4."""
    # 1 (combo) → componente 2; 2 (kit) → componente 3 (escaso, libre 1, q5).
    raw = {1: 9999, 2: 10, 3: 1}
    out = _derivar_compuestos(raw, {1: [(2, 1)], 2: [(3, 5)]})
    assert out["2"] == 0   # el kit 2 SÍ se deriva: min(10, 1//5=0) = 0
    assert out["1"] == 10  # el combo 1 usa raw[2]=10 (NO el derivado 0) → 1 nivel. C4 daría 0.


# ── expandir_demanda — espeja la expansión del gate ──────────────────────────
class _FakeRow(dict):
    pass


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Stub mínimo: responde la query de `componentes_de` (kit_componentes WHERE
    equipo_id IN ...) con los kits dados."""

    def __init__(self, kits):
        self.kits = kits  # {equipo_id: [(componente_id, cantidad), ...]}

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM KIT_COMPONENTES WHERE EQUIPO_ID IN" in s:
            rows = [
                _FakeRow(equipo_id=eid, componente_id=cid, cantidad=q)
                for eid in params
                for (cid, q) in self.kits.get(eid, [])
            ]
            return _FakeCursor(rows)
        return _FakeCursor([])


def test_expandir_demanda_kit():
    # item 10 (kit: 2x comp 4, 1x comp 3) → demanda propia + componentes
    conn = _FakeConn({10: [(4, 2), (3, 1)]})
    assert expandir_demanda(conn, {10: 1}) == {10: 1, 4: 2, 3: 1}


def test_expandir_demanda_multiplica_por_qty_del_item():
    conn = _FakeConn({10: [(4, 2)]})
    assert expandir_demanda(conn, {10: 3}) == {10: 3, 4: 6}


def test_expandir_demanda_consolida_componente_y_suelto():
    # item 10 (kit con comp 4 x2) + item 4 suelto x3 → demanda[4] = 3 + 1*2 = 5
    conn = _FakeConn({10: [(4, 2)]})
    assert expandir_demanda(conn, {10: 1, 4: 3}) == {10: 1, 4: 5}


def test_expandir_demanda_hoja_sola():
    conn = _FakeConn({})
    assert expandir_demanda(conn, {5: 2}) == {5: 2}
