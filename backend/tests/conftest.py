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

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Setear ANTES de cualquier import de módulos del proyecto.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only-in-tests")
os.environ.setdefault("ADMIN_EMAILS", "admin@test.com")
