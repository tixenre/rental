"""routes/specs/core.py — spine del paquete `routes.specs` (#501).

Concentra lo compartido del paquete: el `router` único (sobre el que cada
submódulo registra sus rutas al importarse) y el guard `_require_admin`. Las
superficies de specs viven en submódulos (ver `__init__`): `definitions`
(catálogo), `equipo_specs`, `compatibilidad`, `nombres`, `templates`,
`diagnostico`.
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

# Guard CANÓNICO reexportado bajo el nombre del paquete (`_require_admin`): valida
# que el email de la sesión esté en ADMIN_EMAILS (is_admin_email → 403), no solo
# que exista una sesión. Una copia local que solo chequeara `if not session`
# dejaba pasar a cualquier logueado —incluido un CLIENTE del portal, que mintea la
# misma cookie `session`— → escalada de privilegios. Regresión: test_admin_guard_canonico.
from admin_guard import require_admin as _require_admin  # noqa: F401  (re-export: lo consumen los submódulos del paquete specs)


router = APIRouter()


# ── Modelos del flujo de "propuestas de specs" (skill gear-compatibility) ─
# DEAD CODE: ningún endpoint los consume hoy. El skill documenta endpoints que
# no existen (`/admin/specs/proponer`, `/admin/specs/propuestas`). La decisión
# (construir el flujo vs borrar estos modelos + ajustar el skill) está pendiente
# en #895 — se dejan acá hasta que el dueño resuelva.

class PropuestaInput(BaseModel):
    # Una propuesta del skill resolver. tipo determina el shape del payload:
    # - enum_option: {spec_def_id, options: [str]}
    # - spec_nueva: {spec_key, label, tipo, unidad?, enum_options?, es_compatibilidad?, compatibilidad_modo?, razon}
    # - merge_specs: {keep_spec_def_id, merge_spec_def_ids: [int], razon}
    tipo: str   # "enum_option" | "spec_nueva" | "merge_specs"
    payload: dict
    origen: Optional[str] = None    # ej. "gear-compatibility skill v1"
    confianza: Optional[float] = None


class PropuestasBulkInput(BaseModel):
    items: list[PropuestaInput]
