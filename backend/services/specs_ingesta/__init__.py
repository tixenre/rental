"""services/specs_ingesta — barrel público del motor de ingesta de specs.

F0-F5 del plan (ver docs/PLAN_SPECS_INGESTA.md e issue #1176). `extract_from_html`
es el entry point único — mismo motor determinístico para Railway (vía el
endpoint admin) y para `cli.py` (offline, con la capa LLM como suplemento
opcional, nunca al revés).

Mismo patrón que `services/specs/` y `services/categorias/`: `queries/` =
lectura pura (nunca muta, es lo que corre en Railway), `commands/` = única
puerta de escritura (el embudo que aprende — propone, no aplica). `parse/` y
`parsers/` son los building-blocks de dominio que ninguna de las dos capas
reimplementa. `__all__` es el contrato real — lo que no está ahí es detalle
interno del paquete.
"""

from .errors import ErrorIngesta, HtmlNoParseable
from .queries.extraer import extract_from_html
from .commands.proponer import proponer_desde_unmatched

__all__ = [
    "extract_from_html",
    "proponer_desde_unmatched",
    "ErrorIngesta",
    "HtmlNoParseable",
]
