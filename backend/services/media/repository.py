"""Acceso a DB para media_assets y media_variants.

Usa placeholders `%s` (psycopg nativo).
Sin commits: el caller gestiona la transacción.
"""
from .models import MediaAsset, MediaVariant


def insert_asset(conn, kind: str, status: str = "ready") -> int:
    """Inserta una fila en media_assets y devuelve el id generado."""
    cur = conn.execute(
        "INSERT INTO media_assets (kind, status) VALUES (%s, %s) RETURNING id",
        (kind, status),
    )
    return cur.fetchone()["id"]


def update_asset_status(conn, asset_id: int, status: str) -> None:
    """Actualiza el campo status del asset (pending → ready | failed)."""
    conn.execute(
        "UPDATE media_assets SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, asset_id),
    )


def update_asset_original(
    conn,
    asset_id: int,
    original_key: str,
    original_ct: str,
    width: int,
    height: int,
    size_bytes: int,
    content_hash: str | None = None,
    lqip: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE media_assets
        SET original_key = %s, original_ct = %s, width = %s, height = %s, bytes = %s,
            content_hash = %s, lqip = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (original_key, original_ct, width, height, size_bytes, content_hash, lqip, asset_id),
    )


def insert_variant(
    conn,
    asset_id: int,
    name: str,
    key: str,
    url: str,
    content_type: str,
    width: int,
    height: int,
    size_bytes: int,
) -> int:
    """Inserta una fila en media_variants y devuelve el id generado."""
    cur = conn.execute(
        """
        INSERT INTO media_variants
            (asset_id, name, key, url, content_type, width, height, bytes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (asset_id, name, key, url, content_type, width, height, size_bytes),
    )
    return cur.fetchone()["id"]


def find_by_hash(conn, kind: str, content_hash: str) -> "MediaAsset | None":
    """Busca un asset existente por (kind, content_hash). None si no existe.
    Usado para dedup: si la misma imagen se sube dos veces, devuelve el asset previo.
    """
    row = conn.execute(
        "SELECT * FROM media_assets WHERE kind = %s AND content_hash = %s",
        (kind, content_hash),
    ).fetchone()
    if not row:
        return None
    return load_asset(conn, row["id"])


def collect_asset_keys(conn, asset_id: int) -> list[str]:
    """Devuelve todas las R2 keys (original + variantes) del asset. Sin modificar DB."""
    keys: list[str] = []
    row = conn.execute(
        "SELECT original_key FROM media_assets WHERE id = %s", (asset_id,)
    ).fetchone()
    if row and row["original_key"]:
        keys.append(row["original_key"])
    variant_rows = conn.execute(
        "SELECT key FROM media_variants WHERE asset_id = %s", (asset_id,)
    ).fetchall()
    keys.extend(v["key"] for v in variant_rows if v["key"])
    return keys


def _safe_get(row, key: str):
    """Lee una columna del row tolerando que no exista (assets pre-migración)."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def load_asset(conn, asset_id: int) -> "MediaAsset | None":
    """Carga un MediaAsset completo (con variantes) desde la DB."""
    row = conn.execute("SELECT * FROM media_assets WHERE id = %s", (asset_id,)).fetchone()
    if not row:
        return None
    variant_rows = conn.execute(
        "SELECT * FROM media_variants WHERE asset_id = %s ORDER BY id",
        (asset_id,),
    ).fetchall()
    variants = [
        MediaVariant(
            id=v["id"], asset_id=v["asset_id"], name=v["name"],
            key=v["key"], url=v["url"], content_type=v["content_type"],
            width=v["width"] or 0, height=v["height"] or 0, bytes=v["bytes"] or 0,
        )
        for v in variant_rows
    ]
    return MediaAsset(
        id=row["id"], kind=row["kind"],
        original_key=row["original_key"], original_ct=row["original_ct"],
        width=row["width"], height=row["height"], bytes=row["bytes"],
        content_hash=_safe_get(row, "content_hash"),
        lqip=_safe_get(row, "lqip"),
        status=_safe_get(row, "status") or "ready",
        variants=variants,
    )
