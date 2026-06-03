"""Backfill de la variante OG (jpg) para fotos de equipo existentes (one-off).

Las fotos subidas antes de la variante `og` solo tienen `display.webp` en R2.
WhatsApp no renderiza webp en las previews, así que este script genera el
`og.jpg` que faltaba para cada asset de equipo enlazado a `equipo_fotos`.

Para cada asset SIN variante `og`:
  - Si tiene `original_key` (subidas no-destructivas) → deriva el og del original
    (máxima calidad).
  - Si no (fotos legacy sin original) → lo deriva del `display.webp` ya guardado
    (conversión de formato; la imagen ya está cuadrada/optimizada).
  - Sube `media/equipo/{asset_id}/og.jpg` a R2 + inserta la fila en media_variants.

Idempotente: salta los assets que ya tienen `og`. Best-effort por foto: si una
falla, loguea y sigue. Commit por asset (progreso parcial sobrevive).

Uso:
  cd backend && source .venv/bin/activate && python scripts/backfill_og_fotos.py --dry-run
  # Contra prod (DATABASE_URL + R2_* apuntando a prod):
  cd backend && source .venv/bin/activate && \\
    DATABASE_URL='postgres://...' python scripts/backfill_og_fotos.py
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
        # Assets de equipo enlazados a equipo_fotos que aún no tienen variante 'og'.
        rows = conn.execute(
            """
            SELECT DISTINCT ef.media_id AS asset_id
            FROM equipo_fotos ef
            WHERE ef.media_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM media_variants mv
                  WHERE mv.asset_id = ef.media_id AND mv.name = 'og'
              )
            """
        ).fetchall()
        asset_ids = [r["asset_id"] for r in rows]
        stats["candidatos"] = len(asset_ids)
        print(f"Assets de equipo sin variante 'og': {len(asset_ids)}")

        for asset_id in asset_ids:
            try:
                asset = repository.load_asset(conn, asset_id)
                if asset is None:
                    continue
                # Fuente: original si está, si no el display.webp.
                src_key = asset.original_key
                if not src_key:
                    display = asset.variant("display")
                    src_key = display.key if display else None
                if not src_key:
                    stats["saltados_sin_fuente"] += 1
                    print(f"  asset {asset_id}: sin original ni display → salto")
                    continue

                if dry_run:
                    print(f"  asset {asset_id}: derivaría og.jpg desde {src_key}")
                    continue

                raw = storage.get(src_key)
                content, ct, w, h = _optimize_image(raw, square=True, fmt="jpeg")
                og_key = f"media/{asset.kind}/{asset.id}/og.jpg"
                url = storage.put(og_key, content, ct)
                repository.insert_variant(
                    conn, asset.id, "og", og_key, url, ct, w, h, len(content)
                )
                conn.commit()
                stats["creados"] += 1
                print(f"  asset {asset_id}: og.jpg creado ({len(content) // 1024} KB) → {url}")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                stats["errores"] += 1
                print(f"  asset {asset_id}: ERROR {e}")
    finally:
        conn.close()
    return stats


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"=== Backfill OG fotos {'(DRY RUN)' if dry else '(APLICANDO)'} ===")
    s = backfill(dry_run=dry)
    print(f"=== Resumen: {s} ===")
