"""
Backup de PostgreSQL → gzip → Cloudflare R2.

Solo activo cuando BACKUP_ENABLED=true. Sin esa variable el módulo
importa sin efectos secundarios — seguro en dev y CI.
"""

import gzip
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BACKUP_ENABLED  = os.getenv("BACKUP_ENABLED", "").lower() in ("1", "true", "yes")
BACKUP_RETAIN_DAYS = int(os.getenv("BACKUP_RETAIN_DAYS", "30"))
BACKUP_PREFIX   = "backups/"


def _r2_client():
    account_id = os.getenv("R2_ACCOUNT_ID") or ""
    access_key  = os.getenv("R2_ACCESS_KEY_ID") or ""
    secret_key  = os.getenv("R2_SECRET_ACCESS_KEY") or ""
    missing = [k for k, v in [("R2_ACCOUNT_ID", account_id), ("R2_ACCESS_KEY_ID", access_key), ("R2_SECRET_ACCESS_KEY", secret_key)] if not v]
    if missing:
        raise RuntimeError(f"R2 no configurado: faltan {', '.join(missing)}")
    import boto3
    from botocore.config import Config as BotoConfig
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )


def _bucket() -> str:
    return os.getenv("R2_BUCKET") or "equipos-fotos"


def run_backup() -> dict:
    """
    Ejecuta pg_dump, comprime con gzip y sube a R2.
    Retorna metadata del backup: filename, size_bytes, timestamp.
    Lanza excepción si falla — el caller decide cómo reportarlo.
    """
    if not BACKUP_ENABLED:
        logger.info("Backup omitido: BACKUP_ENABLED no está seteado.")
        return {"skipped": True, "reason": "BACKUP_ENABLED no está seteado"}

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no configurado")

    now = datetime.now(timezone.utc)
    filename = f"backup_{now.strftime('%Y-%m-%d_%H%M%S')}.sql.gz"
    r2_key   = f"{BACKUP_PREFIX}{now.strftime('%Y/%m')}/{filename}"

    logger.info("Iniciando backup → %s", r2_key)

    with tempfile.NamedTemporaryFile(suffix=".sql.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # pg_dump → gzip → archivo temporal
        dump_env = {**os.environ, "PGPASSWORD": _pg_password(database_url)}
        dump_cmd = ["pg_dump", "--no-owner", "--no-acl", "--format=plain", database_url]
        with gzip.open(tmp_path, "wb") as gz:
            proc = subprocess.run(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dump_env,
                check=True,
            )
            gz.write(proc.stdout)

        size = os.path.getsize(tmp_path)
        logger.info("Dump completado: %.1f KB", size / 1024)

        # Upload a R2
        client = _r2_client()
        with open(tmp_path, "rb") as f:
            client.put_object(
                Bucket=_bucket(),
                Key=r2_key,
                Body=f,
                ContentType="application/gzip",
            )
        logger.info("Backup subido a R2: %s (%d bytes)", r2_key, size)

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Limpiar backups viejos
    deleted = _cleanup_old_backups(client)

    return {
        "ok": True,
        "r2_key": r2_key,
        "filename": filename,
        "size_bytes": size,
        "timestamp": now.isoformat(),
        "deleted_old": deleted,
    }


def _cleanup_old_backups(client) -> int:
    """Borra backups en R2 más viejos que BACKUP_RETAIN_DAYS. Retorna cantidad borrada."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKUP_RETAIN_DAYS)
    bucket  = _bucket()
    deleted = 0
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=BACKUP_PREFIX):
            for obj in page.get("Contents", []):
                if obj["LastModified"] < cutoff:
                    client.delete_object(Bucket=bucket, Key=obj["Key"])
                    logger.info("Backup viejo eliminado: %s", obj["Key"])
                    deleted += 1
    except Exception as e:
        logger.warning("Error limpiando backups viejos: %s", e)
    return deleted


def _pg_password(database_url: str) -> str:
    try:
        return urlparse(database_url).password or ""
    except Exception:
        return ""
