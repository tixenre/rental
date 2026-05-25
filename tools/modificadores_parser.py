#!/usr/bin/env python3
"""
tools/modificadores_parser.py — Parser de HTMLs B&H para modificadores
de luz (softbox / spotlight / fresnel / difusión).

Mismo patrón que iluminacion_parser/lentes_parser. La carpeta
~/Desktop/Paginas/Modificadores_Luz/ tiene 7 HTMLs (5 B&H + 2 sitios
del fabricante).

Reusa primitives de iluminacion_parser (BHSpecsParser, _clean_title,
_extract_brand, _extract_id, _find_value, _parse_peso_g).

Outputs:
  - docs/modificadores_raw.json    → relevamiento completo (secciones B&H)
  - docs/modificadores.json        → curado con los 12 specs del registry

Uso:
    python3 tools/modificadores_parser.py ~/Desktop/Paginas/Modificadores_Luz/*.html
"""

import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path

from iluminacion_parser import (  # type: ignore
    BHSpecsParser,
    _clean_title,
    _extract_brand,
    _extract_id,
    _extract_modelo,
    _find_value,
    _parse_peso_g,
)

ROOT = Path(__file__).parent.parent

RAW_PATH = ROOT / "docs" / "modificadores_raw.json"
CURADO_PATH = ROOT / "docs" / "modificadores.json"


# ─── Mappers raw → curado ─────────────────────────────────────────────

# Pistas en "Item Type" → subtipo + forma. El subtipo va al campo
# `modificador_subtipo` (enum del registry); la forma al campo `forma`.
# Si el HTML no tiene Item Type (Spotlight Kit, Fresnel Lens, etc.) el
# subtipo se infiere por keywords del título.

_FORMA_KEYWORDS = [
    # Orden: específico antes que genérico. "hexadecagon" antes que "octa".
    ("hexadecagon", "Hexadecagon"),
    ("16-sided", "Hexadecagon"),
    ("parabolic", "Parabolic"),
    ("octagonal", "Octagonal"),
    ("octa-", "Octagonal"),
    ("lantern", "Lantern Round"),
    ("rounded", "Lantern Round"),
    ("strip", "Strip"),
    ("square", "Square"),
    ("rectangular", "Rectangle"),
    ("rectangle", "Rectangle"),
    ("oval", "Oval"),
    ("deep", "Deep"),
]


def _parse_subtipo(secciones: dict, title: str) -> str | None:
    """Infiere modificador_subtipo (rol/función). La forma geométrica va
    aparte en `_parse_forma`. Enum del registry:
    Softbox, Spotlight, Fresnel, Difusor, Bandera Negra, Reflector."""
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    title_l = title.lower()

    # Softbox incluye Lantern (que es un Softbox con forma Lantern Round).
    if "softbox" in item_type or "softbox" in title_l or "lantern" in item_type or "lantern" in title_l:
        return "Softbox"
    if "spotlight" in title_l or "spotlight" in item_type:
        return "Spotlight"
    if "fresnel" in title_l or "fresnel" in item_type:
        return "Fresnel"
    if "reflector" in title_l:
        return "Reflector"
    if "bandera" in title_l or "flag" in title_l:
        return "Bandera Negra"
    if "difus" in title_l or "diffus" in title_l or "frame" in title_l:
        return "Difusor"
    # Fallback: si tiene "Light Compatibility" probablemente sea Softbox.
    if _find_value(secciones, "Light Compatibility"):
        return "Softbox"
    return None


def _parse_forma(secciones: dict, title: str) -> str | None:
    """Forma geométrica. Aplica sobre todo a Softbox/Lantern."""
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    title_l = title.lower()
    haystack = f"{item_type} {title_l}"
    for kw, label in _FORMA_KEYWORDS:
        if kw in haystack:
            return label
    return None


def _parse_diametro_cm(secciones: dict) -> int | None:
    """Diámetro en cm desde 'Dimensions' (ø: NN cm) o 'Diameter'.
    Solo aplica si el modificador es redondo (softbox parabólico,
    octagonal, lantern)."""

    def _extract_cm(text: str) -> int | None:
        """B&H suele dar 'imperial / métrico' separado por '/'. Tomamos
        siempre la parte métrica si hay separador — el primer ø antes
        del '/' está en pulgadas y nos confundía."""
        if "/" in text:
            text = text.split("/", 1)[1]
        # Después del split, buscar el primer número antes de "cm".
        m = re.search(r"ø:?\s*([\d.]+)", text, re.IGNORECASE)
        if m and "cm" in text.lower():
            return round(float(m.group(1)))
        # Fallback: cualquier número seguido de cm.
        m2 = re.search(r"([\d.]+)\s*cm", text)
        if m2:
            return round(float(m2.group(1)))
        return None

    # Caso 1: campo Diameter directo (Fresnel Lens)
    dia = _find_value(secciones, "Diameter")
    if dia:
        v = _extract_cm(dia)
        if v is not None:
            return v
    # Caso 2: Dimensions con prefijo Ø
    dim = _find_value(secciones, "Dimensions") or ""
    return _extract_cm(dim)


def _parse_dimensiones(secciones: dict) -> str | None:
    """Dimensiones en formato compacto métrico. Extrae la parte cm de
    'Dimensions' o 'Diameter'. Útil para softboxes hexagonales /
    rectangulares (donde diametro_cm no aplica)."""
    dim = _find_value(secciones, "Dimensions")
    if not dim:
        return None
    # "ø: 35 x H: 23.6" / ø: 89 x H: 60 cm (Open)" → "ø: 89 x H: 60 cm (Open)"
    # "9.3" / 23.6 cm" → "23.6 cm"
    # Estrategia: tomar lo que está después del primer "/" si hay split imperial/metric.
    if "/" in dim:
        after = dim.split("/", 1)[1].strip()
        # Conservar paréntesis tipo "(Open)" si están al final
        return after if after else dim
    return dim.strip()


_MOUNT_KEYWORDS = [
    # Nanlite Forza, Aputure Storm/600x, etc. usan Bowens estándar.
    # "for Forza 300/500" en un título indica compatibilidad, no un mount
    # propietario — mapeamos a Bowens.
    ("forza", "Bowens"),
    ("storm", "Bowens"),
    ("bowens", "Bowens"),
    ("elinchrom", "Elinchrom"),
    ("profoto", "Profoto"),
    ("proprietary", "Propietario"),
    ("propietario", "Propietario"),
]


def _parse_montura_luz(secciones: dict, title: str) -> str | None:
    """Detecta montura desde 'Light Compatibility', 'Mounting' o título."""
    raw = (
        (_find_value(secciones, "Light Compatibility") or "")
        + " "
        + (_find_value(secciones, "Mounting") or "")
        + " "
        + title
    ).lower()
    if not raw.strip():
        return None
    for kw, label in _MOUNT_KEYWORDS:
        if kw in raw:
            return label
    return None


def _parse_yes_no(secciones: dict, *labels: str) -> bool | None:
    """Convierte 'Yes (Included)' / 'No' a bool. None si no hay campo."""
    val = _find_value(secciones, *labels)
    if val is None:
        return None
    v = val.strip().lower()
    if v.startswith("yes"):
        return True
    if v.startswith("no"):
        return False
    return None


def _parse_incluye_grid(secciones: dict) -> bool | None:
    """`incluye_grid` significa 'viene CON grid en el kit', no 'lo acepta'.
    B&H distingue 'Yes (Included)' (sí lo tenemos) vs 'Yes (Not Included)'
    (acepta pero el grid se compra aparte → no lo tenemos)."""
    val = _find_value(secciones, "Accepts Grids", "Includes Grid", "Grid")
    if val is None:
        return None
    v = val.strip().lower()
    if "not included" in v:
        return False
    if v.startswith("yes"):
        return True
    if v.startswith("no"):
        return False
    return None


def _parse_plegable(secciones: dict) -> bool | None:
    """'Quick Open Type: Foldable' / 'Click/Locking Type' → True.
    Si dice 'Fixed' o no aparece → None (no podemos asegurar No)."""
    val = _find_value(secciones, "Quick Open Type")
    if val is None:
        return None
    v = val.lower()
    if "foldable" in v or "click" in v or "lock" in v or "quick" in v:
        return True
    if "fixed" in v or "rigid" in v:
        return False
    return None


def _parse_light_loss(secciones: dict) -> float | None:
    """'Light Loss/Gain: 1-Stop Loss' → 1.0 (en stops).
    '2-Stop Loss' → 2.0. 'No' → 0.0 (sin pérdida medida). 'Gain'
    devuelve número negativo. None si el HTML no tiene el campo."""
    val = _find_value(secciones, "Light Loss/Gain", "Light Loss")
    if val is None:
        return None
    v = val.strip()
    if v.lower() in ("no", "none", "n/a", ""):
        return 0.0
    m = re.search(r"([\d.]+)[-\s]*stop", v, re.IGNORECASE)
    if m:
        n = float(m.group(1))
        return -n if "gain" in v.lower() else n
    return None


def _parse_materiales(secciones: dict) -> str | None:
    val = _find_value(secciones, "Materials", "Material of Construction", "Material")
    if not val:
        return None
    return val.strip()[:80]


def _parse_beam_angle(secciones: dict) -> list[float] | None:
    """tipo=rango: emite lista. '36°' → [36], '10-45°' → [10, 45].
    Patrón consistente con `angulo_vision` de Lentes."""
    val = _find_value(secciones, "Beam Angle", "Field Angle", "Spread")
    if not val:
        return None
    v = val.strip()
    m = re.search(r"([\d.]+)\s*[-–]\s*([\d.]+)\s*°", v)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    m1 = re.search(r"([\d.]+)\s*°", v)
    if m1:
        return [float(m1.group(1))]
    return None


def map_modificador_specs(secciones: dict, title: str) -> dict:
    """Aplica todos los mappers; devuelve dict con solo claves
    cuyo valor no es None (canónica del registry)."""
    result: dict = {}

    def _add(key: str, value) -> None:
        if value is not None and value != "" and value != []:
            result[key] = value

    _add("modificador_subtipo", _parse_subtipo(secciones, title))
    _add("forma", _parse_forma(secciones, title))
    _add("diametro_cm", _parse_diametro_cm(secciones))
    _add("dimensions_mm", _parse_dimensiones(secciones))
    _add("montura_luz", _parse_montura_luz(secciones, title))
    _add("incluye_grid", _parse_incluye_grid(secciones))
    _add("incluye_difusor", _parse_yes_no(secciones, "Interior Baffle"))
    _add("plegable", _parse_plegable(secciones))
    _add("light_loss_stops", _parse_light_loss(secciones))
    _add("materials", _parse_materiales(secciones))
    _add("beam_angle", _parse_beam_angle(secciones))
    _add("peso_g", _parse_peso_g(secciones))

    return result


# ─── Extract URL y JSON-LD desde el HTML ──────────────────────────────


def _extract_url_source(html: str) -> str:
    m = re.search(r'<meta\s+property="og:url"\s+content="([^"]+)"', html)
    if m:
        return html_lib.unescape(m.group(1))
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
    return html_lib.unescape(m.group(1)) if m else ""


def _extract_image_url(html: str) -> str:
    m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    return html_lib.unescape(m.group(1)) if m else ""


def _extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return html_lib.unescape(m.group(1)).strip() if m else ""


def _is_bh_html(html: str, url_source: str) -> bool:
    """Heurística: ¿es B&H Photo (no godoxonline / eBay / fabricante)?
    Los HTMLs guardados de B&H tienen 'bhphotovideo.com' en og:image
    aunque a veces no en og:url. Y el title incluye 'B&amp;H'."""
    head = html[:10_000].lower()
    if "bhphotovideo.com" in head:
        return True
    if "bhphoto.com" in head:
        return True
    if "url_source" and "bhphotovideo.com" in url_source.lower():
        return True
    if "b&amp;h photo" in head or "b&h photo" in head:
        return True
    return False


# ─── Pipeline principal ───────────────────────────────────────────────


def parse_html(path: Path) -> dict | None:
    """Parsea un HTML B&H. Devuelve dict con marca/modelo/specs/secciones.
    Retorna None si NO es B&H (otros sitios → manejados por patches)."""
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    url_source = _extract_url_source(html_text)
    if not _is_bh_html(html_text, url_source):
        return None

    raw_title = _extract_title(html_text)
    title = _clean_title(raw_title)
    parser = BHSpecsParser()
    parser.feed(html_text)
    secciones = parser.secciones

    return {
        "id": _extract_id(title),
        "marca": _extract_brand(title),
        "modelo": _extract_modelo(title),
        "url_source": url_source,
        "image_url": _extract_image_url(html_text),
        "status_bh": "OK",
        "fuente": f"B&H HTML guardado ({date.today().isoformat()})",
        "secciones": secciones,
    }


def load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return default


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main(html_paths: list[Path]) -> None:
    raw = load_json(RAW_PATH, {"products": []})
    curado = load_json(CURADO_PATH, {"products": {}})

    raw_existing = {p["id"] for p in raw["products"]}
    added_raw = 0
    added_curado = 0
    skipped = 0

    for p in html_paths:
        if not p.exists():
            print(f"  WARN: no existe: {p}")
            continue
        print(f"Procesando: {p.name}")
        result = parse_html(p)
        if result is None:
            print("  → skip (no es B&H — usar patches)")
            skipped += 1
            continue

        prod_id = result["id"]
        title = f"{result['marca']} {result['modelo']}"

        # Raw
        if prod_id in raw_existing:
            print(f"  → raw ya existe ({prod_id}), upsert")
            for i, existing in enumerate(raw["products"]):
                if existing["id"] == prod_id:
                    raw["products"][i] = result
                    break
        else:
            raw["products"].append(result)
            raw_existing.add(prod_id)
            added_raw += 1
            print(f"  + raw agregado ({prod_id})")

        # Curado
        specs = map_modificador_specs(result["secciones"], title=title)
        curado["products"][prod_id] = {
            "marca": result["marca"],
            "modelo": result["modelo"],
            "url_source": result.get("url_source", ""),
            "specs": specs,
            "ficha": result["secciones"],
        }
        added_curado += 1
        print(f"  + curado ({len(specs)} specs): {list(specs.keys())}")

    save_json(RAW_PATH, raw)
    save_json(CURADO_PATH, curado)

    print(f"\nListo. Raw nuevos: {added_raw} | Curado: {added_curado} | Skipped: {skipped}")
    print(f"  → {RAW_PATH.relative_to(ROOT)}")
    print(f"  → {CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/modificadores_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)
    paths = []
    for arg in sys.argv[1:]:
        if "*" in arg:
            paths.extend(Path(arg).parent.glob(Path(arg).name))
        else:
            paths.append(Path(arg))
    main(paths)
