"""services/luces_html_extractor.py — ⏰ LEGACY (F4 del rediseño de ingesta).

Toda la lógica se movió a `services/specs_ingesta/queries/bespoke.py::extract_iluminacion`
(mismo motor que usa el dispatcher de `equipo_html_extractor.py` y, a futuro,
el CLI offline). La implementación vieja de acá tenía 3 bugs reales que la
unificación corrigió (verificado contra las 103 páginas de luces del dataset,
0 regresiones): `peso` siempre daba None (buscaba la key "peso" en vez de
"peso_g"), `keywords` siempre daba [] (hardcodeado en vez de
`compute_keywords`), y el merge JSON-LD perdía datos por usar dedupe en vez de
anteponer JSON-LD primero (ver `parse/secciones.py`).

Este archivo queda como shim de compatibilidad — verificado que ningún test
ni código en vivo importa nada de acá por nombre salvo este propio módulo —
se poda en F6 junto con el resto de los shims ⏰ LEGACY. Ver
docs/PLAN_SPECS_INGESTA.md e issue #1176.
"""

from services.specs_ingesta.queries.bespoke import extract_iluminacion as extract_from_html

__all__ = ["extract_from_html"]
