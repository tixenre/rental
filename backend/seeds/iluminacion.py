"""seeds/iluminacion.py — Importa el dataset curado de iluminación a la DB.

Patrón unificado:
  1. Specs + sub-categorías → `seed_categoria_from_registry("Iluminación")`
  2. Equipos + valores → este archivo (lee docs/iluminacion.json)

Idempotente:
  - Equipos: match por (marca, modelo) vía docs/equipos_match.json o fallback
  - equipo_specs: ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
"""

import json
import sys
from pathlib import Path

try:
    from .registry_seeder import seed_categoria_from_registry, serialize_spec_value
    from .compat_config import load_match_file, resolve_equipo_id, apply_overrides, write_keywords
    from specs import get_categoria
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from seeds.registry_seeder import seed_categoria_from_registry, serialize_spec_value  # type: ignore
    from seeds.compat_config import load_match_file, resolve_equipo_id, apply_overrides, write_keywords  # type: ignore
    from specs import get_categoria  # type: ignore

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "docs" / "iluminacion.json"
CATEGORIA_RAIZ = "Iluminación"


def categorize(producto: dict) -> str:
    """Sub-cat por color_modes + tipo (canónico: iluminacion_subtipo)."""
    s = producto.get("specs", {})
    tipo = s.get("iluminacion_subtipo") or ""
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
    return "LED Daylight"


def seed_iluminacion(conn, dry_run: bool = False) -> dict:
    """Importa el dataset curado de iluminación."""
    if not DATASET_PATH.exists():
        return {"error": f"Dataset no encontrado: {DATASET_PATH}"}

    with open(DATASET_PATH) as f:
        data = json.load(f)
    products = data.get("products", {})

    # ── 1. Specs + sub-categorías desde registry ────────────────────────
    seeded = seed_categoria_from_registry(conn, CATEGORIA_RAIZ, dry_run=dry_run)
    spec_def_ids = seeded["spec_def_ids"]
    subcat_ids = seeded["subcat_ids"]
    stats = dict(seeded["stats"])
    stats.update({
        "equipos_creados": 0,
        "equipos_actualizados": 0,
        "equipo_specs_insertados": 0,
    })

    cat_reg = get_categoria(CATEGORIA_RAIZ)
    specs_by_key = {s.key: s for s in cat_reg.specs}

    # ── 2. Equipos + equipo_specs ────────────────────────────────────────
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
                conn.execute("""
                    INSERT INTO marcas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING
                """, (marca or '',))
                cur = conn.execute("""
                    INSERT INTO equipos (nombre, brand_id, modelo, foto_url, bh_url, cantidad, dueno)
                    VALUES (%s, (SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(%s)), %s, %s, %s, 1, 'Rambla')
                    RETURNING id
                """, (nombre, marca, modelo, foto_url, bh_url))
                row = cur.fetchone()
                equipo_id = row[0] if isinstance(row, tuple) else row["id"]
                stats["equipos_creados"] += 1

        # Asignar a sub-categoría
        if equipo_id != -1 and subcat_id and not dry_run:
            conn.execute("""
                INSERT INTO equipo_categorias (equipo_id, categoria_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (equipo_id, subcat_id))

        # equipo_specs
        if equipo_id != -1 and not dry_run:
            specs = prod.get("specs", {})
            for spec_key, value in specs.items():
                spec = specs_by_key.get(spec_key)
                if not spec:
                    continue
                spec_def_id = spec_def_ids.get(spec_key)
                if not spec_def_id or spec_def_id < 0:
                    continue
                value_str = serialize_spec_value(spec, value)
                if value_str is None:
                    continue
                conn.execute("""
                    INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
                        SET value = EXCLUDED.value
                """, (equipo_id, spec_def_id, value_str))
                stats["equipo_specs_insertados"] += 1

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

    with get_db() as conn:
        stats = seed_iluminacion(conn, dry_run=dry_run)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
