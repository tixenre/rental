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

# Taxonomía de 2 niveles, alineada con cómo el cliente busca:
#   - Foto / Video / Acción son los "buckets" principales (use case)
#   - Video se sub-divide por MONTURA para que el cliente filtre por
#     compatibilidad de lentes que ya tiene (criterio #1 en rentals cine)
#
# Multi-categorización (M2M via equipo_categorias):
#   - Cámaras híbridas tipo Sony a7V pueden estar en Foto Y Video/Montura E
#   - El placeholder de categoría también respeta esto (un equipo → N cat)
#
# Estructura:
#   Cámaras (raíz)
#     ├─ Foto                — todo lo apto para stills (incluye híbridas)
#     ├─ Video               — contenedor sin productos directos
#     │     ├─ Montura E     — Sony cinema/mirrorless con E mount
#     │     ├─ Montura RF    — Canon/RED RF
#     │     ├─ Montura EF    — Canon EF cine (C200 used, etc.)
#     │     ├─ Montura L     — Panasonic, Leica, Sigma L
#     │     ├─ Montura Z     — Nikon Z
#     │     ├─ Montura PL    — cine PL (Alexa, Sony Venice, RED PL)
#     │     └─ Montura BMD   — Blackmagic Pocket
#     └─ Acción              — GoPro, Insta360, DJI Action

SUBCATEGORIAS_NIVEL1 = [
    ("Foto",   10),   # DSLR, Medium Format, mirrorless híbridas (también acá)
    ("Video",  20),   # contenedor (sub-divide por montura)
    ("Acción", 30),   # GoPro, Insta360, DJI Action
]

# Sub-categorías dentro de "Video", por montura del cuerpo
# (criterio principal de compatibilidad para producción cine)
SUBCATEGORIAS_NIVEL2_VIDEO = [
    ("Montura E",   10),  # Sony cinema + mirrorless E (FX3A, a7V, ZV-E1, FX6, FX9, FX30)
    ("Montura RF",  20),  # Canon R + RED KOMODO RF
    ("Montura EF",  30),  # Canon EF cine (C200, C300, etc.)
    ("Montura L",   40),  # Panasonic S series, Sigma fp, Leica
    ("Montura Z",   50),  # Nikon Z series
    ("Montura PL",  60),  # Cine PL — Alexa, Sony Venice, RED PL
    ("Montura BMD", 70),  # Blackmagic Pocket
]


# Spec definitions específicas de cámaras (se mergan con las de spec_templates.py)
SPECS_CAMARAS = [
    # (spec_key, label, tipo, unidad, enum_options, ayuda)
    ("tipo",            "Tipo",                 "enum", None,
     ["Cinema Camera", "Mirrorless", "DSLR", "Vlogging", "Action Camera", "Compact", "Medium Format", "Camera"],
     "Form factor de la cámara"),
    ("lens_mount",      "Lens mount",           "enum", None,
     ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
     "Null para cámaras con lente fijo (action cams, smartphones)"),
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


def categorize(producto: dict) -> list[str]:
    """Devuelve LISTA de sub-categorías donde va el producto (M2M).

    Regla: categorizar por **caso de uso primario**, no por capacidad técnica.
    Que una cámara PUEDA hacer X no significa que pertenezca a la categoría X.
    Pertenece a X si se RENTA para eso.

    Mapeo por tipo:
      Action Camera           → ["Acción"]
      Medium Format           → ["Foto"]                       (sin video)
      DSLR                    → ["Foto"]                       (primarily stills)
      Compact                 → ["Foto"]                       (point & shoot)
      Cinema Camera           → ["Montura X"]                  (video puro)
      Vlogging                → ["Montura X"]                  (video puro, vlog
                                                                features)
      Mirrorless              → ["Foto", "Montura X"]          (hybrid real:
                                                                a7V, R5, etc.)

    El segundo nivel para Video depende de lens_mount del equipo.
    """
    specs = producto.get("specs", {})
    tipo = specs.get("tipo", "")
    mount = specs.get("lens_mount")

    # 1. Acción
    if tipo == "Action Camera":
        return ["Acción"]

    # 2. Foto puras (sin video relevante)
    if tipo == "Medium Format":
        return ["Foto"]
    if tipo in ("DSLR", "Compact"):
        # Foto primary. Si tiene video razonable también podríamos sumar Video,
        # pero la mayoría se rentan para foto. Mantener simple: solo Foto.
        return ["Foto"]

    # 3. Video puras (cinema cámaras + vlogging)
    if tipo in ("Cinema Camera", "Vlogging"):
        if mount:
            return [_video_subcat_for_mount(mount)]
        return ["Acción"]  # fallback raro

    # 4. Mirrorless / default → híbridas reales (foto + video)
    cats = ["Foto"]
    if mount:
        cats.append(_video_subcat_for_mount(mount))
    return cats


def _video_subcat_for_mount(mount: str) -> str:
    """Mapea lens_mount → nombre de sub-categoría bajo Video."""
    mount = (mount or "").strip().upper()
    if mount in ("E", "RF", "EF", "L", "Z", "PL", "BMD"):
        return f"Montura {mount}"
    # Mount poco común — caer en E como default seguro
    return f"Montura {mount}" if mount else "Montura E"


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

    def _upsert_subcat(name: str, prio: int, parent: int) -> int | None:
        """Inserta o trae el id de una sub-categoría bajo el parent dado."""
        row = conn.execute("SELECT id, parent_id FROM categorias WHERE nombre = %s", (name,)).fetchone()
        if row:
            # Si ya existe pero con otro parent_id, actualizarlo (idempotente)
            if row["parent_id"] != parent and not dry_run:
                conn.execute("UPDATE categorias SET parent_id = %s WHERE id = %s", (parent, row["id"]))
            return row["id"]
        if dry_run:
            stats["subcategorias_creadas"] += 1
            return -1
        cur = conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id) VALUES (%s, %s, %s)
            ON CONFLICT (nombre) DO UPDATE
                SET parent_id = EXCLUDED.parent_id,
                    prioridad = CASE WHEN categorias.prioridad = 100 THEN EXCLUDED.prioridad ELSE categorias.prioridad END
            RETURNING id
        """, (name, prio, parent))
        new = cur.fetchone()
        if new:
            stats["subcategorias_creadas"] += 1
            return new[0] if isinstance(new, tuple) else new["id"]
        return None

    # Nivel 1: Foto / Video (intermediate) / Acción
    nivel1_ids: dict[str, int] = {}
    for name, prio in SUBCATEGORIAS_NIVEL1:
        nid = _upsert_subcat(name, prio, parent_id)
        if nid is not None:
            nivel1_ids[name] = nid
            subcat_ids[name] = nid

    # Nivel 2: Cine, Híbrida dentro de Video
    video_id = nivel1_ids.get("Video")
    if video_id:
        for name, prio in SUBCATEGORIAS_NIVEL2_VIDEO:
            nid = _upsert_subcat(name, prio, video_id)
            if nid is not None:
                subcat_ids[name] = nid

    # NOTA: el código viejo continuaba con SUBCATEGORIAS; ahora skipeamos
    # la iteración antigua porque ya hicimos todo arriba.
    for name, prio in []:  # placeholder vacío para mantener estructura
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
            # 4a. Asignar a sub-categorías (multi-cat M2M)
            for cat_name in categorize(prod):
                cat_id = subcat_ids.get(cat_name)
                if not cat_id:
                    # Sub-categoría no estaba pre-creada (ej. Montura Z sin productos en SUBCATEGORIAS_NIVEL2_VIDEO)
                    # La creamos on-the-fly como child de Video
                    video_pid = nivel1_ids.get("Video")
                    if cat_name.startswith("Montura ") and video_pid:
                        cat_id = _upsert_subcat(cat_name, 99, video_pid)
                        if cat_id:
                            subcat_ids[cat_name] = cat_id
                if cat_id and cat_id != -1:
                    conn.execute("""
                        INSERT INTO equipo_categorias (equipo_id, categoria_id)
                        VALUES (%s, %s)
                        ON CONFLICT (equipo_id, categoria_id) DO NOTHING
                    """, (equipo_id, cat_id))

            # 4b. Spec values
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
