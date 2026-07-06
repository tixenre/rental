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
    _normalize_fecha_compra,
)
# `_attach_disponibilidad` moved to services.catalogo (puerta única); re-exportado
# para back-compat con tests que lo importan desde routes.equipos.
from services.catalogo.proyeccion import _attach_disponibilidad

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
    "admin_dashboard_uso",
    "admin_equipos_sin_serie",
]

# Submódulos extraídos de `core`. Cada uno registra sus rutas sobre el `router`
# compartido al importarse (paths idénticos). Los que re-exportan símbolos que
# tests/main consumen se importan por su símbolo; los que no, vía el tuple
# `_SUBMODULOS` (que también los mantiene "usados" para ruff).
from routes.equipos.dashboard import admin_dashboard_uso, admin_equipos_sin_serie
from routes.equipos.ficha import FichaUpdate
from routes.equipos.fotos import UploadFotoFromUrlInput
from routes.equipos.kit import KitItem, _crea_ciclo_kit
# `disponibilidad` NO se importa acá — `core.py` ya la importa en la posición
# exacta donde importa (antes de registrar su ruta wildcard `/equipos/{id_or_slug}`,
# ver el comentario ahí). Importarla también acá sería inofensivo (Python
# cachea el módulo) pero confuso — dejaría dos lugares "responsables" del orden.
# `busqueda_fotos`/`specs_extraccion` sí pueden ir acá — sus paths no tienen
# el problema de shadowing de `disponibilidad` (ninguno es un wildcard).
from routes.equipos import busqueda_fotos as _busqueda_fotos
from routes.equipos import specs_extraccion as _specs_extraccion
from routes.equipos import mantenimiento as _mantenimiento
from routes.equipos import taxonomia as _taxonomia

_SUBMODULOS = (_busqueda_fotos, _specs_extraccion, _mantenimiento, _taxonomia)
