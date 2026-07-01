"""Taxonomía de equipos: etiquetas (tags) + categorías (#501 fase a, extraído de `core`).

Concentra la taxonomía del equipo, sacada del god-module en dos sub-cortes:
etiquetas (PR1) y categorías (PR2). Registra sus rutas
en el router compartido del paquete `routes.equipos`. Las reglas de gobernanza
viven en `services.categorias`.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel

from auth.guards import require_admin
from database import (
    get_db, row_to_dict, attach_tags, attach_categorias,
    MARCA_SUBQUERY,
)
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

class EtiquetasUpdate(BaseModel):
    # Lista ordenada de etiquetas MANUALES. Las auto (marca/modelo/nombre/categorías)
    # se regeneran solas, no las toques desde acá.
    etiquetas: list[str]


# ── Etiquetas por equipo (reemplaza todas) ────────────────────────────────────

@router.put("/equipos/{id}/etiquetas", status_code=200)
def set_etiquetas(id: int, data: EtiquetasUpdate, request: Request):
    """Reemplaza SOLO las etiquetas manuales del equipo. Las auto se preservan."""
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            # Borrar solo manuales; las auto siguen vivas.
            conn.execute(
                "DELETE FROM equipo_etiquetas WHERE equipo_id = %s AND origen = 'manual'",
                (id,),
            )
            for orden, nombre in enumerate(data.etiquetas):
                nombre = (nombre or "").strip()
                if not nombre:
                    continue
                conn.execute(
                    "INSERT INTO etiquetas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
                    (nombre,),
                )
                row = conn.execute(
                    "SELECT id FROM etiquetas WHERE nombre = %s", (nombre,)
                ).fetchone()
                if not row:
                    continue
                conn.execute("""
                    INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
                    VALUES (%s, %s, %s, 'manual')
                    ON CONFLICT (equipo_id, etiqueta_id)
                    DO UPDATE SET orden = EXCLUDED.orden, origen = 'manual'
                """, (id, row["id"], orden))
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            equipo = attach_tags(conn, [row_to_dict(row)])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


@router.get("/etiquetas")
def list_etiquetas(incluir_auto: int = Query(0)):
    """
    Lista etiquetas. Por defecto devuelve solo las que tienen al menos un uso
    MANUAL (las auto inflan demasiado). `incluir_auto=1` devuelve todo.
    """
    with get_db() as conn:
        if incluir_auto:
            rows = conn.execute("""
                SELECT et.nombre, COUNT(ee.equipo_id) AS total
                FROM etiquetas et
                LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
                GROUP BY et.id, et.nombre
                ORDER BY LOWER(et.nombre)
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT et.nombre, COUNT(ee.equipo_id) AS total
                FROM etiquetas et
                JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
                WHERE ee.origen = 'manual'
                GROUP BY et.id, et.nombre
                ORDER BY LOWER(et.nombre)
            """).fetchall()
        return [{"nombre": r["nombre"], "total": r["total"]} for r in rows]


class EtiquetaCreate(BaseModel):
    nombre:    str
    prioridad: Optional[int] = 100
    parent_id: Optional[int] = None


class EtiquetaPatch(BaseModel):
    nombre:    Optional[str] = None
    prioridad: Optional[int] = None
    parent_id: Optional[int] = None  # explícito None para "limpiar" no soportado vía PATCH; usar -1 para nullear
    set_parent_null: Optional[bool] = False


class EtiquetasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/etiquetas")
def admin_list_etiquetas(request: Request):
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT et.id, et.nombre, et.prioridad, et.parent_id,
                   COUNT(ee.equipo_id) AS total
            FROM etiquetas et
            LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
            GROUP BY et.id, et.nombre, et.prioridad, et.parent_id
            ORDER BY et.prioridad ASC, LOWER(et.nombre) ASC
        """).fetchall()
        return [
            {
                "id":        r["id"],
                "nombre":    r["nombre"],
                "prioridad": r["prioridad"],
                "parent_id": r["parent_id"],
                "total":     r["total"],
            }
            for r in rows
        ]


@router.post("/admin/etiquetas", status_code=201)
def admin_create_etiqueta(data: EtiquetaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    with get_db() as conn:
        try:
            # Validar parent: debe existir y ser raíz (forzar 2 niveles).
            if data.parent_id is not None:
                prow = conn.execute(
                    "SELECT id, parent_id FROM etiquetas WHERE id = %s", (data.parent_id,)
                ).fetchone()
                if not prow:
                    raise HTTPException(400, "parent_id no existe")
                if prow["parent_id"] is not None:
                    raise HTTPException(400, "Solo se permiten 2 niveles (el padre ya es subcategoría)")
            cur = conn.execute("""
                INSERT INTO etiquetas (nombre, prioridad, parent_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (nombre) DO UPDATE
                    SET prioridad = EXCLUDED.prioridad,
                        parent_id = EXCLUDED.parent_id
                RETURNING id, nombre, prioridad, parent_id
            """, (nombre, data.prioridad or 100, data.parent_id))
            row = cur.fetchone()
            conn.commit()
            return {
                "id": row["id"], "nombre": row["nombre"],
                "prioridad": row["prioridad"], "parent_id": row["parent_id"],
                "total": 0,
            }
        except HTTPException:
            conn.rollback(); raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(400, str(e))


@router.patch("/admin/etiquetas/{eid}")
def admin_update_etiqueta(eid: int, patch: EtiquetaPatch, request: Request):
    require_admin(request)
    sets, vals = [], []
    if patch.nombre is not None:
        sets.append("nombre = %s"); vals.append(patch.nombre.strip())
    if patch.prioridad is not None:
        sets.append("prioridad = %s"); vals.append(int(patch.prioridad))
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == eid:
            raise HTTPException(400, "Una etiqueta no puede ser su propio padre")
        # Validar que el padre exista y sea raíz.
        with get_db() as conn0:
            prow = conn0.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = %s", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            # Verificar que esta etiqueta no tenga hijos (sino bajaríamos un nivel raíz).
            chrow = conn0.execute(
                "SELECT 1 FROM etiquetas WHERE parent_id = %s LIMIT 1", (eid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta etiqueta tiene hijos; no puede convertirse en hija")
        sets.append("parent_id = %s"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    with get_db() as conn:
        vals.append(eid)
        conn.execute(f"UPDATE etiquetas SET {', '.join(sets)} WHERE id = %s", tuple(vals))
        conn.commit()
        return {"ok": True}


@router.delete("/admin/etiquetas/{eid}", status_code=204)
def admin_delete_etiqueta(eid: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        # ON DELETE CASCADE en equipo_etiquetas + SET NULL en parent_id de hijos.
        conn.execute("DELETE FROM etiquetas WHERE id = %s", (eid,))
        conn.commit()


@router.post("/admin/etiquetas/reorder")
def admin_reorder_etiquetas(payload: EtiquetasReorder, request: Request):
    require_admin(request)
    with get_db() as conn:
        for idx, eid in enumerate(payload.ids):
            conn.execute(
                "UPDATE etiquetas SET prioridad = %s WHERE id = %s",
                ((idx + 1) * 10, eid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}


class CategoriasUpdate(BaseModel):
    # Lista de IDs de categorías hoja (o raíz) asignadas al equipo.
    categoria_ids: list[int]


@router.put("/equipos/{id}/categorias", status_code=200)
def set_categorias(id: int, data: CategoriasUpdate, request: Request):
    """
    Reemplaza la lista de categorías asignadas al equipo y regenera auto-tags
    (porque los nombres de categoría alimentan la bolsa de etiquetas auto).
    """
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            asignar_categorias(conn, id, data.categoria_ids)
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            equipo = attach_tags(conn, [row_to_dict(row)])[0]
            equipo = attach_categorias(conn, [equipo])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


# ── Etiquetas / Categorías ───────────────────────────────────────────────────


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


# ── Admin: gestión de etiquetas / categorías ─────────────────────────────────


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


# ── Admin: clasificación automática (removida — las categorías se asignan manualmente) ─
