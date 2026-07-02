"""llm/contexto.py — Arma el paquete de contexto del suplemento offline (F7b).

**Decisión de diseño (2026-07, con el dueño):** el suplemento offline NO llama
a un LLM por API propia. Se evaluaron 2 caminos — API directa (key nueva,
costo por llamada, parseo/validación de la respuesta como ingeniería real) vs.
**semi-manual** (armar un bundle prolijo para que una sesión de Claude Code
interactiva — "hay Claude a mano", la frase original del plan — lo razone) —
y se eligió el semi-manual: cero infraestructura nueva, cero secreto nuevo,
el mismo gate de revisión humana que ya exige el principio rector
("correctitud de specs es sagrada", dato externo = hipótesis hasta validar).

Cuándo se usa: cuando `queries/extraer.py` no puede con un HTML (fuente
no-B&H como eBay/fabricante, categoría mal-detectada, o simplemente
`extract_from_html` devolvió specs pobres/vacíos). Se corre `cli.py context`
sobre ESE HTML puntual — no es un paso del flujo normal.

Después de armar el contexto: quien lo razone (Claude Code interactivo o el
dueño a mano) llama DIRECTO a `services.specs.encolar_propuesta` con lo que
concluya — no hace falta un mecanismo de "aplicar" nuevo, esa función ya es
pública y ya está probada (F7a). Nunca se escribe `spec_definitions`/
`equipo_specs` desde acá — la cola (Canal C) es el único camino, igual que
`commands/proponer.py`.

**`llm/` sigue siendo offline-only** (invariante del módulo): solo `cli.py`
importa de acá."""

from __future__ import annotations

import re

from services.specs import get_categoria
from services.specs_ingesta.parse.jsonld import brand_name, jsonld_product
from services.specs_ingesta.parse.pares import extract_raw_pairs
from services.specs_ingesta.queries.detectar import detect_categoria


def armar_contexto(html_content: str, categoria_hint: str | None = None) -> dict:
    """HTML crudo → bundle listo para que un humano/Claude razone specs.

    Usa las primitivas source-agnósticas (JSON-LD + tablas DOM genéricas,
    `parse/pares.py`) — NO los parsers bespoke B&H-específicos (esos ya
    corrieron y no matchearon/no aplican si llegamos hasta acá; asumir su
    estructura sería inútil justo en el caso que este bundle existe para
    cubrir)."""
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    product = jsonld_product(html_content)
    marca_jsonld = brand_name(product)

    categoria = categoria_hint or detect_categoria(html_content, title)
    raw_pairs = extract_raw_pairs(html_content)

    cat_reg = get_categoria(categoria) if categoria and categoria != "Desconocido" else None
    schema_categoria = [
        {
            "spec_key": s.key,
            "label": s.label,
            "tipo": s.tipo,
            "unidad": s.unidad,
            "enum_options": s.enum_options,
        }
        for s in (cat_reg.specs if cat_reg else [])
    ]

    return {
        "titulo": title,
        "marca_jsonld": marca_jsonld,
        "categoria_detectada": categoria,
        "raw_pairs": raw_pairs,
        "schema_categoria": schema_categoria,
        "instrucciones": (
            "Mapear cada raw_pair relevante a un spec_key de schema_categoria "
            "(tipo/unidad/enum_options ya definen la forma esperada del valor). "
            "Un raw_pair que no matchea ningún spec existente pero se repite en "
            "varias fuentes independientes es candidato a proponerse — nunca "
            "escribir specs directo: services.specs.encolar_propuesta(conn, "
            "tipo='spec_nueva', payload={...}, origen='llm-semi-manual', "
            "confianza=...) y que el dueño lo revise desde la cola."
        ),
    }
