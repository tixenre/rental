#!/usr/bin/env python3
"""
tools/camaras_normalizar.py — Normalización post-parse del dataset de cámaras.

Aplica:
  1. Marcas canónicas (Sony, Canon, RED, GoPro, etc.)
  2. Modelos limpios (sin "Full-Frame Cinema Camera" redundante)
  3. IDs estables (sony_fx3a, canon_c200, red_komodo_x, etc.)
  4. Cleanup de extras vacíos
  5. Reorden por relevancia
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "camaras.json"
RAW_PATH = ROOT / "docs" / "camaras_raw.json"


# ── Marcas canónicas ────────────────────────────────────────────────────

BRAND_CANON = {
    "sony": "Sony",
    "canon": "Canon",
    "nikon": "Nikon",
    "panasonic": "Panasonic",
    "fujifilm": "Fujifilm",
    "fuji": "Fujifilm",
    "olympus": "Olympus",
    "om": "OM System",
    "leica": "Leica",
    "hasselblad": "Hasselblad",
    "blackmagic": "Blackmagic Design",
    "bmd": "Blackmagic Design",
    "red": "RED",
    "red digital cinema": "RED",
    "arri": "ARRI",
    "zcam": "Z CAM",
    "z cam": "Z CAM",
    "kinefinity": "Kinefinity",
    "gopro": "GoPro",
    "dji": "DJI",
    "insta360": "Insta360",
}


def canon_brand(brand: str) -> str:
    key = brand.strip().lower()
    return BRAND_CANON.get(key, brand.strip())


# ── Modelo cleanup ──────────────────────────────────────────────────────

# Frases redundantes a quitar del modelo (ya están en `tipo` o `formato`)
# Orden: largas primero, cortas al final. Case-insensitive.
MODEL_NOISE_PHRASES = [
    # Frases largas (3+ palabras) primero
    r"\bFull-?Frame\s+Cinema\s+Camera\b",
    r"\bMirrorless\s+(?:Cinema\s+)?Camera\b",
    r"\bDigital\s+Cinema\s+Camera\b",
    r"\bDIGITAL\s+CINEMA\b",  # caps variant que aparece en RED
    r"\bAction\s+Camera\b",
    r"\bCinema\s+Camera\b",
    # Parentéticos
    r"\b\(EF-?Mount\)\b",
    r"\b\(RF-?Mount\)\b",
    r"\b\(E-?Mount\)\b",
    r"\b\(.*Camera\s+Body.*\)\b",
    # Cortas al final
    r"\bCamera\b",
    r"\bBody\b",
]

# Parentéticos a remover
MODEL_PARENS_NOISE = [
    r"\s*\(Black\)\s*",
    r"\s*\(Gray\)\s*",
    r"\s*\(Silver\)\s*",
    r"\s*\(EF-Mount\)\s*",
    r"\s*\(RF-Mount\)\s*",
    r"\s*\(E-Mount\)\s*",
    r"\s*\(Canon RF.*?\)\s*",
    r"\s*\(Sony.*?Mount\)\s*",
    # Body / kit descriptors
    r"\s*\([^)]*Body[^)]*\)\s*",
    r"\s*\([^)]*Kit[^)]*\)\s*",
]

# Tokens al final a remover (resoluciones, codecs sueltos que no son parte del modelo)
TRAILING_TOKENS = {"6K", "8K", "4K", "12K"}


def canon_modelo(modelo: str) -> str:
    s = modelo
    for pat in MODEL_PARENS_NOISE:
        s = re.sub(pat, " ", s)
    for pat in MODEL_NOISE_PHRASES:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)
    # Quitar SKU/code alfanumérico al final si parece código de B&H:
    # debe tener guión + ser largo (>=7 chars), ej. "ILME-FX3A", "CHDHX-121-TH", "710-0356", "2215C002"
    # NO matchear "C200" o "VL150" que son modelos reales
    s = re.sub(r"\s+[A-Z][A-Z0-9]*-[A-Z0-9-]+\s*$", "", s)  # con guión largo
    s = re.sub(r"\s+\d{7,}\s*$", "", s)  # solo dígitos largos (8+)
    s = re.sub(r"\s+\d{4,}[A-Z]\d+\s*$", "", s)  # ej. 2215C002
    # Sony SKUs (ILCE-7M5, ILME-FX3A) + posibles trailing tokens
    s = re.sub(r"\s+(?:ILCE|ILME)[-/\w]+(?:\s+\w+)?\s*$", "", s, flags=re.IGNORECASE)

    # Quitar duplicados del modelo (case-insensitive, palabra completa o prefijo largo)
    parts = s.split()
    cleaned = []
    seen_upper = set()
    for p in parts:
        pu = p.upper()
        if pu in seen_upper:
            continue
        # Si una versión previa de ESTE token (sin guiones/case) ya existe, skip
        if any(pu == sp or pu.replace("-", "") == sp.replace("-", "") for sp in seen_upper):
            continue
        cleaned.append(p)
        seen_upper.add(pu)

    # Quitar trailing tokens de resolución (6K, 8K, etc.) — pero solo si no son el ÚNICO contenido
    while len(cleaned) > 1 and cleaned[-1].upper() in TRAILING_TOKENS:
        cleaned.pop()

    s = " ".join(cleaned)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── IDs canónicos ───────────────────────────────────────────────────────

# Remapeos manuales si el _extract_id automático queda ambiguo o feo
ID_REMAP = {
    # Sony cameras
    "sony_ilmefx3a": "sony_fx3a",
    "sony_ilcefx3a": "sony_fx3a",
    "sony_ilce7m5": "sony_a7v",
    "sony_ilme7m5": "sony_a7v",
    "sony_a7m5": "sony_a7v",
    "sony_a75": "sony_a7v",
    "sony_zve1": "sony_zve1",
    "sony_zv": "sony_zve1",
    # Canon
    "canon_eos": "canon_c200",  # fallback ambiguo si _extract_id pega solo "eos"
    "canon_c200": "canon_c200",
    # RED — distinguir KOMODO regular vs KOMODO-X.
    # Los IDs raw del parser dependen del título B&H:
    #   "RED KOMODO-X DIGITAL CINEMA KOMODO-X 6K ..." → red_komodox / red_komodo_x
    #   "RED DIGITAL CINEMA KOMODO 6K Camera Production Pack ..." → red_digital
    #   "RED KOMODO 6K ..." → red_komodo
    "red_komodo_x":  "red_komodo_x",
    "red_komodox":   "red_komodo_x",
    "red_komodo":    "red_komodo",     # regular, no X
    "red_digital":   "red_komodo",     # fallback para "RED DIGITAL CINEMA KOMODO" sin X
    # GoPro
    "gopro_hero12": "gopro_hero12",
    "gopro_hero": "gopro_hero12",
}


def canon_id(pid: str) -> str:
    return ID_REMAP.get(pid, pid)


# ── Limpieza de extras ──────────────────────────────────────────────────

def clean_extras(extras: dict) -> dict:
    """Filtra valores basura de extras. Misma lógica que iluminacion_normalizar."""
    cleaned = {}
    GARBAGE = {"1 x", "1x", "n/a", "no", "none", ":", "yes", ""}
    for k, v in extras.items():
        if v is None or v == "" or v == "—":
            continue
        if isinstance(v, str):
            vc = v.strip()
            if vc.lower() in GARBAGE:
                continue
            if vc.lower().startswith("not specified"):
                continue
            cleaned[k] = vc
        else:
            cleaned[k] = v
    return cleaned


# ── Reorden ─────────────────────────────────────────────────────────────

SPECS_ORDER = [
    "tipo", "lens_mount", "formato",
    "resolucion_max", "fps_max", "codecs",
    "megapixels", "continuous_shooting_fps",
    "iso_nativo", "iso_extendido", "rango_dinamico_stops",
    "estabilizacion", "autofocus",
    "fast_slow_motion", "lens_communication",
    "gps", "ip_streaming",
    "netflix_approved",
    "max_aperture", "sensor_crop",
    "recording_limit_min",
    "peso_g",
]

EXTRAS_ORDER = [
    # Imaging
    "sensor", "sensor_size", "total_pixels", "effective_pixels",
    "tipo_estabilizacion", "af_puntos",
    "autofocus_system", "autofocus_sensitivity",
    "focus_modes", "focus_type",
    # Stills
    "image_file_format", "still_image_support", "interval_recording", "creative_effects",
    # Video meta
    "video_output_modes", "video_format", "frame_rate_raw",
    "time_code", "scanning_system", "signal_system", "system_frequency",
    "bit_depth", "aspect_ratio",
    # Exposure
    "shutter_type", "shutter_speed", "shutter_modes",
    "exposure_modes", "exposure_compensation",
    "metering_method", "metering_range",
    "bulb_mode", "self_timer",
    "white_balance", "gamma_curve", "gain", "signal_to_noise",
    # Lens / filters
    "focal_length", "zoom", "field_of_view",
    "built_in_nd", "built_in_cc", "internal_filter_holder", "color_filter_system",
    # Flash
    "built_in_flash", "built_in_light",
    "external_flash", "max_sync_speed", "flash_modes",
    "flash_compensation", "dedicated_flash",
    # Display / viewfinder
    "pantalla", "visor_evf",
    "viewfinder_coverage", "viewfinder_magnification",
    "viewfinder_eye_point", "viewfinder_diopter",
    # Storage / I/O
    "memoria_tipo", "internal_storage",
    "salida_video", "hdmi_output", "sdi",
    "audio_io", "audio_canales", "audio_recording", "audio_inputs",
    "built_in_mic", "headphone", "phantom_power",
    "power_io", "other_io", "inputs_outputs",
    # Mounting
    "tripod_mount", "shoe_mount", "accessory_thread", "tripod_thread",
    # Connectivity
    "wireless", "app_compatible_raw",
    # Power
    "bateria", "consumo_w", "power_supply",
    "charging_time", "battery_life",
    # Physical / environment
    "dimensiones_cm", "materiales",
    "operating_temp", "storage_temp",
    "environmental_resistance", "impact_resistance",
    # Processing
    "processor", "capture_type",
]


def reorder(d: dict, order: list[str]) -> dict:
    out = {}
    for k in order:
        if k in d:
            out[k] = d[k]
    for k, v in d.items():
        if k not in out:
            out[k] = v
    return out


# ── Main ────────────────────────────────────────────────────────────────

def normalizar():
    with open(CURADO_PATH) as f:
        curado = json.load(f)
    with open(RAW_PATH) as f:
        raw = json.load(f)

    new_products = {}
    id_remaps = []

    for old_id, p in curado["products"].items():
        new_id = canon_id(old_id)
        if new_id != old_id:
            id_remaps.append((old_id, new_id))

        p["marca"] = canon_brand(p.get("marca", ""))
        p["modelo"] = canon_modelo(p.get("modelo", ""))
        p["specs"] = reorder(p.get("specs", {}), SPECS_ORDER)
        p["extras"] = reorder(clean_extras(p.get("extras", {})), EXTRAS_ORDER)

        ordered = {
            "marca": p["marca"],
            "modelo": p["modelo"],
            "url_source": p.get("url_source", ""),
            "image_url": p.get("image_url", ""),
        }
        for k in ("specs", "extras", "ficha", "_nota"):
            if k in p:
                ordered[k] = p[k]
        new_products[new_id] = ordered

    curado["products"] = new_products

    for old_id, new_id in id_remaps:
        for rp in raw["products"]:
            if rp.get("id") == old_id:
                rp["id"] = new_id
        print(f"  ID remapped: {old_id} → {new_id}")

    for rp in raw["products"]:
        rp["marca"] = canon_brand(rp.get("marca", ""))

    with open(CURADO_PATH, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nNormalización aplicada: {len(curado['products'])} cámaras")


if __name__ == "__main__":
    normalizar()
