"""Paquete del router de equipos (#179 / #501 fase a).

El god-module `routes/equipos.py` (3.658 líneas) se está partiendo en submódulos
por concern, move-verbatim. Este `__init__` mantiene la API pública estable:
re-exporta los nombres que consumen `main.py` (el `router`) y los tests (que
alcanzan modelos y helpers internos), para no romper imports existentes.

El router es UNO solo (creado en `core`); cada submódulo que se extraiga registra
sus rutas sobre ese mismo router al importarse → los paths quedan idénticos.
"""
from routes.equipos.core import (
    router,
    ESTADOS_RESERVADO,
    EquipoCreate,
    EquipoUpdate,
    FichaUpdate,
    KitItem,
    UploadFotoFromUrlInput,
    _attach_disponibilidad,
    _crea_ciclo_kit,
    _normalize_fecha_compra,
    admin_clasificar,
    admin_dashboard_uso,
    admin_equipos_sin_serie,
)

# `__all__` declara la superficie pública re-exportada (y le dice a ruff que
# estos imports no están "sin usar": son re-exports a propósito).
__all__ = [
    "router",
    "ESTADOS_RESERVADO",
    "EquipoCreate",
    "EquipoUpdate",
    "FichaUpdate",
    "KitItem",
    "UploadFotoFromUrlInput",
    "_attach_disponibilidad",
    "_crea_ciclo_kit",
    "_normalize_fecha_compra",
    "admin_clasificar",
    "admin_dashboard_uso",
    "admin_equipos_sin_serie",
]

# Submódulos extraídos de `core`: importarlos registra sus rutas sobre el `router`
# compartido (paths idénticos). El tuple los mantiene "usados" para ruff.
from routes.equipos import mantenimiento as _mantenimiento

_SUBMODULOS = (_mantenimiento,)
