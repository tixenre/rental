"""Taxonomía de equipos: categorías (#501 fase a, extraído de `core`).

El sistema de etiquetas (tags libres) se eliminó (#1163 F5) — la búsqueda de
equipos se deriva de specs estructurados (services/specs/) en vez de tags
manuales; nada dependía de ellas salvo mostrarlas. Registra las rutas de
categorías en el router compartido del paquete `routes.equipos`. Las reglas
de gobernanza viven en `services.categorias`.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel

from auth.guards import require_admin
from database import (
    get_db, row_to_dict, attach_categorias,
    MARCA_SUBQUERY,
)
from rate_limit import limiter, ADMIN_WRITE_LIMIT
from services.categorias import (
    crear,
    actualizar,
    eliminar,
    reordenar,
    asignar_categorias,
    listar_arbol_publico,
    listar_arbol_publico_flat,
    listar_arbol_admin,
)
from services.categorias.errors import (
    ErrorValidacion, CategoriaNoExiste, NombreDuplicado,
)
from routes.equipos.core import router

logger = logging.getLogger(__name__)


class CategoriasUpdate(BaseModel):
    # Lista de IDs de categorías hoja (o raíz) asignadas al equipo.
    categoria_ids: list[int]


@router.put("/equipos/{id}/categorias", status_code=200)
@limiter.limit(ADMIN_WRITE_LIMIT)
def set_categorias(id: int, data: CategoriasUpdate, request: Request):
    """Reemplaza la lista de categorías asignadas al equipo."""
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            asignar_categorias(conn, id, data.categoria_ids)
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            equipo = attach_categorias(conn, [row_to_dict(row)])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


# ── Categorías ────────────────────────────────────────────────────────────────


@router.get("/categorias")
def get_categorias(flat: int = Query(0)):
    """
    Devuelve el árbol de categorías desde la tabla `categorias`.
    `total` cuenta equipos asignados a esa categoría o a cualquier descendiente
    (vía `equipo_categorias`).
    """
    with get_db() as conn:
        if flat:
            return listar_arbol_publico_flat(conn)
        return listar_arbol_publico(conn)


# ── Admin: CRUD de categorías (árbol propio) ─────────────────────────────────

class CategoriaCreate(BaseModel):
    nombre:    str
    prioridad: Optional[int] = 100
    parent_id: Optional[int] = None


class CategoriaPatch(BaseModel):
    nombre:    Optional[str] = None
    prioridad: Optional[int] = None
    parent_id: Optional[int] = None
    set_parent_null: Optional[bool] = False
    visible:   Optional[bool] = None
    nombre_publico_template: Optional[str] = None


class CategoriasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/categorias")
def admin_list_categorias(request: Request):
    require_admin(request)
    with get_db() as conn:
        return listar_arbol_admin(conn)


@router.post("/admin/categorias", status_code=201)
@limiter.limit(ADMIN_WRITE_LIMIT)
def admin_create_categoria(data: CategoriaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    with get_db() as conn:
        try:
            result = crear(conn, nombre, data.prioridad or 100, data.parent_id)
            conn.commit()
            return result
        except NombreDuplicado as e:
            conn.rollback()
            raise HTTPException(409, str(e))
        except ErrorValidacion as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception as e:
            conn.rollback()
            raise HTTPException(400, str(e))


@router.patch("/admin/categorias/{cid}")
@limiter.limit(ADMIN_WRITE_LIMIT)
def admin_update_categoria(cid: int, patch: CategoriaPatch, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            result = actualizar(conn, cid,
                                nombre=patch.nombre,
                                prioridad=patch.prioridad,
                                visible=patch.visible,
                                parent_id=patch.parent_id,
                                set_parent_null=patch.set_parent_null,
                                nombre_publico_template=patch.nombre_publico_template)
            conn.commit()
            return result
        except CategoriaNoExiste as e:
            conn.rollback()
            raise HTTPException(404, str(e))
        except NombreDuplicado as e:
            conn.rollback()
            raise HTTPException(409, str(e))
        except ErrorValidacion as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception as e:
            conn.rollback()
            logger.error("Error en admin_update_categoria(cid=%s): %s", cid, e, exc_info=True)
            raise HTTPException(500, "Error al actualizar categoría — ver logs del servidor")


@router.delete("/admin/categorias/{cid}", status_code=204)
@limiter.limit(ADMIN_WRITE_LIMIT)
def admin_delete_categoria(cid: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            eliminar(conn, cid)
            conn.commit()
        except CategoriaNoExiste as e:
            conn.rollback()
            raise HTTPException(404, str(e))
        except ErrorValidacion as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception as e:
            conn.rollback()
            logger.error("Error en admin_delete_categoria(cid=%s): %s", cid, e, exc_info=True)
            raise HTTPException(500, "Error al eliminar categoría — ver logs del servidor")


@router.post("/admin/categorias/reorder")
@limiter.limit(ADMIN_WRITE_LIMIT)
def admin_reorder_categorias(payload: CategoriasReorder, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            count = reordenar(conn, payload.ids)
            conn.commit()
            return {"ok": True, "count": count}
        except CategoriaNoExiste as e:
            conn.rollback()
            raise HTTPException(404, str(e))
        except Exception as e:
            conn.rollback()
            logger.error("Error en admin_reorder_categorias: %s", e, exc_info=True)
            raise HTTPException(500, "Error al reordenar categorías — ver logs del servidor")
