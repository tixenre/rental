"""
routes/equipos.py — CRUD de equipos, kits, etiquetas, categorías y fichas.
"""

import calendar as _cal
import datetime
from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from database import (
    get_db, row_to_dict, attach_tags, attach_kit, attach_categorias,
    regenerate_auto_tags,
)
from routes.auth import get_session

router = APIRouter()


# ── Modelos ──────────────────────────────────────────────────────────────────

class EquipoCreate(BaseModel):
    nombre:           str
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         int             = 1
    precio_jornada:   Optional[int]   = None   # precio diario de alquiler (ARS)
    precio_usd:       Optional[float] = None   # valor de mercado (USD)
    roi_pct:          Optional[float] = None   # retorno % (ej: 2.0 → precio = valor*0.02)
    valor_reposicion: Optional[float] = None   # valor para seguro (USD)
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = "Rambla"
    visible_catalogo: Optional[int]   = 1
    estado:           Optional[str]   = "operativo"   # operativo / en_mantenimiento / fuera_servicio


class EquipoUpdate(BaseModel):
    nombre:           Optional[str]   = None
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         Optional[int]   = None
    precio_jornada:   Optional[int]   = None
    precio_usd:       Optional[float] = None
    roi_pct:          Optional[float] = None
    valor_reposicion: Optional[float] = None
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = None
    visible_catalogo: Optional[int]   = None
    estado:           Optional[str]   = None


class FichaUpdate(BaseModel):
    descripcion: Optional[str] = None
    notas:       Optional[str] = None
    specs_json:  Optional[str] = None


class KitItem(BaseModel):
    componente_id: int
    cantidad:      int = 1


class EtiquetasUpdate(BaseModel):
    # Lista ordenada de etiquetas MANUALES. Las auto (marca/modelo/nombre/categorías)
    # se regeneran solas, no las toques desde acá.
    etiquetas: list[str]


class CategoriasUpdate(BaseModel):
    # Lista de IDs de categorías hoja (o raíz) asignadas al equipo.
    categoria_ids: list[int]


# ── Disponibilidad en tiempo real ────────────────────────────────────────────

@router.get("/equipos/afuera")
def equipos_afuera():
    """
    Devuelve los equipos actualmente retirados (pedidos en estado 'retirado'
    con fecha_hasta >= hoy), con cantidad afuera y fecha de devolución.
    Respuesta: { "equipo_id": { cantidad_afuera, stock_total, devuelve, pedidos } }
    """
    conn  = get_db()
    today = datetime.date.today().isoformat()
    try:
        rows = conn.execute("""
            SELECT
                pi.equipo_id,
                e.cantidad                                              AS stock_total,
                SUM(pi.cantidad)                                        AS cantidad_afuera,
                MIN(p.fecha_hasta)                                      AS devuelve_pronto,
                MAX(p.fecha_hasta)                                      AS devuelve_ultimo,
                STRING_AGG(
                    COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre),
                    ', '
                )                                                       AS clientes
            FROM alquiler_items pi
            JOIN alquileres  p ON p.id  = pi.pedido_id
            JOIN equipos  e ON e.id  = pi.equipo_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado    = 'retirado'
              AND p.fecha_hasta >= ?
            GROUP BY pi.equipo_id, e.cantidad
        """, (today,)).fetchall()
        return {str(r["equipo_id"]): row_to_dict(r) for r in rows}
    finally:
        conn.close()


# ── Rutas de equipos ─────────────────────────────────────────────────────────

@router.get("/equipos")
def list_equipos(
    request:       Request,
    q:             Optional[str]  = Query(None),
    etiqueta:      Optional[str]  = Query(None),
    categoria:     Optional[str]  = Query(None),
    solo_visibles: Optional[bool] = Query(None),
    page:          int = Query(1, ge=1),
    per_page:      int = Query(200, ge=1, le=500),
):
    conn   = get_db()
    offset = (page - 1) * per_page
    base_sql = "FROM equipos e WHERE 1=1"
    params: list = []

    is_admin = bool(get_session(request))
    if solo_visibles or not is_admin:
        base_sql += " AND e.visible_catalogo = 1 AND e.estado != 'fuera_servicio'"
    if q:
        base_sql += " AND (e.nombre LIKE ? OR e.marca LIKE ? OR e.modelo LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if categoria:
        # Filtro recursivo: si es padre, incluye descendientes (árbol de `categorias`).
        # Acepta id numérico o nombre.
        try:
            cat_id_int = int(categoria)
            base_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM categorias WHERE id = ?
                        UNION ALL
                        SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                    )
                    SELECT id FROM sub
                )
              )"""
            params.append(cat_id_int)
        except (TypeError, ValueError):
            base_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM categorias WHERE nombre = ?
                        UNION ALL
                        SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                    )
                    SELECT id FROM sub
                )
              )"""
            params.append(categoria)
    if etiqueta:
        # Filtro plano por nombre de etiqueta (la bolsa ya no es jerárquica).
        base_sql += """
          AND e.id IN (
            SELECT ee.equipo_id FROM equipo_etiquetas ee
            JOIN etiquetas et ON et.id = ee.etiqueta_id
            WHERE LOWER(et.nombre) = LOWER(?)
          )"""
        params.append(etiqueta)

    try:
        total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT e.* {base_sql} ORDER BY e.nombre LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        equipos = [row_to_dict(r) for r in rows]
        equipos = attach_tags(conn, equipos)
        equipos = attach_kit(conn, equipos)
        equipos = attach_categorias(conn, equipos)
        return {"total": total, "page": page, "per_page": per_page, "items": equipos}
    finally:
        conn.close()


@router.get("/equipos/{id}")
def get_equipo(id: int):
    conn = get_db()
    try:
        row  = conn.execute("SELECT * FROM equipos WHERE id = ?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        kit = conn.execute("""
            SELECT kc.componente_id, kc.cantidad, e.nombre, e.marca, e.foto_url
            FROM kit_componentes kc JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?  ORDER BY e.nombre
        """, (id,)).fetchall()
        equipo["kit"] = [row_to_dict(r) for r in kit]
        return equipo
    finally:
        conn.close()


@router.post("/equipos", status_code=201)
def create_equipo(data: EquipoCreate):
    conn = get_db()
    try:
        cur  = conn.execute("""
            INSERT INTO equipos (nombre, marca, modelo, cantidad,
                                 precio_jornada, precio_usd, roi_pct,
                                 valor_reposicion, foto_url, fecha_compra,
                                 serie, bh_url, dueno, visible_catalogo, estado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (data.nombre, data.marca, data.modelo, data.cantidad,
              data.precio_jornada, data.precio_usd, data.roi_pct,
              data.valor_reposicion, data.foto_url, data.fecha_compra,
              data.serie, data.bh_url, data.dueno, data.visible_catalogo, data.estado))
        conn.commit()
        new_id = cur.lastrowid
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (new_id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/equipos/{id}")
def update_equipo(id: int, data: EquipoUpdate):
    conn     = get_db()
    try:
        existing = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Equipo no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
        # Registrar cambio de precio si cambió
        if "precio_jornada" in updates and updates["precio_jornada"] != existing["precio_jornada"]:
            conn.execute(
                "INSERT INTO equipo_precio_historial (equipo_id, precio_jornada) VALUES (?,?)",
                (id, updates["precio_jornada"]),
            )
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        conn.execute(f"UPDATE equipos SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}", status_code=204)
def delete_equipo(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute("DELETE FROM equipos WHERE id=?", (id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Ficha por equipo ─────────────────────────────────────────────────────────

@router.get("/equipos/{id}/ficha")
def get_ficha(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)
        ).fetchone()
        if row:
            return row_to_dict(row)
        return {"equipo_id": id, "descripcion": None, "notas": None, "specs_json": None}
    finally:
        conn.close()


@router.put("/equipos/{id}/ficha")
def upsert_ficha(id: int, data: FichaUpdate):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute("""
            INSERT INTO equipo_fichas (equipo_id, descripcion, notas, specs_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(equipo_id) DO UPDATE SET
                descripcion = excluded.descripcion,
                notas       = excluded.notas,
                specs_json  = excluded.specs_json,
                updated_at  = CURRENT_TIMESTAMP
        """, (id, data.descripcion, data.notas, data.specs_json))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Historial de alquileres por equipo ───────────────────────────────────────

@router.get("/equipos/{id}/historial")
def get_equipo_historial(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        rows = conn.execute("""
            SELECT
                p.id, p.numero_pedido, p.estado,
                p.fecha_desde, p.fecha_hasta,
                COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre) AS cliente,
                pi.cantidad, pi.precio_jornada AS precio_item,
                GREATEST(1, DATE_PART('day', LEFT(p.fecha_hasta, 10)::TIMESTAMP - LEFT(p.fecha_desde, 10)::TIMESTAMP))::INTEGER AS dias
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE pi.equipo_id = ?
            ORDER BY p.fecha_desde DESC
        """, (id,)).fetchall()

        items      = [row_to_dict(r) for r in rows]
        total_dias = sum(r["dias"] or 1 for r in items)
        total_rev  = sum((r["precio_item"] or 0) * (r["cantidad"] or 1) * (r["dias"] or 1) for r in items)

        return {
            "historial": items,
            "stats": {
                "total_alquileres": len(items),
                "total_dias":       total_dias,
                "total_revenue":    total_rev,
                "ultimo_alquiler":  items[0]["fecha_desde"] if items else None,
            },
        }
    finally:
        conn.close()


# ── Kit / Componentes ────────────────────────────────────────────────────────

@router.get("/equipos/{id}/kit")
def get_kit(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT kc.id, kc.componente_id, kc.cantidad,
                   e.nombre, e.marca, e.modelo, e.foto_url, e.visible_catalogo
            FROM kit_componentes kc
            JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?
            ORDER BY e.nombre
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/equipos/{id}/kit", status_code=201)
def add_kit_item(id: int, data: KitItem):
    if id == data.componente_id:
        raise HTTPException(400, "Un equipo no puede ser componente de sí mismo")
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (data.componente_id,)).fetchone():
            raise HTTPException(404, "Componente no encontrado")
        try:
            conn.execute("""
                INSERT INTO kit_componentes (equipo_id, componente_id, cantidad)
                VALUES (?,?,?)
                ON CONFLICT(equipo_id, componente_id) DO UPDATE SET cantidad=excluded.cantidad
            """, (id, data.componente_id, data.cantidad))
            conn.commit()
        except Exception as e:
            raise HTTPException(400, str(e))
        return get_kit(id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}/kit/{componente_id}", status_code=204)
def remove_kit_item(id: int, componente_id: int):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM kit_componentes WHERE equipo_id=? AND componente_id=?",
            (id, componente_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Historial de precios ─────────────────────────────────────────────────────

@router.get("/equipos/{id}/precio-historial")
def get_precio_historial(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT precio_jornada, changed_at
            FROM equipo_precio_historial
            WHERE equipo_id = ?
            ORDER BY changed_at DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── Etiquetas por equipo (reemplaza todas) ────────────────────────────────────

@router.put("/equipos/{id}/etiquetas", status_code=200)
def set_etiquetas(id: int, data: EtiquetasUpdate):
    """Reemplaza SOLO las etiquetas manuales del equipo. Las auto se preservan."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
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
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Categorías por equipo ────────────────────────────────────────────────────

@router.put("/equipos/{id}/categorias", status_code=200)
def set_categorias(id: int, data: CategoriasUpdate):
    """
    Reemplaza la lista de categorías asignadas al equipo y regenera auto-tags
    (porque los nombres de categoría alimentan la bolsa de etiquetas auto).
    """
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s", (id,))
        for orden, cid in enumerate(data.categoria_ids):
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            conn.execute("""
                INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                VALUES (%s, %s, %s)
                ON CONFLICT (equipo_id, categoria_id) DO UPDATE SET orden = EXCLUDED.orden
            """, (id, cid_int, orden))
        regenerate_auto_tags(conn, id)
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_categorias(conn, [equipo])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Etiquetas / Categorías ───────────────────────────────────────────────────

@router.get("/etiquetas")
def list_etiquetas():
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT et.nombre, COUNT(ee.equipo_id) as total
            FROM etiquetas et
            LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
            GROUP BY et.id ORDER BY et.nombre
        """).fetchall()
        return [{"nombre": r["nombre"], "total": r["total"]} for r in rows]
    finally:
        conn.close()


@router.get("/categorias")
def get_categorias(flat: int = Query(0)):
    """
    Devuelve el árbol de categorías desde la tabla `categorias`.
    `total` cuenta equipos asignados a esa categoría o a cualquier descendiente
    (vía `equipo_categorias`).
    """
    conn = get_db()
    try:
        cats = conn.execute("""
            SELECT id, nombre, prioridad, parent_id
            FROM categorias
            ORDER BY prioridad ASC, LOWER(nombre) ASC
        """).fetchall()

        nodes = {
            r["id"]: {
                "id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
                "parent_id": r["parent_id"], "total": 0, "children": [],
            }
            for r in cats
        }
        roots = []
        for r in cats:
            n = nodes[r["id"]]
            if r["parent_id"] and r["parent_id"] in nodes:
                nodes[r["parent_id"]]["children"].append(n)
            else:
                roots.append(n)

        # Conteo por subárbol: equipos distintos asignados a la categoría o a un descendiente.
        eq_rows = conn.execute(
            "SELECT equipo_id, categoria_id FROM equipo_categorias"
        ).fetchall()
        from collections import defaultdict
        eq_cats: dict[int, set] = defaultdict(set)
        for r in eq_rows:
            eq_cats[r["equipo_id"]].add(r["categoria_id"])

        def descendants(nid: int) -> set:
            out = {nid}
            stack = [nid]
            while stack:
                cur = stack.pop()
                for n in nodes.values():
                    if n["parent_id"] == cur:
                        out.add(n["id"]); stack.append(n["id"])
            return out

        for nid, n in nodes.items():
            sub = descendants(nid)
            n["total"] = sum(1 for tags in eq_cats.values() if tags & sub)

        for n in nodes.values():
            n["children"].sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))
        roots.sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))

        if flat:
            return [
                {
                    "nombre": r["nombre"], "total": r["total"], "prioridad": r["prioridad"],
                    "subtags": [{"nombre": c["nombre"], "total": c["total"]} for c in r["children"]],
                }
                for r in roots
            ]

        def clean(n):
            return {
                "id": n["id"], "nombre": n["nombre"], "prioridad": n["prioridad"],
                "total": n["total"], "parent_id": n["parent_id"],
                "children": [clean(c) for c in n["children"]],
            }
        return [clean(r) for r in roots]
    finally:
        conn.close()


# ── Admin: gestión de etiquetas / categorías ─────────────────────────────────

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
    from supabase_auth import require_admin
    require_admin(request)
    conn = get_db()
    try:
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
    finally:
        conn.close()


@router.post("/admin/etiquetas", status_code=201)
def admin_create_etiqueta(data: EtiquetaCreate, request: Request):
    from supabase_auth import require_admin
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    conn = get_db()
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
    finally:
        conn.close()


@router.patch("/admin/etiquetas/{eid}")
def admin_update_etiqueta(eid: int, patch: EtiquetaPatch, request: Request):
    from supabase_auth import require_admin
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
        conn0 = get_db()
        try:
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
        finally:
            conn0.close()
        sets.append("parent_id = %s"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    conn = get_db()
    try:
        vals.append(eid)
        conn.execute(f"UPDATE etiquetas SET {', '.join(sets)} WHERE id = %s", tuple(vals))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/admin/etiquetas/{eid}", status_code=204)
def admin_delete_etiqueta(eid: int, request: Request):
    from supabase_auth import require_admin
    require_admin(request)
    conn = get_db()
    try:
        # ON DELETE CASCADE en equipo_etiquetas + SET NULL en parent_id de hijos.
        conn.execute("DELETE FROM etiquetas WHERE id = %s", (eid,))
        conn.commit()
    finally:
        conn.close()


@router.post("/admin/etiquetas/reorder")
def admin_reorder_etiquetas(payload: EtiquetasReorder, request: Request):
    from supabase_auth import require_admin
    require_admin(request)
    conn = get_db()
    try:
        for idx, eid in enumerate(payload.ids):
            conn.execute(
                "UPDATE etiquetas SET prioridad = %s WHERE id = %s",
                ((idx + 1) * 10, eid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
    finally:
        conn.close()


# ── Admin: clasificación automática de equipos ───────────────────────────────

# Reglas leaf → keywords. Orden importa: más específico primero.
# Cada equipo recibe TODAS las hojas que matcheen (multi-asignación).
# Se aplica sobre nombre + marca + modelo (lowercase).
_RULES_LEAF = [
    # ── CÁMARAS (multi: foto+video para mirrorless híbridas) ────────────
    ("Foto",           ["a7 v", "zv-e1"]),  # mirrorless híbridas → también foto
    ("Video",          ["a7 v", "zv-e1", "fx3", "komodo", "c200"]),
    ("Acción",         ["gopro", "insta360"]),
    # ── LENTES ─────────────────────────────────────────────────────────
    ("Vintage",        ["vintage", "carl zeiss jena"]),
    ("Especiales",     ["laowa", "probe macro"]),
    ("Zoom E-mount",   ["sony gm", "montura e"]),
    ("Zoom EF",        ["sigma art 18-35", "sigma art 24-70", "tokina 11-16", "canon 70-200"]),
    ("Fijos EF",       ["sigma art 35mm", "sigma art 50mm"]),
    # ── ADAPTADORES Y FILTROS ──────────────────────────────────────────
    ("Adaptadores de montura", ["adaptador "]),
    ("Filtros 82mm",   ["filtro "]),
    # ── ILUMINACIÓN ────────────────────────────────────────────────────
    ("LED RGB",        ["rgb", "tl60", "m1 mini", "amaran 300c", "accent b7c"]),
    ("LED daylight/bicolor", ["led", "amaran", "nanlite", "godox vl", "spotlight"]),
    ("Tungsteno",      ["tungsteno", "fresnel arri", "mole richardson", "lowel par", "open face", "focus light"]),
    ("Fluorescente",   ["kino flo", "caselight", "pampa tubo", "fluorescente"]),
    ("On-camera / Flash", ["flash godox", "luz on-camera", "yongnuo yn300", "dracast bicolor"]),
    ("Práctica / efecto", ["globo china", "máquina de humo", "smokegenie"]),
    # ── MODIFICADORES ──────────────────────────────────────────────────
    ("Softbox",        ["softbox", "light dome", "ad-s60"]),
    ("Difusión / Frame", ["frame difusión", "fresnel attachment"]),
    ("Reflectores",    ["reflector"]),
    ("Banderas",       ["bandera"]),
    # ── SOPORTES ───────────────────────────────────────────────────────
    ("Trípodes video", ["manfrotto 502", "manfrotto 504", "manfrotto 529", "trípode fluido", "trípode galera"]),
    ("Trípodes foto",  ["xpro 4s", "trípode foto", "manfrotto elements"]),
    ("C-Stands",       ["c-stand"]),
    ("Estabilización", ["gimbal", "ronin", "steadicam", "glidecam", "tilta gravity"]),
    ("Slider / Dolly / Riel", ["slider", "dolly", "riel "]),
    ("Car Mount",      ["car mount", "tilta hydra"]),
    # ── GRIP ───────────────────────────────────────────────────────────
    ("Brazos",         ["brazo ", "boom arm", "magic arm", "superflex", "brazo mágico"]),
    ("Clamps",         ["clamp", "superclamp", "avenger c1510", "avenger c4462", "avenger e390"]),
    ("Wall plates / pins", ["wall plate", "baby pin", "junior pin"]),
    ("Pinzas",         ["pinza"]),
    ("Líneas de seguridad", ["línea de seguridad", "linea de seguridad"]),
    ("Sopapa",         ["sopapa"]),
    ("Lastre",         ["bolsa de arena", "saco de arena"]),
    # ── SONIDO ─────────────────────────────────────────────────────────
    ("Inalámbricos / Lavalier", ["dji mic", "wireless go", "lavalier"]),
    ("Shotgun / Boom", ["shotgun", "ntg2", "mke 600", "caña boom", "zeppelin"]),
    ("On-camera (sonido)", ["videomic", "mke 400"]),
    ("Estudio / Podcast", ["procaster", "rodecaster"]),
    ("Intercom",       ["intercom", "solidcom", "hollyland"]),
    # ── MONITORES Y VIDEO ──────────────────────────────────────────────
    ("Monitores",      ["monitor de campo", "smallhd", "lilliput", "viltrox 6", "monitor on-camera"]),
    ("Grabadores",     ["video assist", "grabador"]),
    ("Transmisión inalámbrica", ["sdr transmission", "transmisor inalámbrico"]),
    ("Follow Focus / Matebox", ["follow focus", "nucleus", "matebox", "matte box"]),
    # ── ENERGÍA ────────────────────────────────────────────────────────
    ("V-Mount",        ["v-mount", "vmount"]),
    ("NP / LP-E6",     ["np-f", "np-fz", "lp-e6", "np serie-l"]),
    ("Distribución eléctrica", ["zapatilla", "alargue eléctrico"]),
    # ── MEDIA Y DATOS ──────────────────────────────────────────────────
    ("Tarjetas SD",    ["tarjeta sd"]),
    ("Tarjetas CFexpress", ["cfexpress"]),
    ("Lectores",       ["lector"]),
    # ── ESTUDIO Y PRODUCCIÓN ───────────────────────────────────────────
    ("Set / Backdrops", ["backdrop", "mesa de producción"]),
    ("Paquetes",       ["rambla estudio", "estudio equipos promo"]),
]


def _propose_tags(nombre: str, marca: str, modelo: str) -> list[str]:
    """Devuelve la lista de etiquetas hoja propuestas para un equipo."""
    text = f"{nombre} {marca or ''} {modelo or ''}".lower()
    matches = []
    for leaf, kws in _RULES_LEAF:
        for kw in kws:
            if kw in text:
                matches.append(leaf)
                break
    # Dedupe preservando orden
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            out.append(m); seen.add(m)
    return out


@router.post("/admin/categorias/clasificar")
def admin_clasificar(request: Request, apply: int = Query(0)):
    """
    Calcula etiquetas hoja propuestas para todos los equipos visibles.
    - apply=0 (default): dry-run, solo devuelve la propuesta.
    - apply=1: aplica las asignaciones (REEMPLAZA las etiquetas existentes
      de cada equipo que tenga al menos 1 match; los que no matchean nada
      no se tocan).

    Respuesta:
      {
        "total": 142, "matched": 130, "unmatched": 12,
        "items": [{id, nombre, marca, propuestas: [...], actuales: [...]}],
        "applied": 0 | <int>,
      }
    """
    from supabase_auth import require_admin
    require_admin(request)

    conn = get_db()
    try:
        equipos = conn.execute("""
            SELECT e.id, e.nombre, e.marca, e.modelo
            FROM equipos e
            ORDER BY e.nombre
        """).fetchall()

        # Cargar etiquetas existentes por equipo.
        rows = conn.execute("""
            SELECT ee.equipo_id, et.nombre
            FROM equipo_etiquetas ee
            JOIN etiquetas et ON et.id = ee.etiqueta_id
        """).fetchall()
        from collections import defaultdict
        actuales: dict[int, list[str]] = defaultdict(list)
        for r in rows:
            actuales[r["equipo_id"]].append(r["nombre"])

        # Mapa nombre→id de hojas válidas.
        leaf_rows = conn.execute(
            "SELECT id, nombre FROM etiquetas WHERE parent_id IS NOT NULL"
        ).fetchall()
        leaf_id = {r["nombre"]: r["id"] for r in leaf_rows}

        items = []
        matched = 0
        applied = 0
        for eq in equipos:
            propuestas = _propose_tags(eq["nombre"], eq["marca"] or "", eq["modelo"] or "")
            # Filtrar a las que existen como hoja en DB.
            propuestas = [p for p in propuestas if p in leaf_id]
            if propuestas:
                matched += 1
                if apply:
                    # REEMPLAZA: borra las actuales y vuelve a insertar las propuestas.
                    conn.execute(
                        "DELETE FROM equipo_etiquetas WHERE equipo_id = %s", (eq["id"],)
                    )
                    for orden, name in enumerate(propuestas):
                        conn.execute("""
                            INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (equipo_id, etiqueta_id)
                            DO UPDATE SET orden = EXCLUDED.orden
                        """, (eq["id"], leaf_id[name], orden))
                    applied += 1
            items.append({
                "id":        eq["id"],
                "nombre":    eq["nombre"],
                "marca":     eq["marca"],
                "propuestas": propuestas,
                "actuales":  actuales.get(eq["id"], []),
            })

        if apply:
            conn.commit()

        return {
            "total":     len(equipos),
            "matched":   matched,
            "unmatched": len(equipos) - matched,
            "applied":   applied,
            "items":     items,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



@router.get("/equipos/{id}/calendario")
def get_equipo_calendario(id: int, year: int = Query(...), month: int = Query(...)):
    """Per-day available unit count for a given equipment and month."""
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mes inválido")

    conn = get_db()
    try:
        equipo = conn.execute(
            "SELECT id, cantidad FROM equipos WHERE id=?", (id,)
        ).fetchone()
        if not equipo:
            raise HTTPException(404, "Equipo no encontrado")

        stock_total     = equipo["cantidad"]
        _, days_in_month = _cal.monthrange(year, month)
        first_day       = _date(year, month, 1).isoformat()
        last_day        = _date(year, month, days_in_month).isoformat()

        ESTADOS = "('presupuesto','confirmado','retirado')"

        # Direct reservations that overlap this month
        directas = conn.execute(f"""
            SELECT LEFT(p.fecha_desde, 10) AS desde,
                   LEFT(p.fecha_hasta, 10) AS hasta,
                   pi.cantidad
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE pi.equipo_id = ?
              AND p.estado IN {ESTADOS}
              AND LEFT(p.fecha_desde, 10) <= ?
              AND LEFT(p.fecha_hasta, 10) > ?
        """, (id, last_day, first_day)).fetchall()

        # Via-kit reservations: this equipment is a component of a rented kit
        via_kit = conn.execute(f"""
            SELECT LEFT(p.fecha_desde, 10) AS desde,
                   LEFT(p.fecha_hasta, 10) AS hasta,
                   pi.cantidad * kc.cantidad AS cantidad
            FROM kit_componentes kc
            JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE kc.componente_id = ?
              AND p.estado IN {ESTADOS}
              AND LEFT(p.fecha_desde, 10) <= ?
              AND LEFT(p.fecha_hasta, 10) > ?
        """, (id, last_day, first_day)).fetchall()

        reservations = [dict(r) for r in directas] + [dict(r) for r in via_kit]

        result: dict[str, int] = {}
        for day_num in range(1, days_in_month + 1):
            d_str    = _date(year, month, day_num).isoformat()
            reservado = sum(
                r["cantidad"]
                for r in reservations
                if r["desde"] <= d_str < r["hasta"]
            )
            result[d_str] = max(0, stock_total - reservado)

        return result
    finally:
        conn.close()
