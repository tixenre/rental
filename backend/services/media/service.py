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


def validate_kind(kind: str) -> None:
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
    background: bool = False,
) -> MediaAsset:
    """Pipeline no-destructivo: valida + strip EXIF + dedup + sube original privado + variantes.

    No hace commit. El caller escribe su fila (ej. equipo_fotos) y commitea.

    `background=True` → fase 1 únicamente (validar + subir original). Las variantes
    se derivan después con `derive_and_finalize(asset_id, ...)` (ej. FastAPI
    BackgroundTasks). El asset retorna con `status="pending"` y `variants=[]`.
    El caller DEBE commitear antes de invocar la tarea de background.

    Parámetros opcionales para el esquema de key F1+ (superficies de entidad):
    - entity_id, entity_slug: contexto de la entidad propietaria.
    - gallery: nombre de la galería dentro de la entidad (ej. "fotos", "portada").
    - position: índice del slot en la galería.
    Sin estos params → usa el esquema legacy con asset_id.
    """
    # Slug sanit: kind va directo a la R2 key → solo [a-z0-9-] (previene path traversal).
    validate_kind(kind)

    # Seguridad: valida magic-bytes + decompression-bomb ANTES de tocar la DB o R2.
    original_ct, ext = validate_and_detect(raw)

    # Privacidad: strip EXIF (GPS, device info, timestamps) del original.
    original_bytes = strip_exif_for_storage(raw, original_ct)

    # LQIP (blur-up placeholder, F0e): 4×4px JPEG → data URI inline.
    # Se genera antes del dedup: si hay hit, el existente ya tiene su lqip.
    lqip = generate_lqip(original_bytes)

    # Dedup por hash: misma imagen → devuelve asset existente sin re-procesar.
    content_hash = hashlib.sha256(original_bytes).hexdigest()
    existing = repository.find_by_hash(conn, kind, content_hash)
    if existing is not None:
        logger.info("store_upload: dedup hit para kind=%s hash=%s…", kind, content_hash[:8])
        return existing

    # INSERT asset (status pending si background, ready si síncrono)
    status = "pending" if background else "ready"
    asset_id = repository.insert_asset(conn, kind, status=status)

    _entity_ctx = dict(
        kind=kind, asset_id=asset_id,
        entity_id=entity_id, entity_slug=entity_slug,
        gallery=gallery, position=position,
    )

    uploaded_keys: list[str] = []
    try:
        # PUT original privado — siempre, en ambos modos.
        original_key = make_original_key(ext=ext, **_entity_ctx)
        storage.put_private(original_key, original_bytes, original_ct)
        uploaded_keys.append(original_key)

        # UPDATE asset con original_key + dims (sin variantes aún en modo BG).
        repository.update_asset_original(
            conn, asset_id, original_key, original_ct, 0, 0,
            len(original_bytes), content_hash=content_hash, lqip=lqip,
        )

        if background:
            # Fase 1 completa: el caller commitea y añade derive_and_finalize como BG task.
            return MediaAsset(
                id=asset_id, kind=kind,
                original_key=original_key, original_ct=original_ct,
                width=0, height=0, bytes=len(original_bytes),
                content_hash=content_hash,
                lqip=lqip,
                status="pending",
                variants=[],
            )

        # Fase 2 (síncrona): derivar variantes y finalizar.
        variant_objects = _derive_variants(
            original_bytes=original_bytes,
            derive_specs=derive_specs,
            asset_id=asset_id,
            entity_ctx=_entity_ctx,
            content_hash=content_hash,
            conn=conn,
            uploaded_keys=uploaded_keys,
        )

        first = variant_objects[0] if variant_objects else None
        repository.update_asset_original(
            conn, asset_id, original_key, original_ct,
            first.width if first else 0,
            first.height if first else 0,
            len(original_bytes), content_hash=content_hash, lqip=lqip,
        )

        return MediaAsset(
            id=asset_id, kind=kind,
            original_key=original_key, original_ct=original_ct,
            width=first.width if first else 0,
            height=first.height if first else 0,
            bytes=len(original_bytes),
            content_hash=content_hash,
            lqip=lqip,
            status="ready",
            variants=variant_objects,
        )

    except MediaError:
        _cleanup_r2(uploaded_keys)
        raise
    except Exception as e:
        _cleanup_r2(uploaded_keys)
        raise MediaError(500, f"Error inesperado al subir media: {e}") from e


def _derive_variants(
    *,
    original_bytes: bytes,
    derive_specs: list[DeriveSpec],
    asset_id: int,
    entity_ctx: dict,
    content_hash: str,
    conn,
    uploaded_keys: list[str],
) -> list[MediaVariant]:
    """Fase 2: optimizar + subir variantes a R2 + insertar en DB. Muta `uploaded_keys`."""
    variant_objects: list[MediaVariant] = []
    for spec in derive_specs:
        v_content, v_ct, v_w, v_h = _optimize_image(
            original_bytes, square=spec.square, fmt=spec.fmt, max_width=spec.max_width
        )
        v_ext = _ext_from_ctype(v_ct)
        v_key = make_variant_key(
            variant_name=spec.name, ext=v_ext, content_hash=content_hash, **entity_ctx
        )
        v_url = storage.put(v_key, v_content, v_ct)
        uploaded_keys.append(v_key)
        vid = repository.insert_variant(conn, asset_id, spec.name, v_key, v_url, v_ct, v_w, v_h, len(v_content))
        variant_objects.append(MediaVariant(
            id=vid, asset_id=asset_id, name=spec.name, key=v_key, url=v_url,
            content_type=v_ct, width=v_w, height=v_h, bytes=len(v_content),
        ))
    return variant_objects


def derive_and_finalize(
    asset_id: int,
    original_bytes: bytes,
    derive_specs: list[DeriveSpec],
) -> None:
    """Tarea de background: deriva variantes y marca el asset como ready.

    Abre su propia conexión DB vía get_db() — la del request ya está cerrada.
    Se invoca vía FastAPI BackgroundTasks después de que el caller commitió.
    """
    from database import get_db  # diferido: evita ciclos en tests/importación temprana

    try:
        conn = get_db()
    except Exception as e:
        logger.error("derive_and_finalize: no se pudo conectar a DB (asset=%s): %s", asset_id, e)
        return

    try:
        row = conn.execute("SELECT * FROM media_assets WHERE id = ?", (asset_id,)).fetchone()
        if not row:
            logger.error("derive_and_finalize: asset %s no encontrado", asset_id)
            return

        kind = row["kind"]
        try:
            content_hash = row["content_hash"] or ""
        except (KeyError, IndexError):
            content_hash = ""

        entity_ctx = dict(kind=kind, asset_id=asset_id,
                          entity_id=None, entity_slug=None, gallery=None, position=None)
        uploaded_keys: list[str] = []

        variant_objects = _derive_variants(
            original_bytes=original_bytes,
            derive_specs=derive_specs,
            asset_id=asset_id,
            entity_ctx=entity_ctx,
            content_hash=content_hash,
            conn=conn,
            uploaded_keys=uploaded_keys,
        )

        first = variant_objects[0] if variant_objects else None
        conn.execute(
            "UPDATE media_assets SET width = ?, height = ?, status = 'ready', "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (first.width if first else 0, first.height if first else 0, asset_id),
        )
        conn.commit()
        logger.info("derive_and_finalize: asset %s → ready (%d variantes)", asset_id, len(variant_objects))

    except Exception as e:
        logger.error("derive_and_finalize: error en asset %s: %s", asset_id, e, exc_info=True)
        try:
            conn.execute(
                "UPDATE media_assets SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (asset_id,),
            )
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


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
