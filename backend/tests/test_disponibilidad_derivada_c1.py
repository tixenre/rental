"""C1 + C2 #635 — disponibilidad derivada de componentes (camino de LECTURA).

C1: deriva un equipo compuesto de sus componentes — `min(stock_propio,
⌊raw[comp]/qty⌋)`. C2: solo los componentes ESENCIALES constriñen; los best-effort
(`esencial=False`) NO bajan la disponibilidad ni bloquean días. El motor es
tipo-agnóstico y espeja la expansión del gate. Recursión = C4.

`comps_by[eid] = [(componente_id, cantidad, esencial), ...]`.
"""
import pytest

from reservas import expandir_demanda
from reservas.disponibilidad import _derivar_compuestos

pytestmark = pytest.mark.unit


# ── _derivar_compuestos — derivación pura (C1) ───────────────────────────────
def test_hoja_sin_componentes_no_cambia():
    raw = {1: 5, 2: 0, 3: 7}
    assert _derivar_compuestos(raw, {}) == {"1": 5, "2": 0, "3": 7}


def test_kit_limitado_por_stock_propio():
    # kit 10: propio 2; componente 4 libre 10, usa 2/u → min(2, 10//2=5) = 2
    assert _derivar_compuestos({10: 2, 4: 10}, {10: [(4, 2, True)]})["10"] == 2


def test_kit_limitado_por_componente():
    # kit 10: propio 5; componente 4 libre 2, usa 2/u → min(5, 2//2=1) = 1
    assert _derivar_compuestos({10: 5, 4: 2}, {10: [(4, 2, True)]})["10"] == 1


def test_componente_agotado_da_cero():
    assert _derivar_compuestos({10: 5, 4: 0}, {10: [(4, 2, True)]})["10"] == 0


def test_combo_sentinel_gobernado_por_componentes():
    # combo 20: cantidad propia sentinel alta; componentes 3 (libre 6, q2) y 4 (libre 5, q1)
    # → min(9999, 6//2=3, 5//1=5) = 3.
    assert _derivar_compuestos({20: 9999, 3: 6, 4: 5}, {20: [(3, 2, True), (4, 1, True)]})["20"] == 3


def test_qty_cero_se_ignora():
    assert _derivar_compuestos({10: 5, 4: 3}, {10: [(4, 0, True)]})["10"] == 5


def test_componente_inexistente_da_cero():
    assert _derivar_compuestos({10: 5}, {10: [(99, 2, True)]})["10"] == 0


def test_recursivo_usa_el_derivado_del_componente():
    """C4: al derivar un compuesto usa el valor DERIVADO de sus componentes
    (bottom-up), NO su `raw`. Un combo que contiene un kit hereda la
    indisponibilidad real del kit, bajando hasta las hojas."""
    raw = {1: 9999, 2: 10, 3: 1}
    out = _derivar_compuestos(raw, {1: [(2, 1, True)], 2: [(3, 5, True)]})
    assert out["2"] == 0   # kit 2: min(10, 1//5=0) = 0
    assert out["1"] == 0   # combo 1 usa el DERIVADO de 2 (=0), no su raw (=10) → 0


def test_recursivo_multiplica_cantidades_por_nivel():
    """La demanda baja multiplicando las cantidades de cada arista: combo 1 lleva
    2× kit 2, y el kit 2 lleva 3× hoja 3 → cada combo necesita 6 hojas."""
    raw = {1: 9999, 2: 9999, 3: 12}
    out = _derivar_compuestos(raw, {1: [(2, 2, True)], 2: [(3, 3, True)]})
    assert out["2"] == 4   # kit 2: min(9999, 12//3=4) = 4
    assert out["1"] == 2   # combo 1: min(9999, derivado[2]=4 // 2 = 2) = 2


# ── C2 — best-effort NO constriñe ────────────────────────────────────────────
def test_best_effort_no_baja_la_disponibilidad():
    # combo 20: componente 3 ESENCIAL (libre 6, q2 → 3); componente 4 BEST-EFFORT
    # (libre 1, q5 → daría 0 pero NO cuenta) → derivado = min(9999, 3) = 3, no 0.
    out = _derivar_compuestos({20: 9999, 3: 6, 4: 1}, {20: [(3, 2, True), (4, 5, False)]})
    assert out["20"] == 3


def test_solo_best_effort_no_constrine():
    # combo con UN componente best-effort agotado → sin restricción esencial →
    # derivado = raw propio (sentinel). El faltante se refleja como "parcial" (A2).
    out = _derivar_compuestos({20: 9999, 4: 0}, {20: [(4, 1, False)]})
    assert out["20"] == 9999


def test_esencial_si_constrine_aunque_haya_best_effort():
    # esencial escaso manda aunque el best-effort esté libre.
    out = _derivar_compuestos(
        {20: 9999, 3: 2, 4: 100}, {20: [(3, 1, True), (4, 1, False)]}
    )
    assert out["20"] == 2


# ── expandir_demanda — solo esenciales aportan demanda ───────────────────────
class _FakeRow(dict):
    pass


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Stub: responde la query de `componentes_de` (grafo completo) con los kits
    dados. `kits = {equipo_id: [(componente_id, cantidad, esencial), ...]}`.

    C4: `expandir_demanda` ahora trae TODO el grafo de una (`componentes_de(conn)`
    sin filtro) y recursa en memoria — la query no lleva `WHERE equipo_id IN`."""

    def __init__(self, kits):
        self.kits = kits

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if s.startswith("SELECT EQUIPO_ID, COMPONENTE_ID, CANTIDAD") and "FROM KIT_COMPONENTES" in s:
            rows = [
                _FakeRow(equipo_id=eid, componente_id=cid, cantidad=q, esencial=ese)
                for eid, comps in self.kits.items()
                for (cid, q, ese) in comps
            ]
            return _FakeCursor(rows)
        return _FakeCursor([])


def test_expandir_demanda_kit():
    conn = _FakeConn({10: [(4, 2, True), (3, 1, True)]})
    assert expandir_demanda(conn, {10: 1}) == {10: 1, 4: 2, 3: 1}


def test_expandir_demanda_multiplica_por_qty_del_item():
    conn = _FakeConn({10: [(4, 2, True)]})
    assert expandir_demanda(conn, {10: 3}) == {10: 3, 4: 6}


def test_expandir_demanda_consolida_componente_y_suelto():
    conn = _FakeConn({10: [(4, 2, True)]})
    assert expandir_demanda(conn, {10: 1, 4: 3}) == {10: 1, 4: 5}


def test_expandir_demanda_hoja_sola():
    conn = _FakeConn({})
    assert expandir_demanda(conn, {5: 2}) == {5: 2}


def test_expandir_demanda_excluye_best_effort():
    # componente 4 esencial (cuenta), componente 9 best-effort (NO bloquea días)
    conn = _FakeConn({10: [(4, 2, True), (9, 3, False)]})
    assert expandir_demanda(conn, {10: 1}) == {10: 1, 4: 2}


# ── expandir_demanda — recursión hasta las hojas (C4) ────────────────────────
def test_expandir_demanda_recursivo_anidado():
    # combo 100 → kit 10 (q1) → hoja 4 (q2): la demanda baja hasta la hoja.
    conn = _FakeConn({100: [(10, 1, True)], 10: [(4, 2, True)]})
    assert expandir_demanda(conn, {100: 1}) == {100: 1, 10: 1, 4: 2}


def test_expandir_demanda_recursivo_multiplica_por_nivel():
    # combo 100 lleva 2× kit 10, el kit 10 lleva 3× hoja 4 → 2 combos = 12 hojas.
    conn = _FakeConn({100: [(10, 2, True)], 10: [(4, 3, True)]})
    assert expandir_demanda(conn, {100: 2}) == {100: 2, 10: 4, 4: 12}


def test_expandir_demanda_best_effort_corta_toda_la_subrama():
    """Decisión C4: una arista best-effort corta el descenso → toda su subrama
    queda fuera de la demanda dura (AND a lo largo del camino). Con
    `solo_esenciales=False` (gate) se cuenta todo."""
    conn = _FakeConn({100: [(10, 1, False)], 10: [(4, 2, True)]})
    assert expandir_demanda(conn, {100: 1}) == {100: 1}  # subrama best-effort fuera
    assert expandir_demanda(conn, {100: 1}, solo_esenciales=False) == {100: 1, 10: 1, 4: 2}
