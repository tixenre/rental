"""
services/nombre_builder.py — Builder inteligente del nombre público.

Estrategia: NO usar un template genérico. Cada categoría tiene su propio
formatter porque "qué hace bueno un nombre" cambia totalmente:

  - Cámara: tipo + marca + modelo + montura + formato
            "Cámara Sony FX3 Montura E Full Frame"
  - Lente:  Lente + marca + linea + focal + apertura + montura
            "Lente Sigma Art 50mm f/1.4 Montura E"
  - Luz:    tipo (LED/Tungsteno/Flash) + marca + modelo + subtipos
            "Luz LED Amaran 300C RGB Bicolor"
  - Adaptador: Adaptador + marca + modelo + in→out
            "Adaptador Sigma MC-11 EF→E"
  - etc.

Mapeo de subcategoría → tipo es **explícito y editable** (al final del archivo).
Si una categoría/subcategoría no está, cae al formatter genérico.

Devuelve dos variantes:
  - `nombre_publico` (corto): catálogo, card, lista admin, app cliente.
  - `nombre_publico_largo` (extendido): albarán, contrato, seguro.

El override manual (template del admin con tokens {marca}, {modelo}, etc.)
sigue funcionando — gana sobre el auto-build.
"""

import re
import unicodedata
from typing import Optional


# ── Mapeo de subcategoría → tipo legible (editable) ─────────────────────
#
# La key es el nombre EXACTO de la subcategoría en `categorias.nombre`.
# El value es cómo aparece en el nombre público.
# Si una subcategoría no está acá, el formatter cae al tipo de la raíz.

SUBCATEGORIA_A_TIPO: dict[str, str] = {
    # Cámaras
    "Video": "Cámara",
    "Foto": "Cámara",
    "Acción": "Cámara Acción",

    # Lentes — todas se llaman "Lente" pero podríamos refinar
    "Zoom E-mount": "Lente",
    "Zoom EF": "Lente",
    "Fijos EF": "Lente",
    "Especiales": "Lente",
    "Vintage": "Lente",

    # Adaptadores y Filtros
    "Adaptadores de montura": "Adaptador",
    "Filtros 82mm": "Filtro",

    # Iluminación — el subtipo es importante
    "LED daylight/bicolor": "Luz LED",
    "LED RGB": "Luz LED",   # los flags rgb/bicolor del template lo refinan
    "Tungsteno": "Luz Tungsteno",
    "Fluorescente": "Luz Fluorescente",
    "On-camera / Flash": "Flash",
    "Práctica / efecto": "Práctico",

    # Modificadores — usamos el spec "tipo" del template (Softbox, Bandera, etc.)
    "Softbox": "Softbox",
    "Difusión / Frame": "Frame de difusión",
    "Reflectores": "Reflector",
    "Banderas": "Bandera",

    # Soportes
    "Trípodes video": "Trípode video",
    "Trípodes foto": "Trípode foto",
    "C-Stands": "C-Stand",
    "Estabilización": "Gimbal",
    "Slider / Dolly / Riel": "Slider",
    "Car Mount": "Car mount",

    # Grip
    "Brazos": "Brazo",
    "Clamps": "Clamp",
    "Wall plates / pins": "Wall plate",
    "Pinzas": "Pinza",
    "Líneas de seguridad": "Línea de seguridad",
    "Sopapa": "Sopapa",
    "Lastre": "Lastre",

    # Sonido
    "Inalámbricos / Lavalier": "Lavalier",
    "Shotgun / Boom": "Shotgun",
    "On-camera (sonido)": "Mic on-camera",
    "Estudio / Podcast": "Mic estudio",
    "Intercom": "Intercom",

    # Monitores y Video
    "Monitores": "Monitor",
    "Grabadores": "Grabador",
    "Transmisión inalámbrica": "TX/RX wireless",
    "Follow Focus / Matebox": "Follow focus",

    # Energía
    "V-Mount": "Batería V-mount",
    "NP / LP-E6": "Batería",
    "Distribución eléctrica": "Distribución",

    # Media y Datos
    "Tarjetas SD": "Tarjeta SD",
    "Tarjetas CFexpress": "Tarjeta CFexpress",
    "Lectores": "Lector",

    # Estudio y Producción
    "Set / Backdrops": "Set",
    "Paquetes": "Kit",
}

# Si no hay subcategoría, fallback al tipo de la raíz.
RAIZ_A_TIPO: dict[str, str] = {
    "Cámaras": "Cámara",
    "Lentes": "Lente",
    "Adaptadores y Filtros": "Adaptador",
    "Iluminación": "Luz",
    "Modificadores": "Modificador",
    "Soportes": "Soporte",
    "Grip": "Grip",
    "Sonido": "Audio",
    "Monitores y Video": "Monitor",
    "Energía": "Batería",
    "Media y Datos": "Media",
    "Estudio y Producción": "Kit",
}


# ── Helpers comunes ─────────────────────────────────────────────────────

_BOOL_TRUE = {"true", "1", "sí", "si", "yes", True, 1}
_BOOL_FALSE = {"false", "0", "no", False, 0, ""}


def _is_true(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in _BOOL_TRUE
    return v in _BOOL_TRUE


def _join(parts: list[str], sep: str = " ") -> str:
    """Une partes no vacías y deduplica palabras case-insensitive."""
    pieces = [p.strip() for p in parts if p and str(p).strip()]
    if not pieces:
        return ""
    out = sep.join(pieces)
    return _dedup_words(out)


def _dedup_words(text: str) -> str:
    """Elimina palabras duplicadas case-insensitive ignorando plurales
    simples. 'Sony Sony FX3' → 'Sony FX3'. 'Pinza Pinzas Grandes' →
    'Pinza Grandes'. Mantiene la **primera** ocurrencia.

    Solo trabaja sobre la palabra ENTERA (no separa por '/' o '-'). Si
    se quiere dedupear sub-palabras (ej. 'Flag/Bandera' vs 'Bandera'),
    el caller debe normalizar antes."""
    def _forms(word: str) -> set[str]:
        """Devuelve formas equivalentes para deduplicar."""
        clean = re.sub(r"[^a-záéíóúñ0-9/\-]", "", word.lower())
        if not clean:
            return set()
        forms = {clean}
        # Plural → agregar singular
        if clean.endswith("s") and len(clean) >= 5:
            forms.add(clean[:-1])
        # Singular → agregar plural candidato
        elif not clean.endswith("s"):
            forms.add(clean + "s")
        return forms

    seen: set[str] = set()
    out: list[str] = []
    for word in text.split():
        forms = _forms(word)
        if forms & seen:
            continue
        seen |= forms
        out.append(word)
    return " ".join(out)


def _cap_largo(s: str, max_chars: int) -> str:
    """Cap suave: si supera max_chars, corta al último espacio + …"""
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars].rsplit(" ", 1)[0]
    return cut + "…" if cut else s[:max_chars]


# ── Display templates por spec ──────────────────────────────────────────
# Renderiza un (spec_key, valor) → string bonito para placeholders y ficha.
#
# Cada spec puede tener DOS variantes:
#   - "short": para nombres públicos (conciso, sin contexto extra)
#              Ej: lumens_at_5600k=19389 → "19389 lumen"
#   - "long":  para ficha técnica / comparador (con contexto explícito)
#              Ej: lumens_at_5600k=19389 → "19389 lm a 5600K"
#
# Formato de cada variante:
#   - "{value}<sufijo>"  interpolación simple
#   - "_smart_kg"        gramos: <1000 → "Xg", >=1000 → "X.X kg"
#   - "_rango_k_short"   rango K corto: solo el rango "X-YK"
#   - "_rango_k_long"    rango K explícito (igual al short para luces)
#   - "_iso_short"       "ISO X-Y" sin paréntesis
#   - "_iso_long"        igual
#   - "_iso_ext"         "ISO X-Y (ext)"
#
# Si tpl es un string plano, se usa para ambas variantes (backwards compat).
# Si es dict {"short": ..., "long": ...}, se respeta cada uno.
#
# Keys: spec_key canónico (estable ante traducciones de label).

SPEC_DISPLAY_TEMPLATES: dict[str, dict | str] = {
    # ── Luces (Iluminación) ──────────────────────────────────────────
    "potencia_w":        "{value}W",  # mismo short/long
    "lumens_at_5600k":   {"short": "{value} lumen",            "long": "{value} lm a 5600K"},
    "lumens_at_3200k":   {"short": "{value} lumen (tungsten)", "long": "{value} lm a 3200K"},
    "lux_at_1m_5600k":   {"short": "{value} lux",              "long": "{value} lux a 1m (5600K)"},
    "lux_at_1m_3200k":   {"short": "{value} lux (tungsten)",   "long": "{value} lux a 1m (3200K)"},
    "cri":               "CRI {value}",
    "tlci":              "TLCI {value}",
    "r9":                "R9 {value}",
    "temperatura_k":     "_rango_k",
    "peso_g":            "_smart_kg",

    # ── Cámaras ──────────────────────────────────────────────────────
    "megapixels":        "{value}MP",
    "fps_max":           "{value}fps",
    "continuous_shooting_fps": {"short": "{value}fps", "long": "{value}fps (ráfaga)"},
    "iso_nativo":        "_iso_short",
    "iso_extendido":     "_iso_ext",
    "rango_dinamico_stops": "{value} stops",
    "recording_limit_min": "{value} min",
    "consumo_w":         "{value}W",

    # ── Otros (crecerán con el dataset) ──────────────────────────────
}


def render_spec_value(spec_key: str, value, variant: str = "short") -> str:
    """Renderiza un spec value con su display template.

    Args:
        spec_key: clave canónica del spec (no label)
        value: valor del spec (str, int, float, bool, dict con {min,max})
        variant: "short" para nombres públicos (default), "long" para ficha técnica

    Si no hay template, devuelve el valor crudo como string.
    """
    if value is None:
        return ""
    raw_tpl = SPEC_DISPLAY_TEMPLATES.get(spec_key)

    # Si es dict, elegir variante; si es string, usar para ambos
    if isinstance(raw_tpl, dict):
        tpl = raw_tpl.get(variant) or raw_tpl.get("short") or raw_tpl.get("long")
    else:
        tpl = raw_tpl

    # Handlers especiales
    if tpl == "_smart_kg":
        try:
            g = float(value)
            return f"{round(g/1000, 2)} kg" if g >= 1000 else f"{int(g)}g"
        except (TypeError, ValueError):
            return str(value)
    if tpl == "_rango_k":
        if isinstance(value, dict) and "min" in value and "max" in value:
            return f"{value['min']}K" if value["min"] == value["max"] else f"{value['min']}-{value['max']}K"
        if isinstance(value, str):
            return value if "K" in value.upper() else f"{value}K"
        return f"{value}K"
    if tpl in ("_iso_short", "_iso_range"):
        if isinstance(value, dict) and "min" in value and "max" in value:
            return f"ISO {value['min']}-{value['max']}"
        return f"ISO {value}"
    if tpl == "_iso_ext":
        if isinstance(value, dict) and "min" in value and "max" in value:
            return f"ISO {value['min']}-{value['max']} (ext)"
        return f"ISO {value} (ext)"
    if tpl == "_bool_yes":
        return "Sí" if value in (True, "true", "1", "Sí", "Si", "yes") else "No"

    # Template con {value}
    if tpl and "{value}" in tpl:
        return tpl.replace("{value}", str(value))

    # Sin template: devolver crudo
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        if "min" in value and "max" in value:
            return f"{value['min']}-{value['max']}"
        return str(value)
    return str(value)


# ── Render de specs (label + valor con formato bonito) ──────────────────

def _spec_value_str(label: str, value: str, *, with_label: bool = True) -> Optional[str]:
    """Convierte un (label, value) en string para el nombre.

    - Si valor es bool true → devuelve el label (ej. "RGB", "Bicolor")
    - Si valor es bool false → devuelve None
    - Si label se ve numérico (apertura, focal, capacidad) → no repite label
    - Por default: "Label valor"
    """
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip()
    label_norm = label.strip()

    # Booleanos: si false, ocultar; si true, mostrar el label
    if v.lower() in ("false", "0", "no"):
        return None
    if v.lower() in ("true", "1", "sí", "si", "yes"):
        return label_norm

    # Sin label cuando ya viene "todo en el valor": apertura "f/1.4",
    # capacidad "150Wh", etc. (heurística simple: si v ya tiene letras
    # de unidad, no repetimos el label).
    looks_self_describing = bool(re.search(r"[a-zA-Z]", v))
    label_lc = label_norm.lower()

    # Casos donde el valor solo es suficiente
    if label_lc in ("apertura máx", "apertura max", "apertura"):
        return v
    if label_lc in ("focal mín", "focal min", "focal máx", "focal max"):
        # Mostrar como "50mm" si no trae unidad
        if v[-2:].lower() != "mm" and v.replace(".", "").isdigit():
            return f"{v}mm"
        return v
    if label_lc == "capacidad" and "wh" not in v.lower() and "gb" not in v.lower():
        # Asumir Wh si la categoría es Energía. Mejor no asumir y dejar valor
        return v

    if not with_label:
        return v

    # Formato general: "Montura E", "Video máx 4K", "ISO máx 102400"
    return f"{label_norm} {v}"


def _specs_dict(specs_en_nombre: list[tuple[str, str]]) -> dict[str, str]:
    """Convierte la lista a dict por label en lowercase para acceso fácil."""
    return {label.lower(): value for label, value in specs_en_nombre}


# ── Override manual con template ────────────────────────────────────────

_TPL_SEP = r"[\s\-–—,/|·]"


def _norm_label(s: str) -> str:
    """Normaliza un label para lookup de specs: lowercase + sin tildes + trim.
    Tiene que matchear el approach del frontend en `nombre-template.ts`."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()


# Mapeo de label normalizado → spec_key para aplicar display templates.
# Permite que `{spec:Lúmenes (5600K)}` aplique el template de `lumens_at_5600k`.
LABEL_TO_SPEC_KEY: dict[str, str] = {
    # Luces
    "potencia":            "potencia_w",
    "lumenes (5600k)":     "lumens_at_5600k",
    "lumens (5600k)":      "lumens_at_5600k",
    "lumenes (3200k)":     "lumens_at_3200k",
    "lumens (3200k)":      "lumens_at_3200k",
    "lux a 1m (5600k)":    "lux_at_1m_5600k",
    "lux a 1m (3200k)":    "lux_at_1m_3200k",
    "cri":                 "cri",
    "tlci":                "tlci",
    "r9":                  "r9",
    "temperatura color":   "temperatura_k",
    "peso":                "peso_g",
    # Cámaras
    "megapixels":          "megapixels",
    "fps max":             "fps_max",
    "rafaga (stills)":     "continuous_shooting_fps",
    "iso nativo":          "iso_nativo",
    "iso extendido":       "iso_extendido",
    "rango dinamico":      "rango_dinamico_stops",
    "limite de grabacion": "recording_limit_min",
    "consumo":             "consumo_w",
}


def _render_template(
    tpl: str,
    vars: dict[str, str],
    specs: Optional[list[tuple[str, str]]] = None,
) -> str:
    """Renderiza `{marca} {modelo} {spec:Lens mount}` con los vars dados.

    Tokens soportados:
      - `{marca}`, `{modelo}`, `{tipo}`, `{nombre}` → resueltos vía `vars`.
      - `{spec:Label}` → busca en `specs` por label normalizado (case+tilde
        insensitive). Si el spec tiene un display template asociado vía
        `LABEL_TO_SPEC_KEY` + `SPEC_DISPLAY_TEMPLATES`, se aplica el formato
        bonito (ej. "8990" → "8990 lm @ 5600K").
    """
    lower = {k.lower(): (v or "").strip() for k, v in vars.items()}
    spec_map: dict[str, str] = {}
    if specs:
        for label, value in specs:
            spec_map[_norm_label(label)] = (value or "").strip()

    def replace_token(m: re.Match) -> str:
        before, key, after = m.group(1), m.group(2), m.group(3)
        key_stripped = key.strip()
        if key_stripped.lower().startswith("spec:"):
            spec_part = key_stripped[len("spec:"):]
            # Detectar variante: {spec:Label:long} → variant="long"
            variant = "short"
            if ":" in spec_part:
                spec_label, variant = spec_part.rsplit(":", 1)
                variant = variant.strip().lower()
                if variant not in ("short", "long"):
                    spec_label = spec_part  # no era variante, era parte del label
                    variant = "short"
            else:
                spec_label = spec_part
            norm = _norm_label(spec_label)
            val = spec_map.get(norm, "")
            spec_key = LABEL_TO_SPEC_KEY.get(norm)
            if spec_key and val:
                val = render_spec_value(spec_key, val, variant=variant)
        else:
            val = lower.get(key_stripped.lower(), "")
        if val:
            return f"{before or ''}{val}{after or ''}"
        if after:
            return before or ""
        if before:
            return ""
        return ""

    # Regex: cualquier token `{...}` que NO contenga `}` adentro. Esto permite
    # `{spec:Formato de sensor}` (con espacios, dos puntos, etc.).
    pattern = "(" + _TPL_SEP + "+)?" + r"\{([^}]+)\}" + "(" + _TPL_SEP + "+)?"
    out = re.sub(pattern, replace_token, tpl)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(rf"^{_TPL_SEP}+|{_TPL_SEP}+$", "", out).strip()
    out = re.sub(rf"({_TPL_SEP})\s*\1+", r"\1", out)
    return out if out and not re.match(rf"^{_TPL_SEP}+$", out) else ""


# ── Formatters específicos por categoría ────────────────────────────────

def _fmt_camara(*, marca, modelo, subcat, specs, raiz, specs_ordered=None) -> tuple[list[str], list[str]]:
    """Cámara Sony FX3 Sensor Full-Frame Montura E 4K — incluye TODAS
    las specs marcadas visible_en_nombre en orden de prioridad."""
    tipo = SUBCATEGORIA_A_TIPO.get(subcat or "", "Cámara")
    base = [tipo, marca, modelo]
    extras_corto: list[str] = []
    extras_largo: list[str] = []
    # Recorrer las specs en orden (ya vienen filtradas por visible_en_nombre
    # y ordenadas por prioridad).
    for label, value in (specs_ordered or []):
        if not value or str(value).strip() == "":
            continue
        v = str(value).strip()
        if v.lower() in ("false", "0", "no"):
            continue
        label_lc = label.strip().lower()
        # Formato especial por key conocida.
        # "lens mount" es el label canónico nuevo; "montura" es legacy.
        if label_lc.startswith("lens mount") or label_lc.startswith("montura"):
            entry = f"Montura {v}"
        elif label_lc.startswith("video"):
            # "UHD 4K hasta 120p" → en el largo tal cual, en el corto
            # extraer solo el "4K" / "6K" / "8K".
            import re as _re
            short = _re.search(r"(\d+K|FHD)", v)
            extras_corto.append(short.group(1) if short else v)
            extras_largo.append(v)
            continue
        elif label_lc.startswith("sensor"):
            entry = v
        elif label_lc.startswith("formato"):
            entry = v
        else:
            # Bool true → solo label; otro → "Label valor"
            if v.lower() in ("true", "1", "sí", "si", "yes"):
                entry = label
            else:
                entry = f"{label} {v}"
        extras_corto.append(entry)
        extras_largo.append(entry)
    return base + extras_corto, base + extras_largo


def _fmt_lente(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Lente Prime Sigma 35mm f/1.4 Art Montura EF
       Lente Zoom Sony FE 24-70mm f/2.8 GM II Montura E

    Detecta Zoom vs Prime desde las specs de focal (si están) o desde el
    modelo (fallback heurístico). Agrega focal y apertura solo si no
    están ya en el modelo (para no duplicar)."""
    tipo = "Lente"
    modelo_lc = (modelo or "").lower()

    # ── Detección Zoom vs Prime ──
    focal_min = specs.get("focal mín") or specs.get("focal min")
    focal_max = specs.get("focal máx") or specs.get("focal max")

    sub_tipo = None
    # focal_min puede venir como "24" + focal_max "70" (campos separados)
    # o como "24-70mm" en un solo campo (caso enriquecimiento legacy).
    def _es_rango(v: str | None) -> bool:
        return bool(v and re.search(r"\d+\s*-\s*\d+", str(v)))

    if focal_min and focal_max:
        sub_tipo = "Zoom" if str(focal_min) != str(focal_max) else "Prime"
    elif _es_rango(focal_min) or _es_rango(focal_max):
        sub_tipo = "Zoom"
    elif focal_min:
        sub_tipo = "Prime"
    else:
        # Fallback: deducir del modelo. "24-70mm" → Zoom, "35mm" → Prime.
        if re.search(r"\d+\s*-\s*\d+\s*mm", modelo_lc):
            sub_tipo = "Zoom"
        elif re.search(r"\b\d+\s*mm\b", modelo_lc):
            sub_tipo = "Prime"

    # ── Ensamblar ──
    base: list[str] = [tipo]
    if sub_tipo:
        base.append(sub_tipo)
    base.extend([marca or "", modelo or ""])

    extras_corto: list[str] = []
    extras_largo: list[str] = []

    # Focal: solo si el modelo no la tiene
    if focal_min and "mm" not in modelo_lc:
        if focal_max and str(focal_max) != str(focal_min):
            extras_corto.append(f"{focal_min}-{focal_max}mm")
        else:
            extras_corto.append(f"{focal_min}mm")

    # Apertura: solo si el modelo no la tiene
    apertura = (
        specs.get("apertura máx")
        or specs.get("apertura max")
        or specs.get("apertura")
    )
    if apertura and "f/" not in modelo_lc and "t/" not in modelo_lc:
        v = str(apertura).strip()
        if v.lower().startswith("t"):
            # Cine: T-stops (T3, T2.1). Dejar tal cual, sin prefijo f/.
            pass
        elif not v.lower().startswith("f/"):
            v = re.sub(r"^f\s*", "", v, flags=re.IGNORECASE)
            v = f"f/{v}"
        extras_corto.append(v)

    # Montura (lens_mount canónico, con fallback a montura legacy).
    mount_val = specs.get("lens_mount") or specs.get("montura")
    if mount_val and "montura" not in modelo_lc and "mount" not in modelo_lc:
        extras_corto.append(f"Montura {mount_val}")
        extras_largo.append(f"Montura {mount_val}")

    # Formato solo en el largo
    if specs.get("formato"):
        extras_largo.append(specs["formato"])

    return base + extras_corto, base + extras_corto + extras_largo


def _fmt_luz(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Luz LED Amaran 300C RGB Bicolor
       Luz LED Nanlite Forza 500 Daylight (si no es RGB/bicolor)
       Flash Godox V1"""
    tipo = SUBCATEGORIA_A_TIPO.get(subcat or "", "Luz")
    # Si subcategoría es "LED daylight/bicolor" pero NI rgb NI bicolor → "Luz LED Daylight"
    es_rgb = _is_true(specs.get("rgb"))
    es_bicolor = _is_true(specs.get("bicolor"))

    base = [tipo, marca, modelo]

    extras_corto = []
    if es_rgb:
        extras_corto.append("RGB")
    if es_bicolor:
        extras_corto.append("Bicolor")

    # Si no es ni RGB ni bicolor y la subcategoría es "LED daylight/bicolor",
    # asumimos daylight (los daylight puros van en esa subcat).
    if not extras_corto and (subcat or "").lower().startswith("led daylight"):
        extras_corto.append("Daylight")

    extras_largo = list(extras_corto)
    if specs.get("potencia"):
        extras_largo.append(f"{specs['potencia']}W")
    return base + extras_corto, base + extras_largo


def _fmt_modificador(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Softbox Aputure 90cm
       Bandera Negra 35x40cm"""
    # Si hay spec "tipo" en specs, lo preferimos sobre subcategoría
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Modificador")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    if specs.get("medidas"):
        extras_corto.append(specs["medidas"])
    extras_largo = list(extras_corto)
    if specs.get("material"):
        extras_largo.append(specs["material"])
    return base + extras_corto, base + extras_largo


def _fmt_soporte(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Trípode video Manfrotto 504 Carga 12kg
       C-Stand Avenger A2030D
       Gimbal Tilta Gravity G2X 3 ejes"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Soporte")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    extras_largo = []
    # Solo gimbal: ejes
    if (specs.get("tipo") == "Gimbal" or "gimbal" in (subcat or "").lower()) and specs.get("ejes"):
        extras_corto.append(f"{specs['ejes']} ejes")
    if specs.get("carga máx") or specs.get("carga max"):
        v = specs.get("carga máx") or specs.get("carga max")
        extras_largo.append(f"Carga {v}kg")
    return base + extras_corto, base + extras_largo


def _fmt_grip(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Brazo Avenger D200
       Lastre Impact 15 lb
       Cage Tilta para FX3"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Grip")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    extras_largo = []
    if specs.get("medidas"):
        extras_corto.append(specs["medidas"])
    return base + extras_corto, base + extras_largo


def _fmt_adaptador(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Adaptador Sigma MC-11 EF→E
       Filtro ND Tiffen 82mm Variable"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Adaptador")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    in_m = specs.get("montura entrada")
    out_m = specs.get("montura salida")
    if in_m and out_m:
        extras_corto.append(f"{in_m}→{out_m}")
    elif in_m:
        extras_corto.append(in_m)
    if specs.get("diámetro") or specs.get("diametro"):
        v = specs.get("diámetro") or specs.get("diametro")
        extras_corto.append(f"{v}mm")
    if specs.get("densidad nd") or specs.get("densidad"):
        v = specs.get("densidad nd") or specs.get("densidad")
        extras_corto.append(v)
    return base + extras_corto, base + extras_corto


def _fmt_sonido(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Lavalier Rode Wireless GO II
       Shotgun Sennheiser MKE 600"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Audio")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    extras_largo = []
    if specs.get("banda"):
        extras_largo.append(specs["banda"])
    return base + extras_corto, base + extras_largo


def _fmt_monitor(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Monitor SmallHD 7" 1080p
       Grabador Atomos Ninja V"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Monitor")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    if specs.get("pulgadas"):
        extras_corto.append(f"{specs['pulgadas']}\"")
    extras_largo = list(extras_corto)
    if specs.get("resolución") or specs.get("resolucion"):
        v = specs.get("resolución") or specs.get("resolucion")
        extras_largo.append(v)
    return base + extras_corto, base + extras_largo


def _fmt_energia(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Batería V-mount 150Wh
       Distribución V-mount 4 canales"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Batería")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    if specs.get("capacidad"):
        extras_corto.append(f"{specs['capacidad']}Wh")
    if specs.get("canales"):
        extras_corto.append(f"{specs['canales']} canales")
    return base + extras_corto, base + extras_corto


def _fmt_media(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Tarjeta SD SanDisk 256GB V90
       Lector CFexpress Sony MRW-G2"""
    tipo = (
        specs.get("tipo")
        or SUBCATEGORIA_A_TIPO.get(subcat or "", "Media")
    )
    base = [tipo, marca, modelo]
    extras_corto = []
    if specs.get("capacidad"):
        extras_corto.append(f"{specs['capacidad']}GB")
    if specs.get("clase"):
        extras_corto.append(specs["clase"])
    return base + extras_corto, base + extras_corto


def _fmt_generico(*, marca, modelo, subcat, specs, raiz, **_) -> tuple[list[str], list[str]]:
    """Fallback: tipo + marca + modelo, sin specs."""
    tipo = SUBCATEGORIA_A_TIPO.get(subcat or "", RAIZ_A_TIPO.get(raiz or "", ""))
    return [tipo, marca, modelo], [tipo, marca, modelo]


# Mapeo de raíz → formatter
_FORMATTERS = {
    "Cámaras": _fmt_camara,
    "Lentes": _fmt_lente,
    "Iluminación": _fmt_luz,
    "Modificadores": _fmt_modificador,
    "Soportes": _fmt_soporte,
    "Grip": _fmt_grip,
    "Adaptadores y Filtros": _fmt_adaptador,
    "Sonido": _fmt_sonido,
    "Monitores y Video": _fmt_monitor,
    "Energía": _fmt_energia,
    "Media y Datos": _fmt_media,
}


# ── API pública ─────────────────────────────────────────────────────────

def construir_nombre_publico(
    *,
    nombre_interno: str,
    marca: Optional[str],
    modelo: Optional[str],
    categoria_raiz: Optional[str],
    categoria_sub: Optional[str] = None,
    specs_en_nombre: list[tuple[str, str]],
    template_override: Optional[str] = None,
    nombre_publico_override: Optional[str] = None,
) -> tuple[str, str]:
    """Devuelve (nombre_publico, nombre_publico_largo).

    Args:
        nombre_interno: el `equipos.nombre` (fallback final).
        marca / modelo: del equipo.
        categoria_raiz: ej. "Iluminación". None si el equipo no tiene
            categoría asignada → fallback a nombre interno.
        categoria_sub: ej. "LED daylight/bicolor". Refina el tipo.
        specs_en_nombre: lista de tuplas (label, value) desde `equipo_specs`,
            filtradas por `visible_en_nombre=TRUE`.
        template_override: si la ficha tiene `nombre_publico_template`,
            se usa con tokens.
        nombre_publico_override: override manual del admin desde la UI de
            validación. Gana sobre todo el resto.
    """
    marca_s = (marca or "").strip()
    modelo_s = (modelo or "").strip()
    nombre_s = (nombre_interno or "").strip()

    # 1. Override del admin (UI de validación) — gana sobre todo
    if nombre_publico_override and nombre_publico_override.strip():
        v = nombre_publico_override.strip()
        return v, v

    # 2. Template manual con tokens (ficha)
    if template_override and template_override.strip():
        vars_dict = {
            "tipo": SUBCATEGORIA_A_TIPO.get(categoria_sub or "", "")
                    or RAIZ_A_TIPO.get(categoria_raiz or "", ""),
            "marca": marca_s,
            "modelo": modelo_s,
            "nombre": nombre_s,
        }
        rendered = _render_template(template_override, vars_dict, specs=specs_en_nombre)
        if rendered:
            return rendered, rendered

    # 3. Auto-build: dispatch al formatter de la categoría raíz
    formatter = _FORMATTERS.get(categoria_raiz or "", _fmt_generico)

    specs_d = _specs_dict(specs_en_nombre)
    # Algunos formatters usan la lista ordenada en lugar de dict (porque
    # importa el orden de prioridad del template).
    parts_corto, parts_largo = formatter(
        marca=marca_s, modelo=modelo_s,
        subcat=categoria_sub, raiz=categoria_raiz,
        specs=specs_d,
        specs_ordered=specs_en_nombre,
    )

    corto = _join(parts_corto)
    largo = _join(parts_largo)

    # Cap suave del corto (60 chars)
    corto = _cap_largo(corto, 60)

    # Fallback si todo quedó vacío
    if not corto:
        corto = nombre_s
    if not largo:
        largo = corto or nombre_s

    return corto, largo
