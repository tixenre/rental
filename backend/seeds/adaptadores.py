"""
seeds/adaptadores.py — Importa el dataset de adaptadores de montura.

Adaptadores se vinculan a la CÁMARA (lens_mount body). Specs: tipo,
lens_mount, lens_mount_out, electronica, incluye_iris, magnificacion, peso_g.

Multi-cat: el Canon Drop-In EF→RF también está en "Filtros" (incluye ND
variable interno). Cada equipo vive en su raíz natural + en las sub-cats
que apliquen.

Idempotente. Uso:
  Manual: python -m backend.seeds.adaptadores [--dry-run]
"""

import json
import sys
from pathlib import Path

try:
    from .compat_config import (
        apply_compat_config, apply_overrides, ensure_categoria_raiz,
        load_match_file, resolve_equipo_id,
        write_keywords,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from compat_config import (  # type: ignore
        apply_compat_config, apply_overrides, ensure_categoria_raiz,
        load_match_file, resolve_equipo_id,
        write_keywords,
    )

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "docs" / "adaptadores.json"

CATEGORIA_RAIZ = "Adaptadores"

# Sub-categorías base + monturas on-the-fly (similar a lentes.py)
SUBCATEGORIAS: list[tuple[str, int]] = []  # las monturas se crean dinámicas
MONTURA_PRIORIDAD_BASE = 10


SPECS_ADAPTADORES = [
    # (spec_key, label, tipo, unidad, enum_options, ayuda)
    ("tipo", "Tipo", "enum", None,
     ["Adaptador montura", "Speedbooster", "Macro tube"],
     "Form factor"),
    ("lens_mount", "Lens mount", "enum", None,
     ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
     "Lado body (la rosca que se enchufa a la cámara)"),
    ("lens_mount_out", "Lens mount — lado lente", "enum", None,
     ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
     "Rosca que recibe el lente del otro sistema"),
    ("electronica", "Comunicación electrónica", "bool", None, None,
     "Transmite AF/aperture del lente al body"),
    ("incluye_iris", "Iris incluido", "bool", None, None,
     "Drop-in adapters con filtro ND variable incorporado"),
    ("magnificacion", "Magnificación", "string", None, None,
     "Solo speedboosters (ej. 0.71x)"),
    ("peso_g", "Peso", "number", "g", None, None),
]


SPEC_FLAGS_ADAPTADORES = {
    "tipo":           (10, True,  True,  True,  True),
    "lens_mount":     (20, True,  True,  True,  True),
    "lens_mount_out": (30, True,  True,  True,  True),
    "electronica":    (40, False, True,  False, False),
    "incluye_iris":   (50, False, False, False, False),
    "magnificacion":  (60, False, False, False, False),
    "peso_g":         (70, False, False, False, False),
}


def categorize_adaptador(prod: dict) -> list[str]:
    """Sub-cat: la montura del lado body. Eje único.

    Nota: el multi-cat con la raíz "Filtros" (caso Canon Drop-In con ND
    interno) NO se hace acá — son raíces distintas. Si querés que aparezca
    también en Filtros, hay que correr seed_filtros con un dataset que lo
    incluya, o cross-postear vía script aparte.
    """
    mount = prod.get("specs", {}).get("lens_mount")
    return [f"Montura {mount}"] if mount else []


def serialize_spec_value(spec_key: str, value) -> str | None:
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


def seed_adaptadores(conn, dry_run: bool = False) -> dict:
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
    for spec_key, label, tipo, unidad, enum_opts, ayuda in SPECS_ADAPTADORES:
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

    # 1b. Marcar specs de compatibilidad (lens_mount)
    stats["compat_specs_marcadas"] = apply_compat_config(
        conn, spec_def_ids, dry_run=dry_run,
        expected_keys={"lens_mount"},
    )

    # 2. Sub-categorías — auto-crea raíz si falta (o la promueve si quedó
    # como sub-cat legacy de "Adaptadores y Filtros")
    parent_id = ensure_categoria_raiz(conn, CATEGORIA_RAIZ, prioridad=25, dry_run=dry_run)
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

    # 3. categoria_spec_templates
    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE categoria_id = %s",
        (parent_id,)
    ).fetchone()
    if not existing or existing["n"] == 0:
        for spec_key, flags in SPEC_FLAGS_ADAPTADORES.items():
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
                ON CONFLICT (categoria_id, spec_def_id) DO NOTHING RETURNING id
            """, (parent_id, spec_def_id, prio, destacado, en_card, en_filtros, en_nombre))
            if cur.fetchone():
                stats["asignaciones_creadas"] += 1

    # 4. Equipos + equipo_specs
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
            # Aplicar overrides (ej. corregir marca mal-etiquetada en DB)
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
            for cat_name in categorize_adaptador(prod):
                cat_id = subcat_ids.get(cat_name)
                if not cat_id and cat_name.startswith("Montura "):
                    cat_id = _upsert_subcat(cat_name, MONTURA_PRIORIDAD_BASE)
                    if cat_id:
                        subcat_ids[cat_name] = cat_id
                if cat_id and cat_id != -1:
                    conn.execute("""
                        INSERT INTO equipo_categorias (equipo_id, categoria_id)
                        VALUES (%s, %s)
                        ON CONFLICT (equipo_id, categoria_id) DO NOTHING
                    """, (equipo_id, cat_id))

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

            # Keywords derivadas (después de poblar specs)
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
        sys.exit(1)

    conn = get_db()
    try:
        stats = seed_adaptadores(conn, dry_run=dry_run)
        if not dry_run:
            conn.commit()
        print(f"\n{'═' * 50}")
        print("  Seed de adaptadores" + (" (DRY RUN)" if dry_run else ""))
        print('═' * 50)
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
    finally:
        conn.close()
