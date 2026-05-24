#!/usr/bin/env python3
"""
tools/camaras_patches.py — Parches manuales sobre el dataset curado.

Se ejecuta como parte de tools/camaras_rebuild.sh después del parser y
antes del normalizador. Sirve para:

1. Cámaras cuyo HTML NO viene de B&H (sites del fabricante, eBay, etc.).
2. Specs que B&H NO documenta en la página pública pero que conocemos por
   datasheet del fabricante o por experiencia con el equipo.

Las dos funciones que importan:
  - `MANUAL_SPEC_PATCHES`: dict {prod_id: {spec_key: value, ...}} con valores
    a mergear en `dataset.products[prod_id].specs`. Si la spec YA está seteada
    por el parser, NO se pisa (gana el parser, B&H es la fuente autoritativa).
  - `apply_patches()`: aplica el dict + cualquier override custom.

Convención:
  - Valores activos: descomentados, se aplican.
  - Valores conocidos pero a verificar: descomentados con comment `# TODO: verificar`
  - Valores que no sé: comentados con `# TODO: investigar (fuente?)`
  - Specs que NO aplican: comentadas con `# N/A` para que quede el rastro
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "camaras.json"
RAW_PATH = ROOT / "docs" / "camaras_raw.json"


# ─────────────────────────────────────────────────────────────────────────────
# Patches manuales por cámara
#
# Generados a partir del balance B&H vs registry de Cámaras al cierre del
# pipeline de extracción. Las claves usan el prod_id del dataset (snake_case,
# ej. sony_fx3a) — NO los slugs de la DB (esos viven en docs/equipos_match.json).
#
# Para cada cámara hay 3 grupos:
#   - "datos que conozco" → descomentados, se aplican
#   - "datos a verificar" → marcados con # TODO: verificar — descomentar cuando
#     confirmes el valor
#   - "datos a investigar" → marcados con # TODO: investigar — falta el dato
#
# Después de editar este archivo, correr: bash tools/camaras_rebuild.sh
# ─────────────────────────────────────────────────────────────────────────────

MANUAL_SPEC_PATCHES: dict[str, dict] = {

    # ── Sony FX3 (id_db=3) ───────────────────────────────────────────────────
    # B&H lista 46 specs. Faltantes que SÉ:
    "sony_fx3a": {
        "sensor_crop": "1x",                    # Full-frame default. Tiene S35 mode 1.5x.
        "continuous_shooting_fps": 10,          # 10 fps stills burst (compressed RAW)
        "processor": "BIONZ XR",
        # "recording_limit_min": None,          # Sin límite (cooling activo). None = no spec.
        # "time_code": "TC In/Out via shoe",    # TODO: verificar formato exacto del string
    },

    # ── Sony a7V (id_db=5) ───────────────────────────────────────────────────
    # B&H lista 43 specs. Faltantes que SÉ:
    "sony_a7v": {
        "lens_communication": True,             # Mirrorless con AF electrónico
        "netflix_approved": False,              # a7V no es Netflix approved
        "processor": "BIONZ XR",
        "rango_dinamico_stops": 15,             # Sony declara ~15 stops (vs 16 stops claim "Color")
        # "power_consumption_w": None,          # TODO: investigar (datasheet Sony)
        # "recording_limit_min": None,          # Sin límite con cooling
        # "time_code": None,                    # a7V NO tiene TC In/Out dedicado
    },

    # ── Sony ZV-E1 (id_db=6) ─────────────────────────────────────────────────
    # B&H lista 42 specs. Faltantes que SÉ:
    "sony_zve1": {
        "lens_communication": True,             # Mirrorless con AF
        "materials": "Polycarbonate",           # Body de plástico (no magnesio como FX3/a7V)
        "netflix_approved": False,
        "processor": "BIONZ XR",
        "rango_dinamico_stops": 15,             # Similar al sensor de la FX3
        # "power_consumption_w": None,          # TODO: investigar
        # "recording_limit_min": None,          # ZV-E1 NO tiene fan, sí tiene límite por temp en 4K60p
        # "time_code": None,                    # No tiene TC dedicado
    },

    # ── Canon EOS C200 (id_db=7) ─────────────────────────────────────────────
    # B&H lista 31 specs. Faltantes que SÉ (cinema cam con muchas particularidades):
    "canon_c200": {
        "built_in_microphone": False,           # No tiene mic interno (sí XLR)
        "internal_recording": True,             # Sí, CFast (Raw) + SD (MP4)
        "materials": "Magnesium Alloy",
        "mobile_app_compatible": False,         # No tiene app móvil
        "netflix_approved": False,
        "operating_conditions": "0 to 40°C",
        "rango_dinamico_stops": 15,             # Canon declara 15 stops con Canon Log
        "sensor_crop": "1.5x",                  # Super 35 vs FF
        "wireless": [],                         # No tiene Wi-Fi/Bluetooth (multi_enum: lista vacía)
        # "continuous_shooting_fps": 1,         # Cinema cam, 1fps stills approx
        # "display_type": "4.0\" LCD Touchscreen (en monitor unit)",  # TODO: confirmar
        # "focus_points": None,                 # Dual Pixel CMOS AF (sin "points" numéricos)
        # "gamma_curve": "Canon Log 3, Canon Log, Wide DR, BT.709",   # TODO: confirmar
        # "power_consumption_w": 21,            # TODO: verificar (datasheet Canon)
        # "recording_limit_min": None,          # Sin límite
        # "shutter_speed": "1/2 to 1/2000",     # TODO: confirmar rango
        # "tripod_mount": "1/4\"-20 + 3/8\"-16", # TODO: confirmar
        # "white_balance": "...",               # TODO: investigar
    },

    # ── RED KOMODO-X (id_db=1) ───────────────────────────────────────────────
    # B&H lista 34 specs. RED publica mucho menos info en B&H que en su sitio.
    "red_komodo_x": {
        "bit_depth": "16-bit",                  # RED siempre 16-bit RAW
        "built_in_nd": False,                   # KOMODO no tiene ND interno (necesita Lite/Pro adapter)
        "iso_nativo": [800],                    # Dual-base ISO: 800 (low) y 3200/6400 (high) según modo
        "processor": "RED A.I. processor",      # TODO: confirmar nombre exacto
        "sensor_crop": "1.5x",                  # Super 35 vs FF
        # "continuous_shooting_fps": None,      # N/A (cinema cam, no stills mode dedicado)
        # "focus_points": None,                 # AF detector reciente, sin grid clásico
        # "gamma_curve": "REDLogFilm, REDgamma4, IPP2",  # TODO: confirmar
        # "iso_extendido": [200, 12800],        # TODO: verificar rango
        # "power_consumption_w": None,          # TODO: investigar (~50W approx con módulos)
        # "recording_limit_min": None,
        # "shoe_mount": None,                   # N/A KOMODO standalone no tiene shoe
        # "shutter_speed": "Cinema (variable angle 1°-360°)",  # TODO
        # "time_code": "TC In/Out via expander",
        # "white_balance": "Manual (1700-10000K)",
    },

    # ── RED KOMODO 6K (id_db=2) ──────────────────────────────────────────────
    # B&H lista 38 specs.
    "red_komodo": {
        "bit_depth": "16-bit",
        "built_in_nd": False,
        "ip_streaming": False,
        # "continuous_shooting_fps": None,      # N/A
        # "focus_points": None,
        # "iso_extendido": [200, 12800],        # TODO: verificar
        # "processor": "RED Komodo processor",  # TODO: confirmar
        # "recording_limit_min": None,
        # "sensor_crop": 1.5,
        # "shoe_mount": None,                   # N/A
        # "time_code": "TC In/Out via expander",
    },

    # ── GoPro HERO12 Black (id_db=8) ─────────────────────────────────────────
    # B&H lista 22 specs. Action cams tienen ficha más pobre en B&H.
    "gopro_hero12": {
        "lens_mount": None,                     # N/A — lente fijo
        "lens_communication": False,            # Lente fijo
        "formato": None,                        # Sensor 1/1.9" no está en FORMATO_ENUM del registry
        "shutter_type": "Electronic",
        "fast_slow_motion": True,               # Slo-mo hasta 8x en 1080p
        "autofocus": True,                      # Sí, contraste
        "gps": True,                            # GoPro tiene GPS
        "audio_io": "3.5mm via Media Mod (no jack interno)",
        "video_io": "HDMI Type-D (Micro) via Media Mod",
        "built_in_microphone": True,            # 3 mics estéreo
        "capture_type": "Stills & Video",
        "netflix_approved": False,
        "materials": "Plastic + Glass + Stainless Steel",
        "processor": "GP2",
        # "bit_depth": "10-bit",                # HEVC 10-bit en HEROlog modes
        # "continuous_shooting_fps": 30,        # 30 fps stills burst
        # "focus_points": None,                 # AF por contraste sin grid
        # "gamma_curve": "GP-Log",              # HEROlog gamma
        # "iso_extendido": None,                # Suele coincidir con nativo en action cams
        # "power_consumption_w": None,          # TODO: investigar
        # "power_io": "USB-C",
        # "other_io": None,                     # N/A
        # "rango_dinamico_stops": None,         # GoPro no publica
        # "recording_limit_min": None,          # Sin límite por archivo (continuos chapters)
        # "sensor_crop": None,                  # No aplica (lente fijo)
        # "shoe_mount": None,                   # N/A
        # "time_code": False,                   # No tiene TC dedicado
        # "tripod_mount": None,                 # Tiene fingers proprietary + 1/4"-20 con adapter
    },
}


def apply_patches():
    """Aplica MANUAL_SPEC_PATCHES sobre docs/camaras.json.

    Reglas:
      - Si la spec ya existe en el dataset (parseada de B&H), NO se pisa.
      - Si no existe, se agrega con el valor del patch.
      - Si el value es None explícito, NO se setea (None = "no aplica").
    """
    if not CURADO_PATH.exists():
        print("  (No existe docs/camaras.json — corré tools/camaras_parser.py primero)")
        return

    with open(CURADO_PATH) as f:
        curado = json.load(f)

    aplicados = 0
    skipped_already_set = 0
    skipped_no_product = 0

    for prod_id, patches in MANUAL_SPEC_PATCHES.items():
        prod = curado["products"].get(prod_id)
        if not prod:
            skipped_no_product += 1
            continue
        specs = prod.setdefault("specs", {})
        for key, value in patches.items():
            if value is None:
                continue
            if key in specs:
                skipped_already_set += 1
                continue
            specs[key] = value
            aplicados += 1

    if aplicados or skipped_already_set:
        with open(CURADO_PATH, "w") as f:
            json.dump(curado, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(
            f"  Parches aplicados: {aplicados} specs nuevas, "
            f"{skipped_already_set} skipped (ya seteadas por parser)"
        )
    else:
        print("  (Sin parches manuales activos — todo lo declarado ya está seteado o vacío)")

    if skipped_no_product:
        print(f"  ⚠ {skipped_no_product} entradas de patch para prod_ids que no están en el dataset")


if __name__ == "__main__":
    apply_patches()
