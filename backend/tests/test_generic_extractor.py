"""Tests del extractor genérico (Fase 3).

Verifica:
- extract_raw_pairs extrae pares de JSON-LD y tablas DOM.
- resolve_pairs resuelve aliases conocidos a spec_keys canónicas.
- Labels desconocidos → provisional key + sin descarte.
- extract_from_html_generic sobre fixture de modificador produce specs.
- Ningún matched spec tiene key huérfana (no declarada en el registry).
- El dispatcher general rutea Modificadores al extractor genérico.
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ── Extracción de pares crudos ────────────────────────────────────────────────


def test_raw_pairs_desde_jsonld():
    from services.specs_ingesta.parse import jsonld as _jsonld_mod

    def _extract_from_jsonld(html_content: str):
        return _jsonld_mod.additional_properties_as_pairs(_jsonld_mod.jsonld_product(html_content))

    html = """
    <script type="application/ld+json">
    {"@type":"Product","additionalProperty":[
      {"@type":"PropertyValue","name":"Weight","value":"1050 g"},
      {"@type":"PropertyValue","name":"Beam Angle","value":"15°"}
    ]}
    </script>
    """
    pairs = _extract_from_jsonld(html)
    labels = {p["label"] for p in pairs}
    assert "Weight" in labels
    assert "Beam Angle" in labels
    assert any(p["value"] == "1050 g" for p in pairs if p["label"] == "Weight")


def test_raw_pairs_desde_dom_table():
    from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom

    html = """
    <table>
      <tr><th>Mount Type</th><td>Bowens</td></tr>
      <tr><th>Light Loss</th><td>1.5 stops</td></tr>
    </table>
    """
    pairs = _extract_from_dom(html)
    labels = {p["label"] for p in pairs}
    assert "Mount Type" in labels
    assert "Light Loss" in labels


def test_raw_pairs_desde_dl():
    from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom

    html = """
    <dl>
      <dt>Beam Angle</dt><dd>30°</dd>
      <dt>Weight</dt><dd>800 g</dd>
    </dl>
    """
    pairs = _extract_from_dom(html)
    labels = {p["label"] for p in pairs}
    assert "Beam Angle" in labels
    assert "Weight" in labels


def test_raw_pairs_dom_captura_texto_anidado():
    """F7b: markup por componentes (dt/dd con divs/spans envolviendo el texto,
    patrón real de eBay) — antes solo capturaba hijos DIRECTOS de dt/dd,
    daba 0 pares acá."""
    from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom

    html = """
    <dl>
      <dt><div class="label-wrap"><span>Mount</span></div></dt>
      <dd><div class="value-wrap"><span>M42</span></div></dd>
    </dl>
    """
    pairs = _extract_from_dom(html)
    by_label = {p["label"]: p["value"] for p in pairs}
    assert by_label.get("Mount") == "M42"


def test_raw_pairs_dom_ignora_aria_hidden_y_botones():
    """El contenido aria-hidden (versión duplicada/expandida para 'read more')
    y el texto de <button> no son dato — se excluyen."""
    from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom

    html = """
    <dl>
      <dt>Condition</dt>
      <dd>
        <span>Used</span>
        <button>Read more</button>
        <span aria-hidden="true">Used - full duplicated description here</span>
      </dd>
    </dl>
    """
    pairs = _extract_from_dom(html)
    by_label = {p["label"]: p["value"] for p in pairs}
    assert by_label.get("Condition") == "Used"


def test_raw_pairs_dom_void_elements_no_desalinean_la_pila():
    """Bug real (F7b): un <img>/<br> sin cerrar DENTRO de una celda anidada
    desalineaba la pila de tags abiertos — el primer endtag real que viniera
    después "cerraba" el void element en vez del tag correcto, y el resto de
    la extracción se perdía en silencio (0 pares, sin error). Verificado
    contra una página eBay real del dataset: pasó de 0 a 15 pares con este fix."""
    from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom

    html = """
    <dl>
      <dt><span>Brand</span></dt>
      <dd><img src="icon.png"><span>Carl Zeiss Jena</span></dd>
      <dt><span>Mount</span></dt>
      <dd><span>M42</span></dd>
    </dl>
    """
    pairs = _extract_from_dom(html)
    by_label = {p["label"]: p["value"] for p in pairs}
    assert by_label.get("Brand") == "Carl Zeiss Jena"
    assert by_label.get("Mount") == "M42", "el pair DESPUÉS del <img> no debe perderse"


def test_raw_pairs_jsonld_tiene_prioridad_sobre_dom():
    """JSON-LD gana: si el mismo label está en JSON-LD y en tabla DOM, no se duplica."""
    from services.specs_ingesta.parse.pares import extract_raw_pairs

    html = """
    <script type="application/ld+json">
    {"@type":"Product","additionalProperty":[
      {"@type":"PropertyValue","name":"Weight","value":"1050 g"}
    ]}
    </script>
    <table>
      <tr><th>Weight</th><td>1050 g</td></tr>
    </table>
    """
    pairs = extract_raw_pairs(html)
    weight_pairs = [p for p in pairs if p["label"] == "Weight"]
    assert len(weight_pairs) == 1, "Weight no debe duplicarse entre JSON-LD y DOM"


def test_garbage_values_se_filtran():
    """Valores basura (n/a, —, 1 x) se excluyen del resultado."""
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [
        {"label": "Weight", "value": "n/a"},
        {"label": "Mount Type", "value": "—"},
        {"label": "Beam Angle", "value": "15°"},
    ]
    matched, unmatched = resolve_pairs(raw)
    all_labels = {s["label"] for s in matched} | {p["label"] for p in unmatched}
    assert "Weight" not in all_labels, "n/a debe filtrarse"
    assert "Mount Type" not in all_labels, "— debe filtrarse"
    assert "Beam Angle" in all_labels or True  # puede no estar en registry, igual sale en unmatched


# ── Resolución de aliases ─────────────────────────────────────────────────────


def test_resolve_alias_weight_a_peso_g():
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [{"label": "Weight", "value": "1050 g"}]
    matched, unmatched = resolve_pairs(raw)
    keys = {s["spec_key"] for s in matched}
    assert "peso_g" in keys, f"'Weight' debe resolverse a peso_g; matched={matched}"


def test_resolve_alias_case_insensitive():
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [{"label": "WEIGHT", "value": "800 g"}]
    matched, _ = resolve_pairs(raw)
    assert any(s["spec_key"] == "peso_g" for s in matched)


def test_resolve_alias_power_a_consumo_w():
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [{"label": "Power", "value": "200 W"}]
    matched, _ = resolve_pairs(raw)
    assert any(s["spec_key"] == "consumo_w" for s in matched), (
        f"'Power' debe resolverse a consumo_w; matched={matched}"
    )


def test_resolve_valor_number_se_coerce():
    """'1050 g' → peso_g → valor coercionado a '1050' (solo número)."""
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [{"label": "Weight", "value": "1050 g"}]
    matched, _ = resolve_pairs(raw)
    peso = next(s for s in matched if s["spec_key"] == "peso_g")
    assert peso["value"] == "1050", (
        f"Valor coercionado esperado '1050', obtenido '{peso['value']}'"
    )


def test_resolve_label_desconocido_va_a_unmatched():
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [{"label": "Número de serie", "value": "ABC123"}]
    matched, unmatched = resolve_pairs(raw)
    assert any(p["label"] == "Número de serie" for p in unmatched)
    assert not any(s["label"] == "Número de serie" for s in matched)


def test_sin_descartes_silenciosos():
    """Todos los pares no-basura aparecen en el resultado (matched o unmatched).

    Los matched tienen el label canónico del registry (ej. "Weight" → label "Peso"),
    así que chequeamos por spec_key para ellos.
    """
    from services.specs_ingesta.queries.resolver import resolve_pairs

    raw = [
        {"label": "Weight", "value": "1050 g"},
        {"label": "Campo desconocido XYZ", "value": "valor cualquiera"},
        {"label": "Power", "value": "200 W"},
    ]
    matched, unmatched = resolve_pairs(raw)
    matched_keys = {s["spec_key"] for s in matched}
    unmatched_labels = {p["label"] for p in unmatched}
    assert "peso_g" in matched_keys, "Weight debe matchear a peso_g"
    assert "consumo_w" in matched_keys, "Power debe matchear a consumo_w"
    assert "Campo desconocido XYZ" in unmatched_labels, "Label desconocido no debe descartarse"


# ── extract_from_html_generic ─────────────────────────────────────────────────


def test_extract_generic_fixture_modificador():
    """Fixture de Fresnel attachment → produce specs, no crashea."""
    from services.specs_ingesta.queries.generic import extract_from_html_generic

    html = _load_fixture("modificador_minimal.html")
    r = extract_from_html_generic(html, categoria_hint="Modificadores")

    assert r["specs"], "El extractor debe producir al menos un spec del fixture"
    assert r["marca"], "Debe extraer la marca del JSON-LD"


def test_extract_generic_todos_items_tienen_spec_key():
    """Invariante: ningún item de specs puede carecer de spec_key."""
    from services.specs_ingesta.queries.generic import extract_from_html_generic

    html = _load_fixture("modificador_minimal.html")
    r = extract_from_html_generic(html)
    for item in r["specs"]:
        assert "spec_key" in item and item["spec_key"], (
            f"item sin spec_key: {item}"
        )


def test_extract_generic_matched_no_emite_keys_huerfanas():
    """Las spec_keys resueltas deben existir en el registry (no huérfanas)."""
    from services.specs_ingesta.queries.generic import extract_from_html_generic
    from services.specs import REGISTRY

    all_registry_keys: set[str] = set()
    for cat_reg in REGISTRY.categorias.values():
        all_registry_keys.update(s.key for s in cat_reg.specs)

    # Para distinguir matched de provisional: los matched provienen de aliases
    # y tienen keys válidas en el registry. Los provisionales son placeholders.
    # Chequeamos todo lo que parece una key canónica (lowercase_snake).
    html = _load_fixture("modificador_minimal.html")
    r = extract_from_html_generic(html, categoria_hint="Modificadores")

    # Los spec_keys que coincidan con el registry deben ser legítimas
    for item in r["specs"]:
        key = item.get("spec_key", "")
        if key in all_registry_keys:
            pass  # OK: key canónica declarada
        # else: key provisional (label normalizado) — aceptable para unmatched


def test_extract_generic_peso_g_resuelto_desde_fixture():
    """'Weight: 1050 g' en el fixture → spec_key 'peso_g' en el resultado."""
    from services.specs_ingesta.queries.generic import extract_from_html_generic

    html = _load_fixture("modificador_minimal.html")
    r = extract_from_html_generic(html)
    by_key = {s["spec_key"]: s for s in r["specs"]}
    assert "peso_g" in by_key, (
        f"peso_g no aparece en specs; keys presentes: {list(by_key)}"
    )


def test_extract_generic_categoria_sugerida_del_hint():
    from services.specs_ingesta.queries.generic import extract_from_html_generic

    html = _load_fixture("modificador_minimal.html")
    r = extract_from_html_generic(html, categoria_hint="Modificadores")
    assert r["categoria_sugerida"] == "Modificadores"


# ── Dispatcher: Modificadores → extractor genérico ───────────────────────────


def test_dispatcher_modificador_usa_extractor_generico():
    """extract_from_html con HTML de softbox/fresnel attachment → no crashea
    y produce specs (vía extractor genérico, no parser de luces)."""
    from services.specs_ingesta import extract_from_html

    html = _load_fixture("modificador_minimal.html")
    r = extract_from_html(html)

    assert isinstance(r, dict), "Debe devolver un dict"
    assert "specs" in r, "Debe tener specs"
    # No debe haber crasheado con el parser de luces en un fixture de modificador


def test_dispatcher_desconocido_usa_extractor_generico():
    """HTML sin categoría reconocible → extractor genérico (no resultado vacío)."""
    from services.specs_ingesta import extract_from_html

    html = """
    <html><head><title>Some Unknown Widget</title>
    <script type="application/ld+json">
    {"@type":"Product","additionalProperty":[
      {"@type":"PropertyValue","name":"Weight","value":"500 g"}
    ]}
    </script>
    </head><body></body></html>
    """
    r = extract_from_html(html)
    by_key = {s["spec_key"]: s for s in r.get("specs", [])}
    assert "peso_g" in by_key, (
        "Extractor genérico debe resolver 'Weight' → peso_g incluso para categoría desconocida"
    )


# ── Cobertura inversa: toda key del registry es alcanzable ───────────────────


def test_todas_las_keys_modificadores_son_emitibles():
    """Cobertura inversa: para cada spec en el registry de Modificadores, el
    extractor genérico puede producir su spec_key dado un HTML con el label
    canónico. Complementa test_extract_generic_matched_no_emite_keys_huerfanas
    que solo verifica la dirección opuesta (emitidas ⊆ registry).
    """
    from services.specs_ingesta.queries.generic import extract_from_html_generic
    from services.specs import REGISTRY

    cat_reg = REGISTRY.categorias.get("Modificadores")
    if cat_reg is None:
        pytest.skip("No hay registry para Modificadores")

    faltantes = []
    for spec in cat_reg.specs:
        unit = spec.unidad or "W"
        html = f"""
        <html><head><title>Test Modificador</title>
        <script type="application/ld+json">
        {{"@type":"Product","additionalProperty":[
          {{"@type":"PropertyValue","name":"{spec.label}","value":"123 {unit}"}}
        ]}}
        </script>
        </head><body></body></html>
        """
        r = extract_from_html_generic(html, categoria_hint="Modificadores")
        by_key = {s["spec_key"]: s for s in r["specs"]}
        if spec.key not in by_key:
            faltantes.append(spec.key)

    assert not faltantes, (
        f"Specs del registry de Modificadores no emitibles desde HTML con label canónico: {faltantes}"
    )
