"""dataio/cli.py — Entrypoint del CLI.

Uso:
    python -m backend.dataio.cli export                    # → data/catalog/
    python -m backend.dataio.cli export --only equipos     # solo una entidad
    python -m backend.dataio.cli export --out /tmp/cat/    # ubicación custom
    python -m backend.dataio.cli import                    # ← data/catalog/
    python -m backend.dataio.cli import --dry-run          # no commitea
    python -m backend.dataio.cli import --prune-m2m        # peligroso
    python -m backend.dataio.cli diff                      # DB vs JSON
    python -m backend.dataio.cli validate                  # solo schema
    python -m backend.dataio.cli init-slugs                # one-shot, ver doc
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import orchestrator
from .paths import DATA_DIR, ENTITY_ORDER

logger = logging.getLogger(__name__)


def _get_conn():
    """Carga lazy de database.get_db (no se importa al colectar args)."""
    # Path setup — el CLI puede correrse desde la raíz del repo
    backend_root = Path(__file__).resolve().parent.parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from database import get_db  # type: ignore
    return get_db()


def cmd_export(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) if args.out else DATA_DIR
    only = args.only.split(",") if args.only else None
    conn = _get_conn()
    try:
        counts = orchestrator.export_all(conn, out_dir, only=only)
    finally:
        conn.close()
    print("\n═ Export terminado ═")
    print(f"  Destino: {out_dir}")
    for entity, n in counts.items():
        print(f"  {entity:<30} {n} filas")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    in_dir = Path(args.in_dir) if args.in_dir else DATA_DIR
    only = args.only.split(",") if args.only else None
    conn = _get_conn()
    try:
        stats = orchestrator.import_all(
            conn,
            in_dir,
            dry_run=args.dry_run,
            prune_m2m=args.prune_m2m,
            only=only,
        )
        if not args.dry_run:
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Import falló: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"\n═ Import terminado {'(DRY-RUN)' if args.dry_run else ''} ═")
    print(f"  Origen: {in_dir}")
    total_ins = total_upd = 0
    for entity, s in stats.items():
        ins = s.get("inserted", 0)
        upd = s.get("updated", 0)
        total_ins += ins
        total_upd += upd
        print(f"  {entity:<30} +{ins} ins, ~{upd} upd")
    print(f"  ─────────────────────────────")
    print(f"  TOTAL                         +{total_ins} ins, ~{total_upd} upd")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    baseline_dir = Path(args.baseline) if args.baseline else DATA_DIR
    conn = _get_conn()
    try:
        diffs = orchestrator.diff_all(conn, baseline_dir)
    finally:
        conn.close()
    print(f"\n═ Diff DB vs {baseline_dir} ═")
    has_changes = False
    for entity, d in diffs.items():
        only_db = d["only_in_db"]
        only_json = d["only_in_json"]
        modified = d["modified"]
        if not (only_db or only_json or modified):
            continue
        has_changes = True
        print(f"\n  {entity}:")
        if only_db:
            print(f"    Solo en DB ({len(only_db)}):")
            for k in only_db[:20]:
                print(f"      + {k}")
            if len(only_db) > 20:
                print(f"      ... y {len(only_db) - 20} más")
        if only_json:
            print(f"    Solo en JSON ({len(only_json)}):")
            for k in only_json[:20]:
                print(f"      - {k}")
            if len(only_json) > 20:
                print(f"      ... y {len(only_json) - 20} más")
        if modified:
            print(f"    Modificadas ({len(modified)}):")
            for k in modified[:20]:
                print(f"      ~ {k}")
            if len(modified) > 20:
                print(f"      ... y {len(modified) - 20} más")
    if not has_changes:
        print("  Sin cambios. DB == JSON.")
    if args.json:
        print("\n" + json.dumps(diffs, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    in_dir = Path(args.in_dir) if args.in_dir else DATA_DIR
    try:
        counts = orchestrator.validate_dir(in_dir)
    except Exception as e:
        print(f"\n✗ Validación falló: {e}", file=sys.stderr)
        return 1
    print(f"\n═ Validación OK ═ ({in_dir})")
    for entity, n in counts.items():
        print(f"  {entity:<30} {n} filas válidas")
    return 0


def cmd_init_slugs(args: argparse.Namespace) -> int:
    """One-shot: puebla `equipos.slug` para filas existentes.

    Respeta `docs/equipos_match.json` para preservar IDs históricos
    (no toca IDs, solo escribe el slug). Si hay colisión, agrega sufijo
    -2, -3, etc. con el id como último recurso.
    """
    from .slug import equipo_slug

    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, nombre, marca, modelo FROM equipos WHERE slug IS NULL"
        ).fetchall()
        if not rows:
            print("  Todos los equipos ya tienen slug. Nada que hacer.")
            return 0

        used_slugs = {
            r["slug"]
            for r in conn.execute(
                "SELECT slug FROM equipos WHERE slug IS NOT NULL"
            ).fetchall()
        }

        n_updated = 0
        n_disambiguated = 0
        for r in rows:
            base = equipo_slug(r["marca"], r["modelo"], r["nombre"])
            if not base:
                base = f"equipo-{r['id']}"

            slug = base
            i = 2
            disamb = False
            while slug in used_slugs:
                slug = f"{base}-{i}"
                i += 1
                disamb = True
                if i > 100:
                    slug = f"{base}-id{r['id']}"
                    break

            if args.dry_run:
                print(f"  [dry-run] equipo {r['id']} → slug='{slug}'")
            else:
                conn.execute(
                    "UPDATE equipos SET slug = ? WHERE id = ?", (slug, r["id"])
                )
            used_slugs.add(slug)
            n_updated += 1
            if disamb:
                n_disambiguated += 1

        if not args.dry_run:
            conn.commit()
        print(f"\n═ init-slugs terminado {'(DRY-RUN)' if args.dry_run else ''} ═")
        print(f"  Equipos actualizados: {n_updated}")
        print(f"  Con desambiguación:   {n_disambiguated}")
    except Exception as e:
        conn.rollback()
        print(f"\n✗ init-slugs falló: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.dataio.cli",
        description="Export/import del catálogo (marcas, categorías, equipos, specs).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="DB → JSONs en data/catalog/")
    pe.add_argument("--out", help="Directorio de salida (default: data/catalog/)")
    pe.add_argument(
        "--only", help=f"Comma-separated subset de entidades: {','.join(ENTITY_ORDER)}"
    )
    pe.set_defaults(func=cmd_export)

    pi = sub.add_parser("import", help="JSONs en data/catalog/ → DB (upsert)")
    pi.add_argument("--in", dest="in_dir", help="Directorio fuente (default: data/catalog/)")
    pi.add_argument("--dry-run", action="store_true", help="No commitea")
    pi.add_argument(
        "--prune-m2m",
        action="store_true",
        help="Borra M2M (equipo_categorias/etiquetas) antes de insertar las del JSON",
    )
    pi.add_argument("--only", help="Comma-separated subset de entidades")
    pi.set_defaults(func=cmd_import)

    pd = sub.add_parser("diff", help="Reporta diferencias DB vs JSON")
    pd.add_argument("--baseline", help="Directorio baseline (default: data/catalog/)")
    pd.add_argument("--json", action="store_true", help="Output completo en JSON")
    pd.set_defaults(func=cmd_diff)

    pv = sub.add_parser("validate", help="Solo valida JSONs vs schema (no DB)")
    pv.add_argument("--in", dest="in_dir", help="Directorio (default: data/catalog/)")
    pv.set_defaults(func=cmd_validate)

    ps = sub.add_parser(
        "init-slugs",
        help="One-shot: puebla equipos.slug para filas existentes (post-migración)",
    )
    ps.add_argument("--dry-run", action="store_true")
    ps.set_defaults(func=cmd_init_slugs)

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
