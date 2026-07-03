#!/usr/bin/env python3
"""
tools/iluminacion_normalizar.py — CLI de normalización post-parse del dataset de luces.

⏰ LEGACY-ADYACENTE (F3 del rediseño de ingesta): canon_brand/canon_modelo/
clean_extras (las 3 funciones que usa el código en vivo) se movieron a
backend/services/specs_ingesta/parsers/normalizar.py — es la fuente única
ahora. Este archivo conserva canon_id/canonicalizar_specs/reorder/normalizar
(orquestación completa del dataset, I/O de docs/iluminacion*.json), que solo
usa el CLI offline.

Toma docs/iluminacion.json y docs/iluminacion_raw.json, aplica reglas de
canonicalización y guarda los archivos normalizados.

Reglas que aplica:
  1. Marcas canónicas (Mole-Richardson, Aputure, etc.) — case y guiones consistentes
  2. Modelos limpios (quita "(Gray)", "RGB LED Monolight", redundancias, etc.)
  3. IDs estables y específicos (nanlite_forza → nanlite_forza_500)
  4. extras de cleanup (None/"" → eliminar)
  5. Orden consistente de campos
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "iluminacion.json"
RAW_PATH = ROOT / "docs" / "iluminacion_raw.json"

# Import de la lógica real (backend/services/specs_ingesta/parsers/) — único
# lugar donde vive canon_brand/canon_modelo/clean_extras. Ver docs/PLAN_SPECS_INGESTA.md.
_BACKEND_DIR = ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from services.specs_ingesta.parsers.normalizar import (  # noqa: E402
    canon_brand,
    canon_modelo,
    clean_extras,
)

__all__ = [
    "canon_brand", "canon_modelo", "clean_extras",
    "canon_id", "canonicalizar_specs", "reorder", "normalizar",
]


STATIC_ID_REMAP = {
    "nanlite_60b": "nanlite_forza_60b",
    "aputure_nova": "aputure_nova_ii_2x1",
    "molerichardson_juniorled": "molerichardson_juniorled_200",
}


def canon_id(pid: str, modelo: str = "") -> str:
    """Devuelve el id canónico. Usa STATIC_ID_REMAP + reglas contextuales
    para resolver IDs ambiguos como `nanlite_forza` que pueden referirse
    a Forza 500, Forza 60, etc."""
    if pid in STATIC_ID_REMAP:
        return STATIC_ID_REMAP[pid]
    # Caso especial: nanlite_forza* — desambiguamos por modelo
    if pid.startswith("nanlite_forza"):
        m = modelo.lower()
        if "500" in m:
            return "nanlite_forza_500"
        if "60b" in m or "60 b" in m:
            return "nanlite_forza_60b"
        if "60" in m:
            return "nanlite_forza_60"
        return "nanlite_forza_500"  # fallback histórico
    return pid


SPECS_ORDER = [
    "iluminacion_subtipo",
    "consumo_w",
    "color_modes",
    "lumens_at_5600k", "lumens_at_3200k",
    "lux_at_1m_5600k", "lux_at_1m_3200k",
    "cri", "tlci", "r9",
    "temperatura_k",
    "dimming",
    "control_inalambrico", "alimentacion", "montura_luz",
    "peso_g",
    "battery", "power_pass_thru",
    "beam_angle", "cooling_system", "display",
    "mobile_app_compatible",
    "umbrella_mount", "effects",
    "wireless_range_m",
    "dimensions_mm",
    "environmental_resistance", "operating_conditions",
    "incluye_estuche", "incluye_modificador",
    "materials", "certifications",
]


def _parse_temperatura_k(value) -> list | None:
    """'5600K' → [5600], '2500-8500K' → [2500, 8500], null → None.

    El registry define `temperatura_k` como tipo `rango`: si es fija usa [v],
    si es variable usa [min, max]. El parser lo devuelve como string crudo,
    acá lo convertimos al formato que espera el seed/dataio.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return value
    s = str(value).strip().upper().replace("K", "").strip()
    if not s:
        return None
    if "-" in s:
        try:
            lo, hi = s.split("-", 1)
            return [int(lo.strip()), int(hi.strip())]
        except ValueError:
            return None
    try:
        return [int(s)]
    except ValueError:
        return None


def canonicalizar_specs(specs: dict) -> dict:
    """Mapea keys legacy del parser → keys del registry (backend/specs/registry.py).

    Transformaciones:
      - {bicolor, rgb} → color_modes: multi_enum ["Bicolor","RGB","Daylight","Tungsten"]
      - lumens → lumens_at_5600k (o _3200k si la luz es tungsten-only)
      - temperatura_k: "5600K"/"2500-8500K" → [5600]/[2500,8500] (rango numérico)

    Las keys originales se eliminan después del mapeo. Si ya existe la key
    canónica (caso edge), no la pisa.
    """
    out = dict(specs)
    bicolor = out.pop("bicolor", None)
    rgb = out.pop("rgb", None)
    lumens = out.pop("lumens", None)
    temp_raw = out.get("temperatura_k")
    temp = (temp_raw or "").strip() if isinstance(temp_raw, str) else ""

    # color_modes (multi_enum)
    if "color_modes" not in out:
        modes = []
        if bicolor:
            modes.append("Bicolor")
        if rgb:
            modes.append("RGB")
        if not modes and bicolor is False and rgb is False:
            # No bicolor, no RGB: derivar de la temperatura si es fija
            if temp.startswith("5600") or temp.startswith("5500"):
                modes.append("Daylight")
            elif temp.startswith("3200") or temp.startswith("3000"):
                modes.append("Tungsten")
        if modes:
            out["color_modes"] = modes

    # lumens → lumens_at_5600k (default) o _3200k si la luz es tungsten-only
    if lumens is not None:
        is_tungsten_only = (
            bicolor is False and rgb is False and
            (temp.startswith("3200") or temp.startswith("3000"))
        )
        target_key = "lumens_at_3200k" if is_tungsten_only else "lumens_at_5600k"
        if target_key not in out:
            out[target_key] = lumens

    # temperatura_k: string → rango numérico
    if "temperatura_k" in out:
        parsed = _parse_temperatura_k(out["temperatura_k"])
        if parsed is None:
            del out["temperatura_k"]
        else:
            out["temperatura_k"] = parsed

    return out

EXTRAS_ORDER = [
    # Solo keys que NO están en el registry (descriptivos legacy).
    "item_type", "bulb_type", "base_type",
    "ip_rating", "photometrics_1m",
    "vida_util_horas",
    "yoke", "fixture_mount", "accessory_diameter",
    "io", "cable_length",
    "voltaje", "reflector", "serie",
]


def reorder(d: dict, order: list[str]) -> dict:
    out = {}
    for k in order:
        if k in d:
            out[k] = d[k]
    # Mantener otros que no están en el orden
    for k, v in d.items():
        if k not in out:
            out[k] = v
    return out


# ── Main ────────────────────────────────────────────────────────────────────

def normalizar():
    with open(CURADO_PATH) as f:
        curado = json.load(f)
    with open(RAW_PATH) as f:
        raw = json.load(f)

    new_products = {}
    id_remaps_applied = []

    for old_id, p in curado["products"].items():
        new_id = canon_id(old_id, modelo=p.get("modelo", ""))
        if new_id != old_id:
            id_remaps_applied.append((old_id, new_id))

        # Normalizar campos
        p["marca"] = canon_brand(p.get("marca", ""))
        p["modelo"] = canon_modelo(p.get("modelo", ""))
        p["specs"] = reorder(canonicalizar_specs(p.get("specs", {})), SPECS_ORDER)
        # `extras` removido (no se persistía a DB). Si el dataset legacy
        # todavía tiene la key, la quitamos para mantener el JSON limpio.
        p.pop("extras", None)
        # Reorder top-level
        ordered = {
            "marca": p["marca"],
            "modelo": p["modelo"],
            "url_source": p.get("url_source", ""),
        }
        for k in ("specs", "extras", "ficha", "_nota"):
            if k in p:
                ordered[k] = p[k]
        new_products[new_id] = ordered

    curado["products"] = new_products

    # Aplicar mismos remaps al raw
    for old_id, new_id in id_remaps_applied:
        for rp in raw["products"]:
            if rp.get("id") == old_id:
                rp["id"] = new_id
        print(f"  ID remapped: {old_id} → {new_id}")

    # Normalizar marcas también en raw
    for rp in raw["products"]:
        rp["marca"] = canon_brand(rp.get("marca", ""))

    with open(CURADO_PATH, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nNormalización aplicada: {len(curado['products'])} productos")


if __name__ == "__main__":
    normalizar()
