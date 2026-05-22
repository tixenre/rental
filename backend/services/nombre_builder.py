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
from typing import Optional

from services.spec_render import (
    norm_spec_label,
    render_spec_placeholder,
)


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

    # Lentes — todas se llaman "Lente"; la montura va por filtro spec
    "Zoom": "Lente",
    "Fijos": "Lente",
    "Especiales": "Lente",
    "Vintage": "Lente",

    # Adaptadores / Filtros (raíces separadas)

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
    "Adaptadores": "Adaptador",
    "Filtros": "Filtro",
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


def _render_template(
    tpl: str,
    vars: dict[str, str],
    specs: Optional[list[dict]] = None,
) -> str:
    """Renderiza `{marca} {modelo} {spec:Lens mount}` con los vars dados.

    Tokens soportados:
      - `{marca}`, `{modelo}`, `{tipo}`, `{nombre}` → resueltos vía `vars`.
      - `{spec:Label}` → busca en `specs` por label normalizado (case+tilde
        insensitive). Si la spec es tabla, formatea con conectores.
      - `{spec:Label.colKey}` → para specs tipo tabla, extrae la celda `colKey`
        de la primera fila y la formatea como texto (valor + unidad). Para
        elegir otra fila: `{spec:Label.colKey[1]}`.

    `specs` es una lista de dicts {label, value, tipo, tabla_columnas, output_config?}.
    """
    lower = {k.lower(): (v or "").strip() for k, v in vars.items()}
    spec_map: dict[str, dict] = {}
    if specs:
        for s in specs:
            spec_map[norm_spec_label(s.get("label") or "")] = {
                "value": (s.get("value") or "").strip(),
                "tipo": s.get("tipo"),
                "unidad": s.get("unidad"),
                "tabla_columnas": s.get("tabla_columnas"),
                "output_config": s.get("output_config"),
            }

    def replace_token(m: re.Match) -> str:
        before, key, after = m.group(1), m.group(2), m.group(3)
        key_stripped = key.strip()
        if key_stripped.lower().startswith("spec:"):
            raw_key = key_stripped[len("spec:"):]
            # Parsear "Label" o "Label.colPath" — el módulo canónico resuelve
            # el path; acá solo separamos label de path.
            dot_idx = raw_key.find(".")
            label = raw_key if dot_idx == -1 else raw_key[:dot_idx]
            path = "" if dot_idx == -1 else raw_key[dot_idx + 1:]
            info = spec_map.get(norm_spec_label(label))
            if info:
                val = render_spec_placeholder(
                    info.get("value", "") or "",
                    info.get("tipo"),
                    info.get("tabla_columnas"),
                    info.get("output_config"),
                    path,
                    unidad=info.get("unidad"),
                )
            else:
                val = ""
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



# ── API pública ─────────────────────────────────────────────────────────

def construir_nombre_publico(
    *,
    nombre_interno: str,
    marca: Optional[str],
    modelo: Optional[str],
    categoria_raiz: Optional[str],
    categoria_sub: Optional[str] = None,
    specs_en_nombre: list[dict],
    template_override: Optional[str] = None,
    nombre_publico_override: Optional[str] = None,
) -> tuple[str, str]:
    """Devuelve (nombre_publico, nombre_publico_largo).

    Jerarquía (decidido en refactor 2026-05-22):
    1. Si hay `nombre_publico_override` (escape hatch manual del admin) →
       gana sobre todo.
    2. Si hay `template_override` (template de categoría o ficha) →
       `_render_template` con specs y vars del equipo.
    3. Si NO hay template → devolver `("", "")`. La UI debe usar
       `nombre_interno` como fallback.

    Antes había un auto-build con formatters por categoría (`_fmt_luz`,
    `_fmt_camara`, etc.) que tomaba decisiones hardcoded y miraba specs
    legacy. Se eliminó porque generaba inconsistencias con el template.

    `categoria_raiz` y `categoria_sub` quedan en la firma por compat con
    callers existentes, pero ya no se usan internamente.

    Args:
        nombre_interno: el `equipos.nombre` (no se usa salvo override).
        marca / modelo: del equipo.
        categoria_raiz: ej. "Iluminación". Compat — no se usa.
        categoria_sub: ej. "LED Bicolor". Compat — no se usa.
        specs_en_nombre: lista de dicts {label, value, tipo, unidad,
            tabla_columnas, output_config} desde `equipo_specs` JOIN
            `spec_definitions`.
        template_override: template con placeholders `{marca}` `{modelo}`
            `{nombre}` y `{spec:Label}`. Hoy viene de
            `categorias.nombre_publico_template`.
        nombre_publico_override: override manual del admin. Gana siempre.

    Returns:
        (corto, largo). Hoy ambos son iguales. `largo` queda en la firma
        por compat con consumers existentes.
    """
    marca_s = (marca or "").strip()
    modelo_s = (modelo or "").strip()
    nombre_s = (nombre_interno or "").strip()

    # 1. Override manual del admin — gana sobre todo
    if nombre_publico_override and nombre_publico_override.strip():
        v = nombre_publico_override.strip()
        return v, v

    # 2. Template del registry (categoría)
    if template_override and template_override.strip():
        vars_dict = {
            "marca": marca_s,
            "modelo": modelo_s,
            "nombre": nombre_s,
        }
        rendered = _render_template(template_override, vars_dict, specs=specs_en_nombre)
        if rendered:
            # Cap suave a 120 chars — los nombres del template suelen ser
            # más descriptivos que el auto-build legacy.
            rendered = _cap_largo(rendered, 120)
            return rendered, rendered
        # Template existe pero rindió vacío (todos los placeholders sin valor).
        # Igual devolvemos vacío para que la UI use nombre interno.

    # 3. Sin template → vacío. La UI usa `equipos.nombre` como fallback.
    return "", ""


# ════════════════════════════════════════════════════════════════════════
# Keywords derivadas de specs canónicos
# ════════════════════════════════════════════════════════════════════════
#
# `compute_keywords(specs)` reemplaza al sistema legacy de keywords LLM
# (que generaba strings raros). Genera lista canónica deduplicada limitada
# a ~12 términos por equipo, derivada de specs como lens_mount, formato,
# tipo, resolución, bicolor, etc.
#
# Reemplaza:
#   - LLM-output en `equipo_fichas.keywords_json` (autocompletar)
#   - El admin podía editar keywords manualmente — ahora se generan
#     determinísticamente en seeds + autocompletar HTML upload.
#
# Para que un spec genere keywords, agregarlo a SPEC_KEYWORDS_TEMPLATES.
# Las que NO están (peso_g, magnificacion, iso, etc.) NO aportan keywords
# porque nadie busca por ellas.


def _fmt_num(n) -> str:
    """123.0 → '123'; 2.8 → '2.8'; 1.4 → '1.4'. Drops trailing .0 from ints-as-float."""
    if n is None:
        return ""
    try:
        f = float(n)
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return str(n)


def _coerce_rango(value) -> list[float]:
    """Normaliza `value` a una lista de floats para handlers de rango.

    Acepta:
      - list / tuple de números
      - string "24-70" o "24-70mm" / "f/2.8" / "63.4°"
      - número solo → [valor]
      - dict {min, max} → [min, max]
      - None / vacío → []
    """
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                pass
        return out
    if isinstance(value, dict):
        if "min" in value and "max" in value:
            try:
                return [float(value["min"]), float(value["max"])]
            except (TypeError, ValueError):
                return []
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        nums = re.findall(r"\d+(?:\.\d+)?", value)
        return [float(n) for n in nums]
    return []


# spec_key → template para keywords. "_handler" → handler dedicado.
SPEC_KEYWORDS_TEMPLATES: dict[str, str] = {
    "lens_mount":     "{value}, {value}-mount, montura {value}",
    "lens_mount_out": "{value}, {value}-mount",
    "formato": "_formato_keywords",
    "resolucion_max": "_resolucion_keywords",
    "tipo": "{value}",
    "linea": "{value}",
    "diametro_filtro": "{value}mm, {value} mm, filter {value}",
    # Booleans útiles (solo si True)
    "bicolor":          "bicolor, bi-color, dual color",
    "rgb":              "RGB, color, full color, multi color",
    "dimming":          "dimmer, dimmable, regulable",
    "estabilizacion":   "estabilización, OSS, IS, stabilization",
    "autofocus":        "autofocus, AF",
    "netflix_approved": "Netflix, netflix approved",
    "ip_streaming":     "streaming, IP streaming, NDI, broadcast",
    "fast_slow_motion": "slow motion, S&Q, high frame rate",
    "electronica":      "comunicación electrónica, AF compatible",
    "incluye_iris":     "iris incluido, variable ND, drop-in",
    "densidad": "ND {value}, {value}",
    "grade": "grado {value}, {value}",
}

_FORMATO_KW: dict[str, list[str]] = {
    "Full-frame":    ["Full-frame", "FF", "full frame", "35mm"],
    "Super 35":      ["Super 35", "S35", "super35"],
    "APS-C":         ["APS-C", "APSC", "crop sensor"],
    "MFT":           ["MFT", "Micro Four Thirds", "M4/3"],
    "M4/3":          ["M4/3", "MFT", "Micro Four Thirds"],
    "Medium Format": ["Medium Format", "MF", "medium format"],
    "1\"":           ["1 pulgada", "1 inch sensor"],
}

_RESOLUCION_KW: dict[str, list[str]] = {
    "12K": ["12K"],
    "8K":  ["8K", "8K video"],
    "6K":  ["6K", "6K video"],
    "5.7K":["5.7K"],
    "5K":  ["5K"],
    "4K":  ["4K", "UHD", "4K UHD", "video 4K"],
    "2K":  ["2K"],
    "FHD": ["FHD", "1080p", "Full HD", "HD"],
}


def _expand_keyword_template(tpl: str, value) -> list[str]:
    """Resuelve un template a la lista de keywords concretas."""
    if not tpl:
        return []
    if tpl == "_formato_keywords":
        return _FORMATO_KW.get(str(value), [str(value)])
    if tpl == "_resolucion_keywords":
        return _RESOLUCION_KW.get(str(value), [str(value)])
    text = tpl.replace("{value}", str(value))
    return [p.strip() for p in text.split(",") if p.strip()]


def compute_keywords(specs: dict, max_total: int = 12) -> list[str]:
    """Genera keywords canónicas derivadas de los specs de un equipo.

    Determinística, deduplicada (case-insensitive), limitada a `max_total`.
    Devuelve lista de strings — guardar como JSON en `equipo_fichas.keywords_json`.
    """
    out: list[str] = []
    seen: set[str] = set()

    for spec_key, tpl in SPEC_KEYWORDS_TEMPLATES.items():
        value = specs.get(spec_key)
        if value is None or value == "" or value == []:
            continue

        if isinstance(value, bool):
            if not value:
                continue
            keywords = [p.strip() for p in tpl.split(",") if p.strip()]
        else:
            if isinstance(value, list):
                keywords = []
                for v in value:
                    keywords.extend(_expand_keyword_template(tpl, v))
            else:
                keywords = _expand_keyword_template(tpl, value)

        for kw in keywords:
            key = kw.lower()
            if key in seen or not kw:
                continue
            seen.add(key)
            out.append(kw)
            if len(out) >= max_total:
                return out

    return out
