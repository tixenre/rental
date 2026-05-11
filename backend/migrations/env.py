"""
Alembic env.py para Rambla Rental.

Lee `DATABASE_URL` desde el entorno (mismo que `backend/database.py`).
NO usa autogenerate — el proyecto no tiene modelos SQLAlchemy. Las
migraciones se escriben a mano con `op.execute(...)` o helpers de
`alembic.op` (create_table, add_column, etc.).

Para crear una migración nueva:
    cd backend
    alembic revision -m "agregar columna foo a equipos"

Para aplicar pendientes:
    alembic upgrade head

Para marcar el estado actual sin correr nada (brownfield):
    alembic stamp head
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Permitir importar `database` etc. desde el código del backend.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# .env.local / .env si existen (mismo loader que database.py)
try:
    from dotenv import load_dotenv
    for _name in (".env.local", ".env"):
        _f = BACKEND_ROOT / _name
        if _f.exists():
            load_dotenv(_f, override=False)
except ImportError:
    pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL del entorno tiene prioridad. Si no, fallback a localhost (dev).
db_url = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost/rambla_rental"
config.set_main_option("sqlalchemy.url", db_url)

# Sin modelos SQLAlchemy: target_metadata=None. Autogenerate no funciona,
# las migraciones se escriben a mano. Es lo deseado para este proyecto que
# usa psycopg2 directo.
target_metadata = None


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse — útil para revisar o aplicar manualmente."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica migraciones contra la BD configurada."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
