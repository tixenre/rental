"""
seeds/lentes.py — Importa el dataset curado de lentes a la DB.

Mismo patrón que seeds/camaras.py:
  1. Sub-categorías de "Lentes" (Zoom / Fijos / Vintage / Especiales) — la
     montura es un FILTRO (spec lens_mount), no parte de la taxonomía.
  2. spec_definitions específicas (lens_mount, distancia_focal rango, apertura rango, etc.)
  3. categoria_spec_templates asignados
  4. equipos + equipo_specs

Idempotente. Uso:
  Manual:    python -m backend.seeds.lentes [--dry-run]
  Auto-run:  agregar seed_lentes(conn) en main.py post-migrations
"""

import json
import sys
from pathlib import Path

# Import compat helpers. Soporta tanto `python -m backend.seeds.lentes` (relativo)
# como `python backend/seeds/lentes.py` (absoluto vía sys.path en __main__).
try:
    from .compat_config import (
        FORMATO_ENUM,
        apply_compat_config,
        apply_overrides,
        apply_rol_compat,
        ensure_categoria_raiz,
        load_match_file,
        resolve_equipo_id,
        write_keywords,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from compat_config import (  # type: ignore
        FORMATO_ENUM,
        apply_compat_config,
        apply_overrides,
        apply_rol_compat,
        ensure_categoria_raiz,
        load_match_file,
        resolve_equipo_id,
        write_keywords,
    )

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "docs" / "lentes.json"

CATEGORIA_RAIZ = "Lentes"

# Sub-categorías predefinidas por SEED_TREE (database.py:548). Aquí solo
# garantizamos las que vamos a usar — el árbol completo se inicializa al
# bootstrap de la DB.
# Sub-categorías por TIPO. Las de MONTURA ("Montura E", "Montura EF", ...)
# se crean on-the-fly en seed_lentes() según el stock real (mismo patrón que
# camaras.py con las monturas bajo "Video").
SUBCATEGORIAS = [
    ("Zoom",       10),
    ("Fijo",       20),
    ("Vintage",    30),
    ("Especiales", 40),
]

# Prioridades base para las sub-cats de montura (van después de las de tipo)
MONTURA_PRIORIDAD_BASE = 50


# Spec definitions de Lentes (alineadas a spec_templates.py::Lentes)
SPECS_LENTES = [
    # (spec_key, label, tipo, unidad, enum_options, ayuda)
    ("lens_mount",      "Lens mount",          "enum", None,
     ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
     "Montura del lente"),
    ("distancia_focal", "Distancia focal",     "rango", "mm", None,
     "Lista: [v] si es fijo, [min, max] si es zoom"),
    ("apertura",        "Apertura",            "rango", "f/", None,
     "Lista: [v] si es fija, [min, max] si es variable"),
    ("formato",         "Formato",             "enum", None, FORMATO_ENUM, None),
    ("diametro_filtro", "Diámetro de filtro",  "number", "mm", None,
     "Diámetro de la rosca del filtro frontal (ej. 67, 77, 82)"),
    ("linea",           "Línea",               "string", None, None,
     "Ej: Art, GM, L, Cinema, Master Prime"),
    ("angulo_vision",   "Ángulo de visión",    "rango", "°", None,
     "Lista: [v] fijo, [min, max] zoom"),
    ("distancia_minima_m", "Distancia mínima de foco", "number", "cm", None, None),
    ("magnificacion",   "Magnificación máxima", "string", None, None, "Ej: 0.32x"),
    ("hojas_diafragma", "Hojas de diafragma",  "number", None, None, None),
    ("estabilizacion",  "Estabilización óptica", "bool", None, None, None),
    ("autofocus",       "Autofocus",           "bool", None, None, None),
    ("construccion_optica", "Construcción óptica", "string", None, None,
     "Ej: 20 elementos / 15 grupos"),
    ("peso_g",          "Peso",                "number", "g", None, "Gramos del lente"),
    ("dimensiones",     "Dimensiones",         "string", None, None,
     "Ej: Ø87.8 × 119.9 mm"),
]


SPEC_FLAGS_LENTES = {
    # spec_key: (prioridad, en_card, en_filtros, en_nombre, destacado)
    "lens_mount":        (10, True,  True,  True,  True),
    "distancia_focal":   (15, True,  True,  True,  True),
    "apertura":          (20, True,  True,  True,  True),
    "formato":           (50, False, True,  False, True),
    "diametro_filtro":   (55, False, True,  False, False),
    "linea":             (60, False, True,  True,  False),
    "angulo_vision":     (65, False, False, False, False),
    "distancia_minima_m": (70, False, False, False, False),
    "magnificacion":     (75, False, False, False, False),
    "hojas_diafragma":   (78, False, False, False, False),
    "estabilizacion":    (80, False, True,  False, False),
    "autofocus":         (90, False, True,  False, False),
    "construccion_optica": (95, False, False, False, False),
    "peso_g":            (100, False, False, False, False),
    "dimensiones":       (105, False, False, False, False),
}


def categorize_lente(prod: dict) -> list[str]:
    """Categoriza por TIPO + MONTURA. Principio multi-cat: cada equipo va en
    TODAS las categorías que reflejan un eje real de búsqueda.

    Ejes:
      - Tipo:    Zoom / Fijo                              (siempre uno)
      - Atributo: + Vintage (si M42) / + Especiales (probe, macro, cinema)
      - Montura: Montura E / Montura EF / Montura M42 / ... (siempre una)

    Ejemplos:
      Sony FE 24-70 GM II    → ["Zoom", "Montura E"]
      Sigma 50 Art EF        → ["Fijo", "Montura EF"]
      Laowa 24 Probe EF      → ["Fijo", "Especiales", "Montura EF"]
      Zeiss Pancolar M42     → ["Fijo", "Vintage", "Montura M42"]
    """
    specs = prod.get("specs", {})
    mount = specs.get("lens_mount")
    linea = (specs.get("linea") or "").lower()
    focal = specs.get("distancia_focal")
    es_zoom = isinstance(focal, list) and len(focal) >= 2 and focal[0] != focal[-1]

    cats = ["Zoom"] if es_zoom else ["Fijo"]

    if mount == "M42":
        cats.append("Vintage")

    es_especial = (
        "probe" in linea or "macro" in linea
        or "cinema" in linea or "master prime" in linea
    )
    if es_especial:
        cats.append("Especiales")

    # Montura como sub-cat adicional (eje independiente de tipo/atributo)
    if mount:
        cats.append(f"Montura {mount}")

    return cats


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


def seed_lentes(conn, dry_run: bool = False) -> dict:
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
    for spec_key, label, tipo, unidad, enum_opts, ayuda in SPECS_LENTES:
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
            if row:
                spec_def_ids[spec_key] = row["id"]

    # 1b. Marcar specs de compatibilidad (lens_mount, formato, diametro_filtro)
    stats["compat_specs_marcadas"] = apply_compat_config(
        conn, spec_def_ids, dry_run=dry_run,
        expected_keys={"lens_mount", "formato", "diametro_filtro"},
    )

    # 2. Sub-categorías — auto-crea raíz si falta
    parent_id = ensure_categoria_raiz(conn, CATEGORIA_RAIZ, prioridad=20, dry_run=dry_run)
    if parent_id is None and not dry_run:
        return {"error": f"No se pudo asegurar la categoría raíz '{CATEGORIA_RAIZ}'."}

    subcat_ids: dict[str, int] = {}

    def _upsert_subcat(name: str, prio: int) -> int | None:
        row = conn.execute(
            "SELECT id, parent_id FROM categorias WHERE nombre = %s", (name,)
        ).fetchone()
        if row:
            if row["parent_id"] != parent_id and not dry_run:
                conn.execute("UPDATE categorias SET parent_id = %s WHERE id = %s",
                             (parent_id, row["id"]))
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
        """, (name, prio, parent_id))
        new = cur.fetchone()
        if new:
            stats["subcategorias_creadas"] += 1
            return new[0] if isinstance(new, tuple) else new["id"]
        return None

    for name, prio in SUBCATEGORIAS:
        sid = _upsert_subcat(name, prio)
        if sid is not None:
            subcat_ids[name] = sid

    # 3. categoria_spec_templates
    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE categoria_id = %s",
        (parent_id,)
    ).fetchone()
    if not existing or existing["n"] == 0:
        for spec_key, flags in SPEC_FLAGS_LENTES.items():
            spec_def_id = spec_def_ids.get(spec_key)
            if not spec_def_id:
                continue
            prio, en_card, en_filtros, en_nombre, destacado = flags
            if dry_run:
                # En dry-run contamos como "se crearía" incluso si spec_def_id=-1
                # (significa que la spec_def también se crearía recién).
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

    # 3b. Setear rol_compatibilidad (Lentes = contenedor para formato)
    stats["rol_compat_marcados"] = apply_rol_compat(
        conn, CATEGORIA_RAIZ, spec_def_ids, parent_id, dry_run=dry_run
    )

    # 4. Equipos + equipo_specs
    # Cargar mapeo manual (si existe) — preserva equipo.id para no romper
    # FKs de pedidos históricos. Generado por tools/equipos_match_preview.py.
    match_map = load_match_file(CATEGORIA_RAIZ)
    stats["matches_aplicados_desde_archivo"] = 0

    for prod_id, prod in products.items():
        marca = prod.get("marca", "")
        modelo = prod.get("modelo", "")
        nombre = f"{marca} {modelo}".strip()
        foto_url = prod.get("image_url", "")
        bh_url = prod.get("url_source", "")

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
            # 4a. Sub-categorías (incluyendo monturas on-the-fly)
            for cat_name in categorize_lente(prod):
                cat_id = subcat_ids.get(cat_name)
                if not cat_id and cat_name.startswith("Montura "):
                    # Crear sub-cat de montura on-the-fly al primer encuentro
                    cat_id = _upsert_subcat(cat_name, MONTURA_PRIORIDAD_BASE)
                    if cat_id:
                        subcat_ids[cat_name] = cat_id
                if cat_id and cat_id != -1:
                    conn.execute("""
                        INSERT INTO equipo_categorias (equipo_id, categoria_id)
                        VALUES (%s, %s)
                        ON CONFLICT (equipo_id, categoria_id) DO NOTHING
                    """, (equipo_id, cat_id))

            # 4b. Spec values
            for spec_key, value in prod.get("specs", {}).items():
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

            # 4c. Keywords derivadas (después de poblar specs)
            n_kw = write_keywords(conn, equipo_id, prod.get("specs", {}), dry_run=dry_run)
            stats["keywords_generadas"] = stats.get("keywords_generadas", 0) + n_kw

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from database import get_db  # type: ignore
    except ImportError as e:
        print(f"Error importando database: {e}")
        print("Correr desde root: python -m backend.seeds.lentes [--dry-run]")
        sys.exit(1)

    conn = get_db()
    try:
        stats = seed_lentes(conn, dry_run=dry_run)
        if not dry_run:
            conn.commit()
        print(f"\n{'═' * 50}")
        print("  Seed de lentes" + (" (DRY RUN)" if dry_run else ""))
        print('═' * 50)
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
    finally:
        conn.close()
