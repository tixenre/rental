"""services/equipo_html_extractor.py — ⏰ LEGACY (F5 del rediseño de ingesta).

El dispatcher (detección + ruteo) se movió a
`services/specs_ingesta/queries/extraer.py` + `queries/detectar.py`. Este
archivo queda como shim de compatibilidad — re-exporta `extract_from_html`
(varios tests lo importan por nombre) y 2 shims ⏰ LEGACY más viejos
(`_build_result`, `_specs_dict_to_array`) que otros tests siguen usando
directo. Se poda en F6 junto con el resto de los shims. Ver
docs/PLAN_SPECS_INGESTA.md e issue #1176.
"""

import json

from services.specs_ingesta.queries.extraer import extract_from_html
from services.specs_ingesta.queries.resultado import build_result as _build_result

__all__ = ["extract_from_html", "_build_result", "_specs_dict_to_array"]


def _specs_dict_to_array(specs_dict: dict, registry_labels: dict | None = None) -> list[dict]:
    """⏰ LEGACY (F2 del rediseño de ingesta): `_build_result` ya NO llama a
    esta función — usa `specs_ingesta.parse.serialize.specs_dict_to_array`
    (delega en spec_render, aplica la unidad del registry). Esta queda solo
    porque `tests/test_spec_key_normalization.py` la importa por nombre con
    esta firma exacta (`registry_labels` simple, sin unidad/tipo) — se poda
    en F6 junto con el resto de los shims. No usar en código nuevo.

    Convierte {spec_key: value} → [{spec_key, label, value}] para el form admin.
    El label viene del registry (fuente única de verdad). Si la key no tiene
    entry en registry_labels, se usa la key limpia como fallback — nunca se
    descarta un item.
    """
    out = []
    for key, value in specs_dict.items():
        label = (registry_labels or {}).get(key) or key.replace("_", " ").title()
        if isinstance(value, bool):
            val_str = "Sí" if value else "No"
        elif isinstance(value, list):
            # Rangos de focal/apertura
            if key in ("distancia_focal", "apertura", "angulo_vision"):
                if len(value) >= 2 and value[0] != value[-1]:
                    val_str = f"{value[0]}-{value[-1]}"
                elif value:
                    val_str = f"{value[0]}"
                else:
                    val_str = ""
            else:
                val_str = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            if "min" in value and "max" in value:
                val_str = f"{value['min']}-{value['max']}"
            else:
                val_str = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (int, float)):
            unit = ""
            if key == "consumo_w": unit = " W"
            elif "lumens" in key:  unit = " lm"
            elif key == "peso_g":  unit = " g"
            elif key == "fps_max": unit = " fps"
            val_str = f"{value}{unit}"
        else:
            val_str = str(value)
        out.append({"spec_key": key, "label": label, "value": val_str})
    return out
