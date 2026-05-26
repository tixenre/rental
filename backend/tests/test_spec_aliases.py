"""Tests de Fase 2 — aliases en el registry y resolución en el lookup index.

Verifica:
- SpecDef acepta el campo `aliases`.
- Todos los SpecDef con aliases en el registry tienen listas no vacías.
- El lookup index construido por _matchear_y_persistir_specs resuelve aliases
  a la spec_key canónica (sin necesitar DB — se prueba la lógica de indexación).
- Variantes de case/normalización son cubiertas por _normalize_label.
- Casos de cola larga prioritarios: Weight→peso_g, Focal Length→distancia_focal,
  Filter Size→diametro_filtro, Color Temperature→temperatura_k, etc.
"""

import json
import pytest

pytestmark = pytest.mark.unit


# ── SpecDef acepta aliases ───────────────────────────────────────────────────


def test_specdef_acepta_aliases():
    from specs.models import SpecDef
    s = SpecDef(
        key="peso_g", label="Peso", tipo="number", unidad="g",
        aliases=["Weight", "Net Weight"],
    )
    assert s.aliases == ["Weight", "Net Weight"]


def test_specdef_aliases_default_lista_vacia():
    from specs.models import SpecDef
    s = SpecDef(key="cri", label="CRI", tipo="number")
    assert s.aliases == []


# ── Invariante: todos los specs con aliases tienen lista no vacía ────────────


def test_registry_aliases_nunca_lista_con_strings_vacios():
    from specs import REGISTRY
    for cat_name, cat_reg in REGISTRY.categorias.items():
        for spec in cat_reg.specs:
            for alias in spec.aliases:
                assert alias and alias.strip(), (
                    f"{cat_name}.{spec.key}: alias vacío en lista"
                )


# ── Lógica de indexación (sin DB) ───────────────────────────────────────────


def _build_index(specs_data: list[dict]) -> dict:
    """Simula la lógica de _index_spec de _matchear_y_persistir_specs."""
    import re

    def _normalize(s: str) -> str:
        s = s.lower().strip()
        s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
        s = re.sub(r"\s+", " ", s)
        return s

    index: dict[str, dict] = {}
    for rd in specs_data:
        index[_normalize(rd["label"])] = rd
        index[_normalize(rd["spec_key"])] = rd
        raw_aliases = rd.get("aliases") or []
        if isinstance(raw_aliases, str):
            try:
                raw_aliases = json.loads(raw_aliases)
            except Exception:
                raw_aliases = []
        for alias in (raw_aliases if isinstance(raw_aliases, list) else []):
            index[_normalize(str(alias))] = rd
    return index


def _make_spec(key: str, label: str, aliases: list[str]) -> dict:
    return {"id": 1, "spec_key": key, "label": label, "tipo": "string",
            "unidad": None, "enum_options": None, "aliases": aliases}


# ── Aliases de cola larga con B&H ────────────────────────────────────────────


def test_alias_weight_resuelve_a_peso_g():
    import re

    def _normalize(s: str) -> str:
        s = s.lower().strip(); s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s); s = re.sub(r"\s+", " ", s)
        return s

    spec = _make_spec("peso_g", "Peso", ["Weight", "Net Weight", "Weight (Body Only)"])
    index = _build_index([spec])
    assert index.get(_normalize("Weight")) is not None
    assert index[_normalize("Weight")]["spec_key"] == "peso_g"
    assert index.get(_normalize("Net Weight")) is not None
    # "Weight (Body Only)" → _normalize strips parens → "weight"
    assert index.get(_normalize("Weight (Body Only)")) is not None


def test_alias_focal_length_resuelve_a_distancia_focal():
    spec = _make_spec("distancia_focal", "Distancia focal",
                      ["Focal Length", "Focal Length Range", "Focal Range"])
    index = _build_index([spec])
    import re

    def _n(s: str) -> str:
        s = s.lower().strip(); s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s); s = re.sub(r"\s+", " ", s)
        return s

    assert index.get(_n("Focal Length")) is not None
    assert index[_n("Focal Length")]["spec_key"] == "distancia_focal"
    assert index.get(_n("Focal Range")) is not None


def test_alias_filter_size_resuelve_a_diametro_filtro():
    spec = _make_spec("diametro_filtro", "Diámetro de filtro",
                      ["Filter Size", "Filter Thread", "Filter Diameter"])
    index = _build_index([spec])
    import re

    def _n(s: str) -> str:
        s = s.lower().strip(); s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s); s = re.sub(r"\s+", " ", s)
        return s

    assert index[_n("Filter Size")]["spec_key"] == "diametro_filtro"
    assert index[_n("Filter Thread")]["spec_key"] == "diametro_filtro"


def test_alias_color_temperature_resuelve_a_temperatura_k():
    spec = _make_spec("temperatura_k", "Temperatura color",
                      ["Color Temperature", "Color Temperature Range"])
    index = _build_index([spec])
    import re

    def _n(s: str) -> str:
        s = s.lower().strip(); s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s); s = re.sub(r"\s+", " ", s)
        return s

    assert index[_n("Color Temperature")]["spec_key"] == "temperatura_k"
    assert index[_n("Color Temperature Range")]["spec_key"] == "temperatura_k"


def test_alias_power_resuelve_a_consumo_w():
    spec = _make_spec("consumo_w", "Consumo eléctrico",
                      ["Power", "Wattage", "Power Consumption", "Power Draw"])
    index = _build_index([spec])
    import re

    def _n(s: str) -> str:
        s = s.lower().strip(); s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s); s = re.sub(r"\s+", " ", s)
        return s

    assert index[_n("Power")]["spec_key"] == "consumo_w"
    assert index[_n("Wattage")]["spec_key"] == "consumo_w"
    assert index[_n("Power Consumption")]["spec_key"] == "consumo_w"


def test_alias_case_insensitive():
    spec = _make_spec("peso_g", "Peso", ["Weight", "Net Weight"])
    index = _build_index([spec])
    import re

    def _n(s: str) -> str:
        s = s.lower().strip(); s = s.replace("_", " ")
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s); s = re.sub(r"\s+", " ", s)
        return s

    assert index.get(_n("WEIGHT")) is not None
    assert index.get(_n("weight")) is not None
    assert index.get(_n("Weight")) is not None


# ── Alias en el registry real ────────────────────────────────────────────────


def test_registry_peso_g_tiene_alias_weight():
    from specs import REGISTRY
    for cat_name, cat_reg in REGISTRY.categorias.items():
        spec = cat_reg.get_spec("peso_g")
        if spec is not None:
            assert "Weight" in spec.aliases, (
                f"{cat_name}.peso_g debería tener alias 'Weight'"
            )


def test_registry_consumo_w_iluminacion_tiene_alias_power():
    from specs import REGISTRY
    cat = REGISTRY.get("Iluminación")
    assert cat is not None
    spec = cat.get_spec("consumo_w")
    assert spec is not None, "Iluminación debe tener spec 'consumo_w' (renombrado de potencia_w)"
    assert "Power" in spec.aliases
    assert "Wattage" in spec.aliases


def test_registry_iluminacion_no_tiene_potencia_w():
    """Verificar que el rename consumó_w se completó y potencia_w no existe."""
    from specs import REGISTRY
    cat = REGISTRY.get("Iluminación")
    assert cat is not None
    assert cat.get_spec("potencia_w") is None, (
        "potencia_w no debería existir — fue renombrado a consumo_w"
    )


def test_registry_iluminacion_no_tiene_power_consumption_w():
    """Verificar que el duplicado power_consumption_w en Iluminación fue eliminado."""
    from specs import REGISTRY
    cat = REGISTRY.get("Iluminación")
    assert cat is not None
    assert cat.get_spec("power_consumption_w") is None, (
        "power_consumption_w en Iluminación fue eliminado (era duplicado de consumo_w)"
    )


def test_registry_distancia_focal_tiene_alias_focal_length():
    from specs import REGISTRY
    cat = REGISTRY.get("Lentes")
    assert cat is not None
    spec = cat.get_spec("distancia_focal")
    assert spec is not None
    assert "Focal Length" in spec.aliases
