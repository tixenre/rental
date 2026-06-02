"""Cloudflare R2 storage — config, singleton boto3, put, delete.

Sin FastAPI: errores de configuración lanzan MediaError(500, ...).
"""
import logging
import os

from .errors import MediaError

logger = logging.getLogger(__name__)


def _r2_config() -> dict:
    """Lee la configuración de R2 desde env. Eleva MediaError(500) si falta algo."""
    cfg = {
        "account_id":  os.getenv("R2_ACCOUNT_ID") or "",
        "access_key_id": os.getenv("R2_ACCESS_KEY_ID") or "",
        "secret_key":  os.getenv("R2_SECRET_ACCESS_KEY") or "",
        "bucket":      os.getenv("R2_BUCKET") or "equipos-fotos",
        "public_base": (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/"),
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


def delete_object(key: str) -> bool:
    """Borra un objeto de R2 (best-effort). Devuelve True si se borró, False si no.
    Nunca eleva: el borrado de la DB es la fuente de verdad.
    """
    if not key:
        return False
    try:
        cfg = _r2_config()
        client = _get_r2_client(cfg)
        client.delete_object(Bucket=cfg["bucket"], Key=key)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("media.storage.delete_object: no se pudo borrar '%s': %s", key, e)
        return False
