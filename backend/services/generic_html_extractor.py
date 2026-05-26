"""services/generic_html_extractor.py — Extractor agnóstico de categoría.

Para categorías SIN parser bespoke (Modificadores, Cables, Audio, etc.),
extrae TODOS los pares {label: value} del HTML y los resuelve contra el
registry de specs vía aliases. Lo que no resuelve → "sin template" visible
en el form admin (cero descartes silenciosos).

Agregar una categoría nueva = crear specs/categorias/<nueva>.py + registrarla
en REGISTRY. Cero código nuevo en este módulo.

Punto de entrada:
    extract_from_html_generic(html_content, categoria_hint=None) -> dict
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


# ── Normalización de labels (igual a la de _matchear_y_persistir_specs) ──────

def _normalize_label(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("_", " ")
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


# ── Índice de aliases (lazy, cacheado por proceso) ───────────────────────────

_ALIAS_INDEX: dict[str, dict] | None = None


def _build_alias_index() -> dict[str, dict]:
    """Construye índice normalizado_label → spec_info desde TODO el registry.

    spec_info contiene: spec_key, label, tipo, unidad, enum_options.
    Incluye: label canónico, spec_key y todos los aliases declarados.
    """
    from specs import REGISTRY

    index: dict[str, dict] = {}
    for cat_reg in REGISTRY.categorias.values():
        for spec in cat_reg.specs:
            info = {
                "spec_key": spec.key,
                "label": spec.label,
                "tipo": spec.tipo,
                "unidad": spec.unidad,
                "enum_options": spec.enum_options,
            }
            # Label canónico y spec_key como entradas
            for key in (_normalize_label(spec.label), _normalize_label(spec.key)):
                if key not in index:
                    index[key] = info
            # Aliases
            for alias in spec.aliases:
                nk = _normalize_label(alias)
                if nk not in index:
                    index[nk] = info
    return index


def _get_alias_index() -> dict[str, dict]:
    global _ALIAS_INDEX
    if _ALIAS_INDEX is None:
        try:
            _ALIAS_INDEX = _build_alias_index()
        except Exception as exc:
            logger.warning("generic_extractor: no se pudo construir alias index: %s", exc)
            _ALIAS_INDEX = {}
    return _ALIAS_INDEX


# ── Extracción de pares crudos ────────────────────────────────────────────────

def _extract_from_jsonld(html_content: str) -> list[dict[str, str]]:
    """Extrae pares {label, value} desde JSON-LD Product.additionalProperty."""
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    pairs: list[dict[str, str]] = []
    seen: set[str] = set()
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if not (isinstance(data, dict) and data.get("@type") == "Product"):
            continue
        ap = data.get("additionalProperty", {})
        props = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
        for pv in props:
            if not isinstance(pv, dict):
                continue
            name = pv.get("name")
            value = pv.get("value")
            if not name or name in seen:
                continue
            seen.add(name)
            if isinstance(value, list):
                val_str = ", ".join(
                    html_lib.unescape(str(v).replace(" ", " "))
                    for v in value if str(v).strip()
                )
            elif isinstance(value, str):
                val_str = html_lib.unescape(value.replace(" ", " "))
            else:
                val_str = str(value) if value is not None else ""
            if val_str.strip():
                pairs.append({"label": name, "value": val_str.strip()})
        break  # solo el primer bloque Product
    return pairs


class _TableParser(HTMLParser):
    """Parser HTML minimalista: extrae pares de tablas <tr><th>L</th><td>V</td></tr>
    y listas de definición <dl><dt>L</dt><dd>V</dd></dl>.
    """

    def __init__(self) -> None:
        super().__init__()
        self.pairs: list[dict[str, str]] = []
        self._tag_stack: list[str] = []
        self._pending_label: str | None = None
        self._buf: str = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._tag_stack.append(tag)
        if tag in ("th", "dt"):
            self._buf = ""
            self._pending_label = None
        elif tag in ("td", "dd"):
            self._buf = ""

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        text = html_lib.unescape(self._buf.replace(" ", " ").strip())
        if tag in ("th", "dt") and text:
            self._pending_label = text
        elif tag in ("td", "dd") and text and self._pending_label:
            self.pairs.append({"label": self._pending_label, "value": text})
            self._pending_label = None
        self._buf = ""

    def handle_data(self, data: str) -> None:
        if self._tag_stack and self._tag_stack[-1] in ("th", "td", "dt", "dd"):
            self._buf += data


def _extract_from_dom(html_content: str) -> list[dict[str, str]]:
    """Extrae pares {label, value} de tablas y listas de definición del DOM."""
    parser = _TableParser()
    try:
        parser.feed(html_content)
    except Exception:
        pass
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for p in parser.pairs:
        if p["label"] not in seen:
            seen.add(p["label"])
            unique.append(p)
    return unique


def extract_raw_pairs(html_content: str) -> list[dict[str, str]]:
    """Extrae TODOS los pares {label, value} del HTML.

    Fuente primaria: JSON-LD additionalProperty.
    Fuente secundaria: tablas y dl del DOM (complementa lo que JSON-LD no tiene).
    Primera aparición de cada label gana.
    """
    jsonld = _extract_from_jsonld(html_content)
    seen = {p["label"] for p in jsonld}

    dom = _extract_from_dom(html_content)
    extra = [p for p in dom if p["label"] not in seen]

    return jsonld + extra


# ── Resolución de aliases → spec_keys ────────────────────────────────────────

_GARBAGE_VALUES = frozenset({"1 x", "1x", "—", "-", "n/a", "", "not specified"})


def _is_garbage(v: str) -> bool:
    v = v.strip().lower()
    return v in _GARBAGE_VALUES or v.startswith("not specified")


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
    from services.spec_coerce import coerce_and_serialize

    if categoria_hint:
        from specs import REGISTRY
        cat_reg = REGISTRY.categorias.get(categoria_hint)
        if cat_reg:
            index: dict = {}
            for spec in cat_reg.specs:
                info = {
                    "spec_key": spec.key,
                    "label": spec.label,
                    "tipo": spec.tipo,
                    "unidad": spec.unidad,
                    "enum_options": spec.enum_options,
                }
                for key in (_normalize_label(spec.label), _normalize_label(spec.key)):
                    index.setdefault(key, info)
                for alias in spec.aliases:
                    index.setdefault(_normalize_label(alias), info)
        else:
            index = _get_alias_index()
    else:
        index = _get_alias_index()
    matched: list[dict] = []
    unmatched: list[dict] = []
    seen_keys: set[str] = set()

    for pair in raw_pairs:
        raw_label = pair["label"]
        raw_value = pair["value"]

        if _is_garbage(raw_value):
            continue

        nk = _normalize_label(raw_label)
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


# ── Helpers JSON-LD (imagen, URL, título) ─────────────────────────────────────

def _jsonld_image(html_content: str) -> str | None:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            img = data.get("image")
            if isinstance(img, list) and img:
                return img[0]
            if isinstance(img, str):
                return img
    return None


def _jsonld_url(html_content: str) -> str | None:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            url = data.get("url")
            if isinstance(url, str):
                return url
    return None


def _jsonld_brand_name(html_content: str) -> str:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            brand = data.get("brand")
            if isinstance(brand, dict):
                return brand.get("name") or ""
            if isinstance(brand, str):
                return brand
    return ""


# ── Entrada principal ─────────────────────────────────────────────────────────

def extract_from_html_generic(
    html_content: str,
    categoria_hint: str | None = None,
) -> dict:
    """Extrae specs de un HTML sin parser bespoke.

    Flujo:
    1. Extrae pares crudos (JSON-LD + DOM tables).
    2. Resuelve cada label contra el registry de aliases.
    3. Matched → specs con spec_key + valor coercionado.
    4. Unmatched → specs con spec_key provisional (label normalizado),
       se muestran como "sin template" en el form admin.

    Compatible con el contrato AutocompletarResult.
    """
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    image = _jsonld_image(html_content)
    url = _jsonld_url(html_content) or ""
    marca = _jsonld_brand_name(html_content)
    if not marca:
        # Fallback heurístico: primera palabra del título
        marca = title.split()[0] if title else ""
    modelo = title

    raw_pairs = extract_raw_pairs(html_content)
    matched, unmatched = resolve_pairs(raw_pairs, categoria_hint)

    # Unmatched: generamos un spec_key provisional del label normalizado para
    # que el frontend pueda mostrar el badge "sin template" (no descartamos nada).
    specs: list[dict] = list(matched)
    for pair in unmatched:
        provisional_key = re.sub(r"[^a-z0-9]+", "_", pair["label"].lower()).strip("_") or "unknown"
        specs.append({
            "spec_key": provisional_key,
            "label": pair["label"],
            "value": pair["value"],
        })

    try:
        from services.nombre_builder import compute_keywords
        matched_specs_dict = {s["spec_key"]: s["value"] for s in matched}
        keywords: list[str] = compute_keywords(matched_specs_dict)
    except Exception:
        keywords = []

    return {
        "marca": marca,
        "modelo": modelo,
        "nombre_normalizado": f"{marca} {modelo}".strip(),
        "descripcion": "",
        "specs": specs,
        "keywords": keywords,
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        "peso": None,
        "dimensiones": None,
        "montura": None,
        "formato": None,
        "resolucion": None,
        "alimentacion": None,
        "incluye": [],
        "conectividad": [],
        "compatible_con": [],
        "video_url": None,
        "precio_bh_usd": None,
        "categoria_sugerida": categoria_hint,
        "fuente_url": url,
        "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": "html-upload (generic extractor)",
        "bh_url": url,
        "extras": {},
        "fuente": "html-upload",
        "raw_secciones": {},
    }
