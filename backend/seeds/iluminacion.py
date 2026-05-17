"""
seeds/iluminacion.py — Importa el dataset curado de iluminación a la DB.

Lee `docs/iluminacion.json` y popula:
  1. categorias: sub-categorías de Iluminación (LED Daylight, LED Bicolor,
     LED RGB, Tungsteno, Flash)
  2. spec_definitions: specs específicas de iluminación (tipo, color_modes,
     lumens_at_*, lux_at_*, tlci, etc.) que no estaban en spec_templates.py
  3. categoria_spec_templates: asignación a categoría "Iluminación"
  4. equipos: una row por luz con foto_url, bh_url, marca, modelo
  5. equipo_specs: valores de spec por equipo

Idempotente:
  - Equipos: match por (marca, modelo); si existe, actualiza foto_url/bh_url
    pero NO toca precio_jornada (lo configura el admin)
  - Specs: ON CONFLICT (spec_key) DO NOTHING
  - Asignaciones: ON CONFLICT (categoria_id, spec_def_id) DO NOTHING

Uso:
  - Auto-import: agregar `seed_iluminacion(conn)` en main.py post-migrations
  - Manual: `python backend/seeds/iluminacion.py [--dry-run]`

Este es el patrón que se va a usar para cámaras, lentes, etc.:
  docs/bh_<categoria>_curado.json + backend/seeds/<categoria>.py
"""

import json
import sys
from pathlib import Path

try:
    from .compat_config import load_match_file, resolve_equipo_id, apply_overrides, write_keywords
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from compat_config import load_match_file, resolve_equipo_id, write_keywords  # type: ignore

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "docs" / "iluminacion.json"

CATEGORIA_RAIZ = "Iluminación"
SUBCATEGORIAS = [
    ("LED Daylight",  10),
    ("LED Bicolor",   20),
    ("LED RGB",       30),
    ("Tungsteno",     40),
    ("Flash",         50),
]


# ── Spec definitions específicas de iluminación ─────────────────────────
# Aumentan lo que ya define spec_templates.py. Cada una se inserta con
# ON CONFLICT DO NOTHING — si ya existe la spec_key, se respeta.

SPECS_ILUMINACION = [
    # spec_key, label, tipo, unidad, enum_options, ayuda
    ("tipo",                "Tipo",                     "enum", None,
     ["Flash","Bulb / Lamp","Panel","Tube Light","Flexible Mat","Monolight","COB Monolight","Spotlight","Fresnel","On-Camera"],
     "Form factor del fixture"),
    ("potencia_w",          "Potencia",                 "number", "W", None, None),
    ("lumens_at_5600k",     "Lúmenes (5600K)",          "number", "lm", None, "Lúmenes totales a daylight 5600K"),
    ("lumens_at_3200k",     "Lúmenes (3200K)",          "number", "lm", None, "Lúmenes totales a tungsten 3200K"),
    ("lux_at_1m_5600k",     "Lux a 1m (5600K)",         "number", "lx", None, "Estándar cine — Lux a 1m daylight"),
    ("lux_at_1m_3200k",     "Lux a 1m (3200K)",         "number", "lx", None, "Lux a 1m tungsten"),
    ("cri",                 "CRI",                      "number", None, None, "Color Rendering Index 0-100"),
    ("tlci",                "TLCI",                     "number", None, None, "Broadcast color rendering 0-100"),
    ("r9",                  "R9",                       "number", None, None, "Deep red rendering 0-100"),
    ("temperatura_k",       "Temperatura color",        "rango", "K", None,
     "Rango Kelvin. Si fijo: usar el mismo valor (ej. '3200-3200')"),
    ("color_modes",         "Modos de color",           "multi_enum", None,
     ["RGB","Daylight","Tungsten","HSI","Bicolor variable"], None),
    ("dimming",             "Dimmer",                   "bool", None, None, None),
    ("control_inalambrico", "Control inalámbrico",      "multi_enum", None,
     ["Bluetooth","DMX","RDM","Wi-Fi","CRMX","Lumenradio","Art-Net","sACN"], None),
    ("alimentacion",        "Alimentación",             "multi_enum", None,
     ["AC","V-mount","Gold Mount","NP-F","D-Tap","USB-C","Batería integrada"], None),
    ("montaje",             "Montaje (modificador)",    "enum", None,
     ["Bowens","Propietario","Fresnel","Profoto","Elinchrom"], None),
    ("peso_g",              "Peso",                     "number", "g", None, "Peso del fixture solo, sin accesorios (gramos como base; UI computa kg/lb)"),
]


# Flags de visibilidad por spec en la categoría Iluminación
# (cuáles aparecen en card, filtros, nombre público)
SPEC_FLAGS_ILUMINACION = {
    # spec_key:        (prioridad, en_card, en_filtros, en_nombre, destacado)
    "tipo":              (10,  True,  True,  True,  True),
    "potencia_w":        (20,  True,  True,  True,  True),
    "color_modes":       (30,  True,  True,  False, True),
    "temperatura_k":     (40,  True,  True,  False, False),
    "cri":               (50,  False, True,  False, False),
    "tlci":              (55,  False, False, False, False),
    "lumens_at_5600k":   (60,  False, True,  False, False),
    "lumens_at_3200k":   (61,  False, False, False, False),
    "lux_at_1m_5600k":   (62,  False, False, False, False),
    "lux_at_1m_3200k":   (63,  False, False, False, False),
    "r9":                (65,  False, False, False, False),
    "dimming":           (70,  False, True,  False, False),
    "control_inalambrico":(80, False, True,  False, False),
    "alimentacion":      (90,  False, True,  False, False),
    "montaje":           (100, False, True,  False, False),
    "peso_g":            (110, False, False, False, False),
}


# ── Mapeo curado → sub-categoría ────────────────────────────────────────

def categorize(producto: dict) -> str:
    """Determina la sub-categoría según specs.color_modes + tipo.

    Reglas (en orden):
      1. tipo=Flash → "Flash"
      2. color_modes contiene RGB → "LED RGB"
      3. color_modes contiene Daylight Y Tungsten → "LED Bicolor"
      4. color_modes solo Daylight → "LED Daylight"
      5. color_modes solo Tungsten → "Tungsteno"
    """
    s = producto.get("specs", {})
    tipo = s.get("tipo", "")
    modes = set(s.get("color_modes", []))

    if tipo == "Flash":
        return "Flash"
    if "RGB" in modes:
        return "LED RGB"
    if "Daylight" in modes and "Tungsten" in modes:
        return "LED Bicolor"
    if modes == {"Daylight"}:
        return "LED Daylight"
    if modes == {"Tungsten"}:
        return "Tungsteno"
    return "LED Daylight"  # fallback razonable


# ── Serialización de valores spec → equipo_specs.value (TEXT) ─────────────

def serialize_spec_value(spec_key: str, value) -> str | None:
    """Convierte el valor del JSON al formato TEXT que espera equipo_specs."""
    if value is None:
        return None

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, list):
        # multi_enum: JSON array. control_inalambrico, alimentacion, color_modes
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, dict):
        # Rangos (temperatura_k): formato "min-max"
        if "min" in value and "max" in value:
            return f"{value['min']}-{value['max']}"
        # Otros dicts: serializar JSON (caso extremo)
        return json.dumps(value, ensure_ascii=False)

    return str(value)


# ── Seed principal ──────────────────────────────────────────────────────

def seed_iluminacion(conn, dry_run: bool = False) -> dict:
    """Importa el dataset curado de iluminación. Devuelve stats {creados, actualizados, ...}."""
    if not DATASET_PATH.exists():
        return {"error": f"Dataset no encontrado: {DATASET_PATH}"}

    with open(DATASET_PATH) as f:
        data = json.load(f)
    products = data.get("products", {})

    stats = {
        "specs_creadas": 0,
        "subcategorias_creadas": 0,
        "asignaciones_creadas": 0,
        "equipos_creados": 0,
        "equipos_actualizados": 0,
        "equipo_specs_insertados": 0,
        "dry_run": dry_run,
    }

    # ── 1. spec_definitions ───────────────────────────────────────────
    spec_def_ids: dict[str, int] = {}
    for spec_key, label, tipo, unidad, enum_opts, ayuda in SPECS_ILUMINACION:
        row = conn.execute(
            "SELECT id FROM spec_definitions WHERE spec_key = %s", (spec_key,)
        ).fetchone()
        if row:
            spec_def_ids[spec_key] = row["id"]
            continue

        if dry_run:
            spec_def_ids[spec_key] = -1  # placeholder
            stats["specs_creadas"] += 1
            continue

        enum_json = json.dumps(enum_opts) if enum_opts else None
        cur = conn.execute("""
            INSERT INTO spec_definitions (spec_key, label, tipo, unidad, enum_options, ayuda)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (spec_key) DO NOTHING
            RETURNING id
        """, (spec_key, label, tipo, unidad, enum_json, ayuda))
        new = cur.fetchone()
        if new:
            spec_def_ids[spec_key] = new[0] if isinstance(new, tuple) else new["id"]
            stats["specs_creadas"] += 1
        else:
            row = conn.execute(
                "SELECT id FROM spec_definitions WHERE spec_key = %s", (spec_key,)
            ).fetchone()
            if row:
                spec_def_ids[spec_key] = row["id"]

    # ── 2. Sub-categorías de Iluminación ──────────────────────────────
    parent_row = conn.execute(
        "SELECT id FROM categorias WHERE nombre = %s AND parent_id IS NULL",
        (CATEGORIA_RAIZ,)
    ).fetchone()
    if not parent_row:
        return {"error": f"Categoría raíz '{CATEGORIA_RAIZ}' no existe. Correr seed de categorias primero."}
    parent_id = parent_row["id"]

    subcat_ids: dict[str, int] = {}
    for name, prioridad in SUBCATEGORIAS:
        row = conn.execute(
            "SELECT id FROM categorias WHERE nombre = %s", (name,)
        ).fetchone()
        if row:
            subcat_ids[name] = row["id"]
            continue

        if dry_run:
            subcat_ids[name] = -1
            stats["subcategorias_creadas"] += 1
            continue

        cur = conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (nombre) DO UPDATE
                SET parent_id = EXCLUDED.parent_id,
                    prioridad = CASE
                        WHEN categorias.prioridad = 100 THEN EXCLUDED.prioridad
                        ELSE categorias.prioridad
                    END
            RETURNING id
        """, (name, prioridad, parent_id))
        new = cur.fetchone()
        if new:
            subcat_ids[name] = new[0] if isinstance(new, tuple) else new["id"]
            stats["subcategorias_creadas"] += 1

    # ── 3. categoria_spec_templates (asignar specs a Iluminación) ─────
    # Solo si la categoría no tiene ninguna asignación (respeto al back-office)
    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE categoria_id = %s",
        (parent_id,)
    ).fetchone()
    if not existing or existing["n"] == 0:
        for spec_key, flags in SPEC_FLAGS_ILUMINACION.items():
            spec_def_id = spec_def_ids.get(spec_key)
            if not spec_def_id:
                continue
            prio, en_card, en_filtros, en_nombre, destacado = flags
            if dry_run:
                # En dry-run contamos como "se crearía" incluso si spec_def_id=-1
                stats["asignaciones_creadas"] += 1
                continue
            cur = conn.execute("""
                INSERT INTO categoria_spec_templates
                  (categoria_id, spec_def_id, prioridad, destacado,
                   visible_en_card, visible_en_filtros, visible_en_nombre)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (categoria_id, spec_def_id) DO NOTHING
                RETURNING id
            """, (parent_id, spec_def_id, prio, destacado, en_card, en_filtros, en_nombre))
            if cur.fetchone():
                stats["asignaciones_creadas"] += 1

    # ── 4. Equipos + equipo_specs ─────────────────────────────────────
    # Mapeo manual desde docs/equipos_match.json (si existe) para preservar
    # equipo.id en updates — protege FKs de pedidos históricos.
    match_map = load_match_file(CATEGORIA_RAIZ)
    stats["matches_aplicados_desde_archivo"] = 0

    for prod_id, prod in products.items():
        marca = prod.get("marca", "")
        modelo = prod.get("modelo", "")
        nombre = f"{marca} {modelo}".strip()
        foto_url = prod.get("image_url", "")
        bh_url = prod.get("url_source", "")
        subcat_name = categorize(prod)
        subcat_id = subcat_ids.get(subcat_name)

        # Resolver equipo_id: usa docs/equipos_match.json si existe, sino
        # fallback a match por (marca, modelo). Preserva FKs de pedidos.
        equipo_id, fuente = resolve_equipo_id(conn, prod_id, marca, modelo, match_map)

        if fuente == "skip":
            stats["skipped"] = stats.get("skipped", 0) + 1
            continue

        if equipo_id is not None:
            if fuente == "match_file":
                stats["matches_aplicados_desde_archivo"] += 1
            applied = apply_overrides(conn, prod_id, equipo_id, match_map, dry_run=dry_run)
            if applied:
                stats["overrides_aplicados"] = stats.get("overrides_aplicados", 0) + 1
            if not dry_run:
                # Actualizar foto_url/bh_url si están vacíos (no pisar admin)
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
                    VALUES (%s, %s, %s, %s, %s, 1, 'Rambla')
                    RETURNING id
                """, (nombre, marca, modelo, foto_url, bh_url))
                row = cur.fetchone()
                equipo_id = row[0] if isinstance(row, tuple) else row["id"]
                stats["equipos_creados"] += 1

        # equipo_specs: valores del producto
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
                    ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
                        SET value = EXCLUDED.value
                """, (equipo_id, spec_def_id, value_str))
                stats["equipo_specs_insertados"] += 1

            # Keywords derivadas (después de poblar specs)
            n_kw = write_keywords(conn, equipo_id, prod.get("specs", {}), dry_run=dry_run)
            stats["keywords_generadas"] = stats.get("keywords_generadas", 0) + n_kw

    return stats


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from database import get_db  # type: ignore
    except ImportError as e:
        print(f"Error importando database: {e}")
        print("Correr desde root: python -m backend.seeds.iluminacion [--dry-run]")
        sys.exit(1)

    conn = get_db()
    try:
        stats = seed_iluminacion(conn, dry_run=dry_run)
        if not dry_run:
            conn.commit()
        print(f"\n{'═' * 50}")
        print("  Seed de luces — Iluminación" + (" (DRY RUN)" if dry_run else ""))
        print('═' * 50)
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
    finally:
        conn.close()
