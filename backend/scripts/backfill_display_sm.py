"""Backfill de la variante display-sm (600px) para fotos de equipo existentes (one-off).

Las fotos subidas antes de `display-sm` solo tienen `display.webp` (1200) en R2.
Para srcset (catálogo en mobile), este script genera el `display-sm.webp` (600) de
cada asset de equipo enlazado a `equipo_fotos`, y rellena `equipos.foto_url_sm` de
los equipos cuya foto PRINCIPAL es ese asset (la denormalización que lee el catálogo).

Para cada asset SIN variante 'display-sm':
  - Fuente: `original_key` si está (máxima calidad), si no el `display.webp` ya guardado.
  - Genera `display-sm.webp` (square 600) → PUT R2 + INSERT media_variants.
  - Si el asset es la foto principal de algún equipo → UPDATE equipos.foto_url_sm.

Idempotente: salta los assets que ya tienen `display-sm`. Best-effort por foto: si
una falla, loguea y sigue. Commit por asset (el progreso parcial sobrevive). NO se
corre en el deploy — lo ejecuta el dueño de forma controlada (empezar con --dry-run).

Uso:
  cd backend && source .venv/bin/activate && python scripts/backfill_display_sm.py --dry-run
  # Contra prod (DATABASE_URL + R2_* apuntando a prod):
  cd backend && source .venv/bin/activate && \\
    DATABASE_URL='postgres://...' python scripts/backfill_display_sm.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db  # noqa: E402
from services.media import repository, storage  # noqa: E402
from services.media.processing import _optimize_image  # noqa: E402


def backfill(dry_run: bool = False) -> dict:
    conn = get_db()
    stats = {"candidatos": 0, "creados": 0, "foto_url_sm": 0, "saltados_sin_fuente": 0, "errores": 0}
    try:
        # Assets de equipo enlazados a equipo_fotos que aún no tienen 'display-sm'.
        rows = conn.execute(
            """
            SELECT DISTINCT ef.media_id AS asset_id
            FROM equipo_fotos ef
            WHERE ef.media_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM media_variants mv
                  WHERE mv.asset_id = ef.media_id AND mv.name = 'display-sm'
              )
            """
        ).fetchall()
        asset_ids = [r["asset_id"] for r in rows]
        stats["candidatos"] = len(asset_ids)
        print(f"Assets de equipo sin variante 'display-sm': {len(asset_ids)}")

        for asset_id in asset_ids:
            try:
                asset = repository.load_asset(conn, asset_id)
                if asset is None:
                    continue
                # Fuente: original si está (máxima calidad), si no el display.webp.
                src_key = asset.original_key
                if not src_key:
                    display = asset.variant("display")
                    src_key = display.key if display else None
                if not src_key:
                    stats["saltados_sin_fuente"] += 1
                    print(f"  asset {asset_id}: sin original ni display → salto")
                    continue

                if dry_run:
                    print(f"  asset {asset_id}: derivaría display-sm desde {src_key}")
                    continue

                raw = storage.get(src_key)
                content, ct, w, h = _optimize_image(raw, square=True, fmt="webp", max_width=600)
                sm_key = f"media/{asset.kind}/{asset.id}/display-sm.webp"
                url = storage.put(sm_key, content, ct)
                repository.insert_variant(
                    conn, asset.id, "display-sm", sm_key, url, ct, w, h, len(content)
                )
                # Denormalizar: si este asset es la principal de algún equipo, llenar foto_url_sm.
                cur = conn.execute(
                    """
                    UPDATE equipos SET foto_url_sm = ?
                    WHERE id IN (
                        SELECT equipo_id FROM equipo_fotos
                        WHERE media_id = ? AND es_principal = TRUE
                    )
                    """,
                    (url, asset_id),
                )
                stats["foto_url_sm"] += getattr(cur, "rowcount", 0) or 0
                conn.commit()
                stats["creados"] += 1
                print(f"  asset {asset_id}: display-sm creado ({len(content) // 1024} KB) → {url}")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                stats["errores"] += 1
                print(f"  asset {asset_id}: ERROR {e}")
    finally:
        conn.close()
    return stats


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"=== Backfill display-sm fotos {'(DRY RUN)' if dry else '(APLICANDO)'} ===")
    s = backfill(dry_run=dry)
    print(f"=== Resumen: {s} ===")
