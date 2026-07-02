"""parsers/base.py — BHSpecsParser + helpers compartidos entre los 4 parsers.

Movido de tools/iluminacion_parser.py (F3 del rediseño de ingesta): antes
camaras_parser.py/lentes_parser.py/modificadores_parser.py importaban estas
piezas de "iluminacion_parser" porque ese archivo fue el primero en
escribirse, no porque BHSpecsParser sea conceptualmente de iluminación. Acá
queda sin dueño de categoría — lo que realmente es.

BHSpecsParser lee la estructura data-selenium específica de B&H (más rica
que el fallback DOM genérico de specs_ingesta/parse/dom.py, que no asume
nada de la estructura de B&H)."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


class BHSpecsParser(HTMLParser):
    """Extrae secciones de specs de un HTML guardado de B&H /specs."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.url = ""
        self.secciones: dict[str, list[dict]] = {}
        self._current_section: str | None = None
        self._in_label = False
        self._in_value = False
        self._pending_label: str | None = None
        self._in_title = False
        self._seen_pairs: set[str] = set()  # dedup (el DOM se repite)

    def handle_comment(self, data: str):
        m = re.search(r"saved from url=\(\d+\)(https?://\S+)", data)
        if m:
            self.url = m.group(1).strip()

    def handle_starttag(self, tag: str, attrs):
        attrs_d = dict(attrs)
        sel = attrs_d.get("data-selenium", "")
        if tag == "title":
            self._in_title = True
        elif sel == "specsItemGroupName":
            self._in_label = True
            self._pending_label = None
            self._current_section = "__GROUP__"
        elif sel == "specsItemGroupTableColumnLabel":
            self._in_label = True
            self._pending_label = None
            # Si no hay sección activa, usar sección genérica
            if not self._current_section or self._current_section == "__GROUP__":
                self._current_section = "Specs"
                self.secciones.setdefault("Specs", [])
        elif sel == "specsItemGroupTableColumnValue":
            self._in_value = True

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str):
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
            return
        if self._in_label:
            if self._current_section == "__GROUP__":
                # Esto es el nombre de la sección
                self._current_section = text
                if text not in self.secciones:
                    self.secciones[text] = []
            else:
                self._pending_label = text
            self._in_label = False
        elif self._in_value:
            # Filtrar valores basura: "1 x", "1x", ":" sueltos vienen de celdas
            # B&H con solo imagen y sin texto. "Not Specified by Manufacturer" tampoco aporta.
            is_garbage = (
                text in ("1 x", "1x", ":", "—", "-", "N/A", "n/a")
                or text.lower().startswith("not specified")
            )
            if self._current_section and self._pending_label and not is_garbage:
                key = f"{self._current_section}|{self._pending_label}|{text}"
                if key not in self._seen_pairs:
                    self._seen_pairs.add(key)
                    self.secciones.setdefault(self._current_section, []).append(
                        {"label": self._pending_label, "value": text}
                    )
            self._pending_label = None
            self._in_value = False


def _find_value(secciones: dict, *labels: str) -> str | None:
    """Busca un label (case-insensitive) en todas las secciones, devuelve primer match."""
    targets = {l.lower() for l in labels}
    for section_items in secciones.values():
        for item in section_items:
            if item["label"].lower() in targets:
                return item["value"]
    return None


_GENERIC_WORDS = {
    "rgb", "rgbww", "led", "bi-color", "bicolor", "mini", "creative",
    "on-camera", "video", "light", "lighting", "gray", "black", "white",
    "the", "and", "with", "for",
}


_DIMENSION_RE = re.compile(r"^\d+x\d+$", re.IGNORECASE)


_UNIT_SPEC_RE = re.compile(r"^\d+(?:\.\d+)?(?:W|V|A|K|kW|MHz|GHz|Hz|mm|cm|kg|g|lb|oz)$", re.IGNORECASE)


def _clean_title(title: str) -> str:
    """Decodifica entities, quita prefijos (Used, Open Box) y sufijos B&H."""
    title = html.unescape(title)
    # Quitar prefijos
    title = re.sub(r"^(?:used|open\s+box|refurbished|demo)\s+", "", title, flags=re.IGNORECASE)
    # Quitar sufijos típicos de B&H/sitios (en orden de más específico a menos)
    title = re.sub(r"\s+(?:B&H|BH)\s+Photo(?:\s+Video)?\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+Photo\s+Video\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+(?:B&H|BH)\.?\s*$", "", title, flags=re.IGNORECASE)
    # Quitar SKU final con guiones (ej. "8941-50REV", "AP00000-191")
    title = re.sub(r"\s+[A-Z0-9]+-[A-Z0-9-]+\s*$", "", title)
    return title.strip()


_strip_title_prefixes = _clean_title


def _extract_id(title: str) -> str:
    """Genera un id snake_case desde el título del producto.

    Estrategia: brand (primera palabra) + primer token que parezca modelo
    (contiene dígitos, no es genérico). Fallback a segunda palabra.

    Ej: "amaran F21x 2x1 Bi-Color LED Flexible Mat" → "amaran_f21x"
        "Godox TL60 RGB LED Tube Light"              → "godox_tl60"
        "Godox RGB Mini Creative M1 On-Camera ..."   → "godox_m1"
    """
    words = title.strip().split()
    if not words:
        return "unknown"
    brand = re.sub(r"[^a-zA-Z0-9]", "", words[0]).lower()

    # Buscar en las primeras 4 palabras tras el brand (los SKUs van al final del título)
    candidates = words[1:5]

    # Prioridad 1: token con letras Y dígitos, no genérico, no dimensión (ej. "TL60", "F21x")
    model_token = None
    for w in candidates:
        clean = re.sub(r"[^a-zA-Z0-9]", "", w).lower()
        if (clean
                and re.search(r"\d", clean)
                and re.search(r"[a-z]", clean)
                and clean not in _GENERIC_WORDS
                and not _DIMENSION_RE.match(clean)
                and not _UNIT_SPEC_RE.match(clean)):
            model_token = clean
            break

    # Prioridad 2: primer token no genérico (ej. "NOVA", "RAY", "ACCENT", "Forza")
    if not model_token:
        for i, w in enumerate(candidates):
            clean = re.sub(r"[^a-zA-Z0-9]", "", w).lower()
            if clean and clean not in _GENERIC_WORDS:
                # Si el siguiente token es un número (ej. "Forza 500"), incorporarlo
                # para diferenciar productos de la misma familia.
                if i + 1 < len(candidates):
                    next_w = re.sub(r"[^a-zA-Z0-9]", "", candidates[i + 1]).lower()
                    if next_w.isdigit():
                        clean = f"{clean}_{next_w}"
                model_token = clean
                break

    if model_token:
        return f"{brand}_{model_token}"
    return re.sub(r"[^a-z0-9_]", "_", title.lower())[:40]


def _extract_brand(title: str) -> str:
    word = title.strip().split()[0] if title.strip() else ""
    return word.capitalize() if word else ""


def _extract_modelo(title: str) -> str:
    """Todo el título menos la primera palabra (brand) y SKU duplicado al final."""
    words = title.strip().split()
    if len(words) <= 1:
        return title

    # Quitar último token si parece un SKU (todo mayúsculas+dígitos, ≥6 chars)
    while words and re.fullmatch(r"[A-Z0-9]{6,}", words[-1]):
        words = words[:-1]

    # Si el último token es igual a algún token previo (SKU/modelo repetido), quitarlo
    if len(words) > 2 and words[-1].upper() in {w.upper() for w in words[1:-1]}:
        words = words[:-1]

    return " ".join(words[1:])


def _parse_peso_g(secciones: dict) -> int | None:
    """Weight → int gramos. Prioridad de unidades: g (directo) > kg > lb.

    B&H suele listar imperial+métrico ('1.5 lb / 695 g'). Preferimos siempre
    el valor métrico directo — convertir desde lb pierde precisión
    (1.5 lb → 680 g ≠ los 695 g del fabricante)."""
    val = _find_value(secciones, "Weight")
    if not val:
        return None
    m_g = re.search(r"([\d.]+)\s*g\b", val, re.IGNORECASE)
    if m_g:
        return int(float(m_g.group(1)))
    m_kg = re.search(r"([\d.]+)\s*kg", val, re.IGNORECASE)
    if m_kg:
        return round(float(m_kg.group(1)) * 1000)
    m_lb = re.search(r"([\d.]+)\s*lb", val, re.IGNORECASE)
    if m_lb:
        return round(float(m_lb.group(1)) * 453.592)
    return None


_parse_peso = _parse_peso_g
