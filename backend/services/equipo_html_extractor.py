"""
services/equipo_html_extractor.py — Dispatcher de extractores HTML por categoría.

Reemplaza al LLM-based autocompletar para equipos: cuando el admin sube un
HTML B&H (o se obtiene rawHtml de Firecrawl), este módulo:

  1. Detecta la categoría del HTML (Cámaras / Lentes / Adaptadores / Filtros /
     Iluminación) por título + JSON-LD.
  2. Delega al parser determinístico correspondiente, vía
     `services.specs_ingesta.queries` (mismo código que usa el CLI offline).
  3. Devuelve estructura `AutocompletarResult` con specs canónicos + keywords.

Calidad idéntica al dataset del seed. Sin LLM (ver split de runtime en
services/specs_ingesta/CLAUDE.md — Railway nunca corre LLM).

Entrada principal:
    extract_from_html(html_content, categoria_hint=None) -> dict
"""

import json
import re

from services.specs_ingesta.queries import bespoke, generic
from services.specs_ingesta.queries.resultado import build_result as _build_result

__all__ = ["extract_from_html", "_build_result", "_specs_dict_to_array"]


# ── Detección de categoría ──────────────────────────────────────────────

def _detect_categoria(html_content: str, title: str = "") -> str:
    """Detecta la categoría del HTML basado en título + JSON-LD + heurística.

    Devuelve: "Cámaras" | "Lentes" | "Adaptadores" | "Filtros" | "Iluminación"
              | "Desconocido"
    """
    t = (title or "").lower()
    body_excerpt = html_content[:50_000].lower()  # primeros 50KB

    # Adaptadores: mention explícita
    if re.search(r"\b(lens\s+mount\s+adapter|mount\s+converter|speedbooster|lens\s+adapter)\b", t):
        return "Adaptadores"
    if "lens mount adapter" in body_excerpt[:5000]:
        return "Adaptadores"

    # Filtros
    if re.search(r"\b(filter|polariz|pro-?mist|nd\s+filter|variable\s+nd)\b", t):
        return "Filtros"

    # Cámaras (incluye action cams)
    if re.search(r"\b(cinema\s+camera|mirrorless|dslr|action\s+camera|action\s+cam\b|camera\s+body|camcorder|gopro|insta360)\b", t):
        return "Cámaras"

    # Lentes (después de adaptadores/filtros para evitar falsos positivos)
    if re.search(r"\b(lens|lente)\b", t) and not re.search(r"\b(adapter|filter|hood|cap)\b", t):
        return "Lentes"

    # Modificadores: accesorios que se acoplan a una luz (antes que Iluminación
    # para evitar que "fresnel attachment" / "softbox" caigan en el parser de luces)
    if re.search(r"\b(fresnel\s+attachment|softbox|octobox|diffusion\s+frame|beauty\s+dish|reflector\s+dish|parabolic)\b", t):
        return "Modificadores"

    # Iluminación: amplio (LED, light, monolight, flash, tube, panel, fresnel)
    if re.search(r"\b(led|light|monolight|spotlight|flash|tube\s+light|fresnel|panel)\b", t):
        return "Iluminación"

    return "Desconocido"


# ── Adapter común: convierte specs dict → array [{spec_key, label, value}] ──

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


# ── Entrada principal ──────────────────────────────────────────────────

def extract_from_html(html_content: str, categoria_hint: str | None = None) -> dict:
    """Extrae specs canónicos de un HTML B&H.

    Dispatcher: detecta categoría (o usa hint) y delega al parser específico
    de `services.specs_ingesta.queries` — mismo motor que usa el CLI offline
    (F5), garantiza online == offline sobre el mismo HTML.

    Args:
        html_content: HTML completo (Cmd+S de B&H o rawHtml de Firecrawl).
        categoria_hint: si el frontend ya sabe la categoría (ej. usuario eligió
                        en un dropdown), evita la detección automática.
    """
    # Title del <head>
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    categoria = (categoria_hint or _detect_categoria(html_content, title)).strip()

    if categoria == "Iluminación":
        return bespoke.extract_iluminacion(html_content)
    if categoria == "Cámaras":
        return bespoke.extract_via_camaras_parser(html_content)
    if categoria in ("Lentes", "Adaptadores", "Filtros"):
        return bespoke.extract_via_lentes_parser(html_content)
    if categoria == "Modificadores":
        return bespoke.extract_via_modificadores_parser(html_content)

    # Categorías sin parser bespoke (Desconocido, futuras) →
    # extractor genérico: saca TODOS los pares crudos y resuelve por aliases.
    # Cero descartes silenciosos: lo que no resuelve queda visible como "sin
    # template" (salvo ruido conocido de shipping/packaging, ver F4).
    return generic.extract_from_html_generic(html_content, categoria_hint=categoria if categoria != "Desconocido" else None)
