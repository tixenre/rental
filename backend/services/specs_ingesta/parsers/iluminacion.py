"""parsers/iluminacion.py — Mappers de specs para Iluminación.

Movido verbatim de tools/iluminacion_parser.py (F3 del rediseño de ingesta) —
solo la lógica de mapeo (secciones B&H → specs); parse_html/main/load_*/save_*
(CLI + I/O de docs/iluminacion*.json) quedan en tools/iluminacion_parser.py,
que ahora importa este módulo en vez de definir los mappers localmente.

Entry points: map_luz_specs(secciones, title) -> dict, map_luz_extras(secciones, title) -> dict."""

from __future__ import annotations

import re

from .base import _find_value, _parse_peso_g


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


def _parse_potencia(secciones: dict) -> int | None:
    val = _find_value(
        secciones,
        "Power Consumption", "Wattage", "Max Power",
        "Max Bulb Wattage", "Bulb Wattage", "Lamp Wattage",
        # Aliases del registry (consumo_w) — sincronizado para no volver a desincronizar:
        "Power Draw", "Power Input", "Rated Power",
    )
    if not val:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*W", val)
    return int(float(m.group(1))) if m else None


def _parse_lumens(secciones: dict) -> dict[str, int]:
    """Devuelve {lumens_at_5600k: n} y/o {lumens_at_3200k: n}.

    Si el valor contiene anotación "3200K" se asigna a tungsten; si no, al
    estándar daylight 5600K. B&H a veces tiene filas separadas por temperatura
    (bicolor), por lo que se recorren todas las ocurrencias del label.
    """
    labels = (
        "Lumens", "Maximum Luminous Flux", "Lumen Output",
        "Luminous Flux", "Total Lumens",
    )
    targets = {l.lower() for l in labels}
    all_vals: list[str] = []
    for section_items in secciones.values():
        for item in section_items:
            if item["label"].lower() in targets:
                all_vals.append(item["value"])

    out: dict[str, int] = {}
    for val in all_vals:
        for line in val.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.search(r"([\d,]+)", line)
            if not m:
                continue
            try:
                num = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if num <= 0:
                continue
            if "3200" in line:
                out.setdefault("lumens_at_3200k", num)
            else:
                out.setdefault("lumens_at_5600k", num)
    return out


def _parse_lux_at_1m(secciones: dict) -> dict[str, int]:
    """Parsea la línea de Fotometría → {lux_at_1m_5600k: n} y/o {lux_at_1m_3200k: n}.

    B&H format: "5600K: 1077 fc / 11,600 Lux" o "3200K: 800 fc / 8,600 Lux".
    """
    val = _find_value(secciones, "Photometrics at 3.3' / 1 m", "Photometrics")
    if not val:
        return {}
    out: dict[str, int] = {}
    for line in val.splitlines():
        line = line.strip()
        if not line:
            continue
        m_lux = re.search(r"([\d,]+)\s*[Ll]ux", line)
        if not m_lux:
            continue
        try:
            lux = int(m_lux.group(1).replace(",", ""))
        except ValueError:
            continue
        if lux <= 0:
            continue
        if "3200" in line:
            out.setdefault("lux_at_1m_3200k", lux)
        else:
            out.setdefault("lux_at_1m_5600k", lux)
    return out


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


def _parse_temperatura(secciones: dict, title: str = "") -> str | None:
    val = _find_value(secciones, "Color Temperature")
    if not val:
        modes = (_find_value(secciones, "Color Modes") or "").strip()
        modes_lower = modes.lower()

        # ¿Es multi-modo (RGB+bicolor)? Entonces la photometrics muestra valores
        # puntuales que NO representan el rango real. Mejor devolver null.
        is_multi_mode = (
            "rgb" in modes_lower
            or ("daylight" in modes_lower and "tungsten" in modes_lower)
            or "," in modes  # múltiples modos
        )

        # Fallback 1: Color Modes con un solo color fijo
        if modes_lower == "tungsten":
            return "3200K"
        if modes_lower == "daylight":
            return "5600K"

        # Fallback 2: solo si NO es multi-modo, usar prefijo de Photometrics
        if not is_multi_mode:
            photo = (_find_value(secciones, "Photometrics", "Photometrics at 3.3' / 1 m") or "")
            m = re.search(r"\b(\d{4,5})K\s*:", photo)
            if m:
                return f"{m.group(1)}K"

        # Fallback 3: keyword en título/item_type — solo para single-color obvios
        item = (_find_value(secciones, "Item Type") or "").lower()
        ctx = f"{title} {item}".lower()
        if "daylight" in ctx and "bi-color" not in ctx and "rgb" not in ctx:
            return "5600K"
        if "tungsten" in ctx and "bi-color" not in ctx and "rgb" not in ctx:
            return "3200K"
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


def _parse_control_inalambrico(secciones: dict) -> list[str] | None:
    """Devuelve lista de protocolos. El registry declara este spec como
    multi_enum, así que SIEMPRE retorna lista (o None si no hay match).
    Enum del registry: Bluetooth, DMX, RDM, Wi-Fi, CRMX, Lumenradio, Art-Net, sACN."""
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

    protocols: list[str] = []
    # Solo agregamos enum values válidos del registry (multi_enum).
    for proto in ("Lumenradio", "CRMX", "Bluetooth", "Wi-Fi", "WiFi"):
        if proto.lower() in combined.lower():
            label = "Wi-Fi" if proto in ("WiFi", "Wi-Fi") else proto
            if label not in protocols:
                protocols.append(label)
    if re.search(r"\bDMX\b", combined, re.IGNORECASE) and "DMX" not in protocols:
        protocols.append("DMX")
    if re.search(r"\bRDM\b", combined, re.IGNORECASE) and "RDM" not in protocols:
        protocols.append("RDM")
    if re.search(r"\bArt-?Net\b", combined, re.IGNORECASE) and "Art-Net" not in protocols:
        protocols.append("Art-Net")
    if re.search(r"\bsACN\b", combined, re.IGNORECASE) and "sACN" not in protocols:
        protocols.append("sACN")

    return protocols if protocols else None


def _parse_alimentacion(secciones: dict) -> list[str]:
    """Devuelve lista de enum values del proyecto, ordenada por prioridad canónica."""
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
    # Orden canónico de aparición en la lista (AC primero, batería integrada al final)
    PRIORITY = ["AC", "V-mount", "Gold Mount", "NP-F", "D-Tap", "USB-C", "Batería integrada"]

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

    if not found:
        found = ["AC"]  # default si no se puede inferir

    # Ordenar por prioridad canónica
    return sorted(found, key=lambda x: PRIORITY.index(x) if x in PRIORITY else 99)


def _parse_montura_luz(secciones: dict) -> str | None:
    """Lado-luz del acople con modificadores. Enum unificado con
    Modificadores: Bowens, Elinchrom, Profoto, Nanlite Forza,
    Propietario, Sin montura. Las luces Fresnel tradicionales (ARRI 650,
    Mole) devuelven 'Sin montura' — no aceptan softboxes Bowens-style."""
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    lens_type = (_find_value(secciones, "Lens Type") or "").lower()
    if "fresnel" in item_type or "fresnel" in lens_type:
        # Algunas Fresnel modernas SÍ aceptan modificadores (Nanlite Forza).
        # Si tienen 'Mounting' con marca conocida, usamos eso; sino, "Sin montura".
        pass  # caer al fallback de Mounting

    val = _find_value(secciones, "Front Accessory Mount", "Accessory Mount", "Mounting")
    val_lower = (val or "").lower()
    if "bowens" in val_lower:
        return "Bowens"
    if "profoto" in val_lower:
        return "Profoto"
    if "elinchrom" in val_lower:
        return "Elinchrom"
    if "nanlite" in val_lower or "forza" in val_lower:
        # Las Nanlite Forza usan Bowens estándar (no propietario).
        return "Bowens"
    if "proprietary" in val_lower or "propietario" in val_lower:
        return "Propietario"
    # Fresnel tradicional (sin mount estándar) → "Sin montura".
    if "fresnel" in item_type or "fresnel" in lens_type:
        return "Sin montura"
    if not val or val_lower.strip() in ("none", "n/a", "no"):
        return None
    # Stud/receiver son montaje de fixture, no de modificador. None.
    if re.search(r'\d/\d["\']|stud|receiver|yoke', val_lower):
        return None
    # Valor desconocido pero presente → Propietario (mejor que None para
    # que el motor de compat tenga algo).
    return "Propietario"


_TIPO_KEYWORDS = [
    ("Fresnel",      ["fresnel"]),
    ("Tube Light",   ["tube light", "led tube"]),
    ("Flexible Mat", ["flexible mat", "flex mat", "flexible light"]),
    ("Panel",        ["light panel", "led panel"]),
    ("Foco",         [
        "cob led monolight", "cob monolight",
        "led monolight", "monolight",
        "spotlight", "video light",
        "led lamp", "lamp",
    ]),
    ("On-Camera",    ["on-camera"]),
    ("Flash",        ["flash", "speedlight", "strobe"]),
]


def _parse_tipo(secciones: dict, title: str = "") -> str | None:
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    haystack = f"{item_type} {title}".lower()
    for label, keywords in _TIPO_KEYWORDS:
        if any(k in haystack for k in keywords):
            return label
    return None


def _parse_beam_angle(secciones: dict) -> list[float] | None:
    """tipo=rango: emite lista. '45°' → [45.0], '15-54°' → [15.0, 54.0].
    Patrón consistente con `angulo_vision` de Lentes y `beam_angle` de
    Modificadores."""
    val = _find_value(secciones, "Beam Angle")
    if not val:
        return None
    line = val.splitlines()[0].strip()
    # "13 to 54°" → "13-54°"
    line = re.sub(r"(\d+)\s+to\s+(\d+)", r"\1-\2", line)
    # Buscar el rango primero, después el valor único.
    m = re.search(r"([\d.]+)\s*[-–]\s*([\d.]+)\s*°", line)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    m1 = re.search(r"([\d.]+)\s*°", line)
    if m1:
        return [float(m1.group(1))]
    return None


def _parse_cooling_system(secciones: dict) -> str | None:
    """Devuelve valor del enum del registry: 'Active (Fan)', 'Passive',
    'Smart Fan' (o None)."""
    val = _find_value(secciones, "Cooling System")
    if not val:
        return None
    v = val.strip().lower()
    if "smart" in v and "fan" in v:
        return "Smart Fan"
    if "fan" in v:
        return "Active (Fan)"
    if "passive" in v:
        return "Passive"
    return None


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

    # B&H a veces tiene typos de decimales en las conversiones cm. Validamos:
    # convertimos inch a cm y si la diferencia es enorme, preferimos calcular de inch.
    m_in = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*[\"']", val)
    m_cm = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*cm", val, re.IGNORECASE)

    if m_in and m_cm:
        inch_vals = [float(x) for x in m_in.groups()]
        cm_vals = [float(x) for x in m_cm.groups()]
        # Si los cm están MAL (off por factor ~10), recalcular desde inches
        expected = inch_vals[0] * 2.54
        if expected > 0 and abs(cm_vals[0] - expected) / expected > 0.5:
            # Recalcular desde inches
            converted = [round(v * 2.54, 1) for v in inch_vals]
            return f"{converted[0]} × {converted[1]} × {converted[2]} cm"
        return f"{cm_vals[0]} × {cm_vals[1]} × {cm_vals[2]} cm"

    # Solo métrico
    if m_cm:
        return f"{m_cm.group(1)} × {m_cm.group(2)} × {m_cm.group(3)} cm"
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
    # Normalizar: "LED (Via Included Power Supply/Controller)" → "LED"
    # "Yes: LCD" → "LCD"
    v = re.sub(r"^Yes:\s*", "", v, flags=re.IGNORECASE)
    v = re.sub(r"\s*\(.*?\)\s*$", "", v)  # quitar parentético al final
    return v.strip() or None


def map_luz_extras(secciones: dict, title: str = "") -> dict:
    """Campos descriptivos que NO están en el registry (informativos para
    la ficha pero no participan del motor de compatibilidad ni filtros).

    Las specs canónicas se emiten desde `map_luz_specs` (incluido
    `beam_angle`, `dimensions_mm`, `materials`, etc. — eso se movió a
    specs para alinearse con el registry).
    """
    result: dict = {}

    # Específicos de iluminación legacy / referencia (no en registry)
    extras_simples = [
        ("Item Type", "item_type"),
        ("Bulb Type", "bulb_type"),
        ("Base Type", "base_type"),
        ("Expected Lamp Life", "vida_util_horas"),
        ("Yoke Type", "yoke"),
        ("Fixture Mounting", "fixture_mount"),
        ("Cable Length", "cable_length"),
        ("Inputs/Outputs", "io"),
    ]
    for src_label, dst_key in extras_simples:
        v = _find_value(secciones, src_label)
        if v:
            result[dst_key] = v.split("\n")[0].strip() if "\n" in v else v.strip()

    # IP rating y photometrics — descriptivos, no son spec canónico.
    ip = _parse_ip_rating(secciones)
    if ip:
        result["ip_rating"] = ip
    photo = _parse_photometrics(secciones)
    if photo:
        result["photometrics_1m"] = photo

    return result


def map_luz_specs(secciones: dict, title: str = "") -> dict:
    """Mapea secciones raw de B&H → spec_keys del proyecto para Iluminación."""
    result: dict = {}

    subtipo = _parse_tipo(secciones, title)
    if subtipo:
        result["iluminacion_subtipo"] = subtipo

    potencia = _parse_potencia(secciones)
    if potencia is not None:
        result["consumo_w"] = potencia

    for k, v in _parse_lumens(secciones).items():
        result[k] = v

    for k, v in _parse_lux_at_1m(secciones).items():
        result[k] = v

    cri = _parse_cri(secciones)
    if cri is not None:
        result["cri"] = cri

    temperatura = _parse_temperatura(secciones, title)
    if temperatura:
        result["temperatura_k"] = temperatura

    _is_bicolor = _parse_bicolor(secciones)
    _is_rgb = _parse_rgb(secciones, title)

    # Sintetizar color_modes (multi_enum del registry) desde las detecciones.
    # Las keys huérfanas "bicolor"/"rgb" se descartan — color_modes es la única
    # key del registry para este concepto.
    _modes: list[str] = []
    if _is_rgb:
        _modes.append("RGB")
    if _is_bicolor:
        _modes.append("Bicolor")
    if not _modes:
        _temp = result.get("temperatura_k", "")
        if isinstance(_temp, str) and _temp:
            if "3200" in _temp and "5600" not in _temp:
                _modes.append("Tungsten")
            else:
                _modes.append("Daylight")
    if _modes:
        result["color_modes"] = _modes

    result["dimming"] = _parse_dimming(secciones)

    control = _parse_control_inalambrico(secciones)
    if control:
        result["control_inalambrico"] = control

    alimentacion = _parse_alimentacion(secciones)
    if alimentacion:
        result["alimentacion"] = alimentacion

    montura = _parse_montura_luz(secciones)
    if montura:
        result["montura_luz"] = montura

    peso = _parse_peso_g(secciones)
    if peso is not None:
        result["peso_g"] = peso

    # ─── Specs adicionales del registry (antes vivían en extras) ──────
    # Patrón: mappers existentes pero promovidos a `specs` para que se
    # persistan en equipo_specs y participen del template del admin.
    beam = _parse_beam_angle(secciones)
    if beam:
        result["beam_angle"] = beam

    dim = _parse_dimensiones(secciones)
    if dim:
        result["dimensions_mm"] = dim

    cooling = _parse_cooling_system(secciones)
    if cooling:
        result["cooling_system"] = cooling

    app_compat = _parse_app_compatible(secciones)
    if app_compat is not None:
        result["mobile_app_compatible"] = app_compat

    display = _parse_display(secciones)
    if display:
        result["display"] = display

    tlci = _parse_tlci(secciones)
    if tlci is not None:
        result["tlci"] = tlci

    # Strings directos del raw cuyo label en registry coincide o se mapea.
    label_to_specs_key = [
        ("Materials", "materials"),
        ("Certifications", "certifications"),
        ("Included Storage Case", "incluye_estuche_label"),  # marker, se procesa abajo
        ("Included Light Modifier", "incluye_modificador"),
        ("Wireless Range", "wireless_range_m"),
        ("Operating Conditions", "operating_conditions"),
        ("Environmental Resistance", "environmental_resistance"),
    ]
    for src_label, dst_key in label_to_specs_key:
        v = _find_value(secciones, src_label)
        if not v:
            continue
        v = v.split("\n")[0].strip() if "\n" in v else v.strip()
        if dst_key == "incluye_estuche_label":
            # `incluye_estuche` es bool en el registry → True si trae estuche.
            result["incluye_estuche"] = v.lower().startswith(("yes", "sí", "si", "included"))
        elif dst_key == "wireless_range_m":
            # Extraer número en metros. "656' / 200 m" → 200
            m = re.search(r"([\d.]+)\s*m\b", v)
            if m:
                result[dst_key] = float(m.group(1))
        else:
            result[dst_key] = v

    return result
