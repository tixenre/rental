"""
seeds/camaras.py — Importa el dataset curado de cámaras a la DB.

Mismo patrón que seeds/iluminacion.py:
  1. Sub-categorías de "Cámaras"
  2. spec_definitions específicas (lens_mount, formato, codecs, etc.)
  3. categoria_spec_templates asignados
  4. equipos + equipo_specs

Idempotente. Uso:
  Manual:    python -m backend.seeds.camaras [--dry-run]
  Auto-run:  agregar seed_camaras(conn) en main.py post-migrations
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "docs" / "camaras.json"

CATEGORIA_RAIZ = "Cámaras"
SUBCATEGORIAS = [
    ("Cinema",      10),  # FX3A, C200, KOMODO-X
    ("Mirrorless",  20),  # a7V
    ("Vlogging",    30),  # ZV-E1
    ("Action",      40),  # HERO12
    ("DSLR",        50),  # futuro
    ("Medium Format", 60),  # futuro
]


# Spec definitions específicas de cámaras (se mergan con las de spec_templates.py)
SPECS_CAMARAS = [
    # (spec_key, label, tipo, unidad, enum_options, ayuda)
    ("tipo",            "Tipo",                 "enum", None,
     ["Cinema Camera", "Mirrorless", "DSLR", "Vlogging", "Action Camera", "Compact", "Medium Format", "Camera"],
     "Form factor de la cámara"),
    ("lens_mount",      "Lens mount",           "enum", None,
     ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42", "Fija"],
     "Fija = lente fijo (action cams, smartphones)"),
    ("formato",         "Formato",              "enum", None,
     ["Full-frame", "Super 35", "APS-C", "MFT", "M4/3", "Medium Format", "1\""],
     None),
    ("resolucion_max",  "Resolución máxima",    "enum", None,
     ["FHD", "2K", "4K", "5K", "5.7K", "6K", "8K", "12K"], None),
    ("fps_max",         "FPS máx",              "number", "fps", None,
     "Frame rate máximo en cualquier resolución"),
    ("megapixels",      "Megapixels",           "number", "MP", None, None),
    ("codecs",          "Codecs principales",   "string", None, None,
     "Ej: ProRes, REDCODE, XAVC S-I 4:2:2"),
    ("iso_nativo",      "ISO nativo",           "rango", "ISO", None,
     "Rango nativo. Ej: '80-102400'"),
    ("iso_extendido",   "ISO extendido",        "rango", "ISO", None,
     "Con boost. Ej: '80-409600'"),
    ("rango_dinamico_stops", "Rango dinámico",  "number", "stops", None, None),
    ("estabilizacion",  "Estabilización óptica", "bool", None, None, None),
    ("autofocus",       "Autofocus",            "bool", None, None, None),
    ("fast_slow_motion","Fast/Slow motion",     "bool", None, None,
     "Soporta variable frame rate / S&Q"),
    ("lens_communication", "Comunicación electrónica lente", "bool", None, None, None),
    ("gps",             "GPS",                  "bool", None, None, None),
    ("ip_streaming",    "IP Streaming",         "bool", None, None,
     "Para broadcast / live streaming"),
    ("netflix_approved", "Netflix approved",    "bool", None, None, None),
    ("continuous_shooting_fps", "Ráfaga (stills)", "number", "fps", None,
     "Burst rate para fotografía"),
    ("max_aperture",    "Apertura máxima (fixed-lens)", "string", None, None,
     "Solo para cámaras con lente fijo (GoPro, etc.)"),
    ("sensor_crop",     "Sensor crop (35mm eq.)", "string", None, None, None),
    ("recording_limit_min", "Límite de grabación", "number", "min", None,
     "Algunos modelos tienen tope 29min59s"),
    ("peso",            "Peso",                 "number", "g", None, None),
]


SPEC_FLAGS_CAMARAS = {
    # spec_key: (prioridad, en_card, en_filtros, en_nombre, destacado)
    "tipo":              (10,  True,  True,  True,  True),
    "lens_mount":        (15,  True,  True,  True,  True),
    "formato":           (20,  True,  True,  True,  True),
    "resolucion_max":    (30,  True,  True,  True,  True),
    "fps_max":           (40,  False, True,  False, True),
    "megapixels":        (45,  False, True,  False, False),
    "codecs":            (60,  False, False, False, False),
    "iso_nativo":        (65,  False, True,  False, False),
    "iso_extendido":     (67,  False, False, False, False),
    "rango_dinamico_stops": (70, False, True, False, False),
    "estabilizacion":    (75,  False, True,  False, False),
    "autofocus":         (80,  False, True,  False, False),
    "netflix_approved":  (98,  True,  True,  False, False),
    "peso":              (100, False, False, False, False),
}


def categorize(producto: dict) -> str:
    """Sub-categoría según tipo."""
    tipo = producto.get("specs", {}).get("tipo", "")
    if tipo == "Cinema Camera": return "Cinema"
    if tipo == "Mirrorless":     return "Mirrorless"
    if tipo == "Vlogging":       return "Vlogging"
    if tipo == "Action Camera":  return "Action"
    if tipo == "DSLR":           return "DSLR"
    if tipo == "Medium Format":  return "Medium Format"
    return "Mirrorless"  # fallback razonable


def serialize_spec_value(spec_key: str, value) -> str | None:
    """Convierte valor JSON al formato TEXT de equipo_specs.value."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if "min" in value and "max" in value:
            return f"{value['min']}-{value['max']}"
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def seed_camaras(conn, dry_run: bool = False) -> dict:
    if not DATASET_PATH.exists():
        return {"error": f"Dataset no encontrado: {DATASET_PATH}"}

    with open(DATASET_PATH) as f:
        data = json.load(f)
    products = data.get("products", {})

    stats = {
        "specs_creadas": 0, "subcategorias_creadas": 0,
        "asignaciones_creadas": 0, "equipos_creados": 0,
        "equipos_actualizados": 0, "equipo_specs_insertados": 0,
        "dry_run": dry_run,
    }

    # 1. spec_definitions
    spec_def_ids: dict[str, int] = {}
    for spec_key, label, tipo, unidad, enum_opts, ayuda in SPECS_CAMARAS:
        row = conn.execute("SELECT id FROM spec_definitions WHERE spec_key = %s", (spec_key,)).fetchone()
        if row:
            spec_def_ids[spec_key] = row["id"]
            continue
        if dry_run:
            spec_def_ids[spec_key] = -1
            stats["specs_creadas"] += 1
            continue
        enum_json = json.dumps(enum_opts) if enum_opts else None
        cur = conn.execute("""
            INSERT INTO spec_definitions (spec_key, label, tipo, unidad, enum_options, ayuda)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (spec_key) DO NOTHING RETURNING id
        """, (spec_key, label, tipo, unidad, enum_json, ayuda))
        new = cur.fetchone()
        if new:
            spec_def_ids[spec_key] = new[0] if isinstance(new, tuple) else new["id"]
            stats["specs_creadas"] += 1
        else:
            row = conn.execute("SELECT id FROM spec_definitions WHERE spec_key = %s", (spec_key,)).fetchone()
            if row: spec_def_ids[spec_key] = row["id"]

    # 2. Sub-categorías de Cámaras
    parent_row = conn.execute(
        "SELECT id FROM categorias WHERE nombre = %s AND parent_id IS NULL",
        (CATEGORIA_RAIZ,)
    ).fetchone()
    if not parent_row:
        return {"error": f"Categoría raíz '{CATEGORIA_RAIZ}' no existe."}
    parent_id = parent_row["id"]

    subcat_ids: dict[str, int] = {}
    for name, prio in SUBCATEGORIAS:
        row = conn.execute("SELECT id FROM categorias WHERE nombre = %s", (name,)).fetchone()
        if row:
            subcat_ids[name] = row["id"]
            continue
        if dry_run:
            subcat_ids[name] = -1
            stats["subcategorias_creadas"] += 1
            continue
        cur = conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id) VALUES (%s, %s, %s)
            ON CONFLICT (nombre) DO UPDATE
                SET parent_id = EXCLUDED.parent_id,
                    prioridad = CASE WHEN categorias.prioridad = 100 THEN EXCLUDED.prioridad ELSE categorias.prioridad END
            RETURNING id
        """, (name, prio, parent_id))
        new = cur.fetchone()
        if new:
            subcat_ids[name] = new[0] if isinstance(new, tuple) else new["id"]
            stats["subcategorias_creadas"] += 1

    # 3. categoria_spec_templates (solo si la categoría no tiene asignaciones)
    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE categoria_id = %s",
        (parent_id,)
    ).fetchone()
    if not existing or existing["n"] == 0:
        for spec_key, flags in SPEC_FLAGS_CAMARAS.items():
            spec_def_id = spec_def_ids.get(spec_key)
            if not spec_def_id or spec_def_id == -1:
                continue
            prio, en_card, en_filtros, en_nombre, destacado = flags
            if dry_run:
                stats["asignaciones_creadas"] += 1
                continue
            cur = conn.execute("""
                INSERT INTO categoria_spec_templates
                  (categoria_id, spec_def_id, prioridad, destacado,
                   visible_en_card, visible_en_filtros, visible_en_nombre)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (categoria_id, spec_def_id) DO NOTHING RETURNING id
            """, (parent_id, spec_def_id, prio, destacado, en_card, en_filtros, en_nombre))
            if cur.fetchone():
                stats["asignaciones_creadas"] += 1

    # 4. Equipos + equipo_specs
    for prod_id, prod in products.items():
        marca = prod.get("marca", "")
        modelo = prod.get("modelo", "")
        nombre = f"{marca} {modelo}".strip()
        foto_url = prod.get("image_url", "")
        bh_url = prod.get("url_source", "")

        existing = conn.execute(
            "SELECT id FROM equipos WHERE marca = %s AND modelo = %s LIMIT 1",
            (marca, modelo)
        ).fetchone()

        if existing:
            equipo_id = existing["id"]
            if not dry_run:
                conn.execute("""
                    UPDATE equipos
                    SET foto_url = COALESCE(NULLIF(foto_url, ''), %s),
                        bh_url   = COALESCE(NULLIF(bh_url, ''), %s)
                    WHERE id = %s
                """, (foto_url, bh_url, equipo_id))
            stats["equipos_actualizados"] += 1
        else:
            if dry_run:
                equipo_id = -1
                stats["equipos_creados"] += 1
            else:
                cur = conn.execute("""
                    INSERT INTO equipos (nombre, marca, modelo, foto_url, bh_url, cantidad, dueno)
                    VALUES (%s, %s, %s, %s, %s, 1, 'Rambla') RETURNING id
                """, (nombre, marca, modelo, foto_url, bh_url))
                row = cur.fetchone()
                equipo_id = row[0] if isinstance(row, tuple) else row["id"]
                stats["equipos_creados"] += 1

        if equipo_id != -1 and not dry_run:
            specs = prod.get("specs", {})
            for spec_key, value in specs.items():
                spec_def_id = spec_def_ids.get(spec_key)
                if not spec_def_id:
                    continue
                value_str = serialize_spec_value(spec_key, value)
                if value_str is None:
                    continue
                conn.execute("""
                    INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (equipo_id, spec_def_id) DO UPDATE SET value = EXCLUDED.value
                """, (equipo_id, spec_def_id, value_str))
                stats["equipo_specs_insertados"] += 1

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from database import get_db  # type: ignore
    except ImportError as e:
        print(f"Error importando database: {e}")
        print("Correr desde root: python -m backend.seeds.camaras [--dry-run]")
        sys.exit(1)

    conn = get_db()
    try:
        stats = seed_camaras(conn, dry_run=dry_run)
        if not dry_run:
            conn.commit()
        print(f"\n{'═' * 50}")
        print("  Seed de cámaras" + (" (DRY RUN)" if dry_run else ""))
        print('═' * 50)
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
    finally:
        conn.close()
