"""Tests puros del motor de decisión de descuentos — backend/descuentos/queries/.

- `calcular_descuento_aplicable`: migrado de `test_precios_service.py::TestDescuentoAplicable`
  (movido junto con la función, Fase A del split de `descuentos/`) — mismos casos, firma nueva
  (dict de fuentes en vez de 2 floats posicionales).
- `calcular_descuento_origen`: nuevo — antes solo se ejercía indirecto vía el JSON de
  `/api/cotizar` (`test_cotizar_endpoint.py`).
- `interpolar_descuento_jornadas`: nuevo — la mitad PURA de `obtener_descuento_jornadas`,
  aislada de la DB por primera vez.
"""
import pytest

from descuentos.queries.decision import (
    calcular_descuento_aplicable,
    calcular_descuento_origen,
    resolver_descuento_pedido,
    resolver_origen_pedido,
    resolver_descuento_monto_pedido,
    resolver_origen_pedido_monto,
)
from descuentos.queries.jornadas import interpolar_descuento_jornadas


pytestmark = pytest.mark.unit


# ── calcular_descuento_aplicable ──────────────────────────────────────────


class TestCalcularDescuentoAplicable:
    def test_cliente_mayor_que_jornadas(self):
        assert calcular_descuento_aplicable({"cliente": 15.0, "jornadas": 5.0}) == 15.0

    def test_jornadas_mayor_que_cliente(self):
        assert calcular_descuento_aplicable({"cliente": 5.0, "jornadas": 15.0}) == 15.0

    def test_empate(self):
        # En empate da lo mismo en monto. El front etiqueta "cliente" (primera key).
        assert calcular_descuento_aplicable({"cliente": 10.0, "jornadas": 10.0}) == 10.0

    def test_ambos_cero(self):
        assert calcular_descuento_aplicable({"cliente": 0, "jornadas": 0}) == 0.0

    def test_none_se_trata_como_cero(self):
        assert calcular_descuento_aplicable({"cliente": None, "jornadas": 5.0}) == 5.0
        assert calcular_descuento_aplicable({"cliente": 5.0, "jornadas": None}) == 5.0
        assert calcular_descuento_aplicable({"cliente": None, "jornadas": None}) == 0.0

    def test_negativos_se_clampan_a_cero(self):
        # Defensivo: nunca permitir descuento "que aumenta el precio".
        assert calcular_descuento_aplicable({"cliente": -10.0, "jornadas": 5.0}) == 5.0

    def test_mayores_a_100_se_topan(self):
        # Un descuento > 100% daría neto/total NEGATIVO → se topa en 100.
        assert calcular_descuento_aplicable({"cliente": 150.0, "jornadas": 5.0}) == 100.0
        assert calcular_descuento_aplicable({"cliente": 5.0, "jornadas": 200.0}) == 100.0
        assert calcular_descuento_aplicable({"cliente": 100.0, "jornadas": 0}) == 100.0

    def test_dict_vacio(self):
        assert calcular_descuento_aplicable({}) == 0.0

    def test_mas_de_2_fuentes(self):
        # La firma extensible: una tercera fuente no requiere tocar nada más.
        assert calcular_descuento_aplicable(
            {"cliente": 5.0, "jornadas": 10.0, "estacional": 20.0}
        ) == 20.0


# ── calcular_descuento_origen ─────────────────────────────────────────────


class TestCalcularDescuentoOrigen:
    def test_gana_cliente(self):
        assert calcular_descuento_origen({"cliente": 15.0, "jornadas": 5.0}) == "cliente"

    def test_gana_jornadas(self):
        assert calcular_descuento_origen({"cliente": 5.0, "jornadas": 15.0}) == "jornadas"

    def test_empate_gana_primera_fuente_declarada(self):
        assert calcular_descuento_origen({"cliente": 10.0, "jornadas": 10.0}) == "cliente"

    def test_ambos_cero_es_ninguno(self):
        assert calcular_descuento_origen({"cliente": 0, "jornadas": 0}) == "ninguno"

    def test_dict_vacio_es_ninguno(self):
        assert calcular_descuento_origen({}) == "ninguno"

    def test_negativo_no_gana_sobre_cero(self):
        # Mismo clamp que calcular_descuento_aplicable: un negativo no cuenta.
        assert calcular_descuento_origen({"cliente": -5.0, "jornadas": 0}) == "ninguno"


# ── interpolar_descuento_jornadas ─────────────────────────────────────────


class TestInterpolarDescuentoJornadas:
    PUNTOS = [(1, 0.0), (2, 3.0), (7, 10.0)]

    def test_antes_del_primer_punto(self):
        assert interpolar_descuento_jornadas(self.PUNTOS, 1) == 0.0

    def test_en_un_punto_ancla(self):
        assert interpolar_descuento_jornadas(self.PUNTOS, 2) == 3.0

    def test_interpola_entre_puntos(self):
        # 4 jornadas → entre (2,3%) y (7,10%): t=(4-2)/(7-2)=0.4 → 3 + 0.4*7 = 5.8
        assert interpolar_descuento_jornadas(self.PUNTOS, 4) == 5.8

    def test_despues_del_ultimo_punto_se_queda_en_el_tope(self):
        assert interpolar_descuento_jornadas(self.PUNTOS, 10) == 10.0

    def test_sin_puntos_devuelve_cero(self):
        assert interpolar_descuento_jornadas([], 5) == 0.0


# ── resolver_descuento_pedido / resolver_origen_pedido (jerarquía C-1) ────


class TestResolverDescuentoPedido:
    def test_manual_gana_outright_aunque_sea_menor(self):
        # 5% manual gana sobre 20% de jornadas — NO compite por tamaño.
        assert resolver_descuento_pedido(5.0, 0, 20.0) == 5.0

    def test_manual_cero_cae_al_fallback(self):
        assert resolver_descuento_pedido(0, 10.0, 20.0) == 20.0

    def test_manual_none_cae_al_fallback(self):
        assert resolver_descuento_pedido(None, 10.0, 20.0) == 20.0

    def test_sin_nada_queda_en_cero(self):
        assert resolver_descuento_pedido(0, 0, 0) == 0.0

    def test_manual_topa_en_100(self):
        assert resolver_descuento_pedido(150.0, 0, 0) == 100.0


class TestResolverOrigenPedido:
    def test_manual_gana_el_origen(self):
        assert resolver_origen_pedido(5.0, 10.0, 20.0) == "manual"

    def test_sin_manual_delega_al_2way(self):
        assert resolver_origen_pedido(0, 10.0, 20.0) == "jornadas"

    def test_sin_nada_es_ninguno(self):
        assert resolver_origen_pedido(0, 0, 0) == "ninguno"


# ── resolver_descuento_monto_pedido / resolver_origen_pedido_monto (C-2) ──


class TestResolverDescuentoMontoPedido:
    def test_tipo_pct_es_byte_identico_al_calculo_previo(self):
        # bruto=10000, manual 5% gana outright sobre jornadas 20% → 500.
        r = resolver_descuento_monto_pedido(10_000, "pct", 5.0, 0, 0, 20.0)
        assert r == {"monto": 500, "pct": 5.0}

    def test_default_tipo_none_se_trata_como_pct(self):
        r = resolver_descuento_monto_pedido(10_000, None, 0, 0, 10.0, 20.0)
        assert r == {"monto": 2000, "pct": 20.0}

    def test_tipo_monto_gana_outright_capeado_a_bruto(self):
        # Override de $50.000 sobre un bruto de $10.000 → capeado a 10.000 (neto no negativo).
        r = resolver_descuento_monto_pedido(10_000, "monto", 0, 50_000, 0, 20.0)
        assert r == {"monto": 10_000, "pct": 100.0}

    def test_tipo_monto_normal_deriva_pct_efectivo(self):
        r = resolver_descuento_monto_pedido(10_000, "monto", 0, 2_500, 10.0, 20.0)
        assert r == {"monto": 2500, "pct": 25.0}

    def test_tipo_monto_cero_cae_al_fallback_pct(self):
        # monto=0 con tipo="monto" es el mismo sentinel "sin override" que pct=0.
        r = resolver_descuento_monto_pedido(10_000, "monto", 0, 0, 10.0, 20.0)
        assert r == {"monto": 2000, "pct": 20.0}

    def test_tipo_monto_gana_sobre_manual_pct_estale(self):
        # El pct manual queda "stale" (irrelevante) cuando tipo="monto" gana.
        r = resolver_descuento_monto_pedido(10_000, "monto", 99.0, 1_000, 0, 0)
        assert r == {"monto": 1000, "pct": 10.0}

    def test_bruto_cero_no_divide_por_cero(self):
        r = resolver_descuento_monto_pedido(0, "monto", 0, 5_000, 0, 0)
        assert r == {"monto": 0, "pct": 0.0}

    def test_sin_nada_queda_en_cero(self):
        r = resolver_descuento_monto_pedido(10_000, "pct", 0, 0, 0, 0)
        assert r == {"monto": 0, "pct": 0.0}


class TestResolverOrigenPedidoMonto:
    def test_tipo_monto_gana_el_origen(self):
        assert resolver_origen_pedido_monto("monto", 0, 5_000, 10.0, 20.0) == "manual"

    def test_tipo_monto_cero_delega_al_2way(self):
        assert resolver_origen_pedido_monto("monto", 0, 0, 10.0, 20.0) == "jornadas"

    def test_tipo_pct_delega_a_resolver_origen_pedido(self):
        assert resolver_origen_pedido_monto("pct", 5.0, 0, 10.0, 20.0) == "manual"
        assert resolver_origen_pedido_monto("pct", 0, 0, 10.0, 20.0) == "jornadas"
