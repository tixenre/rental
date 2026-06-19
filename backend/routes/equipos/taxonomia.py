"""Etiquetas (tags) de equipos (#501 fase a — PR1 de taxonomía, extraído de `core`).

Primer sub-corte de taxonomía: etiquetas manuales por equipo + el catálogo de
etiquetas (público + admin CRUD). Registra sus rutas en el router compartido del
paquete `routes.equipos`. Categorías y el clasificador automático (`_propose_tags`,
`_expand_to_ancestors`, `admin_clasificar`) quedan en `core` y se extraen en el PR2.
"""
from typing import Optional

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db, row_to_dict, attach_tags, MARCA_SUBQUERY
from routes.equipos.core import router

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
            if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            # Borrar solo manuales; las auto siguen vivas.
            conn.execute(
                "DELETE FROM equipo_etiquetas WHERE equipo_id = ? AND origen = 'manual'",
                (id,),
            )
            for orden, nombre in enumerate(data.etiquetas):
                nombre = (nombre or "").strip()
                if not nombre:
                    continue
                conn.execute(
                    "INSERT INTO etiquetas (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING",
                    (nombre,),
                )
                row = conn.execute(
                    "SELECT id FROM etiquetas WHERE nombre = ?", (nombre,)
                ).fetchone()
                if not row:
                    continue
                conn.execute("""
                    INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
                    VALUES (?, ?, ?, 'manual')
                    ON CONFLICT (equipo_id, etiqueta_id)
                    DO UPDATE SET orden = EXCLUDED.orden, origen = 'manual'
                """, (id, row["id"], orden))
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=?", (id,)).fetchone()
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
                    "SELECT id, parent_id FROM etiquetas WHERE id = ?", (data.parent_id,)
                ).fetchone()
                if not prow:
                    raise HTTPException(400, "parent_id no existe")
                if prow["parent_id"] is not None:
                    raise HTTPException(400, "Solo se permiten 2 niveles (el padre ya es subcategoría)")
            cur = conn.execute("""
                INSERT INTO etiquetas (nombre, prioridad, parent_id)
                VALUES (?, ?, ?)
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
        sets.append("nombre = ?"); vals.append(patch.nombre.strip())
    if patch.prioridad is not None:
        sets.append("prioridad = ?"); vals.append(int(patch.prioridad))
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == eid:
            raise HTTPException(400, "Una etiqueta no puede ser su propio padre")
        # Validar que el padre exista y sea raíz.
        with get_db() as conn0:
            prow = conn0.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = ?", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            # Verificar que esta etiqueta no tenga hijos (sino bajaríamos un nivel raíz).
            chrow = conn0.execute(
                "SELECT 1 FROM etiquetas WHERE parent_id = ? LIMIT 1", (eid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta etiqueta tiene hijos; no puede convertirse en hija")
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    with get_db() as conn:
        vals.append(eid)
        conn.execute(f"UPDATE etiquetas SET {', '.join(sets)} WHERE id = ?", tuple(vals))
        conn.commit()
        return {"ok": True}


@router.delete("/admin/etiquetas/{eid}", status_code=204)
def admin_delete_etiqueta(eid: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        # ON DELETE CASCADE en equipo_etiquetas + SET NULL en parent_id de hijos.
        conn.execute("DELETE FROM etiquetas WHERE id = ?", (eid,))
        conn.commit()


@router.post("/admin/etiquetas/reorder")
def admin_reorder_etiquetas(payload: EtiquetasReorder, request: Request):
    require_admin(request)
    with get_db() as conn:
        for idx, eid in enumerate(payload.ids):
            conn.execute(
                "UPDATE etiquetas SET prioridad = ? WHERE id = ?",
                ((idx + 1) * 10, eid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
