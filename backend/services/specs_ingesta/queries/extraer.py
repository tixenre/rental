"""queries/extraer.py — Entry point único de la extracción HTML→specs.

Movido de equipo_html_extractor.py::extract_from_html (F5 del rediseño de
ingesta) — reemplaza al dispatcher que vivía ahí. Mismo motor para los dos
runtimes (invariante del módulo, ver CLAUDE.md): Railway lo llama vía el
endpoint admin, `cli.py` lo llama offline sobre el mismo HTML — sin LLM en
ninguno de los dos, ambos determinísticos, ambos dan el mismo resultado
sobre el mismo input.
"""

import re

from services.specs_ingesta.queries import bespoke, generic
from services.specs_ingesta.queries.detectar import detect_categoria


def extract_from_html(html_content: str, categoria_hint: str | None = None) -> dict:
    """Extrae specs canónicos de un HTML B&H.

    Dispatcher: detecta categoría (o usa hint) y delega al parser específico.
    Devuelve `AutocompletarResult` con specs canónicos + keywords derivadas.

    Args:
        html_content: HTML completo (Cmd+S de B&H o rawHtml de Firecrawl).
        categoria_hint: si el frontend ya sabe la categoría (ej. usuario eligió
                        en un dropdown), evita la detección automática.
    """
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    categoria = (categoria_hint or detect_categoria(html_content, title)).strip()

    if categoria == "Iluminación":
        return bespoke.extract_iluminacion(html_content)
    if categoria == "Cámaras":
        return bespoke.extract_via_camaras_parser(html_content)
    if categoria in ("Lentes", "Adaptadores", "Filtros"):
        return bespoke.extract_via_lentes_parser(html_content)
    if categoria == "Modificadores":
        return bespoke.extract_via_modificadores_parser(html_content)

    # Categorías sin parser bespoke (Desconocido, futuras) →
    # extractor genérico: saca TODOS los pares crudos y resuelve por aliases.
    # Cero descartes silenciosos: lo que no resuelve queda visible como "sin
    # template" (salvo ruido conocido de shipping/packaging, ver F4).
    return generic.extract_from_html_generic(html_content, categoria_hint=categoria if categoria != "Desconocido" else None)
