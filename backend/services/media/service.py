"""Orquestación del pipeline de media: store_upload + helpers de borrado.

store_upload:
  1. Valida kind (slug sanit).
  2. Valida imagen (magic-bytes + decompression-bomb).
  3. Strip EXIF del original (privacidad: GPS, device info).
  4. Dedup por hash: si la misma imagen ya existe, devuelve el asset existente.
  5. INSERT media_assets (inerte sin R2 todavía).
  6. PUT original privado en R2 (put_private: no CDN, no URL pública).
  7. Por cada DeriveSpec: optimize → PUT variante pública.
  8. UPDATE media_assets (original_key, dims, content_hash) + INSERT media_variants.
  9. Devuelve MediaAsset. El caller escribe su fila (ej. equipo_fotos) y commitea.

Fallo parcial:
  - Cualquier excepción dentro de store_upload → best-effort delete de las keys
    R2 ya subidas + re-raise. El caller (route) llama conn.rollback(), que deshace
    el INSERT media_assets no commiteado.

Borrado:
  - collect_asset_keys: carga keys sin tocar DB.
  - purge_r2: best-effort delete de R2 (llamar DESPUÉS del commit del caller).

─── Nomenclatura de keys R2 ────────────────────────────────────────────────────

Esquema canónico (F0a):

  Original (privado):
    media/{kind}/{asset_id}/original.{ext}

  Variantes (públicas, CDN-immutable):
    media/{kind}/{asset_id}/{variant_name}.{ext}

Ejemplo: media/equipo/42/display.webp, media/equipo/42/display-sm.webp

Ciclo de vida:
  - Keys determinísticas por asset_id: mismo asset → mismos keys.
  - Dedup por content_hash: misma imagen → mismo asset → mismos keys.
  - Cache-bust natural: nueva imagen → nuevo asset_id → nuevas URLs.
  - Sin versiones muertas: el GC (F0d, reconcile_media) limpia keys de assets
    huérfanos (borrados de equipo_fotos/estudio_fotos pero con R2 keys activas).

Esquema futuro para superficies de entidad (F1+):
  media/{kind}/{entity_id}-{entity_slug}/{gallery}/{position}/{variant}-{hash8}.{ext}

  Ejemplo: media/equipo/42-camara-sony/fotos/0/display-abc12345.webp

  Diferencias vs. actual:
  - entity_id-slug: path legible por humanos para debug/administración.
  - gallery: nombre del set de fotos ("fotos", "portada", "og").
  - position: índice del slot dentro de la galería (0, 1, 2…).
  - hash8: 8 chars del content_hash → cache-bust al sobreescribir en el mismo slot.
  Los callers de F1+ pasan `entity_id`, `entity_slug`, `gallery`, `position` a
  store_upload para que use make_variant_key() con el esquema completo.

────────────────────────────────────────────────────────────────────────────────
"""
import hashlib
import logging
import re
import unicodedata

from .errors import MediaError
from .models import MediaAsset, MediaVariant, DeriveSpec
from .processing import _optimize_image, _ext_from_ctype, strip_exif_for_storage, generate_lqip
from .validation import validate_and_detect
from . import storage, repository

logger = logging.getLogger(__name__)

_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SLUG_SAFE_RE = re.compile(r"[^a-z0-9]+")


def _validate_kind(kind: str) -> None:
    """Slug sanit del kind: solo [a-z0-9-], 1-64 chars. Previene path traversal en keys R2."""
    if not _KIND_RE.match(kind or ""):
        raise MediaError(400, f"kind inválido: {kind!r}. Solo [a-z0-9-], 1-64 chars.")


def _slugify(text: str, max_len: int = 40) -> str:
    """Normaliza a ASCII lowercase, reemplaza no-alfanuméricos con '-', trunca."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = _SLUG_SAFE_RE.sub("-", text.lower()).strip("-")
    return text[:max_len].rstrip("-") or "x"


def make_variant_key(
    *,
    kind: str,
    asset_id: int,
    variant_name: str,
    ext: str,
    entity_id: int | None = None,
    entity_slug: str | None = None,
    gallery: str | None = None,
    position: int | None = None,
    content_hash: str | None = None,
) -> str:
    """Construye la R2 key de una variante según el esquema canónico.

    Sin entity_id → esquema legacy:  media/{kind}/{asset_id}/{variant_name}.{ext}
    Con entity_id → esquema F1+:     media/{kind}/{entity_id}-{slug}/{gallery}/{position}/{variant_name}-{hash8}.{ext}

    El hash8 en el nombre (esquema F1+) permite overwrite determinístico con cache-bust:
    misma imagen → mismo hash → misma URL; nueva imagen → nuevo hash → nueva URL.
    """
    if entity_id is not None:
        slug = _slugify(entity_slug or "") if entity_slug else "x"
        g = _slugify(gallery or "fotos")
        pos = 0 if position is None else position
        h8 = (content_hash or "")[:8] or asset_id
        return f"media/{kind}/{entity_id}-{slug}/{g}/{pos}/{variant_name}-{h8}.{ext}"
    return f"media/{kind}/{asset_id}/{variant_name}.{ext}"


def make_original_key(
    *,
    kind: str,
    asset_id: int,
    ext: str,
    entity_id: int | None = None,
    entity_slug: str | None = None,
    gallery: str | None = None,
    position: int | None = None,
) -> str:
    """Construye la R2 key del original privado.

    Sin entity_id → media/{kind}/{asset_id}/original.{ext}
    Con entity_id → media/{kind}/{entity_id}-{slug}/{gallery}/{position}/original.{ext}
    El original NO lleva hash8 (es privado, no tiene CDN caching que bust).
    """
    if entity_id is not None:
        slug = _slugify(entity_slug or "") if entity_slug else "x"
        g = _slugify(gallery or "fotos")
        pos = 0 if position is None else position
        return f"media/{kind}/{entity_id}-{slug}/{g}/{pos}/original.{ext}"
    return f"media/{kind}/{asset_id}/original.{ext}"


def store_upload(
    raw: bytes,
    *,
    kind: str,
    derive_specs: list[DeriveSpec],
    conn,
    entity_id: int | None = None,
    entity_slug: str | None = None,
    gallery: str | None = None,
    position: int | None = None,
) -> MediaAsset:
    """Pipeline no-destructivo: valida + strip EXIF + dedup + sube original privado + variantes.

    No hace commit. El caller escribe su fila (ej. equipo_fotos) y commitea.

    Parámetros opcionales para el esquema de key F1+ (superficies de entidad):
    - entity_id, entity_slug: contexto de la entidad propietaria.
    - gallery: nombre de la galería dentro de la entidad (ej. "fotos", "portada").
    - position: índice del slot en la galería.
    Sin estos params → usa el esquema legacy con asset_id.
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

    # LQIP (blur-up placeholder, F0e): 4×4px JPEG → data URI inline.
    # Se genera ANTES del dedup: si hay hit, el asset existente ya tiene su lqip.
    # Fallback None si PIL falla (safe).
    lqip = generate_lqip(original_bytes)

    # Dedup por hash: si la misma imagen (sin EXIF) ya existe para este kind,
    # devolver el asset existente sin re-procesar ni re-subir a R2.
    content_hash = hashlib.sha256(original_bytes).hexdigest()
    existing = repository.find_by_hash(conn, kind, content_hash)
    if existing is not None:
        logger.info("store_upload: dedup hit para kind=%s hash=%s…", kind, content_hash[:8])
        return existing

    # 1. INSERT asset (sin R2 aún — inofensivo si falla después)
    asset_id = repository.insert_asset(conn, kind)

    # Contexto compartido para la construcción de keys (sin ext — varía por variante/original)
    _entity_ctx = dict(
        kind=kind, asset_id=asset_id,
        entity_id=entity_id, entity_slug=entity_slug,
        gallery=gallery, position=position,
    )

    uploaded_keys: list[str] = []
    try:
        # 2. PUT original (sin EXIF) como privado — no se expone en la API ni en CDN.
        original_key = make_original_key(ext=ext, **_entity_ctx)
        storage.put_private(original_key, original_bytes, original_ct)
        uploaded_keys.append(original_key)

        # 3. Derivar variantes desde el original ya sin EXIF (consistente con re-derivación futura)
        variants_data: list[tuple[str, str, str, str, int, int, int]] = []
        for spec in derive_specs:
            v_content, v_ct, v_w, v_h = _optimize_image(
                original_bytes, square=spec.square, fmt=spec.fmt, max_width=spec.max_width
            )
            v_ext = _ext_from_ctype(v_ct)
            v_key = make_variant_key(
                variant_name=spec.name, ext=v_ext, content_hash=content_hash, **_entity_ctx
            )
            v_url = storage.put(v_key, v_content, v_ct)
            uploaded_keys.append(v_key)
            variants_data.append((spec.name, v_key, v_url, v_ct, v_w, v_h, len(v_content)))

        # 4. UPDATE asset_original (con hash para dedup futuro) + INSERT variants
        first_w, first_h = (variants_data[0][4], variants_data[0][5]) if variants_data else (0, 0)
        repository.update_asset_original(
            conn, asset_id, original_key, original_ct, first_w, first_h,
            len(original_bytes), content_hash=content_hash, lqip=lqip,
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
            lqip=lqip,
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
