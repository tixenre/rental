"""Tests de llm/contexto.py — el bundle del suplemento offline semi-manual (F7b).

Sin DB (armar_contexto no persiste nada — solo lee/estructura). El caso
real que motivó el módulo (una página eBay que `extract_from_html` no
resuelve, ver CLAUDE.md de specs_ingesta) se cubre por separado con el
dataset real, no acá — estos son unitarios sobre HTML mínimo.
"""

import pytest

pytestmark = pytest.mark.unit

from services.specs_ingesta.llm.contexto import armar_contexto


_HTML_LENTE = """
<html><head><title>Some Lens on eBay</title>
<script type="application/ld+json">
{"@type":"Product","name":"Some Lens","brand":{"name":"Acme"}}
</script>
</head><body>
<dl>
  <dt><div><span>Mount</span></div></dt>
  <dd><div><span>M42</span></div></dd>
  <dt><div><span>Focal Length</span></div></dt>
  <dd><div><span>50mm</span></div></dd>
</dl>
</body></html>
"""


def test_arma_titulo_marca_y_categoria():
    ctx = armar_contexto(_HTML_LENTE, categoria_hint="Lentes")
    assert ctx["titulo"] == "Some Lens on eBay"
    assert ctx["marca_jsonld"] == "Acme"
    assert ctx["categoria_detectada"] == "Lentes"


def test_raw_pairs_incluye_lo_extraido_del_dom():
    ctx = armar_contexto(_HTML_LENTE, categoria_hint="Lentes")
    by_label = {p["label"]: p["value"] for p in ctx["raw_pairs"]}
    assert by_label.get("Mount") == "M42"
    assert by_label.get("Focal Length") == "50mm"


def test_schema_categoria_trae_los_specs_del_registry():
    ctx = armar_contexto(_HTML_LENTE, categoria_hint="Lentes")
    keys = {s["spec_key"] for s in ctx["schema_categoria"]}
    assert "lens_mount" in keys
    assert "distancia_focal" in keys
    lens_mount = next(s for s in ctx["schema_categoria"] if s["spec_key"] == "lens_mount")
    assert lens_mount["tipo"] == "enum"
    assert "M42" in (lens_mount["enum_options"] or [])


def test_sin_categoria_hint_detecta_por_titulo():
    ctx = armar_contexto(_HTML_LENTE)
    assert ctx["categoria_detectada"] == "Lentes"


def test_categoria_desconocida_da_schema_vacio():
    html = "<html><head><title>Widget misterioso sin pistas</title></head><body></body></html>"
    ctx = armar_contexto(html)
    assert ctx["categoria_detectada"] == "Desconocido"
    assert ctx["schema_categoria"] == []
