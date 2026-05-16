#!/usr/bin/env python3
"""
tools/bh_luz_parser.py — Parser de HTMLs de B&H para productos de iluminación.

Uso:
    python tools/bh_luz_parser.py ~/Desktop/paginas/*.html
    python tools/bh_luz_parser.py ~/Desktop/paginas/amaran*.html

Qué hace:
  1. Parsea los HTMLs (guardados con Cmd+S desde B&H /specs) y extrae los pares
     label/value usando los atributos data-selenium del DOM.
  2. Guarda el raw (secciones B&H originales) en docs/bh_specs_relevamiento.json.
  3. Mapea a los spec_keys del proyecto (Iluminación) y guarda el curado en
     docs/bh_luces_curado.json.

Idempotente: si un producto (por id) ya existe en el JSON no lo pisa.
Si se quiere re-procesar un producto, borrar su entrada primero.
"""

import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

# ── Rutas de output ──────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
RELEVAMIENTO_PATH = ROOT / "docs" / "bh_specs_relevamiento.json"
CURADO_PATH = ROOT / "docs" / "bh_luces_curado.json"

# ── Parser HTML → secciones raw ─────────────────────────────────────────────


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
            if self._current_section and self._pending_label:
                key = f"{self._current_section}|{self._pending_label}|{text}"
                if key not in self._seen_pairs:
                    self._seen_pairs.add(key)
                    self.secciones.setdefault(self._current_section, []).append(
                        {"label": self._pending_label, "value": text}
                    )
            self._pending_label = None
            self._in_value = False


# ── Helpers de extracción ────────────────────────────────────────────────────


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

# Patrón de dimensiones tipo "2x1", "1x1", "4x4" — no son IDs de modelo
_DIMENSION_RE = re.compile(r"^\d+x\d+$", re.IGNORECASE)

# Patrón de specs eléctricas/físicas tipo "200W", "5600K", "8A" — no son IDs de modelo
# Nota: no incluir letras ambiguas como B/b que aparecen en modelos (Forza 60B, etc.)
_UNIT_SPEC_RE = re.compile(r"^\d+(?:\.\d+)?(?:W|V|A|K|kW|MHz|GHz|Hz|mm|cm|kg|g|lb|oz)$", re.IGNORECASE)


def _strip_title_prefixes(title: str) -> str:
    """Quita prefijos que no son parte del nombre del producto (ej. 'Used', 'Open Box')."""
    return re.sub(r"^(?:used|open\s+box|refurbished|demo)\s+", "", title, flags=re.IGNORECASE)


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

    # Prioridad 2: primer token no genérico (ej. "NOVA", "RAY", "ACCENT")
    if not model_token:
        for w in candidates:
            clean = re.sub(r"[^a-zA-Z0-9]", "", w).lower()
            if clean and clean not in _GENERIC_WORDS:
                model_token = clean
                break

    if model_token:
        return f"{brand}_{model_token}"
    return re.sub(r"[^a-z0-9_]", "_", title.lower())[:40]


def _extract_brand(title: str) -> str:
    word = title.strip().split()[0] if title.strip() else ""
    return word.capitalize() if word else ""


def _extract_modelo(title: str) -> str:
    """Todo el título menos la primera palabra (brand) y el SKU final si hay."""
    words = title.strip().split()
    if len(words) <= 1:
        return title
    # Quitar último token si parece un SKU (todo mayúsculas+dígitos, ≥6 chars)
    if re.fullmatch(r"[A-Z0-9]{6,}", words[-1]):
        words = words[:-1]
    return " ".join(words[1:])


def _extract_subtipo(secciones: dict) -> str:
    """Infiere el subtipo desde 'Item Type' + modos de color."""
    item_type = _find_value(secciones, "Item Type") or ""
    # Quitar prefijo de cantidad ("1x ", "2x ", etc.)
    item_type = re.sub(r"^\d+x\s+", "", item_type).strip()

    color_modes = _find_value(secciones, "Color Modes") or ""
    has_rgb = "RGB" in color_modes.upper()

    if item_type and has_rgb and "RGB" not in item_type:
        return f"{item_type} RGB"
    return item_type or "LED Light"


# ── Mapper raw → curado (spec_keys del proyecto) ─────────────────────────────


def _parse_potencia(secciones: dict) -> int | None:
    val = _find_value(
        secciones,
        "Power Consumption", "Wattage", "Max Power",
        "Max Bulb Wattage", "Bulb Wattage", "Lamp Wattage",
    )
    if not val:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*W", val)
    return int(float(m.group(1))) if m else None


def _parse_lumens(secciones: dict) -> int | None:
    val = _find_value(secciones, "Lumens", "Maximum Luminous Flux")
    if not val:
        return None
    # "19,389 (at 5600K)" → 19389
    m = re.search(r"([\d,]+)", val)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_cri(secciones: dict) -> int | None:
    val = _find_value(
        secciones, "Color Accuracy Standard", "CRI", "Color Rendering Index"
    )
    if val:
        m = re.search(r"CRI\s*(\d+)", val, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m2 = re.search(r"(\d+)", val)
        if m2:
            return int(m2.group(1))
    # Fallback: tungsteno/halógeno tiene CRI ~100 por definición física
    bulb = _find_value(secciones, "Bulb Type", "Lamp Type") or ""
    if re.search(r"GY9\.5|GY6\.35|G38|halogen|tungsten|incandescent", bulb, re.IGNORECASE):
        return 100
    return None


def _parse_temperatura(secciones: dict) -> str | None:
    val = _find_value(secciones, "Color Temperature")
    if not val:
        # Fallback: inferir desde Color Modes cuando es color fijo
        modes = (_find_value(secciones, "Color Modes") or "").strip()
        if modes.lower() == "tungsten":
            return "3200K"
        if modes.lower() == "daylight":
            return "5600K"
        return None
    # Tomar primera línea (puede haber varias para distintos modos)
    line = val.splitlines()[0].strip()
    # "2500 to 7500K" → "2500-7500K"
    line = re.sub(r"([\d,]+)\s+to\s+([\d,]+K?)", r"\1-\2", line, flags=re.IGNORECASE)
    # Quitar calificadores tipo "+/- 200K", "±200K" — solo si van precedidos de espacio
    line = re.sub(r"\s+[+\-±].{1,10}K$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\([^)]+\)$", "", line)
    # Asegurar que termina en K
    if not line.upper().endswith("K"):
        line = line + "K"
    # Limpiar comas en números: "20,000K" → "20000K"
    line = re.sub(r"(\d),(\d{3})", r"\1\2", line)
    return line


def _parse_bicolor(secciones: dict) -> bool:
    val = _find_value(secciones, "Color Modes") or ""
    if re.search(r"bi.?color", val, re.IGNORECASE):
        return True
    if "Daylight" in val and "Tungsten" in val:
        return True
    # Si tiene rango de temperatura que cruza tungsten (≤3500K) y daylight (≥5000K)
    temp = _find_value(secciones, "Color Temperature") or ""
    m = re.search(r"([\d,]+)\s*(?:to|-)\s*([\d,]+)", temp)
    if m:
        low = int(m.group(1).replace(",", ""))
        high = int(m.group(2).replace(",", ""))
        if low <= 3500 and high >= 5000:
            return True
    return False


def _parse_rgb(secciones: dict, title: str = "") -> bool:
    val = _find_value(secciones, "Color Modes") or ""
    if re.search(r"\bRGBW?W?\b", val, re.IGNORECASE):
        return True
    # Fallback: buscar en el título del producto (ej. "RGBWW" en el nombre)
    if re.search(r"\bRGBW?W?\b", title, re.IGNORECASE):
        return True
    return False


def _parse_dimming(secciones: dict) -> bool:
    # B&H usa "Dimming", "Dimmable", o "Built-In Dimmer" según el tipo de fixture
    val = _find_value(secciones, "Dimming", "Dimmable", "Built-In Dimmer") or ""
    return val.strip().lower() not in ("", "no", "none", "n/a")


def _parse_control_inalambrico(secciones: dict) -> str | None:
    # Buscar en varios campos
    sources = []
    for label in ("Wireless Remote Control Type", "Control", "Wireless"):
        v = _find_value(secciones, label)
        if v:
            sources.append(v)
    # Buscar DMX/Lumenradio en I/O
    for label in ("Inputs/Outputs", "Input/Output", "I/O"):
        v = _find_value(secciones, label)
        if v:
            sources.append(v)
    # Buscar en Dimming (puede mencionar "DMX")
    v = _find_value(secciones, "Dimming")
    if v:
        sources.append(v)

    combined = " ".join(sources)

    protocols = []
    for proto in ("Lumenradio", "CRMX", "Bluetooth", "Wi-Fi", "WiFi", "Zigbee", "2.4 GHz"):
        if proto.lower() in combined.lower():
            label = "Wi-Fi" if proto in ("WiFi", "Wi-Fi") else proto
            if label not in protocols:
                protocols.append(label)
    if re.search(r"\bDMX\b", combined, re.IGNORECASE):
        protocols.append("DMX")
    if re.search(r"\bRDM\b", combined, re.IGNORECASE):
        protocols.append("RDM")

    return ", ".join(protocols) if protocols else None


def _parse_alimentacion(secciones: dict) -> list[str]:
    """Devuelve lista de enum values del proyecto."""
    ENUM_MAP = {
        # B&H keyword → enum value del proyecto
        "v-mount": "V-mount",
        "v mount": "V-mount",
        "gold mount": "Gold Mount",
        "np-f": "NP-F",
        "np-f series": "NP-F",
        "d-tap": "D-Tap",
        "d tap": "D-Tap",
        "usb-c": "USB-C",
        "usb c": "USB-C",
        "ac": "AC",
        "ac adapter": "AC",
        "ac to dc": "AC",
        "wall outlet": "AC",
        "power outlet": "AC",
        "battery": "Batería integrada",
        "built-in battery": "Batería integrada",
        "integrated battery": "Batería integrada",
        "rechargeable": "Batería integrada",
    }

    sources = []
    for label in (
        "Power Source",
        "Battery Plate Type",
        "Battery Type",
        "Power",
        "Input Power",
        "Battery",
    ):
        v = _find_value(secciones, label)
        if v:
            sources.append(v.lower())

    combined = " | ".join(sources)
    found: list[str] = []
    seen: set[str] = set()

    for kw, enum_val in ENUM_MAP.items():
        if kw in combined and enum_val not in seen:
            found.append(enum_val)
            seen.add(enum_val)

    # Fallback: si Battery Plate Type menciona "V-Mount" explícitamente
    bpt = _find_value(secciones, "Battery Plate Type") or ""
    if "v-mount" in bpt.lower() and "V-mount" not in seen:
        found.append("V-mount")
        seen.add("V-mount")

    return found if found else ["AC"]  # default si no se puede inferir


def _parse_montaje(secciones: dict) -> str | None:
    # Si el fixture es un Fresnel, no tiene montaje de modificador estándar
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    lens_type = (_find_value(secciones, "Lens Type") or "").lower()
    if "fresnel" in item_type or "fresnel" in lens_type:
        return "Fresnel"

    val = _find_value(secciones, "Front Accessory Mount", "Accessory Mount", "Mounting")
    if not val:
        return None
    val_lower = val.lower()
    if "bowens" in val_lower:
        return "Bowens"
    if "profoto" in val_lower:
        return "Profoto"
    if "elinchrom" in val_lower:
        return "Elinchrom"
    if "proprietary" in val_lower or "propietario" in val_lower:
        return "Propietario"
    if "none" in val_lower or "n/a" in val_lower:
        return None
    # Ignorar valores que son stud/receiver (montaje de fixture, no de modificador)
    if re.search(r'\d/\d["\']|stud|receiver|yoke', val_lower):
        return None
    return val.split("\n")[0].strip()


def _parse_peso(secciones: dict) -> str | None:
    val = _find_value(secciones, "Weight")
    if not val:
        return None
    # Preferir valor en kg: "0.86 lb / 0.39 kg (Fixture)" → "390 g"
    # o "2.5 kg" → "2500 g"
    m_kg = re.search(r"([\d.]+)\s*kg", val, re.IGNORECASE)
    if m_kg:
        grams = round(float(m_kg.group(1)) * 1000)
        return f"{grams} g"
    # Si solo hay lb: convertir
    m_lb = re.search(r"([\d.]+)\s*lb", val, re.IGNORECASE)
    if m_lb:
        grams = round(float(m_lb.group(1)) * 453.592)
        return f"{grams} g"
    return val.strip()


# ── Extras (campos estructurados extra para ficha técnica) ───────────────────

_TIPO_KEYWORDS = [
    ("Fresnel", ["fresnel"]),
    ("Tube Light", ["tube light", "led tube"]),
    ("Flexible Mat", ["flexible mat", "flex mat"]),
    ("Panel", ["light panel", "led panel"]),
    ("COB Monolight", ["cob led monolight", "cob monolight"]),
    ("Monolight", ["led monolight", "monolight"]),
    ("Spotlight", ["spotlight"]),
    ("On-Camera", ["on-camera"]),
    ("Bulb / Lamp", ["led lamp", "lamp"]),
    ("Flash", ["flash", "speedlight", "strobe"]),
]


def _parse_tipo(secciones: dict, title: str = "") -> str | None:
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    haystack = f"{item_type} {title}".lower()
    for label, keywords in _TIPO_KEYWORDS:
        if any(k in haystack for k in keywords):
            return label
    return None


def _parse_beam_angle(secciones: dict) -> str | None:
    val = _find_value(secciones, "Beam Angle")
    if not val:
        return None
    # Tomar primera línea, ej. "55°" o "13 to 54°"
    line = val.splitlines()[0].strip()
    # "13 to 54°" → "13-54°"
    line = re.sub(r"(\d+)\s+to\s+(\d+)", r"\1-\2", line)
    return line


def _parse_cooling(secciones: dict) -> str | None:
    val = _find_value(secciones, "Cooling System")
    if not val:
        return None
    v = val.strip().lower()
    if "fan" in v:
        return "Fan"
    if "passive" in v:
        return "Passive"
    return val.strip()


def _parse_ip_rating(secciones: dict) -> str | None:
    val = _find_value(secciones, "Environmental Resistance", "IP Rating")
    if not val:
        return None
    m = re.search(r"IP\d{2}", val)
    return m.group(0) if m else val.strip()


def _parse_dimensiones(secciones: dict) -> str | None:
    val = _find_value(secciones, "Dimensions", "Dimensions (W x H x D)")
    if not val:
        return None
    # Preferir parte métrica: "23.6 x 11.8 x 0.2\" / 60 x 30 x 0.5 cm (Fixture)" → "60 × 30 × 0.5 cm"
    m = re.search(r"([\d.]+\s*x\s*[\d.]+(?:\s*x\s*[\d.]+)?)\s*cm", val, re.IGNORECASE)
    if m:
        return m.group(1).replace("x", "×") + " cm"
    m_mm = re.search(r"([\d.]+\s*x\s*[\d.]+(?:\s*x\s*[\d.]+)?)\s*mm", val, re.IGNORECASE)
    if m_mm:
        return m_mm.group(1).replace("x", "×") + " mm"
    return val.split("\n")[0].strip()


def _parse_photometrics(secciones: dict) -> str | None:
    """Lux/fc a 1m — output real del fixture. B&H lo formatea raro, devolvemos limpio."""
    val = _find_value(secciones, "Photometrics at 3.3' / 1 m", "Photometrics")
    if not val:
        return None
    # Quedarnos con la primera línea útil (descartar ":" sueltos)
    for line in val.splitlines():
        line = line.strip()
        if line and line != ":" and "Lux" in line:
            return line
    return val.splitlines()[0].strip() if val else None


def _parse_tlci(secciones: dict) -> int | None:
    val = _find_value(secciones, "Color Accuracy Standard")
    if not val:
        return None
    m = re.search(r"TLCI\s*(\d+)", val, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_app_compatible(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Mobile App Compatible")
    if not val:
        return None
    return val.strip().lower().startswith(("yes", "sí", "si"))


def _parse_display(secciones: dict) -> str | None:
    val = _find_value(secciones, "Display")
    if not val:
        return None
    v = val.strip()
    if v.lower() in ("no", "none"):
        return None
    return v


def map_luz_extras(secciones: dict, title: str = "") -> dict:
    """Campos extra estructurados para ficha técnica (no son para comparación primaria)."""
    result: dict = {}

    def _add(key, val):
        if val is not None and val != "":
            result[key] = val

    _add("tipo", _parse_tipo(secciones, title))
    _add("beam_angle", _parse_beam_angle(secciones))
    _add("cooling", _parse_cooling(secciones))
    _add("ip_rating", _parse_ip_rating(secciones))
    _add("dimensiones", _parse_dimensiones(secciones))
    _add("photometrics_1m", _parse_photometrics(secciones))
    _add("tlci", _parse_tlci(secciones))
    _add("app_compatible", _parse_app_compatible(secciones))
    _add("display", _parse_display(secciones))

    # Otros campos útiles directos del raw
    for src_label, dst_key in [
        ("Item Type", "item_type"),
        ("Included Light Modifier", "modificador_incluido"),
        ("Included Storage Case", "case_incluido"),
        ("Bulb Type", "bulb_type"),
        ("Base Type", "base_type"),
        ("Expected Lamp Life", "vida_util_horas"),
        ("Yoke Type", "yoke"),
        ("Fixture Mounting", "fixture_mount"),
        ("Cable Length", "cable_length"),
        ("Materials", "materiales"),
        ("Certifications", "certificaciones"),
        ("Wireless Range", "wireless_range"),
        ("Inputs/Outputs", "io"),
    ]:
        v = _find_value(secciones, src_label)
        if v:
            result[dst_key] = v.split("\n")[0].strip() if "\n" in v else v.strip()

    return result


def map_luz_specs(secciones: dict, title: str = "") -> dict:
    """Mapea secciones raw de B&H → spec_keys del proyecto para Iluminación."""
    result: dict = {}

    potencia = _parse_potencia(secciones)
    if potencia is not None:
        result["potencia_w"] = potencia

    lumens = _parse_lumens(secciones)
    if lumens is not None:
        result["lumens"] = lumens

    cri = _parse_cri(secciones)
    if cri is not None:
        result["cri"] = cri

    temperatura = _parse_temperatura(secciones)
    if temperatura:
        result["temperatura_k"] = temperatura

    result["bicolor"] = _parse_bicolor(secciones)
    result["rgb"] = _parse_rgb(secciones, title)
    result["dimming"] = _parse_dimming(secciones)

    control = _parse_control_inalambrico(secciones)
    if control:
        result["control_inalambrico"] = control

    alimentacion = _parse_alimentacion(secciones)
    if alimentacion:
        result["alimentacion"] = alimentacion

    montaje = _parse_montaje(secciones)
    if montaje:
        result["montaje"] = montaje

    peso = _parse_peso(secciones)
    if peso:
        result["peso"] = peso

    return result


# ── Procesamiento de archivos ────────────────────────────────────────────────


def parse_html(path: Path) -> dict:
    """Parsea un .html de B&H y devuelve el dict raw del producto."""
    content = path.read_text(encoding="utf-8", errors="replace")

    # Extraer título con regex (más robusto que acumular en el parser)
    title_m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else path.stem
    title = _strip_title_prefixes(title)

    parser = BHSpecsParser()
    parser.feed(content)

    prod_id = _extract_id(title)
    brand = _extract_brand(title)
    modelo = _extract_modelo(title)
    subtipo = _extract_subtipo(parser.secciones)

    return {
        "id": prod_id,
        "categoria_raiz": "Iluminación",
        "subtipo": subtipo,
        "marca": brand,
        "modelo": modelo,
        "url_source": parser.url or "",
        "status_bh": "Desconocido",
        "fuente": f"html guardado manual ({date.today().isoformat()})",
        "secciones": parser.secciones,
    }


# ── Persistencia ─────────────────────────────────────────────────────────────

_RELEVAMIENTO_META = {
    "version": "1.0",
    "descripcion": (
        "Dataset crudo de specs reales de B&H Photo capturadas por html guardado manual. "
        "Cada producto guarda: categoría, marca, modelo, secciones de B&H, y pares "
        "(label, value) tal cual aparecen. Se usa para análisis del catálogo normalizado."
    ),
    "metodo_captura": "HTML guardado manualmente (Cmd+S → Webpage Complete) desde B&H /specs",
    "uso": (
        "Cuando haya 5-10 productos por categoría, sintetizar para refinar catálogo: "
        "detectar specs nuevas, calibrar enum_options, identificar compuestos que "
        "necesitan parser o tabla."
    ),
    "convencion": {
        "secciones": (
            "B&H usa estas secciones por categoría: Key Specs / Light Fixture / "
            "Connectivity / Power & I/O / Mounting / General / Packaging Info"
        ),
        "values_compuestos": (
            "Cuando un value tiene formato 'X / Y (descripcion)', se preserva tal cual."
        ),
        "categoria_inferida": "Inferida del Item Type + nombre del producto",
    },
}


def load_relevamiento() -> dict:
    if RELEVAMIENTO_PATH.exists():
        return json.loads(RELEVAMIENTO_PATH.read_text(encoding="utf-8"))
    return {"_meta": _RELEVAMIENTO_META, "products": [], "_analisis_pendiente": []}


def save_relevamiento(data: dict):
    RELEVAMIENTO_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_curado() -> dict:
    if CURADO_PATH.exists():
        return json.loads(CURADO_PATH.read_text(encoding="utf-8"))
    return {"_meta": {"descripcion": "Specs curadas mapeadas a spec_keys del proyecto."}, "products": {}}


def save_curado(data: dict):
    CURADO_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Main ─────────────────────────────────────────────────────────────────────


def main(html_paths: list[Path]):
    relevamiento = load_relevamiento()
    curado = load_curado()

    existing_ids = {p["id"] for p in relevamiento["products"]}

    added_raw = 0
    added_curado = 0
    skipped = 0

    for path in html_paths:
        if not path.exists():
            print(f"  ⚠  No existe: {path}")
            continue

        print(f"Procesando: {path.name}")
        raw = parse_html(path)
        prod_id = raw["id"]

        # Raw: append si no existe
        if prod_id in existing_ids:
            print(f"  → raw ya existe ({prod_id}), skip")
            skipped += 1
        else:
            relevamiento["products"].append(raw)
            existing_ids.add(prod_id)
            added_raw += 1
            print(f"  + raw agregado ({prod_id})")

        # Curado: siempre regenerar (para reflectar el mapper actualizado)
        specs = map_luz_specs(raw["secciones"], title=raw["modelo"])
        extras = map_luz_extras(raw["secciones"], title=raw["modelo"])
        curado["products"][prod_id] = {
            "marca": raw["marca"],
            "modelo": raw["modelo"],
            "url_source": raw.get("url_source", ""),
            "specs": specs,         # 11 normalizados para comparación
            "extras": extras,        # campos estructurados extra (tipo, beam_angle, etc.)
            "ficha": raw["secciones"],  # todas las secciones B&H completas
        }
        added_curado += 1
        print(f"  + curado: {specs}")

    save_relevamiento(relevamiento)
    save_curado(curado)

    print(f"\nListo. Raw nuevos: {added_raw} | Curado: {added_curado} | Skipped: {skipped}")
    print(f"  → {RELEVAMIENTO_PATH.relative_to(ROOT)}")
    print(f"  → {CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/bh_luz_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(Path(arg).parent.glob(Path(arg).name) if "*" in arg else [Path(arg)])

    main(paths)
