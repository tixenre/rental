"""Orquestación del pipeline de media: store_upload + helpers de borrado.

store_upload:
  1. INSERT media_assets (inerte sin R2 todavía).
  2. PUT original en R2.
  3. Por cada DeriveSpec: optimize → PUT variante.
  4. UPDATE media_assets (original_key, dims) + INSERT media_variants.
  5. Devuelve MediaAsset. El caller escribe estudio_fotos en la MISMA transacción
     y llama conn.commit() → todo en un solo commit.

Fallo parcial:
  - Cualquier excepción dentro de store_upload → best-effort delete de las keys
    R2 ya subidas + re-raise. El caller (route) llama conn.rollback(), que deshace
    el INSERT media_assets no commiteado.

Borrado:
  - collect_asset_keys: carga keys sin tocar DB.
  - purge_r2: best-effort delete de R2 (llamar DESPUÉS del commit del caller).
"""
import hashlib
import logging
import re

from .errors import MediaError
from .models import MediaAsset, MediaVariant, DeriveSpec
from .processing import _optimize_image, _ext_from_ctype, strip_exif_for_storage
from .validation import validate_and_detect
from . import storage, repository

logger = logging.getLogger(__name__)

_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _validate_kind(kind: str) -> None:
    """Slug sanit del kind: solo [a-z0-9-], 1-64 chars. Previene path traversal en keys R2."""
    if not _KIND_RE.match(kind or ""):
        raise MediaError(400, f"kind inválido: {kind!r}. Solo [a-z0-9-], 1-64 chars.")


def store_upload(
    raw: bytes,
    *,
    kind: str,
    derive_specs: list[DeriveSpec],
    conn,
) -> MediaAsset:
    """Pipeline no-destructivo: guarda el original + deriva variantes.

    No hace commit. El caller escribe su fila (ej. estudio_fotos) y commitea.
    """
    # Slug sanit: kind va directo a la R2 key → solo [a-z0-9-] (previene path traversal).
    _validate_kind(kind)

    # Seguridad: valida magic-bytes + decompression-bomb ANTES de tocar la DB o R2.
    # Rechaza no-imágenes con 400 (en vez del fallback silencioso a jpeg).
    original_ct, ext = validate_and_detect(raw)

    # Privacidad: strip EXIF (GPS, device info, timestamps) del original antes de
    # guardarlo. Bake orientación en píxeles → derivaciones posteriores son
    # orientation-correct sin exif_transpose adicional. Fallback safe al raw.
    original_bytes = strip_exif_for_storage(raw, original_ct)

    # Dedup por hash: si la misma imagen (sin EXIF) ya existe para este kind,
    # devolver el asset existente sin re-procesar ni re-subir a R2.
    content_hash = hashlib.sha256(original_bytes).hexdigest()
    existing = repository.find_by_hash(conn, kind, content_hash)
    if existing is not None:
        logger.info("store_upload: dedup hit para kind=%s hash=%s…", kind, content_hash[:8])
        return existing

    # 1. INSERT asset (sin R2 aún — inofensivo si falla después)
    asset_id = repository.insert_asset(conn, kind)

    uploaded_keys: list[str] = []
    try:
        # 2. PUT original (sin EXIF) como privado — no se expone en la API ni en CDN.
        # put_private: Cache-Control: no-store; bucket privado si R2_PRIVATE_BUCKET configurado.
        original_key = f"media/{kind}/{asset_id}/original.{ext}"
        storage.put_private(original_key, original_bytes, original_ct)
        uploaded_keys.append(original_key)

        # 3. Derivar variantes desde el original ya sin EXIF (consistente con re-derivación futura)
        variants_data: list[tuple[str, str, str, str, int, int, int]] = []
        for spec in derive_specs:
            v_content, v_ct, v_w, v_h = _optimize_image(
                original_bytes, square=spec.square, fmt=spec.fmt, max_width=spec.max_width
            )
            v_key = f"media/{kind}/{asset_id}/{spec.name}.{_ext_from_ctype(v_ct)}"
            v_url = storage.put(v_key, v_content, v_ct)
            uploaded_keys.append(v_key)
            variants_data.append((spec.name, v_key, v_url, v_ct, v_w, v_h, len(v_content)))

        # 4. UPDATE asset_original (con hash para dedup futuro) + INSERT variants
        first_w, first_h = (variants_data[0][4], variants_data[0][5]) if variants_data else (0, 0)
        repository.update_asset_original(
            conn, asset_id, original_key, original_ct, first_w, first_h,
            len(original_bytes), content_hash=content_hash,
        )

        variant_objects: list[MediaVariant] = []
        for name, key, url, ct, w, h, size in variants_data:
            vid = repository.insert_variant(conn, asset_id, name, key, url, ct, w, h, size)
            variant_objects.append(MediaVariant(
                id=vid, asset_id=asset_id, name=name, key=key, url=url,
                content_type=ct, width=w, height=h, bytes=size,
            ))

        return MediaAsset(
            id=asset_id, kind=kind,
            original_key=original_key, original_ct=original_ct,
            width=first_w, height=first_h, bytes=len(original_bytes),
            content_hash=content_hash,
            variants=variant_objects,
        )

    except MediaError:
        _cleanup_r2(uploaded_keys)
        raise
    except Exception as e:
        _cleanup_r2(uploaded_keys)
        raise MediaError(500, f"Error inesperado al subir media: {e}") from e


def _cleanup_r2(keys: list[str]) -> None:
    """Best-effort delete de las keys R2 ya subidas (en caso de fallo parcial).

    El primer key siempre es el original (privado); el resto son variantes (públicas).
    """
    for i, key in enumerate(keys):
        storage.delete_object(key, private=(i == 0))


def collect_asset_keys(conn, asset_id: int) -> list[str]:
    """Devuelve las R2 keys del asset (original + variantes). Sin modificar DB.
    Llamar antes del DELETE para tener las keys disponibles para limpiar R2.
    El primer elemento (si existe) es el original_key (bucket privado).
    """
    return repository.collect_asset_keys(conn, asset_id)


def purge_r2(keys: list[str], *, original_key: str | None = None) -> None:
    """Best-effort delete de todas las R2 keys. Llamar DESPUÉS del commit.

    `original_key` se borra del bucket privado; el resto del bucket público.
    Si no se especifica original_key, se asume que el primer key es el original.
    """
    for i, key in enumerate(keys):
        is_original = key == original_key if original_key else i == 0
        storage.delete_object(key, private=is_original)
