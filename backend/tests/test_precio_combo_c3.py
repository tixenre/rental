"""C3 #635 — precio del combo derivado de sus componentes (dinámico).

El precio de un combo = Σ(precio_componente × cantidad × (1 − descuento_línea/100)),
en vivo (sigue el precio actual de los componentes). Kits y simples usan su precio
propio. Tests de la fórmula pura `_precio_combo_calc`.
"""
import pytest

from services.precios import _precio_combo_calc

pytestmark = pytest.mark.unit


def test_suma_con_descuento_por_linea():
    # comp A: 1000 ×2 desc 10% → 1800 ; comp B: 500 ×1 desc 70% → 150 → 1950
    comps = [
        {"precio_jornada": 1000, "cantidad": 2, "descuento_pct": 10},
        {"precio_jornada": 500, "cantidad": 1, "descuento_pct": 70},
    ]
    assert _precio_combo_calc(comps) == 1950


def test_sin_descuento_suma_full():
    assert _precio_combo_calc([{"precio_jornada": 1000, "cantidad": 2, "descuento_pct": 0}]) == 2000


def test_descuento_100_componente_gratis():
    comps = [
        {"precio_jornada": 1000, "cantidad": 1, "descuento_pct": 100},
        {"precio_jornada": 500, "cantidad": 1, "descuento_pct": 0},
    ]
    assert _precio_combo_calc(comps) == 500


def test_sin_componentes_da_cero():
    assert _precio_combo_calc([]) == 0


def test_redondea():
    # 333 ×1 desc 33% → 333 × 0.67 = 223.11 → 223
    assert _precio_combo_calc([{"precio_jornada": 333, "cantidad": 1, "descuento_pct": 33}]) == 223


def test_campos_nulos_tolerados():
    # precio/cantidad/descuento None → tratados como 0
    comps = [
        {"precio_jornada": None, "cantidad": 2, "descuento_pct": 0},
        {"precio_jornada": 800, "cantidad": None, "descuento_pct": None},
        {"precio_jornada": 600, "cantidad": 1, "descuento_pct": None},
    ]
    assert _precio_combo_calc(comps) == 600
