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
import logging

from .errors import MediaError
from .models import MediaAsset, MediaVariant, DeriveSpec
from .processing import _optimize_image, _ext_from_ctype
from .validation import validate_and_detect
from . import storage, repository

logger = logging.getLogger(__name__)


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
    # Seguridad: valida magic-bytes + decompression-bomb ANTES de tocar la DB o R2.
    # Rechaza no-imágenes con 400 (en vez del fallback silencioso a jpeg).
    original_ct, ext = validate_and_detect(raw)

    # 1. INSERT asset (sin R2 aún — inofensivo si falla después)
    asset_id = repository.insert_asset(conn, kind)

    uploaded_keys: list[str] = []
    try:
        # 2. PUT original (bytes intactos)
        original_key = f"media/{kind}/{asset_id}/original.{ext}"
        storage.put(original_key, raw, original_ct)
        uploaded_keys.append(original_key)

        # 3. Derivar variantes
        variants_data: list[tuple[str, str, str, str, int, int, int]] = []
        for spec in derive_specs:
            v_content, v_ct, v_w, v_h = _optimize_image(
                raw, square=spec.square, fmt=spec.fmt, max_width=spec.max_width
            )
            v_key = f"media/{kind}/{asset_id}/{spec.name}.{_ext_from_ctype(v_ct)}"
            v_url = storage.put(v_key, v_content, v_ct)
            uploaded_keys.append(v_key)
            variants_data.append((spec.name, v_key, v_url, v_ct, v_w, v_h, len(v_content)))

        # 4. UPDATE asset_original + INSERT variants
        first_w, first_h = (variants_data[0][4], variants_data[0][5]) if variants_data else (0, 0)
        repository.update_asset_original(
            conn, asset_id, original_key, original_ct, first_w, first_h, len(raw),
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
            width=first_w, height=first_h, bytes=len(raw),
            variants=variant_objects,
        )

    except MediaError:
        _cleanup_r2(uploaded_keys)
        raise
    except Exception as e:
        _cleanup_r2(uploaded_keys)
        raise MediaError(500, f"Error inesperado al subir media: {e}") from e


def _cleanup_r2(keys: list[str]) -> None:
    """Best-effort delete de las keys R2 ya subidas (en caso de fallo parcial)."""
    for key in keys:
        storage.delete_object(key)


def collect_asset_keys(conn, asset_id: int) -> list[str]:
    """Devuelve las R2 keys del asset (original + variantes). Sin modificar DB.
    Llamar antes del DELETE para tener las keys disponibles para limpiar R2.
    """
    return repository.collect_asset_keys(conn, asset_id)


def purge_r2(keys: list[str]) -> None:
    """Best-effort delete de todas las R2 keys. Llamar DESPUÉS del commit."""
    for key in keys:
        storage.delete_object(key)
