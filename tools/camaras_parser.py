#!/usr/bin/env python3
"""
tools/camaras_parser.py — Parser de HTMLs de B&H para cámaras.

Mismo pipeline que iluminacion_parser pero con spec mapping específico
de cámaras (lens_mount, formato, codecs, ISO, FPS, etc.).

Reusa las primitives genéricas de iluminacion_parser:
  - BHSpecsParser (clase DOM data-selenium)
  - _clean_title, _extract_brand, _extract_modelo, _extract_id (helpers de title)
  - Las regex de cleanup (dimensiones, units, genericos)

Lo único específico de esta categoría son los mappers:
  - map_camara_specs   → 11 spec_keys canónicos para comparación
  - map_camara_extras  → ~15 campos estructurados para ficha técnica

Uso:
    python3 tools/camaras_parser.py ~/Desktop/Paginas/Camaras/*.html
"""

import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path

# Reusar primitives genéricas del parser de iluminación (no duplicar)
from iluminacion_parser import (  # type: ignore
    BHSpecsParser,
    _clean_title,
    _extract_brand,
    _extract_id,
    _extract_modelo,
    _find_value,
)

ROOT = Path(__file__).parent.parent
RELEVAMIENTO_PATH = ROOT / "docs" / "camaras_raw.json"
CURADO_PATH = ROOT / "docs" / "camaras.json"


# ── Spec mappers específicos de cámaras ────────────────────────────────

def _parse_formato(secciones: dict) -> str | None:
    """'Image Sensor' → formato canónico: Full-frame / Super 35 / APS-C / MFT / 1\""""
    val = _find_value(secciones, "Image Sensor", "Sensor Size", "Sensor Type")
    if not val:
        return None
    v = val.lower()
    # Patrones canónicos
    if "full-frame" in v or "full frame" in v:
        return "Full-frame"
    if "super 35" in v or "super35" in v or "s35" in v:
        return "Super 35"
    if "aps-c" in v or "apsc" in v:
        return "APS-C"
    if "micro four thirds" in v or "mft" in v or "m4/3" in v:
        return "MFT"
    if "medium format" in v:
        return "Medium Format"
    if "1/1.9" in v or '1/1.9"' in v or "1/2.3" in v:
        return "1\""
    return val.strip()


def _parse_megapixels(secciones: dict) -> float | None:
    val = _find_value(secciones, "Effective Sensor Resolution", "Effective Pixels", "Total Pixels")
    if not val:
        return None
    m = re.search(r"([\d.]+)\s*Megapixel", val, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m2 = re.search(r"([\d.]+)\s*MP", val, re.IGNORECASE)
    return float(m2.group(1)) if m2 else None


def _parse_lens_mount(secciones: dict, title: str = "") -> str | None:
    """Canon E / RF / EF / L / Z / X / MFT / PL / BMD / B4.

    Source priority: 'Lens Mount' field directo (ej. 'Sony E', 'Canon RF', 'EF').
    Si no hay, inferir desde título.
    """
    val = (_find_value(secciones, "Lens Mount", "Mount") or "").strip().lower()
    title_l = title.lower()

    # 1. Match desde el campo Lens Mount directo (más confiable)
    if val:
        if val in ("sony e", "e", "e-mount"): return "E"
        if val in ("canon rf", "rf", "rf-mount"): return "RF"
        if val in ("canon ef", "ef", "ef-mount"): return "EF"
        if val in ("l", "l-mount"): return "L"
        if val in ("nikon z", "z", "z-mount"): return "Z"
        if val in ("fuji x", "fujifilm x", "x", "x-mount"): return "X"
        if "micro four thirds" in val or val in ("mft", "m4/3"): return "MFT"
        if val in ("pl", "pl-mount"): return "PL"
        if "blackmagic" in val or val in ("bmd", "bmd-mount"): return "BMD"
        if val in ("b4", "b4-mount"): return "B4"
        # Multi-mount listings (KOMODO viene en RF/EF/PL)
        if "rf" in val and "mount" in val: return "RF"  # default RF si lista varios

    # 2. Inferir desde título
    if "gopro" in title_l or re.search(r"\bhero\d", title_l) or "action camera" in title_l:
        return "Fixed (action)"
    # Sony cinema/mirrorless con modelo conocido → E mount
    if re.search(r"\b(ilme|ilce|fx[369]|a[679]|zv-e|nex)", title_l):
        return "E"
    # Canon EOS C-series cinema con (EF-Mount)
    if "(ef-mount)" in title_l or " ef-mount" in title_l:
        return "EF"
    # Canon RF (R-series mirrorless)
    if re.search(r"\beos r\d|\beos rp\b", title_l):
        return "RF"
    return None


def _parse_resolucion_max(secciones: dict, title: str = "") -> str | None:
    """Devuelve resolución máxima canónica: FHD / 2K / 4K / 5.7K / 6K / 8K / 12K"""
    val = _find_value(
        secciones, "Internal Recording", "Max Recording Modes", "Max Video Output",
        "Video Output", "Video Format"
    ) or ""
    haystack = f"{val} {title}".lower()
    # Orden: más alta primero
    for tag, label in [
        (r"\b12k\b|12288\s*x|11520\s*x", "12K"),
        (r"\b8k\b|8192\s*x|7680\s*x", "8K"),
        (r"\b6k\b|6144\s*x|6072\s*x|5760\s*x", "6K"),
        (r"\b5\.7k\b", "5.7K"),
        (r"\b5\.?\d*k\b|5120\s*x|5312\s*x", "5K"),
        (r"\b4k\b|4096\s*x|3840\s*x|\bdci\s*4k\b|\buhd\s*4k\b|\buhd\b", "4K"),
        (r"\b2\.?\d*k\b|2048\s*x", "2K"),
        (r"\b1080\b|\bfhd\b|1920\s*x", "FHD"),
    ]:
        if re.search(tag, haystack):
            return label
    return None


def _parse_fps_max(secciones: dict) -> int | None:
    """FPS máximo. B&H lista varios fps por línea (ej. '23.98/25/29.97/50/59.94 fps').
    Tomamos el máximo global de toda la cadena de Internal Recording.
    """
    val = _find_value(secciones, "Internal Recording", "Max Recording Modes", "Frame Rate") or ""
    if not val:
        return None
    # Patrón 1: lista de números separados por / antes de 'fps' — ej. "29.97/50/59.94/100/120 fps"
    # Capturamos toda la cadena de números/decimales/slash antes de 'fps'
    all_fps = []
    for m in re.finditer(r"([\d./\s]+)\s*fps", val, re.IGNORECASE):
        segment = m.group(1)
        for n in re.findall(r"\d+(?:\.\d+)?", segment):
            all_fps.append(float(n))
    # Patrón 2: "up to N fps" patterns
    for m in re.finditer(r"up\s*to\s*(\d+)\s*fps", val, re.IGNORECASE):
        all_fps.append(float(m.group(1)))
    # Patrón 3: numero seguido de 'p' (120p, 240p) — solo si >= 24
    for m in re.finditer(r"\b(\d{2,4})\s*p\b", val):
        n = float(m.group(1))
        if 24 <= n <= 1000:
            all_fps.append(n)
    if not all_fps:
        return None
    return int(max(all_fps))


def _parse_sensor(secciones: dict) -> str | None:
    """String descriptivo del sensor: 'Full-frame CMOS 10.2MP' etc."""
    image_sensor = _find_value(secciones, "Image Sensor") or ""
    mp = _find_value(secciones, "Effective Sensor Resolution") or ""
    parts = []
    if image_sensor:
        parts.append(image_sensor.strip())
    if mp:
        m = re.search(r"[\d.]+\s*Megapixel", mp, re.IGNORECASE)
        if m:
            parts.append(m.group(0))
    return " — ".join(parts) if parts else None


def _parse_codecs(secciones: dict) -> str | None:
    """Codecs principales — extrae partes claves del 'Internal Recording' o 'Max Recording Modes'."""
    val = _find_value(secciones, "Internal Recording", "Max Recording Modes") or ""
    if not val:
        return None
    # Detectar codecs conocidos (devolvemos una lista compacta como string)
    codecs_found = []
    KNOWN_CODECS = [
        ("ProRes RAW", r"prores\s*raw"),
        ("ProRes", r"prores(?!\s*raw)"),
        ("DNxHR", r"dnxhr"),
        ("RAW 16-Bit", r"raw\s*16-?bit"),
        ("XAVC HS", r"xavc\s*hs"),
        ("XAVC S-I 4:2:2", r"xavc\s*s-?i\s*4:2:2"),
        ("XAVC S 4:2:2", r"xavc\s*s\s*4:2:2"),
        ("XAVC S", r"xavc\s*s(?!-?i)(?!\s*4)"),
        ("REDCODE", r"redcode|r3d"),
        ("Cinema RAW Light", r"cinema\s*raw\s*light"),
        ("Cinema RAW", r"cinema\s*raw(?!\s*light)"),
        ("MPEG-4 AVC", r"mpeg-?4\s*avc"),
        ("H.265 HEVC", r"h\.?265|hevc"),
        ("H.264", r"h\.?264"),
        ("HEIF", r"heif"),
    ]
    seen = set()
    for label, pat in KNOWN_CODECS:
        if re.search(pat, val, re.IGNORECASE) and label not in seen:
            codecs_found.append(label)
            seen.add(label)
    return ", ".join(codecs_found) if codecs_found else None


def _parse_iso_range(secciones: dict, kind: str = "native") -> dict | None:
    """ISO range. kind: 'native' → 'Native: X to Y' | 'extended' → 'X to Y Extended'"""
    val = _find_value(secciones, "ISO/Gain Sensitivity", "ISO Range") or ""
    if not val:
        return None
    if kind == "native":
        m = re.search(r"native:\s*(\d[\d,]*)\s*to\s*(\d[\d,]*)", val, re.IGNORECASE)
    else:
        m = re.search(r"(\d[\d,]*)\s*to\s*(\d[\d,]*)\s*extended", val, re.IGNORECASE)
        if not m:
            m = re.search(r"extended:?\s*(\d[\d,]*)\s*to\s*(\d[\d,]*)", val, re.IGNORECASE)
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
        return {"min": lo, "max": hi}
    return None


def _parse_rango_dinamico(secciones: dict) -> int | None:
    val = _find_value(secciones, "Advertised Dynamic Range", "Dynamic Range") or ""
    if not val:
        return None
    m = re.search(r"([\d.]+)\s*Stops?", val, re.IGNORECASE)
    return int(float(m.group(1))) if m else None


def _parse_estabilizacion(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Image Stabilization")
    if val is None:
        return None
    v = val.strip().lower()
    return v not in ("no", "none", "n/a", "")


def _parse_tipo_estabilizacion(secciones: dict) -> str | None:
    val = _find_value(secciones, "Image Stabilization")
    if not val or val.strip().lower() in ("no", "none", "n/a", "yes"):
        return None
    return val.strip()


def _parse_autofocus(secciones: dict) -> bool | None:
    af_points = _find_value(secciones, "Autofocus Points")
    if af_points and re.search(r"\d", af_points):
        return True
    focus_mode = _find_value(secciones, "Focus Mode", "Focus Modes", "Focus Type", "Autofocus System") or ""
    if re.search(r"\bauto", focus_mode, re.IGNORECASE):
        return True
    return None


def _parse_af_puntos(secciones: dict) -> int | None:
    val = _find_value(secciones, "Autofocus Points") or ""
    if not val:
        return None
    m = re.search(r"(\d+)", val.replace(",", ""))
    return int(m.group(1)) if m else None


def _parse_memoria_tipo(secciones: dict) -> str | None:
    val = _find_value(secciones, "Media/Memory Card Slot", "Recording Media", "Internal Storage")
    return val.strip() if val else None


def _parse_salida_video(secciones: dict) -> str | None:
    val = _find_value(secciones, "Video I/O", "HDMI Output", "SDI") or ""
    if not val:
        return None
    # Quedarnos con descriptores cortos (HDMI Type-A, BNC SDI 12G, etc.)
    outputs = []
    for pat, label in [
        (r"hdmi\s*type-?a", "HDMI Type-A"),
        (r"hdmi\s*type-?d|micro\s*hdmi", "Micro HDMI"),
        (r"hdmi\s*type-?c|mini\s*hdmi", "Mini HDMI"),
        (r"hdmi", "HDMI"),
        (r"3g-?sdi", "3G-SDI"),
        (r"6g-?sdi", "6G-SDI"),
        (r"12g-?sdi", "12G-SDI"),
        (r"sdi", "SDI"),
        (r"usb-?c", "USB-C"),
        (r"thunderbolt", "Thunderbolt"),
        (r"bnc", "BNC"),
    ]:
        if re.search(pat, val, re.IGNORECASE) and label not in outputs:
            outputs.append(label)
    return ", ".join(outputs) if outputs else val.split("|")[0].strip()


def _parse_audio_canales(secciones: dict) -> int | None:
    val = _find_value(secciones, "Audio Recording") or ""
    if not val:
        return None
    m = re.search(r"(\d+)-?Channel", val, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_visor_evf(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Display Type", "Viewfinder Type", "Viewfinder", "Coverage") or ""
    if "evf" in val.lower() or "electronic viewfinder" in val.lower() or "oled viewfinder" in val.lower():
        return True
    return None


def _parse_pantalla(secciones: dict) -> str | None:
    val = _find_value(secciones, "Display Type", "Monitor")
    if not val:
        return None
    # Tomar primera línea / antes de "|"
    line = val.split("|")[0].split("\n")[0].strip()
    return line


def _parse_bateria(secciones: dict) -> str | None:
    val = _find_value(secciones, "Battery", "Battery Type") or ""
    if not val:
        return None
    line = val.split("|")[0].split("\n")[0].strip()
    return line


def _parse_consumo_w(secciones: dict) -> float | None:
    val = _find_value(secciones, "Power Consumption") or ""
    m = re.search(r"([\d.]+)\s*W\b", val, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _parse_netflix_approved(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Netflix Approved")
    if val is None:
        return None
    return val.strip().lower() in ("yes", "true", "sí", "si")


def _parse_peso_g(secciones: dict) -> int | None:
    """Weight → int gramos. B&H formato 'X lb / Y g' o 'X lb / Y kg'."""
    val = _find_value(secciones, "Weight") or ""
    if not val:
        return None
    # Preferir grams del primer token útil (body only típicamente)
    first_part = val.split("|")[0]
    m_g = re.search(r"([\d.]+)\s*g\b", first_part)
    m_kg = re.search(r"([\d.]+)\s*kg", first_part)
    if m_kg:
        return int(float(m_kg.group(1)) * 1000)
    if m_g:
        return int(float(m_g.group(1)))
    # Fallback desde lb
    m_lb = re.search(r"([\d.]+)\s*lb", first_part, re.IGNORECASE)
    if m_lb:
        return int(float(m_lb.group(1)) * 453.592)
    return None


def _parse_dimensiones_cm(secciones: dict) -> dict | None:
    """Dimensions → {largo_cm, ancho_cm, alto_cm}"""
    val = _find_value(secciones, "Dimensions (W x H x D)", "Dimensions", "Size") or ""
    if not val:
        return None
    # Preferir métrico (cm o mm)
    m_cm = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*cm", val, re.IGNORECASE)
    if m_cm:
        return {"largo_cm": float(m_cm.group(1)), "ancho_cm": float(m_cm.group(2)), "alto_cm": float(m_cm.group(3))}
    m_mm = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*mm", val, re.IGNORECASE)
    if m_mm:
        return {"largo_cm": float(m_mm.group(1))/10, "ancho_cm": float(m_mm.group(2))/10, "alto_cm": float(m_mm.group(3))/10}
    # Solo imperial — convertir
    m_in = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*[\"']", val)
    if m_in:
        return {
            "largo_cm": round(float(m_in.group(1)) * 2.54, 2),
            "ancho_cm": round(float(m_in.group(2)) * 2.54, 2),
            "alto_cm": round(float(m_in.group(3)) * 2.54, 2),
        }
    return None


# ── Tipo (categorización canon de cámaras) ──────────────────────────────

_TIPO_KEYWORDS = [
    ("Cinema Camera", ["cinema camera", "digital cinema"]),
    ("Mirrorless", ["mirrorless"]),
    ("DSLR", ["dslr"]),
    ("Action Camera", ["action camera", "gopro hero", "hero1", "hero2", "osmo action"]),
    ("Vlogging", ["zv-", "vlogging", "vlog"]),
    ("Compact", ["compact camera", "point and shoot"]),
    ("Medium Format", ["medium format"]),
]


def _parse_tipo(secciones: dict, title: str = "") -> str | None:
    item = (_find_value(secciones, "Capture Type", "Type") or "").lower()
    ctx = f"{title} {item}".lower()
    # ZV-E1 es vlogging, identificar primero
    if "zv-e" in ctx or "vlogging" in ctx:
        return "Vlogging"
    for label, keywords in _TIPO_KEYWORDS:
        if any(k in ctx for k in keywords):
            return label
    # Default si tiene "camera" en el título y no matchea nada
    if "camera" in ctx:
        return "Camera"
    return None


# ── Mappers principales ─────────────────────────────────────────────────

def _parse_continuous_shooting_fps(secciones: dict) -> int | None:
    """Burst rate fps para stills. Ej. '10 fps' → 10"""
    val = _find_value(secciones, "Continuous Shooting") or ""
    if not val:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", val, re.IGNORECASE)
    return int(float(m.group(1))) if m else None


def _parse_fast_slow_motion(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Fast-/Slow-Motion Support", "Fast-/Slow-Motion")
    if val is None:
        return None
    return val.strip().lower() in ("yes", "true", "sí", "si")


def _parse_lens_communication(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Lens Communication")
    if val is None:
        return None
    return val.strip().lower().startswith(("yes", "sí", "si", "true"))


def _parse_max_aperture(secciones: dict) -> str | None:
    """Solo aplica para fixed-lens (GoPro/action cams)."""
    val = _find_value(secciones, "Maximum Aperture")
    if not val:
        return None
    line = val.split("|")[0].split("\n")[0].strip()
    return line


def _parse_recording_limit_min(secciones: dict) -> int | None:
    """Recording limit en minutos. Ej. 'Unlimited' → null; '29 minutes 59 seconds' → 29"""
    val = _find_value(secciones, "Recording Limit") or ""
    if not val or val.strip().lower() in ("unlimited", "none", "no limit", "no"):
        return None
    m = re.search(r"(\d+)\s*minute", val, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_sensor_crop(secciones: dict) -> str | None:
    val = _find_value(secciones, "Sensor Crop (35mm Equivalent)", "Sensor Crop")
    if not val:
        return None
    return val.strip()


def _parse_gps(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Global Positioning (GPS, GLONASS, etc.)", "GPS")
    if val is None:
        return None
    v = val.strip().lower()
    return v not in ("no", "none", "n/a", "")


def _parse_ip_streaming(secciones: dict) -> bool | None:
    val = _find_value(secciones, "IP Streaming")
    if val is None:
        return None
    return val.strip().lower() in ("yes", "true", "sí", "si")


def _parse_internal_storage(secciones: dict) -> str | None:
    val = _find_value(secciones, "Internal Storage")
    if not val or val.strip().lower() in ("no", "none", "n/a"):
        return None
    return val.strip()


def map_camara_specs(secciones: dict, title: str = "") -> dict:
    """Mapea secciones raw → spec_keys canónicos del proyecto para Cámaras.

    Incluye campos filtrables/comparables. Los descriptivos van en extras.
    """
    result: dict = {}

    def _add(key, val):
        if val is not None and val != "" and val != []:
            result[key] = val

    # Core identity
    _add("tipo", _parse_tipo(secciones, title))
    _add("lens_mount", _parse_lens_mount(secciones, title))
    _add("formato", _parse_formato(secciones))

    # Video specs
    _add("resolucion_max", _parse_resolucion_max(secciones, title))
    _add("fps_max", _parse_fps_max(secciones))
    _add("codecs", _parse_codecs(secciones))

    # Stills specs
    _add("megapixels", _parse_megapixels(secciones))
    _add("continuous_shooting_fps", _parse_continuous_shooting_fps(secciones))

    # ISO / dynamic range
    _add("iso_nativo", _parse_iso_range(secciones, "native"))
    _add("iso_extendido", _parse_iso_range(secciones, "extended"))
    _add("rango_dinamico_stops", _parse_rango_dinamico(secciones))

    # Capabilities (booleans / specific)
    est = _parse_estabilizacion(secciones)
    if est is not None: result["estabilizacion"] = est
    af = _parse_autofocus(secciones)
    if af is not None: result["autofocus"] = af
    fsm = _parse_fast_slow_motion(secciones)
    if fsm is not None: result["fast_slow_motion"] = fsm
    lc = _parse_lens_communication(secciones)
    if lc is not None: result["lens_communication"] = lc
    gps = _parse_gps(secciones)
    if gps is not None: result["gps"] = gps
    ips = _parse_ip_streaming(secciones)
    if ips is not None: result["ip_streaming"] = ips

    # Cinema-grade
    _add("netflix_approved", _parse_netflix_approved(secciones))

    # Fixed-lens specs (GoPro/action)
    _add("max_aperture", _parse_max_aperture(secciones))
    _add("sensor_crop", _parse_sensor_crop(secciones))

    # Recording limits
    _add("recording_limit_min", _parse_recording_limit_min(secciones))

    # Physical
    _add("peso_g", _parse_peso_g(secciones))

    return result


def map_camara_extras(secciones: dict, title: str = "") -> dict:
    """Campos extra estructurados para ficha técnica de cámaras.

    Captura sistemáticamente TODO lo útil del JSON-LD de B&H que no esté
    ya en `specs`. Cada campo del raw → key estructurada.
    """
    result: dict = {}

    def _add(key, val):
        if val is not None and val != "" and val != []:
            result[key] = val

    # ── Imaging ──────────────────────────────────────────────────────
    _add("sensor", _parse_sensor(secciones))
    _add("tipo_estabilizacion", _parse_tipo_estabilizacion(secciones))
    _add("af_puntos", _parse_af_puntos(secciones))

    # ── Storage / memoria ────────────────────────────────────────────
    _add("memoria_tipo", _parse_memoria_tipo(secciones))
    _add("internal_storage", _parse_internal_storage(secciones))

    # ── I/O ───────────────────────────────────────────────────────────
    _add("salida_video", _parse_salida_video(secciones))
    _add("audio_canales", _parse_audio_canales(secciones))

    # ── Display ───────────────────────────────────────────────────────
    _add("visor_evf", _parse_visor_evf(secciones))
    _add("pantalla", _parse_pantalla(secciones))

    # ── Power ─────────────────────────────────────────────────────────
    _add("bateria", _parse_bateria(secciones))
    _add("consumo_w", _parse_consumo_w(secciones))

    # ── Physical ──────────────────────────────────────────────────────
    _add("dimensiones_cm", _parse_dimensiones_cm(secciones))

    # ── Catch-all: campos directos del JSON-LD de B&H ────────────────
    # Cada (label_raw, key_destino) — preserva valor multi-línea con \n
    FIELD_MAP = [
        # Connectivity & I/O
        ("Mobile App Compatible", "app_compatible_raw"),
        ("Wireless",              "wireless"),
        ("Audio I/O",             "audio_io"),
        ("Power I/O",             "power_io"),
        ("Other I/O",             "other_io"),
        ("HDMI Output",           "hdmi_output"),
        ("SDI",                   "sdi"),
        ("Inputs/Outputs",        "inputs_outputs"),
        ("Headphone Connector",   "headphone"),
        ("Phantom Power",         "phantom_power"),

        # Mounting
        ("Tripod Mount",          "tripod_mount"),
        ("Shoe Mount",            "shoe_mount"),
        ("Accessory Mounting Thread", "accessory_thread"),
        ("Tripod Mounting Thread", "tripod_thread"),

        # Audio
        ("Built-In Microphone",   "built_in_mic"),
        ("Audio Recording",       "audio_recording"),
        ("Audio Input Terminals", "audio_inputs"),

        # Filters / lens
        ("Built-In ND Filter",    "built_in_nd"),
        ("Built-In CC Filter",    "built_in_cc"),
        ("Internal Filter Holder", "internal_filter_holder"),
        ("Color Filter System",   "color_filter_system"),
        ("Focal Length",          "focal_length"),
        ("Zoom",                  "zoom"),
        ("Field of View",         "field_of_view"),

        # Exposure
        ("Shutter Type",          "shutter_type"),
        ("Shutter Speed",         "shutter_speed"),
        ("Shutter Modes",         "shutter_modes"),
        ("Exposure Modes",        "exposure_modes"),
        ("Exposure Compensation", "exposure_compensation"),
        ("Metering Method",       "metering_method"),
        ("Metering Range",        "metering_range"),
        ("Bulb/Time Mode",        "bulb_mode"),
        ("Self-Timer",            "self_timer"),
        ("Bit Depth",             "bit_depth"),
        ("Aspect Ratio",          "aspect_ratio"),
        ("White Balance",         "white_balance"),
        ("Gamma Curve",           "gamma_curve"),
        ("Gain",                  "gain"),
        ("Signal-to-Noise Ratio", "signal_to_noise"),
        ("Autofocus Sensitivity", "autofocus_sensitivity"),
        ("Autofocus System",      "autofocus_system"),
        ("Focus Mode",            "focus_modes"),
        ("Focus Modes",           "focus_modes"),
        ("Focus Type",            "focus_type"),

        # Flash
        ("External Flash Connection", "external_flash"),
        ("Maximum Sync Speed",    "max_sync_speed"),
        ("Flash Modes",           "flash_modes"),
        ("Flash Compensation",    "flash_compensation"),
        ("Dedicated Flash System", "dedicated_flash"),
        ("Built-In Flash/Light",  "built_in_flash"),
        ("Built-In Light",        "built_in_light"),

        # Stills / file
        ("Image File Format",     "image_file_format"),
        ("Still Image Support",   "still_image_support"),
        ("Interval Recording",    "interval_recording"),
        ("Creative Effects",      "creative_effects"),

        # Video meta
        ("Video Output",          "video_output_modes"),
        ("Video Format",          "video_format"),
        ("Frame Rate",            "frame_rate_raw"),
        ("Time Code",             "time_code"),
        ("Scanning System",       "scanning_system"),
        ("Signal System",         "signal_system"),
        ("System Frequency Selection", "system_frequency"),

        # Viewfinder details
        ("Coverage",              "viewfinder_coverage"),
        ("Magnification",         "viewfinder_magnification"),
        ("Eye Point",             "viewfinder_eye_point"),
        ("Diopter Adjustment",    "viewfinder_diopter"),

        # Physical / general
        ("Materials",             "materiales"),
        ("Capture Type",          "capture_type"),
        ("Operating Conditions",  "operating_temp"),
        ("Storage Conditions",    "storage_temp"),
        ("Environmental Resistance", "environmental_resistance"),
        ("Impact Resistance",     "impact_resistance"),
        ("Processor",             "processor"),
        ("Power Supply",          "power_supply"),
        ("Charging Time",         "charging_time"),
        ("Estimated Battery Life", "battery_life"),
        ("Sensor Size",           "sensor_size"),
        ("Total Pixels",          "total_pixels"),
        ("Effective Pixels",      "effective_pixels"),
    ]

    seen_keys = set()
    for src, dst in FIELD_MAP:
        if dst in seen_keys:
            continue  # ya capturado por otra variante de label
        v = _find_value(secciones, src)
        if v:
            # Preservar multi-línea (B&H lista varios valores con \n)
            line = v.strip()
            if line and line.lower() not in ("no", "n/a", "none", "1 x"):
                result[dst] = line
                seen_keys.add(dst)

    return result


# ── JSON-LD enrichment (mismo flow que iluminacion) ────────────────────

def jsonld_specs(html_path: Path) -> dict:
    """Extrae propiedades desde Product.additionalProperty del JSON-LD."""
    if not html_path.exists():
        return {}
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if not (isinstance(data, dict) and data.get("@type") == "Product"):
            continue
        ap = data.get("additionalProperty", {})
        props = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
        result = {}
        for pv in props:
            if isinstance(pv, dict):
                n = pv.get("name")
                v = pv.get("value")
                if n:
                    if isinstance(v, list):
                        v = [html_lib.unescape(x.replace(" ", " ")) if isinstance(x, str) else x for x in v]
                    elif isinstance(v, str):
                        v = html_lib.unescape(v.replace(" ", " "))
                    result[n] = v
        return result
    return {}


def jsonld_image(html_path: Path) -> str | None:
    if not html_path.exists():
        return None
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
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


def jsonld_url(html_path: Path) -> str | None:
    if not html_path.exists():
        return None
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
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


# ── Procesamiento de archivo ────────────────────────────────────────────

_GARBAGE_VALUES = {"1 x", "1x", ":", "—", "-", "N/A", "n/a", ""}


def _is_garbage(v: str) -> bool:
    v = (v or "").strip()
    return v in _GARBAGE_VALUES or v.lower().startswith("not specified")


def parse_html(path: Path) -> dict:
    """Parsea un .html de B&H cámara y devuelve dict raw del producto."""
    content = path.read_text(encoding="utf-8", errors="replace")

    title_m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else path.stem
    title = _clean_title(title)

    parser = BHSpecsParser()
    parser.feed(content)
    secciones = dict(parser.secciones)

    # Mergear JSON-LD (más rico que DOM para cámaras)
    jl = jsonld_specs(path)
    if jl:
        jl_items = []
        for name, value in jl.items():
            if isinstance(value, list):
                # Filtrar basura, JOIN como string multi-línea para preservar contexto
                # (ej. "Max Recording Modes" tiene codec + resolución + fps en cadena)
                clean_parts = [str(v) for v in value if not _is_garbage(str(v))]
                if clean_parts:
                    jl_items.append({"label": name, "value": "\n".join(clean_parts)})
            elif not _is_garbage(str(value)):
                jl_items.append({"label": name, "value": str(value)})
        if jl_items:
            # JSON-LD primero (autoritativo), DOM como fallback
            secciones = {"Specs (JSON-LD)": jl_items, **secciones}

    image = jsonld_image(path)
    url = jsonld_url(path)
    if not url:
        saved = re.search(r"saved from url=\(\d+\)(https?://\S+)", content)
        if saved:
            url = saved.group(1).strip()

    prod_id = _extract_id(title)
    brand = _extract_brand(title)
    modelo = _extract_modelo(title)
    tipo = _parse_tipo(secciones, title) or "Camera"

    return {
        "id": prod_id,
        "categoria_raiz": "Cámaras",
        "subtipo": tipo,
        "marca": brand,
        "modelo": modelo,
        "url_source": url or "",
        "image_url": image or "",
        "status_bh": "Desconocido",
        "fuente": f"html guardado manual ({date.today().isoformat()})",
        "secciones": secciones,
    }


# ── Persistencia ────────────────────────────────────────────────────────

_META_TEMPLATE = {
    "version": "1.0",
    "descripcion": (
        "Dataset crudo de specs reales de B&H Photo (cámaras) capturadas por html "
        "guardado manual. Mismo workflow que docs/iluminacion_raw.json — fuente "
        "agnóstica, B&H primario + manufacturer sites como fallback."
    ),
    "metodo_captura": "HTML guardado manual (Cmd+S → Webpage Complete)",
    "convencion": "secciones B&H + JSON-LD merged",
}


def load_raw() -> dict:
    if RELEVAMIENTO_PATH.exists():
        return json.loads(RELEVAMIENTO_PATH.read_text(encoding="utf-8"))
    return {"_meta": _META_TEMPLATE, "products": []}


def save_raw(data: dict):
    RELEVAMIENTO_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_curado() -> dict:
    if CURADO_PATH.exists():
        return json.loads(CURADO_PATH.read_text(encoding="utf-8"))
    return {"_meta": {"descripcion": "Specs curadas de cámaras mapeadas a spec_keys del proyecto."}, "products": {}}


def save_curado(data: dict):
    CURADO_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────────────

def main(html_paths: list[Path]):
    raw_data = load_raw()
    curado = load_curado()

    existing_ids = {p["id"] for p in raw_data["products"]}
    added_raw = 0
    added_curado = 0
    skipped = 0

    for path in html_paths:
        if not path.exists():
            print(f"  WARN: no existe: {path}")
            continue

        print(f"Procesando: {path.name}")
        raw = parse_html(path)
        prod_id = raw["id"]

        if prod_id in existing_ids:
            print(f"  → raw ya existe ({prod_id}), skip")
            skipped += 1
        else:
            raw_data["products"].append(raw)
            existing_ids.add(prod_id)
            added_raw += 1
            print(f"  + raw agregado ({prod_id})")

        specs = map_camara_specs(raw["secciones"], title=raw["modelo"])
        extras = map_camara_extras(raw["secciones"], title=raw["modelo"])
        curado["products"][prod_id] = {
            "marca": raw["marca"],
            "modelo": raw["modelo"],
            "url_source": raw.get("url_source", ""),
            "image_url": raw.get("image_url", ""),
            "specs": specs,
            "extras": extras,
            "ficha": raw["secciones"],
        }
        added_curado += 1
        print(f"  + curado: {specs}")

    save_raw(raw_data)
    save_curado(curado)
    print(f"\nListo. Raw nuevos: {added_raw} | Curado: {added_curado} | Skipped: {skipped}")
    print(f"  → {RELEVAMIENTO_PATH.relative_to(ROOT)}")
    print(f"  → {CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/camaras_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)
    paths = []
    for arg in sys.argv[1:]:
        paths.extend(Path(arg).parent.glob(Path(arg).name) if "*" in arg else [Path(arg)])
    main(paths)
