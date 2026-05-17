#!/usr/bin/env python3
"""
tools/iluminacion_patches.py — Parches manuales para productos que no se pueden
parsear automáticamente desde HTMLs de B&H.

Casos cubiertos:
  - ARRI 650 Plus: sitio fabricante (arri.com), 33 campos oficiales
  - Mole-Richardson 1000W 407 Baby Solarspot: sitio fabricante (mole.com)
  - amaran 300c: B&H no lista Color Temperature explícito (range 2500-7500K oficial)

Corre después del parser principal y antes del normalizador.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "iluminacion.json"
RAW_PATH = ROOT / "docs" / "iluminacion_raw.json"


ARRI_FICHA = {
    "Technical Data": [
        {"label": "Category", "value": "Tungsten"},
        {"label": "Series", "value": "ARRI Junior"},
        {"label": "Model", "value": "ARRI 650 Plus"},
        {"label": "Mains Plug", "value": "Schuko, Bare Ends"},
        {"label": "Lamphead Type", "value": "Fresnel, 650 W"},
        {"label": "Reflector", "value": "Spherical specular high purity aluminium"},
        {"label": "Lamp Type", "value": "CP89 FRL 650 W / 230 V; CP89 FRK 650 W / 120 V; CP82 500W; CP81 300W"},
        {"label": "Power Consumption", "value": "650 W, 500 W, 300 W"},
        {"label": "Voltage Range", "value": "230 V / 120 V"},
        {"label": "Lamp Base", "value": "GY9.5"},
        {"label": "Dimming", "value": "yes, 0 to 100 % via external dimming system"},
        {"label": "Correlated Color Temperature", "value": "3,200 K"},
        {"label": "Beam Angle", "value": "12° to 52°"},
        {"label": "Weight in kg net*", "value": "approx. 3 kg"},
        {"label": "Weight in kg packed*", "value": "approx. 4 kg"},
        {"label": "Weight in lbs. net*", "value": "approx. 6 lbs"},
        {"label": "Weight in lbs. Packed*", "value": "approx. 8 lbs"},
        {"label": "Measurements (HxWxL) incl. Pin in mm*", "value": "300 x 220 x 190 mm"},
        {"label": "Measurements (HxWxL) excl. Pin in mm*", "value": "256 x 220 x 190 mm"},
        {"label": "Measurements (HxWxL) incl. Pin in inch*", "value": "11.8 x 8.7 x 7.5\""},
        {"label": "Measurements (HxWxL) excl. Pin in inch*", "value": "10.1 x 8.7 x 7.5\""},
        {"label": "Measurements (HxWxL) Packed size in mm*", "value": "295 x 220 x 255 mm"},
        {"label": "Measurements (HxWxL) Packed size in inch*", "value": "11.6 x 8.7 x 10.0\""},
        {"label": "Lens / UV-Protection Glass Diameter in mm", "value": "112 mm"},
        {"label": "Lens / UV-Protection Glass Diameter in inch", "value": "4.4\""},
        {"label": "Accessory Diameter in mm", "value": "168 mm"},
        {"label": "Accessory Diameter in inch", "value": "6.6\" (Scrim)"},
        {"label": "Barndoor in mm", "value": "168 mm"},
        {"label": "Barndoor in inch", "value": "6.6\""},
        {"label": "Mounting", "value": "Socket 16 mm / 5/8\" (0.6\")"},
        {"label": "Housing Color", "value": "Blue/Silver, Black"},
        {"label": "Protection Class / IP Rating", "value": "I / IP20"},
        {"label": "Certifications", "value": "CE, UKCA, CB, GS, cNRTLus"},
    ]
}

MOLE_FICHA = {
    "Technical Specifications": [
        {"label": "Model", "value": "407 Baby Solarspot 6\" — equipado con bulb 2000W"},
        {"label": "Power Rating", "value": "2000 Watts (con bulb FCM/FFR-style 2kW; el chassis 407 oficialmente es 1000W pero el usuario lo opera con bulb 2kW)"},
        {"label": "Voltage", "value": "120 / 240 VAC or DC"},
        {"label": "Lamp Socket", "value": "Medium Bi-post"},
        {"label": "Lens", "value": "Fresnel 6\" (152 mm), vidrio"},
        {"label": "Field Angle", "value": "15° to 58°"},
        {"label": "Reflector", "value": "Alzak aluminum, condensador con lente Fresnel"},
        {"label": "Yoke", "value": "Aluminio fundido, spud 5/8\" (16 mm)"},
        {"label": "Finish", "value": "Maroon powder coat enamel"},
        {"label": "Dimensions", "value": "11¼\" × 8⅝\" × 10½\""},
        {"label": "Weight", "value": "13¾ lbs (6.24 kg) con cable"},
        {"label": "Cable", "value": "25 ft, Type SO, 3 cond #16/3 con Edison plug"},
        {"label": "_nota_bulb", "value": "El chassis 407 es el 'Baby Solarspot' de Mole. Físicamente idéntico al 1000W (HTML de B&H/mole.com), pero el usuario lo opera con un bulb de 2000W. Specs físicos = del 1000W; specs eléctricos (potencia, lumens) escalan con bulb."},
    ]
}


def apply_patches():
    with open(CURADO_PATH) as f:
        curado = json.load(f)
    with open(RAW_PATH) as f:
        raw = json.load(f)

    # ── ARRI 650 Plus ────────────────────────────────────────────────────
    curado["products"]["arri_650plus"] = {
        "marca": "ARRI",
        "modelo": "650 Plus",
        "url_source": "https://www.arri.com/en/lighting/daylight-tungsten/tungsten/arri-junior/arri-650-plus",
        "specs": {
            "potencia_w": 650, "cri": 100, "temperatura_k": "3200K",
            "bicolor": False, "rgb": False, "dimming": True,
            "alimentacion": ["AC"], "montaje": "Fresnel", "peso_g": 3000,
        },
        "extras": {
            "tipo": "Fresnel",
            "item_type": "Tungsten Fresnel",
            "bulb_type": "GY9.5 — CP89 FRL/FRK 650W (acepta CP82 500W / CP81 300W)",
            "beam_angle": "12-52°",
            "cooling": "Passive",
            "ip_rating": "IP20",
            "dimensiones": "30 × 22 × 19 cm",
            "fixture_mount": "Socket 5/8\" (16 mm)",
            "accessory_diameter": "168 mm / 6.6\"",
            "voltaje": "230 V / 120 V",
            "reflector": "Esférico especular de aluminio de alta pureza",
            "serie": "ARRI Junior",
            "certificaciones": "CE, UKCA, CB, GS, cNRTLus",
        },
        "ficha": ARRI_FICHA,
        "_nota": "Datos oficiales arri.com (33 campos exactos)",
    }
    raw["products"] = [p for p in raw["products"] if p.get("id") != "arri_650plus"]
    raw["products"].append({
        "id": "arri_650plus", "categoria_raiz": "Iluminación",
        "subtipo": "Tungsten Fresnel", "marca": "ARRI", "modelo": "650 Plus",
        "url_source": "https://www.arri.com/en/lighting/daylight-tungsten/tungsten/arri-junior/arri-650-plus",
        "status_bh": "N/A — sitio fabricante",
        "fuente": "ARRI oficial (web fetch)",
        "secciones": ARRI_FICHA,
    })

    # ── Mole-Richardson 2000W (chassis 407 Baby Solarspot + bulb 2kW) ─────
    # Físicamente es el "407 Baby Solarspot 1000W" de Mole (HTML de mole.com)
    # pero el inventario del usuario lo opera con bulb de 2000W. Chassis
    # idéntico, distinta lámpara.
    curado["products"]["molerichardson_2000w"] = {
        "marca": "Mole-Richardson",
        "modelo": "407 Baby Solarspot 2000W 6\"",
        "url_source": "https://www.mole.com/407-baby-solarspot",
        "specs": {
            "potencia_w": 2000, "cri": 100, "temperatura_k": "3200K",
            "bicolor": False, "rgb": False, "dimming": True,
            "alimentacion": ["AC"], "montaje": "Fresnel", "peso_g": 6240,
        },
        "extras": {
            "tipo": "Fresnel",
            "item_type": "Tungsten Fresnel Spotlight",
            "bulb_type": "Medium Bi-post (2000W tungsten) — el chassis 407 es nominal 1000W; el usuario opera con bulb 2kW",
            "beam_angle": "15-58°",
            "cooling": "Passive",
            "dimensiones": "28.6 × 21.9 × 26.7 cm",
            "fixture_mount": "Yoke con spud 5/8\" (16 mm)",
            "accessory_diameter": "6 5/8\" (168 mm)",
            "voltaje": "120 / 240 VAC",
            "cable_length": "25 ft (7.6 m) Type SO",
        },
        "ficha": MOLE_FICHA,
        "_nota": "Chassis 407 Baby Solarspot de Mole-Richardson (HTML/mole.com lo lista como 1000W). Usuario lo opera con bulb 2000W. Specs físicos vienen del chassis 1000W; potencia y bulb_type reflejan el bulb real.",
    }
    # También limpio si quedó 'molerichardson_1000w' de versiones previas del seed
    if "molerichardson_1000w" in curado["products"]:
        del curado["products"]["molerichardson_1000w"]
    raw["products"] = [
        p for p in raw["products"]
        if p.get("id") not in ("molerichardson_1000w", "molerichardson_2000w")
    ]
    raw["products"].append({
        "id": "molerichardson_2000w", "categoria_raiz": "Iluminación",
        "subtipo": "Tungsten Fresnel", "marca": "Mole-Richardson",
        "modelo": "407 Baby Solarspot 2000W 6\"",
        "url_source": "https://www.mole.com/407-baby-solarspot",
        "status_bh": "N/A — chassis del 1000W operado con bulb 2kW",
        "fuente": "mole.com (web fetch del chassis 1000W) + override bulb",
        "secciones": MOLE_FICHA,
    })

    # ── amaran 300c: B&H no lista Color Temperature explícito ────────────
    if "amaran_300c" in curado["products"]:
        curado["products"]["amaran_300c"]["specs"]["temperatura_k"] = "2500-7500K"

    # ── Aputure B7c: HTML estaba incompleto, peso desde specs Aputure oficial ─
    # B7c es un bulbo E26 — 4.54" alto × 2.74" diámetro, ~210g
    if "aputure_b7c" in curado["products"]:
        b7c_specs = curado["products"]["aputure_b7c"]["specs"]
        if b7c_specs.get("peso_g") is None:
            b7c_specs["peso_g"] = 210
        b7c_extras = curado["products"]["aputure_b7c"].setdefault("extras", {})
        if "dimensiones" not in b7c_extras:
            b7c_extras["dimensiones"] = "11.5 × 7 cm (alto × diámetro)"

    with open(CURADO_PATH, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  Parches aplicados: ARRI 650 Plus, Mole 1000W, amaran 300c (temp), Aputure B7c (peso)")


if __name__ == "__main__":
    apply_patches()
