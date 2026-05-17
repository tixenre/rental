#!/usr/bin/env python3
"""
tools/specs_reset.py — Borra la metadata de specs legacy antes de correr
los seeds canónicos.

Qué borra (en orden seguro):
  1. equipo_specs                — valores de spec por equipo (los seeds repueblan)
  2. categoria_spec_templates    — asignación spec↔categoría (los seeds repueblan)
  3. spec_definitions            — catálogo de specs (los seeds recrean)
  4. equipo_fichas.keywords_json — keywords legacy autogeneradas por LLM
                                   (los seeds las regeneran canónicas desde specs)

Qué NO toca (seguro):
  - equipos (preserva ids, FKs de pedidos intactas)
  - equipo_categorias (la categorización manual del admin queda)
  - categorias (las raíces; los seeds promueven si hace falta)
  - alquileres / pedidos / equipos_fichas / etc.

Uso:
    export DATABASE_URL='postgresql://...'
    python -m tools.specs_reset --dry-run    # ver qué se borraría
    python -m tools.specs_reset --apply      # ejecutar (transaccional)
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Asegurar que podemos importar desde backend/
sys.path.insert(0, str(ROOT / "backend"))


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true",
                     help="Solo muestra qué se borraría (sin tocar la DB)")
    grp.add_argument("--apply", action="store_true",
                     help="Ejecuta los DELETE (transaccional, rollback si falla)")
    args = ap.parse_args()

    try:
        from database import get_db  # type: ignore
    except ImportError as e:
        print(f"❌ No pude importar backend.database: {e}")
        sys.exit(1)

    conn = get_db()
    try:
        # ── Conteos previos ──────────────────────────────────────────────
        equipo_specs_n = conn.execute(
            "SELECT COUNT(*) AS n FROM equipo_specs"
        ).fetchone()["n"]
        templates_n = conn.execute(
            "SELECT COUNT(*) AS n FROM categoria_spec_templates"
        ).fetchone()["n"]
        spec_defs_n = conn.execute(
            "SELECT COUNT(*) AS n FROM spec_definitions"
        ).fetchone()["n"]
        keywords_n = conn.execute(
            "SELECT COUNT(*) AS n FROM equipo_fichas "
            "WHERE keywords_json IS NOT NULL AND keywords_json != ''"
        ).fetchone()["n"]

        # Top spec_keys que se van a borrar (informativo)
        top_specs = conn.execute("""
            SELECT sd.spec_key, COUNT(es.id) AS uso
            FROM spec_definitions sd
            LEFT JOIN equipo_specs es ON es.spec_def_id = sd.id
            GROUP BY sd.spec_key
            ORDER BY uso DESC
            LIMIT 20
        """).fetchall()

        # Equipos protegidos (no se tocan)
        equipos_n = conn.execute(
            "SELECT COUNT(*) AS n FROM equipos WHERE eliminado_at IS NULL"
        ).fetchone()["n"]
        cats_n = conn.execute(
            "SELECT COUNT(*) AS n FROM categorias"
        ).fetchone()["n"]
        equipo_cat_n = conn.execute(
            "SELECT COUNT(*) AS n FROM equipo_categorias"
        ).fetchone()["n"]

        print("═══ Specs Reset — estado actual ═══")
        print()
        print("Se BORRARÁ:")
        print(f"  equipo_specs                  {equipo_specs_n:>5} filas")
        print(f"  categoria_spec_templates      {templates_n:>5} filas")
        print(f"  spec_definitions              {spec_defs_n:>5} filas")
        print(f"  equipo_fichas.keywords_json   {keywords_n:>5} equipos con keywords (se limpia el campo)")
        print()
        print("Top spec_keys por uso (los más utilizados):")
        for r in top_specs:
            print(f"  {r['spec_key']:<35} {r['uso']:>4} valores")
        print()
        print("NO se toca (preservado):")
        print(f"  equipos                   {equipos_n:>5} equipos (FKs de pedidos intactas)")
        print(f"  categorias                {cats_n:>5} categorías")
        print(f"  equipo_categorias         {equipo_cat_n:>5} asignaciones")
        print()

        if args.dry_run:
            print("→ DRY RUN. No se borró nada. Para aplicar:")
            print("  python -m tools.specs_reset --apply")
            return

        # ── Aplicar DELETEs (transaccional) ──────────────────────────────
        print("→ APPLY: borrando en transacción...")
        try:
            # Orden: equipo_specs primero (FKs hacia spec_definitions),
            # después categoria_spec_templates (FK hacia spec_definitions),
            # finalmente spec_definitions.
            conn.execute("DELETE FROM equipo_specs")
            conn.execute("DELETE FROM categoria_spec_templates")
            conn.execute("DELETE FROM spec_definitions")
            # Limpiar keywords legacy (autogeneradas por LLM, los seeds las
            # regeneran canónicas desde specs)
            conn.execute(
                "UPDATE equipo_fichas SET keywords_json = NULL "
                "WHERE keywords_json IS NOT NULL"
            )
            conn.commit()
            print("✓ Borrado completo (commit)")
        except Exception as e:
            conn.rollback()
            print(f"✗ Error — rollback: {e}")
            sys.exit(1)

        # Verificación post-delete
        after_es = conn.execute("SELECT COUNT(*) AS n FROM equipo_specs").fetchone()["n"]
        after_t  = conn.execute("SELECT COUNT(*) AS n FROM categoria_spec_templates").fetchone()["n"]
        after_sd = conn.execute("SELECT COUNT(*) AS n FROM spec_definitions").fetchone()["n"]
        after_kw = conn.execute(
            "SELECT COUNT(*) AS n FROM equipo_fichas "
            "WHERE keywords_json IS NOT NULL AND keywords_json != ''"
        ).fetchone()["n"]
        print()
        print("Estado post-reset:")
        print(f"  equipo_specs                  {after_es}")
        print(f"  categoria_spec_templates      {after_t}")
        print(f"  spec_definitions              {after_sd}")
        print(f"  equipo_fichas.keywords_json   {after_kw} (con valor)")
        print()
        print("Próximo paso: correr los seeds para repoblar:")
        print("  python -m backend.seeds.camaras")
        print("  python -m backend.seeds.lentes")
        print("  python -m backend.seeds.adaptadores")
        print("  python -m backend.seeds.filtros")
        print("  python -m backend.seeds.iluminacion")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
