"""Tests Fase 6b-i — Cobertura de extracción de Iluminación.

Verifica los fixes de sincronización parser ↔ registry:
  1. consumo_w: aliases Power Draw / Rated Power / Power Input
  2. lumens: re-keyed a lumens_at_5600k / lumens_at_3200k
  3. lux: nuevo _parse_lux_at_1m → lux_at_1m_5600k / lux_at_1m_3200k
  4. temperatura_k: _coerce_rango no confunde separador de miles con decimal
  5. color_modes: sintetizado desde bicolor/rgb; keys huérfanas eliminadas
  6. Cobertura bidireccional: el parser no emite keys fuera del registry
"""

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _secciones_from(pairs: list[tuple[str, str]]) -> dict:
    """Helper para construir secciones mínimas para tests unitarios del parser."""
    return {"Specs": [{"label": label, "value": value} for label, value in pairs]}


# ── consumo_w: aliases sincronizados con registry ─────────────────────────────


def test_parse_potencia_power_draw():
    from iluminacion_parser import _parse_potencia

    secciones = _secciones_from([("Power Draw", "320 W")])
    assert _parse_potencia(secciones) == 320


def test_parse_potencia_rated_power():
    from iluminacion_parser import _parse_potencia

    secciones = _secciones_from([("Rated Power", "200 W")])
    assert _parse_potencia(secciones) == 200


def test_parse_potencia_power_input():
    from iluminacion_parser import _parse_potencia

    secciones = _secciones_from([("Power Input", "150W")])
    assert _parse_potencia(secciones) == 150


def test_parse_potencia_power_consumption_sigue_funcionando():
    from iluminacion_parser import _parse_potencia

    secciones = _secciones_from([("Power Consumption", "320 W  (Maximum)")])
    assert _parse_potencia(secciones) == 320


# ── lumens: re-keyed a lumens_at_5600k / lumens_at_3200k ─────────────────────


def test_parse_lumens_rekeyed_5600k():
    from iluminacion_parser import _parse_lumens

    secciones = _secciones_from([("Maximum Luminous Flux", "19,389 lm (at 5600K)")])
    result = _parse_lumens(secciones)
    assert "lumens_at_5600k" in result
    assert result["lumens_at_5600k"] == 19389
    assert "lumens_at_3200k" not in result


def test_parse_lumens_3200k():
    from iluminacion_parser import _parse_lumens

    secciones = _secciones_from([("Maximum Luminous Flux", "12,000 lm (at 3200K)")])
    result = _parse_lumens(secciones)
    assert "lumens_at_3200k" in result
    assert result["lumens_at_3200k"] == 12000
    assert "lumens_at_5600k" not in result


def test_parse_lumens_sin_anotacion_default_5600k():
    """Un valor de lúmenes sin anotación de temperatura va a 5600K (estándar)."""
    from iluminacion_parser import _parse_lumens

    secciones = _secciones_from([("Lumens", "5000")])
    result = _parse_lumens(secciones)
    assert "lumens_at_5600k" in result


def test_map_luz_specs_no_emite_key_lumens():
    """La key huérfana 'lumens' no debe aparecer en el output de map_luz_specs."""
    from iluminacion_parser import map_luz_specs

    secciones = _secciones_from([
        ("Maximum Luminous Flux", "19,389 lm (at 5600K)"),
        ("Wattage", "300 W"),
    ])
    specs = map_luz_specs(secciones)
    assert "lumens" not in specs
    assert "lumens_at_5600k" in specs


# ── lux: nuevo _parse_lux_at_1m ─────────────────────────────────────────────


def test_parse_lux_at_1m_5600k():
    from iluminacion_parser import _parse_lux_at_1m

    secciones = _secciones_from([
        ("Photometrics at 3.3' / 1 m", "5600K: 1077 fc / 11,600 Lux"),
    ])
    result = _parse_lux_at_1m(secciones)
    assert result.get("lux_at_1m_5600k") == 11600
    assert "lux_at_1m_3200k" not in result


def test_parse_lux_at_1m_3200k():
    from iluminacion_parser import _parse_lux_at_1m

    secciones = _secciones_from([
        ("Photometrics at 3.3' / 1 m", "3200K: 800 fc / 8,600 Lux"),
    ])
    result = _parse_lux_at_1m(secciones)
    assert result.get("lux_at_1m_3200k") == 8600
    assert "lux_at_1m_5600k" not in result


def test_parse_lux_multiline_bicolor():
    from iluminacion_parser import _parse_lux_at_1m

    secciones = _secciones_from([
        ("Photometrics at 3.3' / 1 m", "5600K: 1077 fc / 11,600 Lux\n3200K: 800 fc / 8,600 Lux"),
    ])
    result = _parse_lux_at_1m(secciones)
    assert result.get("lux_at_1m_5600k") == 11600
    assert result.get("lux_at_1m_3200k") == 8600


def test_parse_lux_emitido_en_map_luz_specs():
    from iluminacion_parser import map_luz_specs

    secciones = _secciones_from([
        ("Photometrics at 3.3' / 1 m", "5600K: 1077 fc / 11,600 Lux"),
        ("Power Consumption", "320 W"),
    ])
    specs = map_luz_specs(secciones)
    assert "lux_at_1m_5600k" in specs
    assert specs["lux_at_1m_5600k"] == 11600


# ── temperatura_k: separador de miles en _coerce_rango ───────────────────────


def test_coerce_rango_miles_range():
    """`2,500-7,500` (separador de miles) → [2500, 7500], no [2.5, 7.5]."""
    from services.specs.commands.coerce import _coerce_rango

    result = json.loads(_coerce_rango("2,500-7,500"))
    assert result == [2500, 7500]


def test_coerce_rango_miles_simple():
    """`2,500K` (separador de miles) → [2500], no [2.5]."""
    from services.specs.commands.coerce import _coerce_rango

    # La K la strip el coerce_rango, el resultado es [2500]
    result = json.loads(_coerce_rango("2,500K"))
    assert result == [2500]


def test_coerce_rango_decimal_coma_no_contaminada():
    """`1,5` (decimal europeo, 1 cifra tras coma) → [1.5], sin tocar."""
    from services.specs.commands.coerce import _coerce_rango

    result = json.loads(_coerce_rango("1,5"))
    assert result == [1.5]


def test_coerce_rango_temperatura_pipeline():
    """Pipeline completo: '2,500 to 7,500K' → _parse_temperatura → _coerce_rango → [2500, 7500]."""
    from iluminacion_parser import _parse_temperatura
    from services.specs.commands.coerce import _coerce_rango

    secciones = _secciones_from([("Color Temperature", "2,500 to 7,500K")])
    temperatura_str = _parse_temperatura(secciones)
    assert temperatura_str is not None, "_parse_temperatura no debe retornar None"
    result = json.loads(_coerce_rango(temperatura_str))
    assert result == [2500, 7500], f"Esperado [2500, 7500], obtenido {result}"


def test_coerce_number_miles():
    """`11,600` → 11600, no 11.6."""
    from services.specs.commands.coerce import _coerce_number

    assert _coerce_number("11,600 Lux") == "11600"


# ── color_modes: síntesis desde bicolor/rgb, sin keys huérfanas ──────────────


def test_color_modes_daylight():
    from iluminacion_parser import map_luz_specs

    secciones = _secciones_from([
        ("Color Temperature", "5600 K"),
        ("Wattage", "200 W"),
    ])
    specs = map_luz_specs(secciones)
    assert "bicolor" not in specs, "bicolor es key huérfana, no debe aparecer"
    assert "rgb" not in specs, "rgb es key huérfana, no debe aparecer"
    assert specs.get("color_modes") == ["Daylight"]


def test_color_modes_tungsten():
    from iluminacion_parser import map_luz_specs

    secciones = _secciones_from([
        ("Color Modes", "Tungsten"),
        ("Wattage", "200 W"),
    ])
    specs = map_luz_specs(secciones)
    assert "bicolor" not in specs
    assert "rgb" not in specs
    assert "Tungsten" in (specs.get("color_modes") or [])


def test_color_modes_bicolor_desde_rango():
    from iluminacion_parser import map_luz_specs

    secciones = _secciones_from([
        ("Color Temperature", "2500 to 7500K"),
        ("Wattage", "300 W"),
    ])
    specs = map_luz_specs(secciones)
    assert "bicolor" not in specs
    assert "rgb" not in specs
    assert "Bicolor" in (specs.get("color_modes") or [])


def test_color_modes_rgb():
    from iluminacion_parser import map_luz_specs

    secciones = _secciones_from([
        ("Color Modes", "RGBWW"),
        ("Wattage", "300 W"),
    ])
    specs = map_luz_specs(secciones)
    assert "bicolor" not in specs
    assert "rgb" not in specs
    assert "RGB" in (specs.get("color_modes") or [])


# ── Cobertura bidireccional — no orphan keys, fixture real ───────────────────


def _registry_iluminacion_keys() -> set[str]:
    from services.specs import REGISTRY

    cat = REGISTRY.get("Iluminación")
    assert cat is not None, "Categoría 'Iluminación' no encontrada en REGISTRY"
    return {s.key for s in cat.specs}


def test_no_orphan_keys_luz_minimal():
    """El parser no emite keys fuera del registry (fixture luz_minimal)."""
    from iluminacion_parser import BHSpecsParser, map_luz_specs

    html = _load_fixture("luz_minimal.html")
    parser = BHSpecsParser()
    parser.feed(html)
    specs = map_luz_specs(dict(parser.secciones))

    registry_keys = _registry_iluminacion_keys()
    orphans = {k for k in specs if k not in registry_keys}
    assert not orphans, (
        f"Parser emitió keys fuera del registry: {orphans}"
    )


def test_no_orphan_keys_vl300():
    """El parser no emite keys fuera del registry (fixture VL300 con lux)."""
    from iluminacion_parser import BHSpecsParser, map_luz_specs

    html = _load_fixture("luz_vl300_minimal.html")
    parser = BHSpecsParser()
    parser.feed(html)
    specs = map_luz_specs(dict(parser.secciones))

    registry_keys = _registry_iluminacion_keys()
    orphans = {k for k in specs if k not in registry_keys}
    assert not orphans, (
        f"Parser (VL300) emitió keys fuera del registry: {orphans}"
    )


def test_no_orphan_keys_bicolor():
    """El parser no emite keys fuera del registry (fixture bicolor con Power Draw)."""
    from iluminacion_parser import BHSpecsParser, map_luz_specs

    html = _load_fixture("luz_bicolor_minimal.html")
    parser = BHSpecsParser()
    parser.feed(html)
    specs = map_luz_specs(dict(parser.secciones))

    registry_keys = _registry_iluminacion_keys()
    orphans = {k for k in specs if k not in registry_keys}
    assert not orphans, (
        f"Parser (bicolor) emitió keys fuera del registry: {orphans}"
    )


def test_vl300_fixture_extrae_lux_y_consumo():
    """Fixture VL300 tiene lux_at_1m_5600k=11600 y consumo_w=320."""
    from iluminacion_parser import BHSpecsParser, map_luz_specs

    html = _load_fixture("luz_vl300_minimal.html")
    parser = BHSpecsParser()
    parser.feed(html)
    specs = map_luz_specs(dict(parser.secciones))

    assert specs.get("lux_at_1m_5600k") == 11600, (
        f"lux_at_1m_5600k esperado 11600, obtenido {specs.get('lux_at_1m_5600k')}"
    )
    assert specs.get("consumo_w") == 320


def test_bicolor_fixture_extrae_consumo_y_lumens():
    """Fixture bicolor tiene consumo_w=340 (via 'Power Draw') y lumens_at_5600k=19389."""
    from iluminacion_parser import BHSpecsParser, map_luz_specs

    html = _load_fixture("luz_bicolor_minimal.html")
    parser = BHSpecsParser()
    parser.feed(html)
    specs = map_luz_specs(dict(parser.secciones))

    assert specs.get("consumo_w") == 340, (
        f"consumo_w esperado 340 (via 'Power Draw'), obtenido {specs.get('consumo_w')}"
    )
    assert specs.get("lumens_at_5600k") == 19389, (
        f"lumens_at_5600k esperado 19389, obtenido {specs.get('lumens_at_5600k')}"
    )
