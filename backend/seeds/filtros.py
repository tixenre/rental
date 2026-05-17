"""
seeds/filtros.py — Importa el dataset de filtros.

Filtros se vinculan al FRENTE del lente (diametro_filtro). Specs: tipo,
diametro_filtro, densidad, material, grade, peso_g.

Sub-categorías: por diámetro ("82mm", "77mm", ...) creadas on-the-fly.

Idempotente. Uso:
  Manual: python -m backend.seeds.filtros [--dry-run]
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
DATASET_PATH = ROOT / "docs" / "filtros.json"

CATEGORIA_RAIZ = "Filtros"

SUBCATEGORIAS: list[tuple[str, int]] = []  # diámetros on-the-fly
DIAMETRO_PRIORIDAD_BASE = 10


SPECS_FILTROS = [
    ("tipo", "Tipo", "enum", None,
     ["Filtro ND", "Filtro polarizador", "Filtro UV", "Filtro variable", "Filtro difusión"],
     "Form factor"),
    ("diametro_filtro", "Diámetro de filtro", "number", "mm", None,
     "Rosca del filter thread (67, 77, 82, etc.). Compartido con Lentes — habilita match automático."),
    ("densidad", "Densidad ND", "string", None, None,
     "Ej: 1.2-Stop, 2-8 Stop (variable)"),
    ("material", "Material", "enum", None,
     ["Vidrio", "Resina", "Polímero"],
     "Vidrio óptico es estándar"),
    ("grade", "Grado", "string", None, None,
     "Solo difusión: 1/8, 1/4, 1/2, 1, 2"),
    ("peso_g", "Peso", "number", "g", None, None),
]


SPEC_FLAGS_FILTROS = {
    "tipo":         (10, True,  True,  True,  True),
    "diametro_filtro":  (20, True,  True,  True,  True),
    "densidad":     (30, False, True,  True,  False),
    "material":     (40, False, True,  False, False),
    "grade":        (50, False, True,  True,  False),
    "peso_g":       (60, False, False, False, False),
}


def categorize_filtro(prod: dict) -> list[str]:
    """Sub-cat: por diámetro (82mm, 77mm, etc.)."""
    d = prod.get("specs", {}).get("diametro_filtro")
    return [f"{d}mm"] if d else []


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


def seed_filtros(conn, dry_run: bool = False) -> dict:
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

    spec_def_ids: dict[str, int] = {}
    for spec_key, label, tipo, unidad, enum_opts, ayuda in SPECS_FILTROS:
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

    # 1b. Marcar specs de compatibilidad (diametro_filtro)
    stats["compat_specs_marcadas"] = apply_compat_config(
        conn, spec_def_ids, dry_run=dry_run,
        expected_keys={"diametro_filtro"},
    )

    parent_id = ensure_categoria_raiz(conn, CATEGORIA_RAIZ, prioridad=27, dry_run=dry_run)
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

    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE categoria_id = %s",
        (parent_id,)
    ).fetchone()
    if not existing or existing["n"] == 0:
        for spec_key, flags in SPEC_FLAGS_FILTROS.items():
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
            for cat_name in categorize_filtro(prod):
                cat_id = subcat_ids.get(cat_name)
                if not cat_id:
                    cat_id = _upsert_subcat(cat_name, DIAMETRO_PRIORIDAD_BASE)
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
        stats = seed_filtros(conn, dry_run=dry_run)
        if not dry_run:
            conn.commit()
        print(f"\n{'═' * 50}")
        print("  Seed de filtros" + (" (DRY RUN)" if dry_run else ""))
        print('═' * 50)
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
    finally:
        conn.close()
