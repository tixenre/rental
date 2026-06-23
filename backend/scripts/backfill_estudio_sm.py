"""Backfill de la variante display-sm (800px) para fotos del estudio existentes (one-off).

Las fotos subidas antes de esta variante solo tienen `display.webp` (1600px) en R2.
Para srcset (hero en mobile), este script genera el `display-sm.webp` (800px) de
cada asset de estudio y rellena `estudio_fotos.url_sm`.

Para cada foto del estudio SIN variante 'display-sm':
  - Fuente: `original_key` si está, si no el `display.webp` ya guardado.
  - Genera `display-sm.webp` (800px, keep-aspect) → PUT R2 + INSERT media_variants.
  - UPDATE estudio_fotos.url_sm con la URL generada.

Idempotente: salta los assets que ya tienen 'display-sm'. Best-effort por foto: si
una falla, loguea y sigue. NO se corre en el deploy — lo ejecuta el dueño (empezar
con --dry-run).

Uso:
  cd backend && source .venv/bin/activate && python scripts/backfill_estudio_sm.py --dry-run
  cd backend && source .venv/bin/activate && python scripts/backfill_estudio_sm.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db  # noqa: E402
from services.media import repository, storage  # noqa: E402
from services.media.processing import _optimize_image  # noqa: E402


def backfill(dry_run: bool = False) -> dict:
    conn = get_db()
    stats = {"candidatos": 0, "creados": 0, "saltados_sin_fuente": 0, "errores": 0}
    try:
        # Fotos del estudio que tienen media_id pero aún no tienen url_sm ni variante 'display-sm'.
        rows = conn.execute(
            """
            SELECT ef.id AS foto_id, ef.media_id AS asset_id
            FROM estudio_fotos ef
            WHERE ef.media_id IS NOT NULL
              AND (ef.url_sm IS NULL OR ef.url_sm = '')
              AND NOT EXISTS (
                  SELECT 1 FROM media_variants mv
                  WHERE mv.asset_id = ef.media_id AND mv.name = 'display-sm'
              )
            ORDER BY ef.id
            """
        ).fetchall()
        stats["candidatos"] = len(rows)
        print(f"Fotos del estudio sin variante 'display-sm': {len(rows)}")

        for row in rows:
            foto_id = row["foto_id"]
            asset_id = row["asset_id"]
            try:
                asset = repository.load_asset(conn, asset_id)
                if asset is None:
                    stats["saltados_sin_fuente"] += 1
                    print(f"  foto {foto_id} / asset {asset_id}: asset no encontrado → salto")
                    continue

                src_key = asset.original_key
                if not src_key:
                    display = asset.variant("display")
                    src_key = display.key if display else None
                if not src_key:
                    stats["saltados_sin_fuente"] += 1
                    print(f"  foto {foto_id} / asset {asset_id}: sin original ni display → salto")
                    continue

                if dry_run:
                    print(f"  foto {foto_id} / asset {asset_id}: derivaría display-sm desde {src_key}")
                    continue

                raw = storage.get(src_key)
                # keep-aspect (square=False), 800px lado largo → hero mobile
                content, ct, w, h = _optimize_image(raw, square=False, fmt="webp", max_width=800)
                sm_key = f"media/{asset.kind}/{asset.id}/display-sm.webp"
                url = storage.put(sm_key, content, ct)
                repository.insert_variant(
                    conn, asset.id, "display-sm", sm_key, url, ct, w, h, len(content)
                )
                conn.execute(
                    "UPDATE estudio_fotos SET url_sm = %s WHERE id = %s",
                    (url, foto_id),
                )
                conn.commit()
                stats["creados"] += 1
                print(f"  foto {foto_id} / asset {asset_id}: display-sm creado ({len(content) // 1024} KB) → {url}")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                stats["errores"] += 1
                print(f"  foto {foto_id} / asset {asset_id}: ERROR {e}")
    finally:
        conn.close()
    return stats


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"=== Backfill display-sm fotos estudio {'(DRY RUN)' if dry else '(APLICANDO)'} ===")
    s = backfill(dry_run=dry)
    print(f"=== Resumen: {s} ===")
