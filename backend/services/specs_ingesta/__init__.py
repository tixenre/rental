"""services/specs_ingesta — barrel público del motor de ingesta de specs.

F0-F1 del plan (ver docs/PLAN_SPECS_INGESTA.md e issue #1176). `extract_from_html`
es un re-export temporal del extractor viejo (`services.equipo_html_extractor`)
— no se movió el entry point todavía, eso es F5. Las primitivas (parse/,
queries/resolver.py) ya se movieron (F1).

Mismo patrón que `services/specs/` y `services/categorias/`: `queries/` =
lectura pura (nunca muta, es lo que corre en Railway), `commands/` = única
puerta de escritura (el embudo que aprende — propone, no aplica). `parse/` y
`parsers/` son los building-blocks de dominio que ninguna de las dos capas
reimplementa. `__all__` es el contrato real — lo que no está ahí es detalle
interno del paquete.

Gotcha (F1): `extract_from_html` se resuelve LAZY (`__getattr__`, PEP 562), no
con un import de módulo directo. Import directo crearía un ciclo: este barrel
→ equipo_html_extractor → services.specs_ingesta.parse (que dispara la carga
de ESTE barrel de nuevo, todavía a mitad de inicializar). Se cae solo cuando
F5 mueva `extract_from_html` a `queries/extraer.py` — ahí el shim desaparece
y con él la necesidad del lazy-load.
"""

from .errors import ErrorIngesta, HtmlNoParseable

__all__ = [
    "extract_from_html",
    "ErrorIngesta",
    "HtmlNoParseable",
]


def __getattr__(name: str):
    if name == "extract_from_html":
        from services.equipo_html_extractor import extract_from_html

        return extract_from_html
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
