"""Tests de Fase 1: spec_key end-to-end en el pipeline de normalización.

Verifica:
- _specs_dict_to_array produce {spec_key, label, value} por item.
- Label viene del registry (fuente única) — no de _SPEC_LABELS borrado.
- lens_mount → label "Montura" para Cámaras (antes era "Lens mount" divergente).
- Specs sin registry_labels reciben fallback label (nunca se descartan).
- Cobertura: qué spec_keys del registry emite _build_result por categoría.
- _normalize_label del companion unifica _ ↔ espacio.
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.unit

from services.equipo_html_extractor import _specs_dict_to_array, _build_result


FIXTURES = Path(__file__).parent / "fixtures" / "html"


# ── _specs_dict_to_array ────────────────────────────────────────────────────


def test_specs_dict_incluye_spec_key():
    result = _specs_dict_to_array({"lens_mount": "E", "fps_max": 120})
    keys = {item["spec_key"] for item in result}
    assert "lens_mount" in keys
    assert "fps_max" in keys


def test_specs_dict_item_tiene_tres_campos():
    result = _specs_dict_to_array({"lens_mount": "E"})
    item = result[0]
    assert "spec_key" in item
    assert "label" in item
    assert "value" in item


def test_specs_dict_fallback_label_sin_registry():
    # Sin registry_labels, el label es la key limpia (title-case) — no se descarta.
    result = _specs_dict_to_array({"lens_mount": "E"})
    item = next(x for x in result if x["spec_key"] == "lens_mount")
    assert item["label"]  # no vacío
    assert item["value"] == "E"


def test_specs_dict_label_de_registry_labels():
    registry_labels = {"lens_mount": "Montura", "fps_max": "FPS máx"}
    result = _specs_dict_to_array({"lens_mount": "E", "fps_max": 120}, registry_labels=registry_labels)
    by_key = {item["spec_key"]: item for item in result}
    assert by_key["lens_mount"]["label"] == "Montura"
    assert by_key["fps_max"]["label"] == "FPS máx"


def test_zero_descartes_spec_key_desconocido():
    # Una key que no existe en registry_labels igual aparece en la salida.
    registry_labels = {"lens_mount": "Montura"}
    result = _specs_dict_to_array(
        {"lens_mount": "E", "unknown_future_key": "valor"}, registry_labels=registry_labels
    )
    keys = {item["spec_key"] for item in result}
    assert "unknown_future_key" in keys, "spec desconocida no debe descartarse"


# ── _build_result — label sale del registry ─────────────────────────────────


def test_lens_mount_label_montura_para_camaras():
    """Caso testigo principal: lens_mount → label "Montura" (del registry), no "Lens mount"."""
    r = _build_result(
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
    r = _build_result(
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
    from specs import REGISTRY
    keys: set[str] = set()
    for cat_reg in REGISTRY.categorias.values():
        keys.update(s.key for s in cat_reg.specs)
    return keys


def test_cobertura_real_camaras():
    """Parser de Cámaras no emite keys huérfanas (emitidas pero no en el registry)."""
    from services.equipo_html_extractor import extract_from_html
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
    from services.equipo_html_extractor import extract_from_html
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
    from services.equipo_html_extractor import extract_from_html
    html = _load_fixture("luz_minimal.html")
    r = extract_from_html(html, categoria_hint="Iluminación")
    emitted = {s["spec_key"] for s in r["specs"] if s.get("spec_key")}
    all_registry_keys = _registry_all_keys()
    orphans = emitted - all_registry_keys - _KNOWN_ORPHANS_GLOBAL
    assert not orphans, (
        f"Parser Iluminación emitió spec_keys no declaradas en el registry: {orphans}"
    )
    assert emitted, "El extractor debe emitir al menos una spec del fixture"


# ── _normalize_label del companion (unifica _ ↔ espacio) ───────────────────


def _get_normalize_label():
    from services.generic_html_extractor import _normalize_label
    return _normalize_label


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
    from services.equipo_html_extractor import extract_from_html
    html = _load_fixture("camara_minimal.html")
    r = extract_from_html(html)
    assert r["specs"], "debe extraer al menos un spec"
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], f"item sin spec_key: {item}"


def test_extract_lente_specs_tienen_spec_key():
    from services.equipo_html_extractor import extract_from_html
    html = _load_fixture("lente_minimal.html")
    r = extract_from_html(html)
    assert r["specs"], "debe extraer al menos un spec"
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], f"item sin spec_key: {item}"


def test_extract_luz_specs_tienen_spec_key():
    from services.equipo_html_extractor import extract_from_html
    html = _load_fixture("luz_minimal.html")
    r = extract_from_html(html)
    assert r["specs"], "debe extraer al menos un spec"
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], f"item sin spec_key: {item}"


def test_extract_camara_lens_mount_label_canonico():
    """lens_mount extraído de fixture HTML → label canónico del registry, no "Lens mount"."""
    from services.equipo_html_extractor import extract_from_html
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
    from services.equipo_html_extractor import extract_from_html
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
    import sys
    from pathlib import Path
    _tools = Path(__file__).parent.parent.parent / "tools"
    sys.path.insert(0, str(_tools))
    from iluminacion_parser import map_luz_specs, BHSpecsParser

    from specs import REGISTRY
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
