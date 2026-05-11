"""
services/migracion_specs.py — Migración de specs_json viejos a equipo_specs.

El sistema viejo guardaba specs como [{label, value}] en `equipo_fichas.specs_json`
(formato libre). El sistema nuevo (PR A del rediseño) los tiene estructurados
en `equipo_specs (spec_key, value)` siguiendo el template de la categoría.

Esta migración:
  1. Para cada equipo con specs_json, parsea el JSON.
  2. Para cada (label, value), busca un spec_key del template que matchee
     (por nombre exacto o alias conocido).
  3. Inserta en equipo_specs (o lo deja como `_extra_<slug>` si no matchea).
  4. Devuelve reporte: cuántos matcheados vs extras vs errores.

Idempotente: usa ON CONFLICT DO UPDATE (re-correrla no rompe nada).

Diccionario de alias: label viejo → spec_key del template. Cubre los 122
labels más comunes del inventario real (auditoría 2026-05-10).
"""

import json
import re
from typing import Optional


# ── Diccionario de alias: label viejo → spec_key estándar ──────────────
# Las keys son normalizadas (lowercase, sin acentos, sin puntuación).
# Los matches son CASE-INSENSITIVE y se hace ignore de paréntesis.

ALIAS: dict[str, str] = {
    # Cámaras
    "sensor": "sensor",
    "tipo de sensor": "sensor",
    "image sensor": "sensor",
    "mount": "montura",
    "montaje": "montura",
    "lens mount": "montura",
    "montura": "montura",
    "compatibilidad de camara": "montura",
    "compatibilidad camara": "montura",
    "compatibilidad de lente": "montura",
    "compatibilidad de lentes": "montura",
    "format": "formato",
    "formato": "formato",
    "grabacion de video": "video_max",
    "video": "video_max",
    "video resolution": "video_max",
    "video maximo": "video_max",
    "video max": "video_max",
    "max video": "video_max",
    "max video resolution": "video_max",
    "fps": "fps_max",
    "fps max": "fps_max",
    "frame rate": "fps_max",
    "iso": "iso_max",
    "iso max": "iso_max",
    "max iso": "iso_max",
    "rango iso": "iso_max",
    "estabilizacion": "estabilizacion",
    "estabilizacion de imagen": "estabilizacion",
    "image stabilization": "estabilizacion",
    "ibis": "estabilizacion",
    "autofocus": "autofocus",
    "auto focus": "autofocus",
    "af": "autofocus",
    "peso": "peso",
    "weight": "peso",
    "incluye": "incluye",
    "in the box": "incluye",
    "what's in the box": "incluye",
    "viene con": "incluye",

    # Lentes
    "focal length": "focal_min",
    "focal": "focal_min",
    "distancia focal": "focal_min",
    "aperture": "apertura_max",
    "max aperture": "apertura_max",
    "apertura": "apertura_max",
    "apertura maxima": "apertura_max",
    "apertura max": "apertura_max",
    "linea": "linea",
    "series": "linea",
    "serie": "linea",
    "distancia minima de enfoque": "distancia_minima_m",
    "minimum focus distance": "distancia_minima_m",
    "construccion optica": "construccion_optica",
    "optical construction": "construccion_optica",
    "elementos": "construccion_optica",

    # Iluminación
    "potencia": "potencia_w",
    "power": "potencia_w",
    "consumo de energia": "potencia_w",
    "consumo": "potencia_w",
    "wattage": "potencia_w",
    "lumens": "lumens",
    "lumenes": "lumens",
    "luminosidad": "lumens",
    "cri": "cri",
    "tlci": "cri",
    "temperatura de color": "temperatura_k",
    "color temperature": "temperatura_k",
    "kelvin": "temperatura_k",
    "bicolor": "bicolor",
    "rgb": "rgb",
    "dimming": "dimming",
    "control inalambrico": "control_inalambrico",
    "wireless control": "control_inalambrico",
    "dmx": "control_inalambrico",
    "alimentacion": "alimentacion",
    "power source": "alimentacion",
    "fuente de alimentacion": "alimentacion",
    "bateria": "alimentacion",
    "battery": "alimentacion",
    "montaje fijo": "montaje",

    # Modificadores
    "medidas": "medidas",
    "size": "medidas",
    "dimensiones": "medidas",
    "diameter": "medidas",
    "diametro": "medidas",
    "material": "material",
    "materiales": "material",
    "plegable": "plegable",

    # Soportes
    "altura maxima": "altura_max_m",
    "altura max": "altura_max_m",
    "max height": "altura_max_m",
    "altura minima": "altura_min_m",
    "altura min": "altura_min_m",
    "min height": "altura_min_m",
    "capacidad de carga": "peso_max_kg",
    "load capacity": "peso_max_kg",
    "carga maxima": "peso_max_kg",
    "carga max": "peso_max_kg",
    "max load": "peso_max_kg",
    "cabezal": "cabeza",
    "head": "cabeza",
    "nivel": "nivel",
    "ejes": "ejes",
    "axes": "ejes",
    "autonomia": "autonomia_h",

    # Grip
    "montaje 1/4": "montaje",
    "montura de tornillo": "montaje",
    "thread": "montaje",
    "rosca": "montaje",

    # Sonido
    "patron polar": "patron",
    "polar pattern": "patron",
    "patron": "patron",
    "banda": "banda_freq",
    "frequency band": "banda_freq",
    "frequency": "banda_freq",
    "canales": "canales",
    "channels": "canales",
    "conexion": "conexion",
    "connection": "conexion",
    "conector": "conexion",
    "connector": "conexion",

    # Monitor / Grabador
    "tamano de pantalla": "pulgadas",
    "pulgadas": "pulgadas",
    "screen size": "pulgadas",
    "resolucion": "resolucion",
    "resolution": "resolucion",
    "brillo": "brillo_nits",
    "brightness": "brillo_nits",
    "nits": "brillo_nits",
    "entradas": "entradas",
    "inputs": "entradas",
    "salidas": "salidas",
    "outputs": "salidas",
    "codecs": "codecs",
    "codec": "codecs",

    # Adaptador / Filtro
    "tipo": "tipo",
    "type": "tipo",
    "comunicacion electronica": "electronica",
    "electronic communication": "electronica",
    "af compatibility": "electronica",
    "densidad nd": "densidad",
    "densidad": "densidad",
    "nd": "densidad",

    # Energía
    "capacidad": "capacidad_wh",
    "capacity": "capacidad_wh",
    "voltaje": "voltaje",
    "voltage": "voltaje",
    "voltage output": "voltaje",
    "amperaje": "amperaje",
    "amperage": "amperaje",

    # Media
    "velocidad de lectura": "velocidad_lectura",
    "read speed": "velocidad_lectura",
    "velocidad lectura": "velocidad_lectura",
    "velocidad de escritura": "velocidad_escritura",
    "write speed": "velocidad_escritura",
    "velocidad escritura": "velocidad_escritura",
    "clase": "clase",
    "class": "clase",
    "speed class": "clase",
    "interfaz": "interfaz",
    "interface": "interfaz",
}


def _normalize_label(label: str) -> str:
    """Normaliza un label para buscar en ALIAS:
       - lowercase
       - sin acentos
       - sin puntuación / paréntesis
       - colapsa espacios.
    """
    if not label:
        return ""
    s = label.strip().lower()
    # Remover acentos básicos
    for old, new in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        s = s.replace(old, new)
    # Quitar paréntesis y su contenido
    s = re.sub(r"\([^)]*\)", "", s)
    # Quitar puntuación, normalizar espacios
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _slug_extra(label: str) -> str:
    """Genera una key para guardar specs que no matchearon ningún alias.
    Prefijo `_extra_` para distinguirlos del template oficial."""
    norm = _normalize_label(label)
    slug = re.sub(r"[^a-z0-9]+", "_", norm).strip("_")
    return f"_extra_{slug}" if slug else "_extra_unnamed"


def _bool_value(v: str) -> Optional[str]:
    """Si el valor parece booleano, normalizar a 'true'/'false'.
    Sino, None."""
    if v is None:
        return None
    vl = str(v).strip().lower()
    if vl in ("sí", "si", "yes", "true", "1", "incluye", "compatible"):
        return "true"
    if vl in ("no", "false", "0", "no incluye", "no compatible", "n/a", "n / a"):
        return "false"
    return None


def migrar_specs_de_equipo(
    conn,
    equipo_id: int,
    *,
    dry_run: bool = False,
) -> dict:
    """Migra los specs_json de un equipo a la tabla equipo_specs.
    Devuelve {matcheados, extras, errores, items}."""
    # Cargar specs_json
    row = conn.execute(
        "SELECT specs_json FROM equipo_fichas WHERE equipo_id = ?",
        (equipo_id,),
    ).fetchone()
    if not row or not row["specs_json"]:
        return {"matcheados": 0, "extras": 0, "errores": [], "items": []}

    try:
        specs_arr = json.loads(row["specs_json"])
    except (json.JSONDecodeError, TypeError):
        return {"matcheados": 0, "extras": 0,
                "errores": ["JSON inválido"], "items": []}

    if not isinstance(specs_arr, list):
        return {"matcheados": 0, "extras": 0,
                "errores": ["specs_json no es array"], "items": []}

    # Cargar las spec_keys del template de la categoría del equipo (para
    # validar que el target key existe).
    template_keys = {
        r["spec_key"]
        for r in conn.execute(
            """
            SELECT DISTINCT t.spec_key
            FROM categoria_spec_templates t
            JOIN equipo_categorias ec ON ec.categoria_id = t.categoria_id
            WHERE ec.equipo_id = ?
            """,
            (equipo_id,),
        ).fetchall()
    }

    items: list[dict] = []
    matcheados = 0
    extras = 0
    errores: list[str] = []

    for entry in specs_arr:
        if not isinstance(entry, dict):
            continue
        label = (entry.get("label") or "").strip()
        value = entry.get("value")
        if not label or value is None or str(value).strip() == "":
            continue
        value_str = str(value).strip()

        norm_label = _normalize_label(label)
        target_key = ALIAS.get(norm_label)

        if target_key and target_key in template_keys:
            # Match exitoso. Para booleanos, normalizamos el valor.
            bool_v = _bool_value(value_str)
            stored = bool_v if bool_v is not None else value_str
            items.append({"key": target_key, "value": stored, "label_original": label, "tipo": "matched"})
            matcheados += 1
            if not dry_run:
                conn.execute(
                    """
                    INSERT INTO equipo_specs (equipo_id, spec_key, value)
                    VALUES (?, ?, ?)
                    ON CONFLICT (equipo_id, spec_key) DO UPDATE
                        SET value = EXCLUDED.value
                    """,
                    (equipo_id, target_key, stored),
                )
        else:
            # Sin match — guardar como extra
            extra_key = _slug_extra(label)
            items.append({"key": extra_key, "value": value_str, "label_original": label, "tipo": "extra"})
            extras += 1
            if not dry_run:
                conn.execute(
                    """
                    INSERT INTO equipo_specs (equipo_id, spec_key, value)
                    VALUES (?, ?, ?)
                    ON CONFLICT (equipo_id, spec_key) DO UPDATE
                        SET value = EXCLUDED.value
                    """,
                    (equipo_id, extra_key, value_str),
                )

    if not dry_run:
        conn.commit()

    return {
        "equipo_id": equipo_id,
        "matcheados": matcheados,
        "extras": extras,
        "errores": errores,
        "items": items,
    }


def migrar_specs_todos(conn, *, dry_run: bool = False) -> dict:
    """Migra specs_json de todos los equipos que tengan ficha. Devuelve
    un reporte agregado."""
    rows = conn.execute(
        """
        SELECT equipo_id
        FROM equipo_fichas
        WHERE specs_json IS NOT NULL AND specs_json != '' AND specs_json != '[]'
        """
    ).fetchall()

    total_matcheados = 0
    total_extras = 0
    detalle_errores: list[dict] = []
    procesados = 0

    for r in rows:
        try:
            res = migrar_specs_de_equipo(conn, r["equipo_id"], dry_run=dry_run)
            total_matcheados += res["matcheados"]
            total_extras += res["extras"]
            procesados += 1
            if res["errores"]:
                detalle_errores.append({"equipo_id": r["equipo_id"], "errores": res["errores"]})
        except Exception as e:
            detalle_errores.append({"equipo_id": r["equipo_id"], "error": str(e)})

    return {
        "procesados": procesados,
        "total_matcheados": total_matcheados,
        "total_extras": total_extras,
        "errores": detalle_errores,
        "dry_run": dry_run,
    }
