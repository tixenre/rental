"""seeds/lentes.py — Importa el dataset curado de lentes.

Patrón unificado:
  1. Specs + sub-categorías base (Zoom/Fijo/Vintage/Especiales) → registry_seeder
  2. Sub-categorías de montura (Montura E/EF/M42/...) → on-the-fly según stock
  3. Equipos + valores → este archivo

Multi-cat M2M:
  Sony FE 24-70 GM II    → [Zoom, Montura E]
  Sigma 50 Art EF        → [Fijo, Montura EF]
  Zeiss Pancolar M42     → [Fijo, Vintage, Montura M42]
"""

import json
import sys
from pathlib import Path

try:
    from .registry_seeder import seed_categoria_from_registry, serialize_spec_value
    from .compat_config import (
        apply_overrides, load_match_file, resolve_equipo_id, write_keywords,
    )
    from specs import get_categoria
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from seeds.registry_seeder import seed_categoria_from_registry, serialize_spec_value  # type: ignore
    from seeds.compat_config import (  # type: ignore
        apply_overrides, load_match_file, resolve_equipo_id, write_keywords,
    )
    from specs import get_categoria  # type: ignore

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "docs" / "lentes.json"
CATEGORIA_RAIZ = "Lentes"


def categorize_lente(prod: dict) -> list[str]:
    """Sub-categorías M2M: tipo + atributo + montura.

    Ejes (todos independientes):
      Tipo:    Zoom | Fijo                            (siempre uno)
      Atributo: + Vintage (M42) / + Especiales       (opcional)
      Montura: Montura E/EF/M42/...                  (siempre una)
    """
    specs = prod.get("specs", {})
    mount = specs.get("lens_mount")
    linea = (specs.get("linea") or "").lower()
    focal = specs.get("distancia_focal")
    es_zoom = isinstance(focal, list) and len(focal) >= 2 and focal[0] != focal[-1]

    cats = ["Zoom"] if es_zoom else ["Fijo"]

    if mount == "M42":
        cats.append("Vintage")

    if any(t in linea for t in ("probe", "macro", "cinema", "master prime")):
        cats.append("Especiales")

    if mount:
        cats.append(f"Montura {mount}")

    return cats


def _ensure_montura_subcat(conn, mount_name: str, raiz_id: int,
                            subcat_ids: dict, dry_run: bool) -> int | None:
    if mount_name in subcat_ids:
        return subcat_ids[mount_name]
    row = conn.execute(
        "SELECT id FROM categorias WHERE nombre = %s", (mount_name,)
    ).fetchone()
    if row:
        subcat_ids[mount_name] = row["id"]
        if not dry_run:
            conn.execute(
                "UPDATE categorias SET parent_id = %s WHERE id = %s AND parent_id IS DISTINCT FROM %s",
                (raiz_id, row["id"], raiz_id),
            )
        return row["id"]
    if dry_run:
        return -1
    cur = conn.execute(
        """
        INSERT INTO categorias (nombre, prioridad, parent_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (nombre) DO UPDATE SET parent_id = EXCLUDED.parent_id
        RETURNING id
        """,
        (mount_name, 50, raiz_id),
    )
    new = cur.fetchone()
    sid = new[0] if isinstance(new, tuple) else new["id"]
    subcat_ids[mount_name] = sid
    return sid


def seed_lentes(conn, dry_run: bool = False) -> dict:
    if not DATASET_PATH.exists():
        return {"error": f"Dataset no encontrado: {DATASET_PATH}"}

    with open(DATASET_PATH) as f:
        data = json.load(f)
    products = data.get("products", {})

    seeded = seed_categoria_from_registry(conn, CATEGORIA_RAIZ, dry_run=dry_run)
    spec_def_ids = seeded["spec_def_ids"]
    subcat_ids = dict(seeded["subcat_ids"])
    raiz_id = seeded["raiz_id"]
    stats = dict(seeded["stats"])
    stats.update({
        "equipos_creados": 0,
        "equipos_actualizados": 0,
        "equipo_specs_insertados": 0,
    })

    cat_reg = get_categoria(CATEGORIA_RAIZ)
    specs_by_key = {s.key: s for s in cat_reg.specs}

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
                    INSERT INTO marcas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING
                """, (marca or '',))
                cur = conn.execute("""
                    INSERT INTO equipos (nombre, brand_id, modelo, foto_url, bh_url, cantidad, dueno)
                    VALUES (%s, (SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(%s)), %s, %s, %s, 1, 'Rambla') RETURNING id
                """, (nombre, marca, modelo, foto_url, bh_url))
                row = cur.fetchone()
                equipo_id = row[0] if isinstance(row, tuple) else row["id"]
                stats["equipos_creados"] += 1

        if equipo_id != -1 and not dry_run:
            for cat_name in categorize_lente(prod):
                cat_id = subcat_ids.get(cat_name)
                if not cat_id and cat_name.startswith("Montura ") and raiz_id:
                    cat_id = _ensure_montura_subcat(conn, cat_name, raiz_id, subcat_ids, dry_run)
                if cat_id and cat_id != -1:
                    conn.execute("""
                        INSERT INTO equipo_categorias (equipo_id, categoria_id)
                        VALUES (%s, %s) ON CONFLICT (equipo_id, categoria_id) DO NOTHING
                    """, (equipo_id, cat_id))

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
                    ON CONFLICT (equipo_id, spec_def_id) DO UPDATE SET value = EXCLUDED.value
                """, (equipo_id, spec_def_id, value_str))
                stats["equipo_specs_insertados"] += 1

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
        print(f"\n{'═' * 50}\n  Seed de lentes" + (" (DRY RUN)" if dry_run else "") + f"\n{'═' * 50}")
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
    finally:
        conn.close()
