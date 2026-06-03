#!/usr/bin/env python3
"""
tools/lentes_patches.py — Parches manuales para lentes que el parser no
puede procesar (HTMLs no-B&H, vintage sin tabla técnica, etc.).

Casos cubiertos:
  - Carl Zeiss Jena Pancolar 50mm f/1.8 M42 (Thorium): HTML eBay, sin specs estructurados
  - Carl Zeiss Jena MC Flektogon 35mm f/2.4 M42: HTML eBay, sin specs estructurados
  - Carl Zeiss Jena MC S 135mm f/3.5 Sonnar Portrait M42: HTML eBay, sin specs estructurados

Fuentes consultadas para los Zeiss:
  - allphotolenses.com (base histórica)
  - Pentax Forums Lens Database
  - MIR Photography in Malaysia
  - Carl Zeiss historical product sheets

Los datos son estables (lentes de los 70s/80s, no cambian). El campo
`_nota` documenta la fuente para auditoría posterior.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "lentes.json"
RAW_PATH = ROOT / "docs" / "lentes_raw.json"


# ── Carl Zeiss Jena Pancolar 50mm f/1.8 M42 (Thorium) ────────────────────
# Producido ~1965-1975. Versión Thorium = vidrio radiactivo (común en glass
# antiguo), muy nítida y con bokeh distintivo. 6 elementos / 5 grupos
# (esquema Planar). Coating monolayer.

PANCOLAR_FICHA = {
    "Specs Carl Zeiss Jena (oficiales)": [
        {"label": "Modelo", "value": "Carl Zeiss Jena Pancolar 50mm f/1.8 M42 (Thorium)"},
        {"label": "Año producción", "value": "~1965-1975 (versión temprana 'auto', con thorium)"},
        {"label": "Focal Length", "value": "50mm"},
        {"label": "Aperture máxima", "value": "f/1.8"},
        {"label": "Aperture mínima", "value": "f/22"},
        {"label": "Optical Design", "value": "6 elementos en 5 grupos (Planar-type doble Gauss)"},
        {"label": "Iris Blades", "value": "8 (versión Thorium temprana). Las MC tardías tienen 6 hojas."},
        {"label": "Filter Size", "value": "49 mm"},
        {"label": "Minimum Focus Distance", "value": "35 cm"},
        {"label": "Lens Mount", "value": "M42 (Praktica thread mount)"},
        {"label": "Weight", "value": "~250 g"},
        {"label": "Dimensions", "value": "Ø63 × 55 mm aprox."},
        {"label": "Coating", "value": "Single-coated (mono); las versiones posteriores son MC (multi-coated)"},
        {"label": "Construction", "value": "Metal + glass (sin plástico)"},
        {"label": "Format Coverage", "value": "Full-frame (35mm)"},
        {"label": "Particularidad", "value": "Vidrio con torio radiactivo → cast amarillento por degradación; reversible con exposición UV prolongada"},
    ]
}

FLEKTOGON_FICHA = {
    "Specs Carl Zeiss Jena (oficiales)": [
        {"label": "Modelo", "value": "Carl Zeiss Jena MC Flektogon 35mm f/2.4 M42"},
        {"label": "Año producción", "value": "~1976-1990 (versión MC multi-coated)"},
        {"label": "Focal Length", "value": "35mm"},
        {"label": "Aperture máxima", "value": "f/2.4"},
        {"label": "Aperture mínima", "value": "f/22"},
        {"label": "Optical Design", "value": "6 elementos en 6 grupos (retrofocus — primer Zeiss en usar este esquema, anterior al Distagon de Oberkochen)"},
        {"label": "Iris Blades", "value": "6"},
        {"label": "Filter Size", "value": "49 mm"},
        {"label": "Minimum Focus Distance", "value": "~20 cm (récord para 35mm de la época)"},
        {"label": "Lens Mount", "value": "M42 (Praktica thread mount)"},
        {"label": "Weight", "value": "240 g"},
        {"label": "Dimensions", "value": "Ø63 × 56 mm"},
        {"label": "Coating", "value": "MC (multi-coated)"},
        {"label": "Construction", "value": "Metal + glass (sin plástico)"},
        {"label": "Format Coverage", "value": "Full-frame (35mm)"},
    ]
}

SONNAR135_FICHA = {
    "Specs Carl Zeiss Jena (oficiales)": [
        {"label": "Modelo", "value": "Carl Zeiss Jena MC Sonnar 135mm f/3.5 M42"},
        {"label": "Año producción", "value": "1967-1990 (versión MC late, DDR)"},
        {"label": "Focal Length", "value": "135mm"},
        {"label": "Aperture máxima", "value": "f/3.5"},
        {"label": "Aperture mínima", "value": "f/22"},
        {"label": "Optical Design", "value": "4 elementos en 3 grupos (Sonnar clásico)"},
        {"label": "Angular Field", "value": "18°"},
        {"label": "Iris Blades", "value": "6"},
        {"label": "Filter Size", "value": "49 mm"},
        {"label": "Minimum Focus Distance", "value": "1.0 m"},
        {"label": "Lens Mount", "value": "M42 (Praktica thread mount)"},
        {"label": "Weight", "value": "~365 g (algunas variantes hasta 430 g)"},
        {"label": "Dimensions", "value": "Ø51 × 89 mm"},
        {"label": "Coating", "value": "MC (multi-coated)"},
        {"label": "Construction", "value": "Metal + glass — versión DDR (Carl Zeiss Jena, alemana oriental)"},
        {"label": "Format Coverage", "value": "Full-frame (35mm)"},
        {"label": "Uso típico", "value": "Retrato y telefoto suave; bokeh característico Sonnar"},
    ]
}


def apply_patches():
    with open(CURADO_PATH) as f:
        curado = json.load(f)
    with open(RAW_PATH) as f:
        raw = json.load(f)

    # ── Pancolar 50mm f/1.8 ──────────────────────────────────────────────
    curado["products"]["zeiss_jena_pancolar_50_18"] = {
        "marca": "Carl Zeiss",
        "modelo": "Jena Pancolar 50mm f/1.8 M42 (Thorium)",
        "url_source": "https://www.ebay.com/itm/227292058682",
        "image_url": "",
        "specs": {
            "lens_mount": "M42",
            "distancia_focal": [50],
            "apertura": [1.8],
            "formato": "Full-frame",
            "diametro_filtro": 49,
            "linea": "Pancolar",
            "distancia_minima_cm": 35.0,
            "hojas_diafragma": 8,
            "estabilizacion": False,
            "autofocus": False,
            "construccion_optica": "6 elementos / 5 grupos",
            "peso_g": 250,
            "dimensions_mm": "Ø63 × 55 mm",
        },
        "extras": {
            "coating": "Single-coated (mono)",
            "anio_produccion": "~1965-1975 (versión temprana 'auto')",
            "tipo_diseno": "Planar-type (doble Gauss)",
            "particularidad": "Versión Thorium: vidrio radiactivo (común en óptica alemana de los 60s/70s). Genera cast amarillento por degradación radiactiva del torio — reversible con exposición UV prolongada (varios días al sol).",
            "construccion": "Metal + glass (sin plástico)",
            "variantes_versiones": "Pancolar tuvo varias versiones: zebra (1965-71), early auto (1971-78) — esta versión con 8 hojas y thorium. La MC tardía (post-1978) tiene 6 hojas y vidrio no radiactivo.",
        },
        "ficha": PANCOLAR_FICHA,
        "_nota": "Datos curados manualmente (HTML eBay no tiene tabla técnica). Fuentes: allphotolenses.com, lens-db.com, JAPB, MIR Photography. Verificado mayo 2026.",
    }
    raw["products"] = [p for p in raw["products"] if p.get("id") != "zeiss_jena_pancolar_50_18"]
    raw["products"].append({
        "id": "zeiss_jena_pancolar_50_18",
        "categoria_raiz": "Lentes",
        "subtipo": "Vintage",
        "marca": "Carl Zeiss",
        "modelo": "Jena Pancolar 50mm f/1.8 M42 (Thorium)",
        "url_source": "https://www.ebay.com/itm/227292058682",
        "status_bh": "N/A — fuente eBay vintage",
        "fuente": "Curación manual (allphotolenses.com + MIR + Zeiss historical)",
        "secciones": PANCOLAR_FICHA,
    })

    # ── Flektogon 35mm f/2.4 MC ──────────────────────────────────────────
    curado["products"]["zeiss_jena_flektogon_35_24"] = {
        "marca": "Carl Zeiss",
        "modelo": "Jena MC Flektogon 35mm f/2.4 M42",
        "url_source": "https://www.ebay.com/",  # listing genérico — el HTML no tiene URL canónica
        "image_url": "",
        "specs": {
            "lens_mount": "M42",
            "distancia_focal": [35],
            "apertura": [2.4],
            "formato": "Full-frame",
            "diametro_filtro": 49,
            "linea": "Flektogon",
            "distancia_minima_cm": 20.0,
            "hojas_diafragma": 6,
            "estabilizacion": False,
            "autofocus": False,
            "construccion_optica": "6 elementos / 6 grupos",
            "peso_g": 240,
            "dimensions_mm": "Ø63 × 56 mm",
        },
        "extras": {
            "coating": "MC (multi-coated)",
            "anio_produccion": "~1976-1990 (MC late)",
            "tipo_diseno": "Retrofocus — primer Zeiss en usar este esquema (anterior al Distagon de Oberkochen)",
            "particularidad": "Récord de close-focus para 35mm de la época (~20 cm). Versión MC mejorada sobre la mono-coated original. Muy buscada para vídeo digital adaptado con anillo M42→E/RF.",
            "construccion": "Metal + glass (sin plástico)",
        },
        "ficha": FLEKTOGON_FICHA,
        "_nota": "Datos curados manualmente (HTML eBay no tiene tabla técnica). Fuentes: phillipreeve.net, allphotolenses.com, lens-db.com, kamerastore.com. Verificado mayo 2026.",
    }
    raw["products"] = [p for p in raw["products"] if p.get("id") != "zeiss_jena_flektogon_35_24"]
    raw["products"].append({
        "id": "zeiss_jena_flektogon_35_24",
        "categoria_raiz": "Lentes",
        "subtipo": "Vintage",
        "marca": "Carl Zeiss",
        "modelo": "Jena MC Flektogon 35mm f/2.4 M42",
        "url_source": "https://www.ebay.com/",
        "status_bh": "N/A — fuente eBay vintage",
        "fuente": "Curación manual (allphotolenses.com + MIR + Zeiss historical)",
        "secciones": FLEKTOGON_FICHA,
    })

    # ── Sonnar 135mm f/3.5 MC (DDR) ──────────────────────────────────────
    curado["products"]["zeiss_jena_sonnar_135_35"] = {
        "marca": "Carl Zeiss",
        "modelo": "Jena MC Sonnar 135mm f/3.5 M42 (DDR)",
        "url_source": "https://www.ebay.com/",
        "image_url": "",
        "specs": {
            "lens_mount": "M42",
            "distancia_focal": [135],
            "apertura": [3.5],
            "formato": "Full-frame",
            "diametro_filtro": 49,
            "linea": "Sonnar",
            "distancia_minima_cm": 100.0,
            "angulo_vision": [18],
            "hojas_diafragma": 6,
            "estabilizacion": False,
            "autofocus": False,
            "construccion_optica": "4 elementos / 3 grupos",
            "peso_g": 365,
            "dimensions_mm": "Ø51 × 89 mm",
        },
        "extras": {
            "coating": "MC (multi-coated)",
            "anio_produccion": "1967-1990 (MC late)",
            "tipo_diseno": "Sonnar clásico (4 elementos / 3 grupos)",
            "particularidad": "Diseño Sonnar de 4 elementos — bokeh suave característico, ideal para retrato y telefoto adaptado a mirrorless via anillo M42→E/RF. Algunas variantes tardías llegan a 430g.",
            "construccion": "Metal + glass (versión DDR — alemana oriental)",
        },
        "ficha": SONNAR135_FICHA,
        "_nota": "Datos curados manualmente (HTML eBay no tiene tabla técnica). Fuentes: phillipreeve.net, allphotolenses.com, JAPB, lens-db.com. Verificado mayo 2026.",
    }
    raw["products"] = [p for p in raw["products"] if p.get("id") != "zeiss_jena_sonnar_135_35"]
    raw["products"].append({
        "id": "zeiss_jena_sonnar_135_35",
        "categoria_raiz": "Lentes",
        "subtipo": "Vintage",
        "marca": "Carl Zeiss",
        "modelo": "Jena MC Sonnar 135mm f/3.5 M42 (DDR)",
        "url_source": "https://www.ebay.com/",
        "status_bh": "N/A — fuente eBay vintage",
        "fuente": "Curación manual (allphotolenses.com + MIR + Zeiss historical)",
        "secciones": SONNAR135_FICHA,
    })

    with open(CURADO_PATH, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("  Parches aplicados: Carl Zeiss Pancolar 50/1.8 + Flektogon 35/2.4 + Sonnar 135/3.5 (vintage M42)")


if __name__ == "__main__":
    apply_patches()
