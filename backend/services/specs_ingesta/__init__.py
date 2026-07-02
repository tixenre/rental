"""services/specs_ingesta — barrel público del motor de ingesta de specs.

F0 del plan (ver docs/PLAN_SPECS_INGESTA.md e issue #1176): scaffold vacío.
`extract_from_html` es un re-export temporal del extractor viejo
(`services.equipo_html_extractor`) — no se movió lógica todavía, solo se fija
el contrato público antes de mover nada (mismo método que `services/specs/`
F0-F6). Las fases siguientes mueven la implementación real a `parse/`,
`parsers/`, `queries/` y `commands/` sin cambiar este símbolo.

Mismo patrón que `services/specs/` y `services/categorias/`: `queries/` =
lectura pura (nunca muta, es lo que corre en Railway), `commands/` = única
puerta de escritura (el embudo que aprende — propone, no aplica). `parse/` y
`parsers/` son los building-blocks de dominio que ninguna de las dos capas
reimplementa. `__all__` es el contrato real — lo que no está ahí es detalle
interno del paquete.
"""

from services.equipo_html_extractor import extract_from_html  # noqa: F401 — shim temporal F0

from .errors import ErrorIngesta, HtmlNoParseable

__all__ = [
    "extract_from_html",
    "ErrorIngesta",
    "HtmlNoParseable",
]
