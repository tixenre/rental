"""Paquete del router de specs (#501 — split del god-module `routes/specs.py`).

`main.py` importa solo `router`. El router es UNO (creado en `core`); cada
submódulo extraído registra sus rutas sobre ese mismo router al importarse.
"""
from routes.specs.core import router

__all__ = ["router"]

# Submódulos extraídos de `core` (registran sus rutas sobre el `router` al
# importarse; el tuple los mantiene "usados" para ruff).
from routes.specs import equipo_specs as _equipo_specs

_SUBMODULOS = (_equipo_specs,)
