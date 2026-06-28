"""
Configuración global de pytest.

- Agrega `backend/` al sys.path para que los tests importen como en producción.
- Setea env vars dummy necesarias para que los imports no fallen:
  · `SECRET_KEY` — `routes/auth.py` la exige en import time.
  · `ADMIN_EMAILS` — fija un admin conocido para los tests de guards.
"""

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Setear ANTES de cualquier import de módulos del proyecto.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only-in-tests")
os.environ.setdefault("ADMIN_EMAILS", "admin@test.com")
# Kill-switch del scheduler de recordatorios: el thread arranca al importar main
# (start_scheduler) y sondea la DB en runtime; en tests no queremos un thread
# tocando Postgres. Los tests del scheduler borran esta env para probar el arranque.
os.environ.setdefault("REMINDERS_SCHEDULER_DISABLED", "1")
# Pool de DB: cuánto espera `getconn()` por una conexión libre. El job
# `python-tests` corre SIN Postgres (no setea DATABASE_URL) y sus tests de
# contrato golpean handlers reales a propósito (verifican ruteo/guards; aceptan
# un 500). Sin acotar el timeout, cada request colgaba los 30s default del pool
# antes del 500 → ~150 requests = ~38 min. Cuando NO hay DATABASE_URL (= sin DB
# real) lo bajamos a 1s: el 500 sale igual, pero al toque. El job de integración
# SÍ setea DATABASE_URL → ahí no tocamos nada (queda en 30s, comportamiento
# idéntico al de hoy). Prod tampoco (conftest no corre). Override explícito gana.
if not os.environ.get("DATABASE_URL"):
    os.environ.setdefault("DB_POOL_TIMEOUT", "1")


@pytest.fixture(autouse=True)
def _reset_buffer_cache():
    """El motor de reservas cachea `buffer_horas_alquiler` a nivel proceso. Los
    tests usan FakeConns con distintos buffers en el mismo proceso → reseteamos
    el cache antes y después de cada test para que no se arrastre un valor."""
    from reservas import invalidate_buffer_cache

    invalidate_buffer_cache()
    yield
    invalidate_buffer_cache()
