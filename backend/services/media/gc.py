"""Garbage collector de media (F0d).

reconcile_media  — borra de R2 + DB los assets huérfanos (no referenciados por
                   ninguna tabla de entidad). Llamar periódicamente o tras
                   operaciones de borrado masivo.

rederive_variants — re-genera variantes de un asset desde su original privado en R2.
                   Útil cuando cambian los specs o si una variante quedó corrupta.

Un asset es huérfano si su id no aparece en ninguna de las tablas de entidades
que registran media_id:
  - equipo_fotos.media_id
  - estudio_fotos.media_id
  - marcas.media_id

⚠️  Al agregar una nueva tabla de entidad que use media_id → actualizar _ENTITY_REFS
    (array de (tabla, columna)). El supervisor/CI detectará el drift si se añade
    un equipo_fotos-like sin actualizar la lista.
"""
import logging
from dataclasses import dataclass, field

from .errors import MediaError
from .models import MediaVariant, DeriveSpec

logger = logging.getLogger(__name__)

# Tablas de entidad que referencian media_assets.id.
# Ampliar al agregar nuevas superficies de entidad (F1, F2, talleres…).
_ENTITY_REFS: list[tuple[str, str]] = [
    ("equipo_fotos", "media_id"),
    ("estudio_fotos", "media_id"),
    ("marcas",        "media_id"),
]


@dataclass
class ReconcileResult:
    orphans_found: int = 0
    orphans_purged: int = 0
    r2_keys_deleted: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "orphans_found":   self.orphans_found,
            "orphans_purged":  self.orphans_purged,
            "r2_keys_deleted": self.r2_keys_deleted,
            "errors":          self.errors,
            "dry_run":         self.dry_run,
        }


def _find_orphan_ids(conn, *, kind: str | None = None) -> list[int]:
    """IDs de media_assets no referenciados por ninguna tabla de entidad.

    Si `kind` está presente, limita al kind dado (ej. "equipo").
    Usa NOT EXISTS repetido — portable a Postgres y SQLite (tests).
    """
    not_exists_clauses = " AND ".join(
        f"NOT EXISTS (SELECT 1 FROM {tbl} WHERE {col} = ma.id)"
        for tbl, col in _ENTITY_REFS
    )
    where = f"WHERE {not_exists_clauses}"
    if kind:
        where += " AND ma.kind = ?"
        params: tuple = (kind,)
    else:
        params = ()

    rows = conn.execute(
        f"SELECT ma.id FROM media_assets ma {where} ORDER BY ma.id",
        params,
    ).fetchall()
    return [r["id"] for r in rows]


def reconcile_media(
    conn,
    *,
    kind: str | None = None,
    dry_run: bool = False,
) -> ReconcileResult:
    """Borra assets huérfanos: R2 (best-effort) + DB.

    dry_run=True: detecta y reporta sin borrar nada.
    kind: si se pasa, limita el GC al kind dado.
    El conn NO hace commit aquí — el caller commitea (o revierte) al terminar.
    """
    from . import storage, repository

    result = ReconcileResult(dry_run=dry_run)
    orphan_ids = _find_orphan_ids(conn, kind=kind)
    result.orphans_found = len(orphan_ids)

    if dry_run or not orphan_ids:
        return result

    for asset_id in orphan_ids:
        try:
            keys = repository.collect_asset_keys(conn, asset_id)
            original_key = None
            row = conn.execute(
                "SELECT original_key FROM media_assets WHERE id = ?", (asset_id,)
            ).fetchone()
            if row:
                original_key = row["original_key"]

            # Borrar de R2 (best-effort — si falla no cancela el GC)
            for key in keys:
                is_orig = key == original_key
                deleted = storage.delete_object(key, private=is_orig)
                if deleted:
                    result.r2_keys_deleted += 1

            # Borrar de DB (media_variants borrado en CASCADE)
            conn.execute("DELETE FROM media_assets WHERE id = ?", (asset_id,))
            result.orphans_purged += 1

        except Exception as e:
            msg = f"Error borrando asset {asset_id}: {e}"
            logger.warning("reconcile_media: %s", msg)
            result.errors.append(msg)

    return result


def rederive_variants(
    asset_id: int,
    *,
    derive_specs: list[DeriveSpec],
    conn,
) -> list[MediaVariant]:
    """Re-genera variantes de un asset existente desde su original privado en R2.

    Útil cuando:
    - Se agregan nuevas specs al pipeline (ej. se agrega display-thumb).
    - Una variante quedó corrupta o incompleta.
    - Se quiere regenerar con mejores parámetros.

    Las variantes existentes con el mismo nombre se REEMPLAZAN (update_or_insert).
    El original en R2 no se toca.
    Eleva MediaError si no encuentra el original o si R2 falla.
    """
    from .processing import _optimize_image, _ext_from_ctype
    from . import storage, repository

    row = conn.execute(
        "SELECT original_key, original_ct FROM media_assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if not row or not row["original_key"]:
        raise MediaError(404, f"Asset {asset_id} no encontrado o sin original_key")

    original_bytes = storage.get_original(row["original_key"])
    original_ct = row["original_ct"] or "image/jpeg"

    new_variants: list[MediaVariant] = []
    for spec in derive_specs:
        v_content, v_ct, v_w, v_h = _optimize_image(
            original_bytes, square=spec.square, fmt=spec.fmt, max_width=spec.max_width
        )
        v_ext = _ext_from_ctype(v_ct)

        # Clave determinística: si ya existe la variante en la DB, reusar la key
        existing = conn.execute(
            "SELECT key FROM media_variants WHERE asset_id = ? AND name = ?",
            (asset_id, spec.name),
        ).fetchone()

        if existing and existing["key"]:
            v_key = existing["key"]
        else:
            from .service import make_variant_key
            v_key = make_variant_key(
                kind=row["original_ct"] or "equipo",  # fallback — se sobrescribe
                asset_id=asset_id, variant_name=spec.name, ext=v_ext,
            )
            # Corregir el key usando el kind real del asset
            kind_row = conn.execute(
                "SELECT kind FROM media_assets WHERE id = ?", (asset_id,)
            ).fetchone()
            if kind_row:
                v_key = make_variant_key(
                    kind=kind_row["kind"], asset_id=asset_id,
                    variant_name=spec.name, ext=v_ext,
                )

        v_url = storage.put(v_key, v_content, v_ct)

        # Upsert en media_variants
        existing2 = conn.execute(
            "SELECT id FROM media_variants WHERE asset_id = ? AND name = ?",
            (asset_id, spec.name),
        ).fetchone()
        if existing2:
            conn.execute(
                "UPDATE media_variants SET key=?, url=?, content_type=?, width=?, height=?, bytes=? "
                "WHERE id=?",
                (v_key, v_url, v_ct, v_w, v_h, len(v_content), existing2["id"]),
            )
            vid = existing2["id"]
        else:
            vid = repository.insert_variant(conn, asset_id, spec.name, v_key, v_url, v_ct, v_w, v_h, len(v_content))

        new_variants.append(MediaVariant(
            id=vid, asset_id=asset_id, name=spec.name, key=v_key, url=v_url,
            content_type=v_ct, width=v_w, height=v_h, bytes=len(v_content),
        ))

    return new_variants
