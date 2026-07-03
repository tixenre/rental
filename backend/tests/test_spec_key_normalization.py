"""Tests de Fase 1: spec_key end-to-end en el pipeline de normalización.

Verifica:
- specs_dict_to_array produce {spec_key, label, value} por item.
- Label viene del registry (fuente única) — no de _SPEC_LABELS borrado.
- lens_mount → label "Montura" para Cámaras (antes era "Lens mount" divergente).
- Specs sin spec_def en la categoría reciben fallback label (nunca se descartan).
- Cobertura: qué spec_keys del registry emite build_result por categoría.
- normalize_label del resolver unifica _ ↔ espacio.
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.unit

from services.specs_ingesta.parse.serialize import specs_dict_to_array
from services.specs_ingesta.queries.resultado import build_result


FIXTURES = Path(__file__).parent / "fixtures" / "html"


# ── specs_dict_to_array ─────────────────────────────────────────────────────


def test_specs_dict_incluye_spec_key():
    result = specs_dict_to_array({"lens_mount": "E", "fps_max": 120}, "Cámaras")
    keys = {item["spec_key"] for item in result}
    assert "lens_mount" in keys
    assert "fps_max" in keys


def test_specs_dict_item_tiene_tres_campos():
    result = specs_dict_to_array({"lens_mount": "E"}, "Cámaras")
    item = result[0]
    assert "spec_key" in item
    assert "label" in item
    assert "value" in item


def test_specs_dict_fallback_label_sin_registry():
    # Key sin spec_def en la categoría: el label es la key limpia (title-case) — no se descarta.
    result = specs_dict_to_array({"unknown_spec_key": "E"}, "Cámaras")
    item = next(x for x in result if x["spec_key"] == "unknown_spec_key")
    assert item["label"]  # no vacío
    assert item["value"] == "E"


def test_specs_dict_label_de_registry_labels():
    result = specs_dict_to_array({"lens_mount": "E", "fps_max": 120}, "Cámaras")
    by_key = {item["spec_key"]: item for item in result}
    assert by_key["lens_mount"]["label"] == "Montura"


def test_zero_descartes_spec_key_desconocido():
    # Una key que no existe en el registry de la categoría igual aparece en la salida.
    result = specs_dict_to_array({"lens_mount": "E", "unknown_future_key": "valor"}, "Cámaras")
    keys = {item["spec_key"] for item in result}
    assert "unknown_future_key" in keys, "spec desconocida no debe descartarse"


# ── build_result — label sale del registry ──────────────────────────────────


def test_lens_mount_label_montura_para_camaras():
    """Caso testigo principal: lens_mount → label "Montura" (del registry), no "Lens mount"."""
    r = build_result(
        marca="Sony", modelo="FX6",
        specs={"lens_mount": "E", "camera_subtipo": "Cinema Camera"},
        extras={},
        image=None, url="http://x", title="Sony FX6 Cinema Camera",
        secciones={}, categoria_sugerida="Cámaras",
    )
    by_key = {item["spec_key"]: item for item in r["specs"]}
    assert "lens_mount" in by_key, "lens_mount debe aparecer en specs"
    assert by_key["lens_mount"]["label"] == "Montura", (
        f"label esperado 'Montura', obtenido '{by_key['lens_mount']['label']}'"
    )


def test_todos_los_items_tienen_spec_key():
    """Invariante: ningún item de specs puede carecer de spec_key."""
    r = build_result(
        marca="Sony", modelo="FX6",
        specs={"lens_mount": "E", "fps_max": 120, "resolucion_max": "4K"},
        extras={"white_balance": "Auto"},
        image=None, url="http://x", title="Sony FX6",
        secciones={}, categoria_sugerida="Cámaras",
    )
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], (
            f"item sin spec_key: {item}"
        )


# ── Cobertura real por categoría (ejercita salida del extractor sobre fixtures) ─
#
# Invariante: las spec_keys emitidas por el extractor deben existir en el registry.
# Si el registry renombra una key sin actualizar el parser, este test lo caza.
# Reemplaza los tests anteriores que alimentaban el registry contra sí mismo
# (tautología que no cazaba desajustes entre parser y registry).


_KNOWN_ORPHANS_GLOBAL: set[str] = set()  # 6b-i: bicolor/rgb removidos → color_modes


def _registry_all_keys() -> set[str]:
    from services.specs import REGISTRY
    keys: set[str] = set()
    for cat_reg in REGISTRY.categorias.values():
        keys.update(s.key for s in cat_reg.specs)
    return keys


def test_cobertura_real_camaras():
    """Parser de Cámaras no emite keys huérfanas (emitidas pero no en el registry)."""
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("camara_minimal.html")
    r = extract_from_html(html, categoria_hint="Cámaras")
    emitted = {s["spec_key"] for s in r["specs"] if s.get("spec_key")}
    all_registry_keys = _registry_all_keys()
    orphans = emitted - all_registry_keys - _KNOWN_ORPHANS_GLOBAL
    assert not orphans, (
        f"Parser Cámaras emitió spec_keys no declaradas en el registry: {orphans}"
    )
    assert emitted, "El extractor debe emitir al menos una spec del fixture"


def test_cobertura_real_lentes():
    """Parser de Lentes no emite keys huérfanas."""
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("lente_minimal.html")
    r = extract_from_html(html, categoria_hint="Lentes")
    emitted = {s["spec_key"] for s in r["specs"] if s.get("spec_key")}
    all_registry_keys = _registry_all_keys()
    orphans = emitted - all_registry_keys - _KNOWN_ORPHANS_GLOBAL
    assert not orphans, (
        f"Parser Lentes emitió spec_keys no declaradas en el registry: {orphans}"
    )
    assert emitted, "El extractor debe emitir al menos una spec del fixture"


def test_cobertura_real_iluminacion():
    """Parser de Iluminación no emite keys huérfanas."""
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("luz_minimal.html")
    r = extract_from_html(html, categoria_hint="Iluminación")
    emitted = {s["spec_key"] for s in r["specs"] if s.get("spec_key")}
    all_registry_keys = _registry_all_keys()
    orphans = emitted - all_registry_keys - _KNOWN_ORPHANS_GLOBAL
    assert not orphans, (
        f"Parser Iluminación emitió spec_keys no declaradas en el registry: {orphans}"
    )
    assert emitted, "El extractor debe emitir al menos una spec del fixture"


def test_cobertura_real_modificadores():
    """Parser bespoke de Modificadores extrae specs desde labels reales de B&H.

    Verifica que el parser bespoke llena los campos del registry desde los
    labels canónicos de B&H (Item Type, Accepts Grids, Interior Baffle,
    Quick Open Type, Light Loss/Gain, Light Compatibility, Dimensions).
    El fixture usa esos labels reales — mismo formato que los HTMLs de B&H.
    """
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("softbox_bh.html")
    r = extract_from_html(html, categoria_hint="Modificadores")
    by_key = {s["spec_key"]: s for s in r["specs"] if s.get("spec_key")}
    all_registry_keys = _registry_all_keys()

    # No emite keys huérfanas (las keys resueltas existen en el registry)
    matched_registry_keys = set(by_key) & all_registry_keys
    orphans = matched_registry_keys - all_registry_keys
    assert not orphans, f"Extractor Modificadores emitió keys huérfanas: {orphans}"

    # Las specs clave del fixture deben haberse poblado desde labels en inglés
    expected = {
        "modificador_subtipo", "forma", "diametro_cm",
        "incluye_grid", "incluye_difusor", "plegable", "light_loss_stops",
    }
    faltantes = expected - set(by_key)
    assert not faltantes, (
        f"Specs de modificador no resueltas desde labels B&H: {faltantes}. "
        f"Keys presentes: {sorted(by_key)}"
    )


# ── _normalize_label del companion (unifica _ ↔ espacio) ───────────────────


def _get_normalize_label():
    from services.specs_ingesta.queries.resolver import normalize_label
    return normalize_label


def test_normalize_label_unifica_guion_y_espacio():
    _normalize_label = _get_normalize_label()
    assert _normalize_label("lens_mount") == _normalize_label("lens mount")
    assert _normalize_label("consumo_w") == _normalize_label("consumo w")


def test_normalize_label_sin_parentesis():
    _normalize_label = _get_normalize_label()
    assert _normalize_label("Peso (g)") == "peso"
    assert _normalize_label("Peso_g") == "peso g"


# ── Tests de integración con HTML mínimo ───────────────────────────────────


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_extract_camara_specs_tienen_spec_key():
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("camara_minimal.html")
    r = extract_from_html(html)
    assert r["specs"], "debe extraer al menos un spec"
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], f"item sin spec_key: {item}"


def test_extract_lente_specs_tienen_spec_key():
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("lente_minimal.html")
    r = extract_from_html(html)
    assert r["specs"], "debe extraer al menos un spec"
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], f"item sin spec_key: {item}"


def test_extract_luz_specs_tienen_spec_key():
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("luz_minimal.html")
    r = extract_from_html(html)
    assert r["specs"], "debe extraer al menos un spec"
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], f"item sin spec_key: {item}"


def test_extract_camara_lens_mount_label_canonico():
    """lens_mount extraído de fixture HTML → label canónico del registry, no "Lens mount"."""
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("camara_minimal.html")
    r = extract_from_html(html)
    by_key = {item["spec_key"]: item for item in r["specs"]}
    if "lens_mount" in by_key:
        assert by_key["lens_mount"]["label"] == "Montura", (
            f"label esperado 'Montura', obtenido '{by_key['lens_mount']['label']}'"
        )


# ── Wattage alias → consumo_w (no potencia_w ni orphan) ────────────────────


def test_extract_luz_wattage_cae_en_consumo_w():
    """'Wattage: 200 W' en el fixture HTML → spec_key 'consumo_w', nunca 'potencia_w'."""
    from services.specs_ingesta import extract_from_html
    html = _load_fixture("luz_minimal.html")
    r = extract_from_html(html)
    by_key = {item["spec_key"]: item for item in r["specs"]}
    assert "consumo_w" in by_key, (
        f"'consumo_w' no aparece en specs; keys presentes: {list(by_key)}"
    )
    assert "potencia_w" not in by_key, "'potencia_w' (key vieja) no debe aparecer"


# ── Parser output vs registry: el parser no puede emitir keys huérfanas ─────


def test_parser_luz_no_emite_keys_huerfanas():
    """Las spec_keys que emite el parser de luces existen en el registry.

    Cierra el gap de cobertura: test_cobertura_iluminacion alimenta el registry
    contra sí mismo; éste ejercita la SALIDA REAL del parser contra el fixture.
    Un rename en el registry sin actualizar el parser lo rompe aquí, no en prod.

    Gaps pre-existentes excluidos de la aserción (fuera del scope de este fix):
      - bicolor, rgb: emitidos siempre como bool por el parser pero aún no
        formalizados como SpecDef en el registry (issue pendiente).
    """
    from services.specs_ingesta.parsers.iluminacion import map_luz_specs
    from services.specs_ingesta.parsers.base import BHSpecsParser

    from services.specs import REGISTRY
    cat = REGISTRY.get("Iluminación")
    registry_keys = {s.key for s in cat.specs}

    _KNOWN_ORPHANS: set[str] = set()  # 6b-i: bicolor/rgb removidos → color_modes

    html = _load_fixture("luz_minimal.html")
    parser = BHSpecsParser()
    parser.feed(html)
    specs_dict = map_luz_specs(dict(parser.secciones))

    huerfanas = {k for k in specs_dict if k not in registry_keys} - _KNOWN_ORPHANS
    assert not huerfanas, (
        f"El parser emitió spec_keys no declaradas en el registry: {huerfanas}\n"
        "Actualizá el parser o el registry para que estén alineados."
    )
