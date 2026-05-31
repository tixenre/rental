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


def test_es_un_solo_nivel_no_recursivo():
    """C1 es 1 nivel: al derivar un compuesto usa el `raw` de sus componentes,
    NO su valor derivado. La recursión (combo que contiene un kit) es C4."""
    raw = {1: 9999, 2: 10, 3: 1}
    out = _derivar_compuestos(raw, {1: [(2, 1, True)], 2: [(3, 5, True)]})
    assert out["2"] == 0   # el kit 2 SÍ se deriva: min(10, 1//5=0) = 0
    assert out["1"] == 10  # el combo 1 usa raw[2]=10 (NO el derivado 0) → 1 nivel. C4 daría 0.


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
    """Stub: responde la query de `componentes_de` con los kits dados.
    `kits = {equipo_id: [(componente_id, cantidad, esencial), ...]}`."""

    def __init__(self, kits):
        self.kits = kits

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM KIT_COMPONENTES WHERE EQUIPO_ID IN" in s:
            rows = [
                _FakeRow(equipo_id=eid, componente_id=cid, cantidad=q, esencial=ese)
                for eid in params
                for (cid, q, ese) in self.kits.get(eid, [])
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
