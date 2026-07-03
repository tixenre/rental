"""queries/bespoke.py — Extracción por categoría con parser bespoke
(Cámaras, Lentes/Filtros/Adaptadores, Modificadores, Iluminación).

Movido de equipo_html_extractor.py (_extract_via_*) y luces_html_extractor.py
(F4 del rediseño de ingesta). Las 4 funciones comparten el mismo esqueleto
(parsear DOM con BHSpecsParser, mergear JSON-LD, mapear, armar el resultado
con `resultado.build_result`) — antes cada una tenía su propia copia del
merge JSON-LD (3 idénticas en equipo + 1 distinta y con bugs en luces, ver
`parse/secciones.py`) y luces ni siquiera pasaba por `build_result`.

Nota: `extract_iluminacion` extrae el título con regex sobre el HTML crudo
(igual que el luces_html_extractor.py original) en vez de `BHSpecsParser.title`
(que usan las otras 3) — se preserva así, no se unifica, porque son 2
mecanismos de título ya distintos en el código original y no hay evidencia
de que produzcan el mismo resultado en todos los casos."""

from __future__ import annotations

import re

from services.specs_ingesta.parse import jsonld as _jsonld
from services.specs_ingesta.parse.secciones import merge_jsonld_into_secciones
from services.specs_ingesta.parsers.base import BHSpecsParser, _clean_title, _extract_brand, _extract_modelo
from services.specs_ingesta.queries.resultado import build_result, generic_fallback_result


def _parse_dom_y_mergear(html_content: str) -> tuple[dict, str, str | None, str]:
    """Pasos comunes a camaras/lentes/modificadores: un solo BHSpecsParser.feed()
    (título + secciones), un solo jsonld_product(), merge. Devuelve
    (secciones, title, image, url)."""
    parser = BHSpecsParser()
    parser.feed(html_content)
    secciones = dict(parser.secciones)
    title = _clean_title(parser.title or "")

    product = _jsonld.jsonld_product(html_content)
    image = _jsonld.image(product)
    url = _jsonld.url(product) or ""
    secciones = merge_jsonld_into_secciones(secciones, product)

    return secciones, title, image, url


def extract_iluminacion(html_content: str) -> dict:
    """Usa services/specs_ingesta/parsers/iluminacion.py + normalizar.py."""
    from services.specs_ingesta.parsers.iluminacion import map_luz_specs, map_luz_extras
    from services.specs_ingesta.parsers.normalizar import canon_brand, canon_modelo, clean_extras

    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = _clean_title(title_m.group(1).strip()) if title_m else ""
    marca = canon_brand(_extract_brand(title))
    modelo = canon_modelo(_extract_modelo(title))

    parser = BHSpecsParser()
    parser.feed(html_content)
    secciones = dict(parser.secciones)

    product = _jsonld.jsonld_product(html_content)
    image = _jsonld.image(product)
    url = _jsonld.url(product)
    if not url:
        saved = re.search(r"saved from url=\(\d+\)(https?://\S+)", html_content)
        if saved:
            url = saved.group(1).strip()
    url = url or ""
    secciones = merge_jsonld_into_secciones(secciones, product)

    specs = map_luz_specs(secciones, title=modelo)
    extras = clean_extras(map_luz_extras(secciones, title=modelo))

    return build_result(
        marca=marca, modelo=modelo, specs=specs, extras=extras,
        image=image, url=url, title=title, secciones=secciones,
        categoria_sugerida="Iluminación",
    )


def extract_via_lentes_parser(html_content: str) -> dict:
    """Usa services/specs_ingesta/parsers/lentes.py — clasifica lente/adaptador/filtro
    internamente. El parser ya tiene `_classify()`, `map_lente_specs()`,
    `map_filtro_specs()`, `map_adaptador_specs()`. Reusamos.
    """
    from services.specs_ingesta.parsers.lentes import (
        _classify,
        _build_lens_id, _build_filter_id,
        _build_adapter_id, _build_accesorio_model,
        map_lente_specs, map_filtro_specs, map_adaptador_specs,
        map_lente_extras, map_accesorio_extras,
    )

    secciones, title, image, url = _parse_dom_y_mergear(html_content)
    marca = _extract_brand(title)
    clase = _classify(secciones, title)

    if clase == "lente":
        specs = map_lente_specs(secciones, title=title)
        extras = map_lente_extras(secciones, title=title)
        _build_lens_id(marca, specs, title)  # prod_id: no se usa hoy (ver gotcha F3)
        modelo = title  # mantenemos el título canónico
        categoria_sugerida = "Lentes"
    elif clase == "filtro":
        specs = map_filtro_specs(secciones, title=title)
        extras = map_accesorio_extras(secciones, title=title)
        _build_filter_id(marca, specs, title)
        modelo = _build_accesorio_model(marca, specs, title)
        categoria_sugerida = "Filtros"
    elif clase == "adaptador":
        specs = map_adaptador_specs(secciones, title=title)
        extras = map_accesorio_extras(secciones, title=title)
        _build_adapter_id(marca, specs, title)
        modelo = _build_accesorio_model(marca, specs, title)
        categoria_sugerida = "Adaptadores"
    else:
        # Fallback genérico — devolver title como modelo, specs vacíos
        return generic_fallback_result(title, marca, "", image, url)

    return build_result(
        marca=marca, modelo=modelo, specs=specs, extras=extras,
        image=image, url=url, title=title, secciones=secciones,
        categoria_sugerida=categoria_sugerida,
    )


def extract_via_modificadores_parser(html_content: str) -> dict:
    """Usa services/specs_ingesta/parsers/modificadores.py — softbox / spotlight / fresnel / difusor."""
    from services.specs_ingesta.parsers.modificadores import map_modificador_specs

    secciones, title, image, url = _parse_dom_y_mergear(html_content)
    marca = _extract_brand(title)
    modelo = _extract_modelo(title)
    specs = map_modificador_specs(secciones, title=title)

    return build_result(
        marca=marca, modelo=modelo, specs=specs, extras={},
        image=image, url=url, title=title, secciones=secciones,
        categoria_sugerida="Modificadores",
    )


def extract_via_camaras_parser(html_content: str) -> dict:
    """Usa services/specs_ingesta/parsers/camaras.py — cámaras."""
    from services.specs_ingesta.parsers.camaras import map_camara_specs, map_camara_extras

    secciones, title, image, url = _parse_dom_y_mergear(html_content)
    marca = _extract_brand(title)
    modelo = _extract_modelo(title)
    specs = map_camara_specs(secciones, title=title)
    extras = map_camara_extras(secciones, title=title)

    return build_result(
        marca=marca, modelo=modelo, specs=specs, extras=extras,
        image=image, url=url, title=title, secciones=secciones,
        categoria_sugerida="Cámaras",
    )
