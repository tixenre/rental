"""Backfill de variantes AVIF para fotos de equipo existentes (one-off, idempotente).

Para cada foto de equipo con media_id que NO tenga las variantes AVIF (display-avif,
display-sm-avif, display-thumb-avif), llama a rederive_variants() — que lee el original
privado de R2 y re-genera las variantes indicadas sin tocar las existentes.

Correr DESPUÉS de backfill_ingest_legacy.py (que puebla media_id).

Idempotente: rederive_variants hace UPDATE-or-INSERT; si la variante ya existe la
reemplaza (más fresco/mejor codec). Commit por asset.

Uso:
  cd backend && source .venv/bin/activate
  python scripts/backfill_display_avif.py --dry-run
  python scripts/backfill_display_avif.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db                                     # noqa: E402
from services.media.gc import rederive_variants                 # noqa: E402
from services.media.errors import MediaError                    # noqa: E402
from services.media.specs import (                              # noqa: E402
    DISPLAY_SQUARE_AVIF,
    DISPLAY_SQUARE_SM_AVIF,
    DISPLAY_SQUARE_THUMB_AVIF,
)
from routes.equipos.fotos import _sync_principal_denorm         # noqa: E402

AVIF_SPECS = [DISPLAY_SQUARE_AVIF, DISPLAY_SQUARE_SM_AVIF, DISPLAY_SQUARE_THUMB_AVIF]
AVIF_NAMES = {s.name for s in AVIF_SPECS}


def backfill(dry_run: bool = False) -> dict:
    stats = {
        "candidatos": 0,
        "derivados": 0,
        "sin_original": 0,
        "errores": 0,
    }
    conn = get_db()
    try:
        # Assets de equipo con media_id que les falta al menos una variante AVIF
        rows = conn.execute(
            """
            SELECT DISTINCT ef.media_id AS asset_id, ef.equipo_id, ef.es_principal
            FROM equipo_fotos ef
            WHERE ef.media_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM media_variants mv
                  WHERE mv.asset_id = ef.media_id
                    AND mv.name IN ('display-avif','display-sm-avif','display-thumb-avif')
              )
            ORDER BY ef.equipo_id
            """
        ).fetchall()

        stats["candidatos"] = len(rows)
        print(f"Assets sin variantes AVIF: {len(rows)}")

        for row in rows:
            asset_id = row["asset_id"]
            equipo_id = row["equipo_id"]
            is_principal = bool(row["es_principal"])
            label = f"asset {asset_id} (equipo {equipo_id})"

            if dry_run:
                print(f"  {label}: derivaría {[s.name for s in AVIF_SPECS]}")
                continue

            try:
                new_variants = rederive_variants(
                    asset_id,
                    derive_specs=AVIF_SPECS,
                    conn=conn,
                )
                if is_principal:
                    _sync_principal_denorm(conn, equipo_id)
                conn.commit()
                stats["derivados"] += 1
                names = [v.name for v in new_variants]
                print(f"  {label}: OK → {names}")

            except MediaError as e:
                conn.rollback()
                if e.status == 404:
                    stats["sin_original"] += 1
                    print(f"  {label}: sin original en R2 (saltado)")
                else:
                    stats["errores"] += 1
                    print(f"  {label}: MediaError {e.status}: {e.detail}")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                stats["errores"] += 1
                print(f"  {label}: ERROR {type(e).__name__}: {e}")

    finally:
        conn.close()

    return stats


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"=== Backfill variantes AVIF {'(DRY RUN)' if dry else '(APLICANDO)'} ===")
    s = backfill(dry_run=dry)
    print(f"=== Resumen: {s} ===")
    sys.exit(0 if s["errores"] == 0 else 1)
