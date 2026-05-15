"""
Script de backup para Railway Cron Job.

Configurar en Railway como un servicio separado de tipo "Cron":
  - Comando: python backend/backup_cron.py
  - Schedule: 0 3 * * *   (todos los días a las 3am UTC)
  - Variables: DATABASE_URL, R2_*, BACKUP_ENABLED=true, SENTRY_DSN (opcional)

Si BACKUP_ENABLED no está seteado, el script termina sin hacer nada.
"""

import logging
import os
import sys

# Setup logging básico para el cron (sin el setup completo del servidor)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from services.backup_service import run_backup, BACKUP_ENABLED

    if not BACKUP_ENABLED:
        logger.info("BACKUP_ENABLED no está seteado — cron sin efecto. Setear en Railway cuando estén en producción.")
        sys.exit(0)

    # Inicializar Sentry si está configurado
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=sentry_dsn, environment=os.environ.get("RAILWAY_ENVIRONMENT", "production"))

    try:
        result = run_backup()
        logger.info("Backup OK: %s", result)
        sys.exit(0)
    except Exception as e:
        logger.error("Backup FALLÓ: %s", e, exc_info=True)
        if sentry_dsn:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            sentry_sdk.flush(timeout=5)
        sys.exit(1)


if __name__ == "__main__":
    # Asegurar que los imports del backend funcionen desde cualquier directorio
    import pathlib
    backend_dir = pathlib.Path(__file__).parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from dotenv import load_dotenv
    load_dotenv(backend_dir / ".env")
    load_dotenv(backend_dir.parent / ".env.local", override=True)

    main()
