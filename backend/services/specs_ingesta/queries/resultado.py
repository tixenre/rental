"""queries/resultado.py — Arma el AutocompletarResult, fuente ÚNICA para las
4 categorías con parser bespoke (Cámaras/Lentes/Filtros/Adaptadores/
Modificadores/Iluminación).

Movido de equipo_html_extractor.py::_build_result (F4 del rediseño de
ingesta). Antes luces_html_extractor.py armaba su PROPIO dict a mano, sin
pasar por acá — con 2 consecuencias reales (verificadas contra las 54
páginas, no supuestas):
  - `peso` de una luz SIEMPRE daba None: buscaba la key "peso" en vez de
    "peso_g" (la real que devuelve el mapper). Bug preexistente, se corrige
    solo al unificar — no hacía falta tocar nada aparte.
  - `keywords` de una luz SIEMPRE daba [] (hardcodeado) en vez de usar
    compute_keywords() como las demás categorías — sin ninguna razón
    category-specific para excluirla (compute_keywords es genérica,
    data-driven vía SPEC_KEYWORDS_TEMPLATES).
  `dimensiones`/`incluye`/`alimentacion` de luces ya estaban efectivamente
  vacíos/equivalentes en la práctica (verificado contra las 54 páginas) —
  unificar no les cambia nada observable."""

from __future__ import annotations

import logging

from services.nombre_builder import compute_keywords
from services.specs_ingesta.parse.serialize import specs_dict_to_array

logger = logging.getLogger(__name__)


def build_result(*, marca: str, modelo: str, specs: dict, extras: dict,
                  image: str | None, url: str, title: str,
                  secciones: dict, categoria_sugerida: str) -> dict:
    """Estructura común AutocompletarResult con keywords canónicas."""
    # La ficha técnica se nutre de specs (bucket curado) + extras (cola larga
    # del parser). Sólo se promueven las keys de extras que correspondan a un
    # spec del registry de la categoría — así nada parseado se pierde y no se
    # generan propuestas-basura por datos sin spec. El bucket curado gana en
    # caso de colisión de key.
    specs_para_persistir = dict(specs)
    try:
        from services.specs import REGISTRY  # import local: evita ciclos al boot

        cat_reg = REGISTRY.get(categoria_sugerida)
        if cat_reg:
            registry_keys = {s.key for s in cat_reg.specs}
            for k, v in (extras or {}).items():
                if k in registry_keys and k not in specs_para_persistir:
                    specs_para_persistir[k] = v
    except Exception as exc:
        logger.warning("extras wiring: no se pudo promover extras para '%s': %s", categoria_sugerida, exc)

    # Serialización delegada en specs_ingesta (fuente única de display, vía
    # spec_render) — aplica la unidad que el registry declara.
    specs_array = specs_dict_to_array(specs_para_persistir, categoria_sugerida)
    keywords = compute_keywords(specs)

    # Campos derivados para AutocompletarResult (ficha extendida)
    peso_str: str | None = None
    if isinstance(specs.get("peso_g"), (int, float)):
        g = specs["peso_g"]
        peso_str = f"{round(g/1000, 2)} kg" if g >= 1000 else f"{int(g)} g"

    return {
        "marca": marca,
        "modelo": modelo,
        "nombre_normalizado": f"{marca} {modelo}".strip(),
        "descripcion": "",
        "specs": specs_array,
        "keywords": keywords,  # ← derivadas de specs canónicos, no LLM
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        "peso": peso_str,
        "dimensiones": specs.get("dimensiones") or extras.get("dimensiones") or None,
        "montura": specs.get("lens_mount"),
        "formato": specs.get("formato"),
        "resolucion": specs.get("resolucion_max"),
        "alimentacion": ", ".join(specs["alimentacion"]) if isinstance(specs.get("alimentacion"), list) else (specs.get("alimentacion") or None),
        "incluye": [],
        "conectividad": [],
        "compatible_con": [],
        "video_url": None,
        "precio_bh_usd": None,
        "categoria_sugerida": categoria_sugerida,
        "fuente_url": url,
        "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": f"html-upload (parser {categoria_sugerida.lower()})",
        "bh_url": url,
        "extras": extras,
        "fuente": "html-upload",
        "raw_secciones": secciones,
    }


def generic_fallback_result(title: str, marca: str, modelo: str, image: str | None,
                             url: str) -> dict:
    """Fallback cuando no se pudo clasificar dentro de un parser bespoke
    (ej. lentes_parser detecta 'lente'/'filtro'/'adaptador' pero ninguno matchea):
    devuelve mínimo (title + foto), specs vacíos. Movido de
    equipo_html_extractor.py::_generic_result."""
    return {
        "marca": marca,
        "modelo": modelo or title,
        "nombre_normalizado": f"{marca} {modelo or title}".strip(),
        "descripcion": "",
        "specs": [],
        "keywords": [],
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        "peso": None, "dimensiones": None,
        "montura": None, "formato": None, "resolucion": None,
        "alimentacion": None, "incluye": [], "conectividad": [],
        "compatible_con": [], "video_url": None,
        "precio_bh_usd": None, "categoria_sugerida": None,
        "fuente_url": url, "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": "html-upload (categoria desconocida)",
        "bh_url": url, "extras": {}, "fuente": "html-upload",
        "raw_secciones": {},
    }
