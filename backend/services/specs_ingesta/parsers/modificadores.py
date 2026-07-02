"""parsers/modificadores.py — Mapper de specs para Modificadores de luz.

Movido verbatim de tools/modificadores_parser.py (F3 del rediseño de ingesta)
— solo la lógica de mapeo; parse_html/main/load_json/save_json (CLI + I/O de
docs/modificadores*.json) quedan en tools/modificadores_parser.py.

Entry point: map_modificador_specs(secciones, title) -> dict."""

from __future__ import annotations

import re

from .base import _find_value, _parse_peso_g


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
