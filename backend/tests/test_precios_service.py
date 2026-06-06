"""Tests del servicio canónico de precios — services/precios.py.

Fuente de verdad de los totales del pedido. Estos tests aseguran:
- La fórmula de jornadas no trunca (#502).
- Los descuentos se aplican como max(cliente, jornadas) — no acumulativos.
- En empate gana cliente (alineado con front cart-total.ts).
- IVA solo para Responsable Inscripto.
- `neto` se persiste en `alquileres.monto_total`; el IVA es derivado.
"""

from datetime import datetime

import pytest

from services.precios import (
    IVA_PCT,
    PERFIL_RI,
    calcular_total,
    descuento_aplicable,
    es_responsable_inscripto,
    jornadas_periodo,
)


pytestmark = pytest.mark.unit


# ── jornadas_periodo ─────────────────────────────────────────────────────


class TestJornadasPeriodo:
    def test_un_dia_exacto(self):
        d0 = datetime(2026, 6, 1, 10, 0)
        d1 = datetime(2026, 6, 2, 10, 0)
        assert jornadas_periodo(d0, d1) == 1

    def test_un_dia_y_medio_redondea_arriba(self):
        # 36 horas → 2 jornadas (ceil)
        d0 = datetime(2026, 6, 1, 10, 0)
        d1 = datetime(2026, 6, 2, 22, 0)
        assert jornadas_periodo(d0, d1) == 2

    def test_dos_dias_exactos(self):
        d0 = datetime(2026, 6, 1, 10, 0)
        d1 = datetime(2026, 6, 3, 10, 0)
        assert jornadas_periodo(d0, d1) == 2

    def test_retiro_10am_devolucion_14pm_dia_siguiente_es_2_jornadas(self):
        # Regresión #502: el cálculo viejo (.days) daba 1; el correcto (ceil/24h) da 2.
        d0 = datetime(2026, 6, 1, 10, 0)
        d1 = datetime(2026, 6, 2, 14, 0)  # 28 horas
        assert jornadas_periodo(d0, d1) == 2

    def test_fechas_nulas_devuelven_uno(self):
        assert jornadas_periodo(None, None) == 1
        assert jornadas_periodo(datetime(2026, 6, 1), None) == 1
        assert jornadas_periodo(None, datetime(2026, 6, 2)) == 1

    def test_fechas_invertidas_devuelven_uno(self):
        d0 = datetime(2026, 6, 2)
        d1 = datetime(2026, 6, 1)
        assert jornadas_periodo(d0, d1) == 1

    def test_misma_fecha_devuelve_uno(self):
        d = datetime(2026, 6, 1, 10, 0)
        assert jornadas_periodo(d, d) == 1


# ── descuento_aplicable ──────────────────────────────────────────────────


class TestDescuentoAplicable:
    def test_cliente_mayor_que_jornadas(self):
        assert descuento_aplicable(15.0, 5.0) == 15.0

    def test_jornadas_mayor_que_cliente(self):
        assert descuento_aplicable(5.0, 15.0) == 15.0

    def test_empate(self):
        # En empate da lo mismo en monto. El front etiqueta "cliente".
        assert descuento_aplicable(10.0, 10.0) == 10.0

    def test_ambos_cero(self):
        assert descuento_aplicable(0, 0) == 0.0

    def test_none_se_trata_como_cero(self):
        assert descuento_aplicable(None, 5.0) == 5.0
        assert descuento_aplicable(5.0, None) == 5.0
        assert descuento_aplicable(None, None) == 0.0

    def test_negativos_se_clampan_a_cero(self):
        # Defensivo: nunca permitir descuento "que aumenta el precio".
        assert descuento_aplicable(-10.0, 5.0) == 5.0


# ── es_responsable_inscripto ─────────────────────────────────────────────


class TestEsResponsableInscripto:
    def test_ri(self):
        assert es_responsable_inscripto("responsable_inscripto") is True

    def test_consumidor_final(self):
        assert es_responsable_inscripto("consumidor_final") is False

    def test_monotributo_no_es_ri(self):
        # Monotributo no factura IVA discriminado en este negocio.
        assert es_responsable_inscripto("monotributo") is False

    def test_none_no_es_ri(self):
        assert es_responsable_inscripto(None) is False

    def test_vacio_no_es_ri(self):
        assert es_responsable_inscripto("") is False


# ── calcular_total ───────────────────────────────────────────────────────


class TestCalcularTotal:
    def test_pedido_simple_sin_descuento_sin_iva(self):
        # 2 items × 1000/jornada × 3 jornadas = 6000
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 2, "precio_jornada": 1000}],
            jornadas=3,
        )
        assert r["bruto"] == 6000
        assert r["descuento_pct"] == 0
        assert r["descuento_monto"] == 0
        assert r["neto"] == 6000
        assert r["con_iva"] is False
        assert r["iva_monto"] == 0
        assert r["total_final"] == 6000

    def test_pedido_con_descuento_cliente(self):
        # 10000 - 10% = 9000
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=1,
            descuento_cliente_pct=10.0,
        )
        assert r["bruto"] == 10000
        assert r["descuento_pct"] == 10.0
        assert r["descuento_monto"] == 1000
        assert r["neto"] == 9000

    def test_descuento_jornadas_gana_si_es_mayor(self):
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=7,
            descuento_cliente_pct=5.0,
            descuento_jornadas_pct=15.0,
        )
        # bruto = 10000 * 7 = 70000; 15% off = 59500
        assert r["descuento_pct"] == 15.0
        assert r["neto"] == 59500

    def test_descuento_cliente_gana_si_es_mayor(self):
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=2,
            descuento_cliente_pct=20.0,
            descuento_jornadas_pct=5.0,
        )
        # bruto = 20000; 20% off = 16000
        assert r["descuento_pct"] == 20.0
        assert r["neto"] == 16000

    def test_descuento_empate_no_se_acumula(self):
        # Si fueran acumulativos sería 20%, pero el modelo dice max → 10%.
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=1,
            descuento_cliente_pct=10.0,
            descuento_jornadas_pct=10.0,
        )
        assert r["descuento_pct"] == 10.0
        assert r["neto"] == 9000

    def test_responsable_inscripto_suma_iva(self):
        # 10000 neto + 21% IVA = 12100
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=1,
            perfil_impuestos=PERFIL_RI,
        )
        assert r["con_iva"] is True
        assert r["iva_pct"] == IVA_PCT
        assert r["iva_monto"] == 2100
        assert r["neto"] == 10000
        assert r["total_final"] == 12100

    def test_consumidor_final_no_suma_iva(self):
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=1,
            perfil_impuestos="consumidor_final",
        )
        assert r["con_iva"] is False
        assert r["iva_monto"] == 0
        assert r["total_final"] == 10000

    def test_ri_con_descuento_iva_sobre_neto(self):
        # Regresión del lado #502: el IVA debe calcularse SOBRE el neto
        # (con descuento aplicado), no sobre el bruto.
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 10000}],
            jornadas=1,
            descuento_cliente_pct=10.0,
            perfil_impuestos=PERFIL_RI,
        )
        # bruto 10000, neto 9000, IVA = round(9000 * 0.21) = 1890
        assert r["neto"] == 9000
        assert r["iva_monto"] == 1890
        assert r["total_final"] == 10890

    def test_items_vacios(self):
        r = calcular_total(items=[], jornadas=3, perfil_impuestos=PERFIL_RI)
        assert r["bruto"] == 0
        assert r["neto"] == 0
        assert r["iva_monto"] == 0
        assert r["total_final"] == 0

    def test_jornadas_cero_se_clampa_a_uno(self):
        # Defensivo: si llega 0 (no debería), tratamos como 1.
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 1000}],
            jornadas=0,
        )
        assert r["bruto"] == 1000

    def test_redondeo_es_consistente(self):
        # Caso real de test_pricing: 231300 con 15% → 196605 (no 196604.5)
        r = calcular_total(
            items=[{"equipo_id": 1, "cantidad": 1, "precio_jornada": 231300}],
            jornadas=1,
            descuento_cliente_pct=15.0,
        )
        assert r["neto"] == 196605
