"""Acceso a DB para media_assets y media_variants.

Usa placeholders `?` (PGCursor los traduce a `%s`).
Sin commits: el caller gestiona la transacción.
"""
from .models import MediaAsset, MediaVariant


def insert_asset(conn, kind: str) -> int:
    """Inserta una fila en media_assets y devuelve el id generado."""
    cur = conn.execute(
        "INSERT INTO media_assets (kind) VALUES (?) RETURNING id",
        (kind,),
    )
    return cur.fetchone()["id"]


def update_asset_original(
    conn,
    asset_id: int,
    original_key: str,
    original_ct: str,
    width: int,
    height: int,
    size_bytes: int,
) -> None:
    conn.execute(
        """
        UPDATE media_assets
        SET original_key = ?, original_ct = ?, width = ?, height = ?, bytes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (original_key, original_ct, width, height, size_bytes, asset_id),
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (asset_id, name, key, url, content_type, width, height, size_bytes),
    )
    return cur.fetchone()["id"]


def collect_asset_keys(conn, asset_id: int) -> list[str]:
    """Devuelve todas las R2 keys (original + variantes) del asset. Sin modificar DB."""
    keys: list[str] = []
    row = conn.execute(
        "SELECT original_key FROM media_assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if row and row["original_key"]:
        keys.append(row["original_key"])
    variant_rows = conn.execute(
        "SELECT key FROM media_variants WHERE asset_id = ?", (asset_id,)
    ).fetchall()
    keys.extend(v["key"] for v in variant_rows if v["key"])
    return keys


def load_asset(conn, asset_id: int) -> "MediaAsset | None":
    """Carga un MediaAsset completo (con variantes) desde la DB."""
    row = conn.execute("SELECT * FROM media_assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        return None
    variant_rows = conn.execute(
        "SELECT * FROM media_variants WHERE asset_id = ? ORDER BY id",
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
        variants=variants,
    )
