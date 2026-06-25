"""Cloudflare R2 storage — config, singleton boto3, put / put_private / get / delete.

Dos modos de subida:
- put()         → variantes públicas: CDN-friendly (Cache-Control: immutable).
                  Devuelve URL pública {public_base}/{key}.
- put_private() → originals: no se cachea en CDN, no devuelve URL pública.
                  Con R2_PRIVATE_BUCKET usa bucket separado (acceso privado real);
                  sin él usa el mismo bucket con Cache-Control: no-store (privacy by
                  design: URL nunca expuesta en API, CDN no la cachea).
                  Para leer: usar get() / get_original() vía boto3, nunca la URL CDN.

Sin FastAPI: errores de configuración lanzan MediaError(500, ...).
"""
import logging
import os

from .errors import MediaError

logger = logging.getLogger(__name__)


def _r2_config() -> dict:
    """Lee la configuración de R2 desde env. Eleva MediaError(500) si falta algo."""
    cfg = {
        "account_id":    os.getenv("R2_ACCOUNT_ID") or "",
        "access_key_id": os.getenv("R2_ACCESS_KEY_ID") or "",
        "secret_key":    os.getenv("R2_SECRET_ACCESS_KEY") or "",
        "bucket":        os.getenv("R2_BUCKET") or "equipos-fotos",
        "public_base":   (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/"),
        # Bucket privado opcional para originales. Si no está configurado, se usa
        # el mismo bucket (sin exponer la URL). Para privacidad real: crear un
        # segundo bucket en Cloudflare sin acceso público y setear R2_PRIVATE_BUCKET.
        "private_bucket": os.getenv("R2_PRIVATE_BUCKET") or "",
    }
    missing = [k for k in ("account_id", "access_key_id", "secret_key") if not cfg[k]]
    if missing:
        raise MediaError(
            500,
            f"R2 no configurado: faltan env vars {', '.join('R2_'+m.upper() for m in missing)}. "
            "Configurá en Railway: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
            "R2_BUCKET, R2_PUBLIC_BASE.",
        )
    if not cfg["public_base"]:
        cfg["public_base"] = f"https://pub-{cfg['account_id']}.r2.dev"
    return cfg


_r2_client_cache: tuple[tuple, object] | None = None


def _get_r2_client(cfg: dict) -> object:
    """Devuelve un cliente boto3 reutilizable para el bucket R2 (singleton)."""
    global _r2_client_cache
    cfg_key = (cfg["account_id"], cfg["access_key_id"], cfg["secret_key"])
    if _r2_client_cache is not None and _r2_client_cache[0] == cfg_key:
        return _r2_client_cache[1]
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise MediaError(500, "boto3 no instalado en el backend")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )
    _r2_client_cache = (cfg_key, client)
    return client


def put(key: str, content: bytes, content_type: str) -> str:
    """Sube `content` a R2 bajo `key`. Devuelve la URL pública. Eleva MediaError si falla."""
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    try:
        client.put_object(
            Bucket=cfg["bucket"],
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        raise MediaError(502, f"R2 upload falló: {e}")
    return f"{cfg['public_base']}/{key}"


def put_private(key: str, content: bytes, content_type: str) -> None:
    """Sube `content` a R2 como objeto privado. NO devuelve URL pública.

    Usa R2_PRIVATE_BUCKET si está configurado (bucket sin acceso público real).
    Sin R2_PRIVATE_BUCKET usa el bucket principal con Cache-Control: no-store
    (el CDN no lo cachea; la URL nunca se expone en la API).
    Para leer el original: usar get_original(key).
    """
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    bucket = cfg["private_bucket"] or cfg["bucket"]
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl="no-store",
        )
    except Exception as e:
        raise MediaError(502, f"R2 put_private falló: {e}")


def get_original(key: str) -> bytes:
    """Lee el original privado de R2 vía boto3 (autenticado). Eleva MediaError si falla.
    Usa R2_PRIVATE_BUCKET si está configurado; si no, el bucket principal.
    """
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    bucket = cfg["private_bucket"] or cfg["bucket"]
    try:
        resp = client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()
    except Exception as e:
        raise MediaError(502, f"R2 get_original falló para '{key}': {e}")


def get(key: str) -> bytes:
    """Descarga el objeto `key` de R2 (bucket público). Eleva MediaError si falla.
    Usado por backfills que necesitan re-derivar variantes desde el original guardado.
    Para originals: preferir get_original().
    """
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    try:
        resp = client.get_object(Bucket=cfg["bucket"], Key=key)
        return resp["Body"].read()
    except Exception as e:
        raise MediaError(502, f"R2 get falló para '{key}': {e}")


def delete_object(key: str, *, private: bool = False) -> bool:
    """Borra un objeto de R2 (best-effort). Devuelve True si se borró, False si no.
    Nunca eleva: el borrado de la DB es la fuente de verdad.
    `private=True` borra del bucket privado (R2_PRIVATE_BUCKET si existe, sino el principal).
    """
    if not key:
        return False
    try:
        cfg = _r2_config()
        client = _get_r2_client(cfg)
        bucket = (cfg["private_bucket"] or cfg["bucket"]) if private else cfg["bucket"]
        client.delete_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("media.storage.delete_object: no se pudo borrar '%s': %s", key, e)
        return False
