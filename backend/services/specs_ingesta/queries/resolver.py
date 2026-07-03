"""queries/resolver.py — Resuelve pares crudos {label, value} contra el
registry de specs (Canal A: lee REGISTRY + coerce_and_serialize de
services.specs, nunca escribe). Movido verbatim de
generic_html_extractor.py::resolve_pairs + su índice de aliases.

Lado LECTURA del embudo — es lo que corre en Railway. No toca DB (el índice
de aliases vive en el registry Python, cacheado por proceso)."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def normalize_label(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("_", " ")
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


_ALIAS_INDEX: dict[str, dict] | None = None


def _spec_info(spec) -> dict:
    return {
        "spec_key": spec.key,
        "label": spec.label,
        "tipo": spec.tipo,
        "unidad": spec.unidad,
        "enum_options": spec.enum_options,
    }


def _index_categoria(cat_reg) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for spec in cat_reg.specs:
        info = _spec_info(spec)
        for key in (normalize_label(spec.label), normalize_label(spec.key)):
            index.setdefault(key, info)
        for alias in spec.aliases:
            index.setdefault(normalize_label(alias), info)
    return index


def _build_alias_index() -> dict[str, dict]:
    """Construye índice normalizado_label → spec_info desde TODO el registry.

    spec_info contiene: spec_key, label, tipo, unidad, enum_options.
    Incluye: label canónico, spec_key y todos los aliases declarados.
    """
    from services.specs import REGISTRY

    index: dict[str, dict] = {}
    for cat_reg in REGISTRY.categorias.values():
        index.update({k: v for k, v in _index_categoria(cat_reg).items() if k not in index})
    return index


def _get_alias_index() -> dict[str, dict]:
    global _ALIAS_INDEX
    if _ALIAS_INDEX is None:
        try:
            _ALIAS_INDEX = _build_alias_index()
        except Exception as exc:
            logger.warning("resolver: no se pudo construir alias index: %s", exc)
            _ALIAS_INDEX = {}
    return _ALIAS_INDEX


def resolve_pairs(
    raw_pairs: list[dict[str, str]],
    categoria_hint: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Resuelve pares crudos {label, value} contra el registry de aliases.

    Cuando se provee categoria_hint, filtra el índice a solo las specs de esa
    categoría — evita colisiones cross-categoría (alias compartido entre
    "Cámaras" y "Iluminación" que resolvería al primer ganador global).

    Retorna (matched, unmatched):
    - matched:   [{spec_key, label, value}] — resueltos y con valor coercionado
    - unmatched: [{label, value}]           — no resolvieron contra ningún alias
    """
    from services.specs import coerce_and_serialize

    from ..parse.garbage import is_garbage

    if categoria_hint:
        from services.specs import REGISTRY

        cat_reg = REGISTRY.categorias.get(categoria_hint)
        index = _index_categoria(cat_reg) if cat_reg else _get_alias_index()
    else:
        index = _get_alias_index()

    matched: list[dict] = []
    unmatched: list[dict] = []
    seen_keys: set[str] = set()

    for pair in raw_pairs:
        raw_label = pair["label"]
        raw_value = pair["value"]

        if is_garbage(raw_value):
            continue

        nk = normalize_label(raw_label)
        spec_info = index.get(nk)

        if spec_info:
            spec_key = spec_info["spec_key"]
            if spec_key in seen_keys:
                continue
            seen_keys.add(spec_key)

            coerced = coerce_and_serialize(
                raw_value,
                spec_info["tipo"],
                spec_info["unidad"],
                spec_info["enum_options"],
            )
            matched.append({
                "spec_key": spec_key,
                "label": spec_info["label"],
                "value": coerced if coerced is not None else raw_value,
            })
        else:
            unmatched.append({"label": raw_label, "value": raw_value})

    return matched, unmatched
