"""Catálogo: descuento visible ANTES del carrito (jornadas universal, o el del
cliente si es mayor — NO acumulables, `descuentos/`).

`_resolver_descuento_catalogo` es el costo fijo (2 queries, GLOBAL — igual que
`_attach_disponibilidad`); `_aplicar_descuento_a_equipos` es la parte PURA que
decide qué le llega a cada equipo (combos quedan afuera a propósito, Fase C-3
#1219). El caso Postgres real end-to-end vive en
`test_catalogo_descuento_db.py`.
"""
import pytest

from services.catalogo.proyeccion import (
    _aplicar_descuento_a_equipos,
    _resolver_descuento_catalogo,
)

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


class DescuentoFakeConn:
    """Stubea `obtener_descuento_jornadas` (SELECT descuentos_jornada) y
    `obtener_descuento_cliente` (SELECT clientes)."""

    def __init__(self, puntos_jornadas=(), descuento_cliente=None):
        self.puntos_jornadas = puntos_jornadas
        self.descuento_cliente = descuento_cliente

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if s.startswith("SELECT JORNADAS, PCT FROM DESCUENTOS_JORNADA"):
            return FakeCursor([FakeRow(jornadas=j, pct=p) for j, p in self.puntos_jornadas])
        if s.startswith("SELECT DESCUENTO FROM CLIENTES"):
            if self.descuento_cliente is None:
                return FakeCursor([])
            return FakeCursor([FakeRow(descuento=self.descuento_cliente)])
        return FakeCursor([])


class TestResolverDescuentoCatalogo:
    def test_solo_jornadas_sin_cliente(self):
        conn = DescuentoFakeConn(puntos_jornadas=[(1, 0), (7, 10)])
        pct, origen = _resolver_descuento_catalogo(conn, jornadas=7, cliente_id=None)
        assert pct == 10.0
        assert origen == "jornadas"

    def test_cliente_gana_si_es_mayor(self):
        conn = DescuentoFakeConn(puntos_jornadas=[(1, 0), (7, 10)], descuento_cliente=25)
        pct, origen = _resolver_descuento_catalogo(conn, jornadas=7, cliente_id=42)
        assert pct == 25.0
        assert origen == "cliente"

    def test_jornadas_gana_si_es_mayor_pese_a_haber_cliente(self):
        conn = DescuentoFakeConn(puntos_jornadas=[(1, 0), (7, 30)], descuento_cliente=5)
        pct, origen = _resolver_descuento_catalogo(conn, jornadas=7, cliente_id=42)
        assert pct == 30.0
        assert origen == "jornadas"

    def test_sin_cliente_id_no_consulta_descuento_de_nadie(self):
        conn = DescuentoFakeConn(puntos_jornadas=[(1, 0)], descuento_cliente=99)
        pct, origen = _resolver_descuento_catalogo(conn, jornadas=1, cliente_id=None)
        assert pct == 0.0
        assert origen is None

    def test_sin_descuento_alguno_origen_es_none(self):
        conn = DescuentoFakeConn(puntos_jornadas=[(1, 0)])
        pct, origen = _resolver_descuento_catalogo(conn, jornadas=1, cliente_id=None)
        assert pct == 0.0
        assert origen is None


class TestAplicarDescuentoAEquipos:
    def test_reparte_el_pct_ganador_a_equipos_simples(self):
        equipos = [{"id": 1, "tipo": "simple", "precio_jornada": 10000}]
        out = _aplicar_descuento_a_equipos(equipos, pct=20.0, origen="jornadas")
        assert out[0]["descuento_pct"] == 20.0
        assert out[0]["descuento_origen"] == "jornadas"
        assert out[0]["precio_jornada_final"] == 8000

    def test_combo_queda_afuera_del_descuento_global(self):
        # Fase C-3 (#1219): un combo no acumula el descuento global — su precio
        # ya viene rebajado por su propio descuento de componente.
        equipos = [{"id": 2, "tipo": "combo", "precio_jornada": 9500}]
        out = _aplicar_descuento_a_equipos(equipos, pct=20.0, origen="jornadas")
        assert out[0]["descuento_pct"] == 0.0
        assert out[0]["descuento_origen"] is None
        assert out[0]["precio_jornada_final"] == 9500  # intacto

    def test_pct_cero_no_marca_descuento_en_ningun_equipo(self):
        equipos = [{"id": 1, "tipo": "simple", "precio_jornada": 10000}]
        out = _aplicar_descuento_a_equipos(equipos, pct=0.0, origen=None)
        assert out[0]["descuento_pct"] == 0.0
        assert out[0]["precio_jornada_final"] == 10000

    def test_redondea_el_precio_final(self):
        equipos = [{"id": 1, "tipo": "simple", "precio_jornada": 10001}]
        out = _aplicar_descuento_a_equipos(equipos, pct=15.0, origen="cliente")
        # 10001 * 0.85 = 8500.85 → 8501
        assert out[0]["precio_jornada_final"] == 8501

    def test_mix_de_simples_y_combos_en_la_misma_lista(self):
        equipos = [
            {"id": 1, "tipo": "simple", "precio_jornada": 10000},
            {"id": 2, "tipo": "combo", "precio_jornada": 9500},
            {"id": 3, "tipo": "kit", "precio_jornada": 5000},
        ]
        out = _aplicar_descuento_a_equipos(equipos, pct=10.0, origen="jornadas")
        assert out[0]["precio_jornada_final"] == 9000
        assert out[1]["precio_jornada_final"] == 9500  # combo intacto
        assert out[2]["precio_jornada_final"] == 4500
