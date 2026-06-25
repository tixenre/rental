"""Backfill de ingesta de fotos legacy al motor de media (one-off, idempotente).

Migra las fotos de equipo que tienen `media_id IS NULL` (no ingresadas por el nuevo
motor) al pipeline completo: original privado + variantes webp/AVIF/LQIP en R2.

Dos tiers:
  Tier B — URLs de nuestro R2 viejo (1 sola variante 1200px, key en R2_PUBLIC_BASE).
           Descarga por boto3 (sin red externa).
  Tier C — URLs externas (bhphotovideo etc.). Descarga con anti-SSRF + allowlist.

Al terminar cada foto:
  - UPDATE equipo_fotos SET media_id, url, path  (no INSERT — la fila ya existe)
  - Si es_principal → _sync_principal_denorm (actualiza las 7 columnas denorm)

Idempotente: `store_upload` deduplica por content_hash. Si se interrumpe, reanudar
simplemente volviendo a correr.

Uso (contra staging):
  cd backend && source .venv/bin/activate
  python scripts/backfill_ingest_legacy.py --dry-run
  python scripts/backfill_ingest_legacy.py --solo-tier=b    # 103 fotos R2 propias
  python scripts/backfill_ingest_legacy.py --solo-tier=c    # 9 fotos externas

Contra prod (después de probar en staging):
  DATABASE_URL='postgres://...' R2_ACCESS_KEY_ID='...' ... python backfill_ingest_legacy.py
"""

import os
import sys
import argparse
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db                                # noqa: E402
from services.media import store_upload, EQUIPO_DERIVE_SPECS  # noqa: E402
from services.media.errors import MediaError               # noqa: E402
from services.media import storage as _storage             # noqa: E402
from services.media.security import (                      # noqa: E402
    _validate_external_image_url,
    _download_image_bytes,
)
from routes.equipos.fotos import _sync_principal_denorm    # noqa: E402


def _r2_public_base() -> str:
    base = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if not base:
        account_id = os.getenv("R2_ACCOUNT_ID") or ""
        if account_id:
            base = f"https://pub-{account_id}.r2.dev"
    return base


def _classify(url: str, r2_base: str) -> str | None:
    """Clasifica la URL en 'B' (R2 propio), 'C' (externo) o None (irreconocible)."""
    if not url:
        return None
    url_lower = url.lower()
    # Tier B: coincide con nuestro R2_PUBLIC_BASE, o es un dominio r2.dev
    if r2_base and url.startswith(r2_base + "/"):
        return "B"
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.endswith(".r2.dev") or "r2.dev" in host:
        return "B"
    # Tier C: cualquier host externo HTTP/S con URL absoluta
    if url_lower.startswith("http://") or url_lower.startswith("https://"):
        return "C"
    return None


def _download_tier_b(url: str, r2_base: str) -> bytes:
    """Descarga desde R2 propio vía boto3 (sin red externa)."""
    if r2_base and url.startswith(r2_base + "/"):
        key = url[len(r2_base) + 1:].split("?")[0]
    else:
        # r2.dev URL sin match exacto: extraer path como key
        key = urlparse(url).path.lstrip("/").split("?")[0]
    return _storage.get(key)


def backfill(dry_run: bool = False, solo_tier: str | None = None) -> dict:
    stats = {
        "candidatos": 0,
        "tier_b": 0,
        "tier_c": 0,
        "ingresados": 0,
        "dedup": 0,
        "errores": 0,
        "irreconocibles": 0,
    }
    r2_base = _r2_public_base()

    conn = get_db()
    try:
        # Snapshot de IDs existentes para detectar dedup (store_upload devuelve el
        # asset ya existente si el content_hash coincide — indistinguible por el objeto).
        existing_ids = {r["id"] for r in conn.execute("SELECT id FROM media_assets").fetchall()}

        rows = conn.execute(
            """
            SELECT ef.id AS foto_id, ef.equipo_id, ef.url, ef.es_principal
            FROM equipo_fotos ef
            WHERE ef.media_id IS NULL
              AND ef.url IS NOT NULL
              AND ef.url != ''
            ORDER BY ef.equipo_id, ef.orden, ef.id
            """
        ).fetchall()

        candidatos = [dict(r) for r in rows]
        stats["candidatos"] = len(candidatos)
        print(f"Fotos sin media_id: {len(candidatos)}")

        for row in candidatos:
            url = row["url"]
            equipo_id = row["equipo_id"]
            foto_id = row["foto_id"]

            tier = _classify(url, r2_base)
            if tier is None:
                stats["irreconocibles"] += 1
                print(f"  foto {foto_id} (equipo {equipo_id}): URL irreconocible → {url[:80]!r}")
                continue

            if solo_tier and tier.lower() != solo_tier.lower():
                continue

            stats[f"tier_{tier.lower()}"] += 1
            label = f"foto {foto_id} (equipo {equipo_id}, tier {tier})"

            if dry_run:
                print(f"  {label}: clasificado → {url[:80]!r}")
                continue

            try:
                # 1. Descargar bytes
                if tier == "B":
                    raw = _download_tier_b(url, r2_base)
                else:
                    _validate_external_image_url(url)
                    raw, _ = _download_image_bytes(url)

                # 2. Ingestar (dedup por content_hash — idempotente)
                asset = store_upload(
                    raw,
                    kind="equipo",
                    derive_specs=EQUIPO_DERIVE_SPECS,
                    conn=conn,
                )

                display = asset.variant("display")
                if not display:
                    raise MediaError(500, "store_upload no generó variante 'display'")

                # 3. UPDATE equipo_fotos (no INSERT — la fila ya existe)
                conn.execute(
                    "UPDATE equipo_fotos SET media_id = ?, url = ?, path = ? WHERE id = ?",
                    (asset.id, display.url, display.key, foto_id),
                )

                # 4. Sync columnas denorm de la principal
                if row["es_principal"]:
                    _sync_principal_denorm(conn, equipo_id)

                conn.commit()
                was_dedup = asset.id in existing_ids
                existing_ids.add(asset.id)
                if was_dedup:
                    stats["dedup"] += 1
                    print(f"  {label}: dedup (asset {asset.id}) → {display.url[:60]}")
                else:
                    stats["ingresados"] += 1
                    sz = len(raw) // 1024
                    print(f"  {label}: OK (asset {asset.id}, {sz} KB orig) → {display.url[:60]}")

            except (MediaError, Exception) as e:  # noqa: BLE001
                conn.rollback()
                stats["errores"] += 1
                print(f"  {label}: ERROR {type(e).__name__}: {e}")

    finally:
        conn.close()

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill ingesta de fotos legacy")
    parser.add_argument("--dry-run", action="store_true", help="Solo clasificar, no ingestar")
    parser.add_argument("--solo-tier", choices=["b", "c", "B", "C"], help="Correr solo el tier indicado")
    args = parser.parse_args()

    print(f"=== Backfill ingesta fotos legacy {'(DRY RUN)' if args.dry_run else '(APLICANDO)'} "
          f"{'solo-tier=' + args.solo_tier if args.solo_tier else 'todos los tiers'} ===")
    s = backfill(dry_run=args.dry_run, solo_tier=args.solo_tier)
    print(f"=== Resumen: {s} ===")
    ok = s["errores"] == 0 and s["irreconocibles"] == 0
    sys.exit(0 if ok else 1)
