"""Ficha por equipo (descripción / notas / contenido incluido) — #501 fase a.

Extraído de `core` (move-verbatim). Registra sus rutas sobre el router compartido.
`FichaUpdate` lo importan tests vía el `__init__` del paquete (re-export). Las
specs físicas NO viven acá (van por /admin/equipos/{id}/specs desde Fase F).
"""
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from auth.guards import require_admin
from database import get_db, row_to_dict
from services.nombre_service import actualizar_nombres_de
from routes.equipos.core import router


class FichaUpdate(BaseModel):
    """Update parcial de equipo_fichas. Las specs físicas (montura/
    formato/resolucion/peso/dimensiones/alimentacion) viven en
    equipo_specs desde Fase F — actualizar vía PUT /admin/equipos/{id}/specs.
    `specs_json` y `raw_json` eliminados en Fase E."""
    descripcion:   Optional[str] = None
    notas:         Optional[str] = None
    keywords_json: Optional[str] = None
    nombre_publico_template: Optional[str] = None
    # Listas y multimedia del enriquecimiento (no son specs estructuradas).
    # `incluye_json` dropeado (F5): el "qué incluye" deriva de kit_componentes.
    conectividad_json:   Optional[str]   = None
    compatible_con_json: Optional[str]   = None
    video_url:           Optional[str]   = None
    precio_bh_usd:       Optional[float] = None
    fuente_url:          Optional[str]   = None
    fuente_titulo:       Optional[str]   = None
    enriquecido_fuente:  Optional[str]   = None
    # B1 #635: contenido incluido (dim. 3) — JSON de [{nombre, cantidad, foto_url?}]
    contenido_incluido_json: Optional[str] = None

    from pydantic import field_validator as _fv
    import json as _json

    @_fv("contenido_incluido_json")
    @classmethod
    def _validar_contenido_incluido(cls, v):
        import json as _j
        if v is None:
            return v
        try:
            items = _j.loads(v)
        except Exception:
            raise ValueError("contenido_incluido_json: JSON inválido")
        if not isinstance(items, list):
            raise ValueError("contenido_incluido_json: debe ser una lista")
        if len(items) > 100:
            raise ValueError("contenido_incluido_json: máximo 100 ítems")
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"ítem {idx}: debe ser un objeto")
            nombre = item.get("nombre", "")
            if not isinstance(nombre, str) or not nombre.strip():
                raise ValueError(f"ítem {idx}: 'nombre' no puede estar vacío")
            cantidad = item.get("cantidad", 1)
            if not isinstance(cantidad, int) or not (1 <= cantidad <= 999):
                raise ValueError(f"ítem {idx}: 'cantidad' debe ser un entero entre 1 y 999")
        return v


@router.get("/equipos/{id}/ficha")
def get_ficha(id: int):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = %s", (id,)
        ).fetchone()
        base = row_to_dict(row) if row else {
            "equipo_id": id, "descripcion": None, "notas": None,
            "keywords_json": None, "nombre_publico_template": None,
        }
        # Las specs estructuradas se sirven por separado vía
        # GET /admin/equipos/{id}/specs (post-PR #456). Este endpoint
        # devuelve sólo los campos de equipo_fichas (descripción, notas,
        # nombre_publico_template, keywords_json + columnas legacy que el
        # catálogo público todavía usa).
        return base


@router.put("/equipos/{id}/ficha")
def upsert_ficha(id: int, data: FichaUpdate, request: Request):
    """
    PATCH-style upsert: solo actualiza columnas que vinieron en el body
    (no las nullea si el cliente no las mandó). Esto evita que enriquecer con
    IA borre montura/formato/resolución existentes.
    """
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")

            patch = data.model_dump(exclude_unset=True)
            # Inserta una fila vacía si no existe (para que el UPDATE encuentre algo).
            conn.execute(
                "INSERT INTO equipo_fichas (equipo_id) VALUES (%s) ON CONFLICT(equipo_id) DO NOTHING",
                (id,),
            )
            if patch:
                set_clause = ", ".join(f"{k} = %s" for k in patch)
                set_clause += ", updated_at = CURRENT_TIMESTAMP"
                conn.execute(
                    f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = %s",
                    list(patch.values()) + [id],
                )
                # Hook: si cambió el template de nombre, recalcular nombre_publico.
                # (Post-Fase F las specs físicas viven en equipo_specs, no en
                # equipo_fichas — cambiarlas no pasa por este endpoint.)
                if "nombre_publico_template" in patch:
                    try:
                        actualizar_nombres_de(conn, id, commit=False)
                    except Exception:
                        pass
            conn.commit()
            row = conn.execute(
                "SELECT * FROM equipo_fichas WHERE equipo_id = %s", (id,)
            ).fetchone()
            return row_to_dict(row)
        except Exception:
            conn.rollback()
            raise
