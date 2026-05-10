"""
routes/equipos.py — CRUD de equipos, kits, etiquetas, categorías y fichas.
"""

import calendar as _cal
import datetime
import os
from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from database import (
    get_db, row_to_dict, attach_tags, attach_kit, attach_categorias,
    attach_ficha, regenerate_auto_tags,
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
    descripcion:   Optional[str] = None
    notas:         Optional[str] = None
    specs_json:    Optional[str] = None
    montura:       Optional[str] = None
    formato:       Optional[str] = None
    resolucion:    Optional[str] = None
    keywords_json: Optional[str] = None
    nombre_publico_template: Optional[str] = None
    # Ficha extendida (enriquecimiento)
    peso:                Optional[str]   = None
    dimensiones:         Optional[str]   = None
    alimentacion:        Optional[str]   = None
    incluye_json:        Optional[str]   = None
    conectividad_json:   Optional[str]   = None
    compatible_con_json: Optional[str]   = None
    video_url:           Optional[str]   = None
    precio_bh_usd:       Optional[float] = None
    fuente_url:          Optional[str]   = None
    fuente_titulo:       Optional[str]   = None
    raw_json:            Optional[str]   = None
    enriquecido_fuente:  Optional[str]   = None


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
        # ILIKE = case-insensitive (Postgres). Permite buscar "sony" / "Sony" / "SONY".
        base_sql += " AND (e.nombre ILIKE ? OR e.marca ILIKE ? OR e.modelo ILIKE ?)"
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
        equipos = attach_ficha(conn, equipos)
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
        equipo = attach_ficha(conn, [equipo])[0]
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
        # Si cambió algo que alimenta auto-tags, regenerar.
        if any(k in updates for k in ("nombre", "marca", "modelo")):
            regenerate_auto_tags(conn, id)
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
        return {
            "equipo_id": id, "descripcion": None, "notas": None, "specs_json": None,
            "montura": None, "formato": None, "resolucion": None, "keywords_json": None,
            "nombre_publico_template": None,
        }
    finally:
        conn.close()


@router.put("/equipos/{id}/ficha")
def upsert_ficha(id: int, data: FichaUpdate):
    """
    PATCH-style upsert: solo actualiza columnas que vinieron en el body
    (no las nullea si el cliente no las mandó). Esto evita que enriquecer con
    IA borre montura/formato/resolución existentes.
    """
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        patch = data.model_dump(exclude_unset=True)
        # Inserta una fila vacía si no existe (para que el UPDATE encuentre algo).
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id) VALUES (?) ON CONFLICT(equipo_id) DO NOTHING",
            (id,),
        )
        if patch:
            set_clause = ", ".join(f"{k} = ?" for k in patch)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = ?",
                list(patch.values()) + [id],
            )
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
def list_etiquetas(incluir_auto: int = Query(0)):
    """
    Lista etiquetas. Por defecto devuelve solo las que tienen al menos un uso
    MANUAL (las auto inflan demasiado). `incluir_auto=1` devuelve todo.
    """
    conn = get_db()
    try:
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
    from admin_guard import require_admin
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
    from admin_guard import require_admin
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
    from admin_guard import require_admin
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
    from admin_guard import require_admin
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
    from admin_guard import require_admin
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


class CategoriasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/categorias")
def admin_list_categorias(request: Request):
    from admin_guard import require_admin
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT c.id, c.nombre, c.prioridad, c.parent_id,
                   COUNT(ec.equipo_id) AS total
            FROM categorias c
            LEFT JOIN equipo_categorias ec ON ec.categoria_id = c.id
            GROUP BY c.id, c.nombre, c.prioridad, c.parent_id
            ORDER BY c.prioridad ASC, LOWER(c.nombre) ASC
        """).fetchall()
        return [
            {"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
             "parent_id": r["parent_id"], "total": r["total"]}
            for r in rows
        ]
    finally:
        conn.close()


@router.post("/admin/categorias", status_code=201)
def admin_create_categoria(data: CategoriaCreate, request: Request):
    from admin_guard import require_admin
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    conn = get_db()
    try:
        if data.parent_id is not None:
            prow = conn.execute(
                "SELECT id, parent_id FROM categorias WHERE id = %s", (data.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
        cur = conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (nombre) DO UPDATE
                SET prioridad = EXCLUDED.prioridad,
                    parent_id = EXCLUDED.parent_id
            RETURNING id, nombre, prioridad, parent_id
        """, (nombre, data.prioridad or 100, data.parent_id))
        row = cur.fetchone()
        conn.commit()
        return {"id": row["id"], "nombre": row["nombre"],
                "prioridad": row["prioridad"], "parent_id": row["parent_id"], "total": 0}
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.patch("/admin/categorias/{cid}")
def admin_update_categoria(cid: int, patch: CategoriaPatch, request: Request):
    from admin_guard import require_admin
    require_admin(request)
    sets, vals = [], []
    if patch.nombre is not None:
        sets.append("nombre = %s"); vals.append(patch.nombre.strip())
    if patch.prioridad is not None:
        sets.append("prioridad = %s"); vals.append(int(patch.prioridad))
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == cid:
            raise HTTPException(400, "Una categoría no puede ser su propio padre")
        conn0 = get_db()
        try:
            prow = conn0.execute(
                "SELECT id, parent_id FROM categorias WHERE id = %s", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            chrow = conn0.execute(
                "SELECT 1 FROM categorias WHERE parent_id = %s LIMIT 1", (cid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta categoría tiene hijos")
        finally:
            conn0.close()
        sets.append("parent_id = %s"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    conn = get_db()
    try:
        vals.append(cid)
        conn.execute(f"UPDATE categorias SET {', '.join(sets)} WHERE id = %s", tuple(vals))
        # Si renombró, regenerar auto-tags de los equipos afectados.
        if patch.nombre is not None:
            eq_rows = conn.execute(
                "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = %s", (cid,)
            ).fetchall()
            for r in eq_rows:
                regenerate_auto_tags(conn, r["equipo_id"])
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/admin/categorias/{cid}", status_code=204)
def admin_delete_categoria(cid: int, request: Request):
    from admin_guard import require_admin
    require_admin(request)
    conn = get_db()
    try:
        eq_rows = conn.execute(
            "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = %s", (cid,)
        ).fetchall()
        affected = [r["equipo_id"] for r in eq_rows]
        conn.execute("DELETE FROM categorias WHERE id = %s", (cid,))
        for eid in affected:
            regenerate_auto_tags(conn, eid)
        conn.commit()
    finally:
        conn.close()


@router.post("/admin/categorias/reorder")
def admin_reorder_categorias(payload: CategoriasReorder, request: Request):
    from admin_guard import require_admin
    require_admin(request)
    conn = get_db()
    try:
        for idx, cid in enumerate(payload.ids):
            conn.execute(
                "UPDATE categorias SET prioridad = %s WHERE id = %s",
                ((idx + 1) * 10, cid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
    finally:
        conn.close()


# ── Admin: clasificación automática (escribe en equipo_categorias) ───────────

@router.post("/admin/categorias/clasificar")
def admin_clasificar(request: Request, apply: int = Query(0)):
    """
    Calcula categorías hoja propuestas para todos los equipos.
    - apply=0: dry-run.
    - apply=1: REEMPLAZA las categorías de cada equipo que matchee al menos 1
      regla; los que no matchean no se tocan. Regenera auto-tags después.
    """
    from admin_guard import require_admin
    require_admin(request)

    conn = get_db()
    try:
        equipos = conn.execute("""
            SELECT e.id, e.nombre, e.marca, e.modelo
            FROM equipos e
            ORDER BY e.nombre
        """).fetchall()

        # Categorías actuales por equipo (para mostrar el diff).
        rows = conn.execute("""
            SELECT ec.equipo_id, c.nombre
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
        """).fetchall()
        from collections import defaultdict
        actuales: dict[int, list[str]] = defaultdict(list)
        for r in rows:
            actuales[r["equipo_id"]].append(r["nombre"])

        # Mapa nombre→id de categorías hoja válidas.
        leaf_rows = conn.execute(
            "SELECT id, nombre FROM categorias WHERE parent_id IS NOT NULL"
        ).fetchall()
        leaf_id = {r["nombre"]: r["id"] for r in leaf_rows}

        items = []
        matched = 0
        applied = 0
        for eq in equipos:
            propuestas = _propose_tags(eq["nombre"], eq["marca"] or "", eq["modelo"] or "")
            propuestas = [p for p in propuestas if p in leaf_id]
            if propuestas:
                matched += 1
                if apply:
                    conn.execute(
                        "DELETE FROM equipo_categorias WHERE equipo_id = %s", (eq["id"],)
                    )
                    for orden, name in enumerate(propuestas):
                        conn.execute("""
                            INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (equipo_id, categoria_id)
                            DO UPDATE SET orden = EXCLUDED.orden
                        """, (eq["id"], leaf_id[name], orden))
                    regenerate_auto_tags(conn, eq["id"])
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


# ── Admin: enriquecimiento con IA (Firecrawl + Lovable AI) ────────────────────

class EnriquecerInput(BaseModel):
    nombre: Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    url:    Optional[str] = None   # Si está presente, salta la búsqueda y scrapea esa URL directo


@router.post("/admin/equipos/enriquecer")
def admin_enriquecer_equipo(payload: EnriquecerInput, request: Request):
    """
    Busca el equipo en B&H/Adorama, scrapea la página y usa Lovable AI para
    extraer marca/modelo/specs/foto en JSON estructurado. Devuelve un preview;
    el frontend decide qué campos aplicar via PATCH normal.
    """
    from admin_guard import require_admin
    require_admin(request)

    import os, httpx

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado en el backend")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida (debe empezar con http:// o https://)")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url para enriquecer")

    headers_fc = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    def _extract_results(j: dict) -> list[dict]:
        data = j.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("web", []) or []
        return []

    OFFICIAL_SITES = (
        "site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        "site:fujifilm.com OR site:fujifilm-x.com OR site:panasonic.com OR "
        "site:blackmagicdesign.com OR site:aputure.com OR site:godox.com OR "
        "site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        "site:tilta.com OR site:smallrig.com OR site:zoom-na.com OR site:zhiyun-tech.com"
    )

    def _search(q: str, client: "httpx.Client") -> list[dict]:
        try:
            rr = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers_fc,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if rr.status_code != 200:
            return []
        return _extract_results(rr.json())

    def _first_valid(results: list[dict]) -> dict | None:
        for r in results:
            u = (r.get("url") or "").strip()
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                return r
        return None

    json_format = {
        "type": "json",
        "prompt": (
            "Extraé información completa del equipo audiovisual (cámara, lente, "
            "luz, audio, soporte) desde la ficha de producto. "
            "Descripcion: 1-2 oraciones en español neutral. "
            "Specs: máximo 10, label corto y value conciso (ej. 'Sensor': 'Full-frame 24MP'). "
            "Keywords: 3-6 palabras clave cortas en español lowercase que describan la "
            "PERSONALIDAD/diferenciales del equipo (ej: 'bicolor', 'silenciosa', "
            "'v-mount', 'global shutter', 'weather sealed', 'cri 96', 'cine-ready'). "
            "Distintas y específicas — nada genérico como 'profesional' o 'calidad'. "
            "Peso: con unidad (ej '640g', '1.2kg'). "
            "Dimensiones: WxHxD con unidad (ej '129.7 x 77.8 x 84.5 mm'). "
            "Montura: nombre canónico (ej 'Sony E', 'Canon RF', 'EF', 'MFT', 'PL'). "
            "Formato: 'Full-frame' | 'APS-C' | 'MFT' | 'Super 35' | etc. para cámaras/lentes. "
            "Resolucion: para cámaras/monitores (ej '4K 120p', '6K Open Gate', '1080p'). "
            "Alimentacion: tipo de batería o fuente (ej 'NP-FZ100', 'V-mount', 'AC 220V', '2x AA'). "
            "Incluye: array de items que vienen en la caja (ej ['Cuerpo','Tapa','Cargador']). "
            "Conectividad: array de puertos (ej ['USB-C','HDMI Type-A','XLR x2','Mini-jack 3.5mm']). "
            "Compatible_con: array de etiquetas de compatibilidad (montura, formato, sistemas). "
            "Precio_usd: precio listado en USD si está visible (sólo número). "
            "Video_url: URL absoluta a un video YouTube de demo si aparece linkeado. "
            "Categoria_sugerida: una de ['Cámara','Lente','Iluminación','Audio','Soporte','Monitor','Accesorio']. "
            "Foto_urls: array con hasta 5 URLs ABSOLUTAS (http/https) de imágenes del producto, "
            "ordenadas de MÁS A MENOS relevante para el producto principal. "
            "Incluí ángulos distintos (frente, lateral, detalle) si están disponibles. "
            "JPG/PNG/WebP únicamente — NO uses placeholders, sprites, SVGs decorativos, "
            "tracking pixels, banners de categoría, fotos de productos relacionados, ni rutas relativas. "
            "Si no estás 100% seguro de que una URL existe y apunta al producto, NO la incluyas. "
            "Cualquier campo que no esté en la ficha → dejalo vacío. NO inventes."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "marca":  {"type": "string"},
                "modelo": {"type": "string"},
                "nombre_normalizado": {"type": "string"},
                "descripcion": {"type": "string"},
                "foto_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "specs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "value": {"type": "string"},
                        },
                        "required": ["label", "value"],
                    },
                },
                "keywords":          {"type": "array", "items": {"type": "string"}},
                "peso":              {"type": "string"},
                "dimensiones":       {"type": "string"},
                "montura":           {"type": "string"},
                "formato":           {"type": "string"},
                "resolucion":        {"type": "string"},
                "alimentacion":      {"type": "string"},
                "incluye":           {"type": "array", "items": {"type": "string"}},
                "conectividad":      {"type": "array", "items": {"type": "string"}},
                "compatible_con":    {"type": "array", "items": {"type": "string"}},
                "precio_usd":        {"type": "number"},
                "video_url":         {"type": "string"},
                "categoria_sugerida": {"type": "string"},
            },
            "required": ["marca", "modelo", "descripcion", "specs"],
        },
    }

    def _scrape(url: str, client: "httpx.Client") -> dict | None:
        """Devuelve {extracted, foto_candidates, meta} o None si falló.
        foto_candidates es una lista ordenada de URLs candidatas (LLM primero,
        luego og:image, twitter:image, dedupe).
        """
        try:
            rs = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers_fc,
                json={
                    "url": url,
                    "formats": ["markdown", json_format],
                    "onlyMainContent": True,
                },
            )
        except httpx.HTTPError:
            return None
        if rs.status_code == 402:
            raise HTTPException(402, "Sin créditos de Firecrawl. Recargá tu plan.")
        if rs.status_code == 429:
            raise HTTPException(429, "Rate-limit de Firecrawl. Probá en un minuto.")
        if rs.status_code != 200:
            return None
        sj = rs.json()
        sd = sj.get("data") or sj
        meta      = sd.get("metadata") or {}
        extracted = sd.get("json") or {}

        # Candidatos: LLM (array) primero (mejor ranking), después meta tags
        candidates: list[str] = []
        seen_lower: set[str] = set()

        def _push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            key = u.lower()
            if key in seen_lower:
                return
            seen_lower.add(key)
            candidates.append(u)

        # 1. LLM array (foto_urls) — orden de relevancia ya viene de la IA
        for u in (extracted.get("foto_urls") or []):
            _push(u)
        # 2. Backwards-compat: si vino foto_url scalar (esquema viejo)
        _push(extracted.get("foto_url"))
        # 3. Meta tags
        _push(meta.get("ogImage") or meta.get("og:image"))
        _push(meta.get("twitterImage") or meta.get("twitter:image"))

        return {"extracted": extracted, "foto_candidates": candidates[:6], "meta": meta}

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            # Modo URL directa: scrape de esa página, sin búsqueda.
            # Si la URL es de B&H la tratamos como bh_top, sino como alt_top
            # (esto sólo afecta dónde queda el canonical_url y el labelling).
            from urllib.parse import urlparse as _up
            host = (_up(direct_url).hostname or "").lower()
            top_entry = {"url": direct_url, "title": direct_url}
            if "bhphotovideo" in host:
                bh_top, alt_top = top_entry, None
                bh_scrape, alt_scrape = _scrape(direct_url, client), None
            else:
                bh_top, alt_top = None, top_entry
                bh_scrape, alt_scrape = None, _scrape(direct_url, client)

            if bh_scrape is None and alt_scrape is None:
                raise HTTPException(422, "No se pudo scrapear la URL")
        else:
            # Etapa A: B&H (canónico para bh_url)
            bh_results = _search(f"{query} site:bhphotovideo.com", client)
            bh_top = _first_valid(bh_results)

            # Etapa B: sitios oficiales del fabricante
            alt_results = _search(f"{query} ({OFFICIAL_SITES})", client)
            alt_top = _first_valid(alt_results)

            # Etapa C: Adorama / Amazon (último recurso)
            if not alt_top:
                adoram_results = _search(f"{query} site:adorama.com OR site:amazon.com", client)
                alt_top = _first_valid(adoram_results)

            if not bh_top and not alt_top:
                raise HTTPException(404, "No se encontraron resultados en internet")

            bh_scrape  = _scrape(bh_top["url"], client) if bh_top else None
            alt_scrape = None
            # Sólo scrapeamos alternativa si B&H no aportó datos o foto
            needs_alt = (
                alt_top is not None and (
                    bh_scrape is None
                    or not bh_scrape.get("foto_candidate")
                    or not (bh_scrape.get("extracted") or {}).get("descripcion")
                )
            )
            if needs_alt:
                alt_scrape = _scrape(alt_top["url"], client)

    # ── Merge B&H + alt (B&H pisa, alt rellena gaps) ────────────────────────
    primary = bh_scrape or alt_scrape or {}
    secondary = alt_scrape if bh_scrape else None
    extracted = dict(primary.get("extracted") or {})
    _MERGE_KEYS = (
        "descripcion", "specs", "keywords", "marca", "modelo", "nombre_normalizado",
        "peso", "dimensiones", "montura", "formato", "resolucion", "alimentacion",
        "incluye", "conectividad", "compatible_con", "precio_usd", "video_url",
        "categoria_sugerida",
    )
    if secondary:
        sec_ext = secondary.get("extracted") or {}
        for k in _MERGE_KEYS:
            if not extracted.get(k):
                extracted[k] = sec_ext.get(k)

    if not extracted:
        raise HTTPException(422, "No se pudo extraer información estructurada")

    # ── Validación de foto: HEAD/GET parcial antes de devolver ──────────────
    def _validate_image(url: str | None) -> tuple[bool, str]:
        """Devuelve (ok, motivo). motivo es '' si ok=True."""
        if not url:
            return False, "sin candidata"
        if not url.lower().startswith(("http://", "https://")):
            return False, "URL no absoluta"
        from urllib.parse import urlparse as _up
        host = (_up(url).hostname or "").lower()
        ref = f"https://{host}/" if host else None
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if ref:
            hdrs["Referer"] = ref
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as c:
                # HEAD primero
                try:
                    rh = c.head(url, headers=hdrs)
                    if rh.status_code == 200:
                        ct = rh.headers.get("content-type", "")
                        cl = int(rh.headers.get("content-length", "0") or "0")
                        if ct.startswith("image/") and (cl == 0 or cl > 1024):
                            return True, ""
                        if not ct.startswith("image/"):
                            return False, f"content-type {ct or 'desconocido'}"
                        if cl and cl <= 1024:
                            return False, "imagen muy chica (<1KB)"
                except httpx.HTTPError:
                    pass
                # GET con Range como fallback (HEAD a veces no está soportado)
                hdrs["Range"] = "bytes=0-2048"
                rg = c.get(url, headers=hdrs)
                if rg.status_code in (200, 206):
                    ct = rg.headers.get("content-type", "")
                    if ct.startswith("image/"):
                        return True, ""
                    return False, f"content-type {ct or 'desconocido'}"
                return False, f"HTTP {rg.status_code} en origen"
        except httpx.HTTPError as e:
            return False, f"error de red: {type(e).__name__}"

    # Juntar todos los candidatos: B&H primero, después alt (sin dedupe-cross,
    # se dedupe cuando los unimos)
    bh_cands  = (bh_scrape or {}).get("foto_candidates") or []
    alt_cands = (alt_scrape or {}).get("foto_candidates") or []

    # Si alt no se scrapeó pero existe URL, scrape ahora para sumar candidatos
    if not alt_scrape and alt_top:
        try:
            with httpx.Client(timeout=45.0) as c2:
                alt_scrape = _scrape(alt_top["url"], c2)
            alt_cands = (alt_scrape or {}).get("foto_candidates") or []
        except Exception:
            pass

    all_candidates: list[str] = []
    seen_lc: set[str] = set()
    for u in (bh_cands + alt_cands):
        k = u.lower()
        if k in seen_lc:
            continue
        seen_lc.add(k)
        all_candidates.append(u)

    # Validar cada candidato (HEAD/GET); guardar los que pasen + motivo de los que no
    foto_validas: list[str] = []
    foto_invalidas: list[dict] = []
    for u in all_candidates[:8]:  # límite hard para no validar 50 imágenes
        ok, motivo = _validate_image(u)
        if ok:
            foto_validas.append(u)
        else:
            foto_invalidas.append({"url": u, "motivo": motivo})

    foto_url = foto_validas[0] if foto_validas else None
    fuente_foto_url = (bh_top or alt_top or {}).get("url") if foto_url else None
    foto_motivo = ""
    if not foto_url:
        if foto_invalidas:
            foto_motivo = " | ".join(f"{(d['motivo'] or 'inválida')}" for d in foto_invalidas[:3])
        else:
            foto_motivo = "no se encontró imagen en ninguna fuente"

    # bh_url canónico = el de B&H si hubo, sino el alternativo (como referencia)
    canonical_url = (bh_top or alt_top)["url"]
    canonical_title = (bh_top or alt_top).get("title") or canonical_url

    # Sanitizar keywords: lowercase, trim, dedupe, max 6
    raw_kws = extracted.get("keywords") or []
    seen_kw: set[str] = set()
    keywords: list[str] = []
    for k in raw_kws:
        if not isinstance(k, str):
            continue
        kk = k.strip().lower()
        if not kk or kk in seen_kw or len(kk) > 40:
            continue
        seen_kw.add(kk)
        keywords.append(kk)
        if len(keywords) >= 6:
            break

    # ── Sanitización de listas de strings ──────────────────────────────────
    def _clean_str_list(raw, max_items: int = 12, max_len: int = 80) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        if not isinstance(raw, list):
            return out
        for v in raw:
            if not isinstance(v, str):
                continue
            s = v.strip()
            if not s or len(s) > max_len or s.lower() in seen:
                continue
            seen.add(s.lower())
            out.append(s)
            if len(out) >= max_items:
                break
        return out

    incluye        = _clean_str_list(extracted.get("incluye"),        max_items=15)
    conectividad   = _clean_str_list(extracted.get("conectividad"),   max_items=10)
    compatible_con = _clean_str_list(extracted.get("compatible_con"), max_items=8)

    # video_url: validar http(s), nada de javascript: ni rutas relativas
    video_url = extracted.get("video_url")
    if isinstance(video_url, str) and not video_url.lower().startswith(("http://", "https://")):
        video_url = None

    # precio_usd: aceptar número o string numérico, sino None
    precio_bh_usd = None
    raw_precio = extracted.get("precio_usd")
    if isinstance(raw_precio, (int, float)) and raw_precio > 0:
        precio_bh_usd = float(raw_precio)
    elif isinstance(raw_precio, str):
        try:
            v = float(raw_precio.replace(",", "").replace("$", "").strip())
            if v > 0:
                precio_bh_usd = v
        except ValueError:
            pass

    fuente_de_enriquecimiento = (
        "firecrawl-bh" if bh_scrape else
        "firecrawl-oficial" if alt_scrape else
        "firecrawl"
    )

    return {
        "marca":  (extracted.get("marca")  or payload.marca  or "").strip() or None,
        "modelo": (extracted.get("modelo") or payload.modelo or "").strip() or None,
        "nombre_normalizado": (extracted.get("nombre_normalizado") or payload.nombre or "").strip() or None,
        "descripcion": (extracted.get("descripcion") or "").strip(),
        "specs": (extracted.get("specs") or [])[:12],
        "keywords": keywords,
        "foto_url": foto_url,
        "foto_candidates": foto_validas,  # todas las URLs válidas (la primera es la elegida por defecto)
        # Ficha técnica extendida
        "peso":           (extracted.get("peso") or "").strip() or None,
        "dimensiones":    (extracted.get("dimensiones") or "").strip() or None,
        "montura":        (extracted.get("montura") or "").strip() or None,
        "formato":        (extracted.get("formato") or "").strip() or None,
        "resolucion":     (extracted.get("resolucion") or "").strip() or None,
        "alimentacion":   (extracted.get("alimentacion") or "").strip() or None,
        "incluye":        incluye,
        "conectividad":   conectividad,
        "compatible_con": compatible_con,
        "video_url":      video_url,
        "precio_bh_usd":  precio_bh_usd,
        "categoria_sugerida": (extracted.get("categoria_sugerida") or "").strip() or None,
        # Trazabilidad
        "fuente_url":      canonical_url,
        "fuente_titulo":   canonical_title,
        "fuente_foto_url": fuente_foto_url,
        "foto_motivo":     foto_motivo or None,
        "enriquecido_fuente": fuente_de_enriquecimiento,
        # Raw para guardar tal cual (preserva todo lo que la IA devolvió)
        "raw": extracted,
    }


# ── Admin: búsqueda dedicada de fotos (separada del enriquecimiento) ─────────
#
# El enriquecedor general usa B&H/Adorama (mejor para specs) pero esos sitios
# bloquean hotlinking de fotos. Este endpoint busca específicamente en sitios
# con imágenes confiables (Wikipedia, manufacturer, sitios de review).

class BuscarFotosInput(BaseModel):
    nombre: Optional[str]      = None
    marca:  Optional[str]      = None
    modelo: Optional[str]      = None
    url:    Optional[str]      = None
    exclude: Optional[list[str]] = None  # URLs ya conocidas (para "buscar más")


@router.post("/admin/equipos/buscar-fotos")
def admin_buscar_fotos(payload: BuscarFotosInput, request: Request):
    """Busca fotos del equipo en fuentes optimizadas para imágenes (Wikipedia,
    manufacturer oficial, review sites). Devuelve lista validada de candidatos."""
    from admin_guard import require_admin
    require_admin(request)

    import httpx
    import re

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url")

    exclude_lc: set[str] = {(u or "").strip().lower() for u in (payload.exclude or [])}

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    # Queries específicos para fotos. Wikipedia primero (sin hotlink-block,
    # imágenes limpias), después review sites, después manufacturer.
    PHOTO_QUERIES = [
        f"{query} (site:en.wikipedia.org OR site:commons.wikimedia.org OR site:es.wikipedia.org)",
        f"{query} review (site:dpreview.com OR site:photographyblog.com OR site:cinema5d.com OR "
        f"site:newsshooter.com OR site:fstoppers.com OR site:petapixel.com)",
        f"{query} (site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        f"site:fujifilm.com OR site:panasonic.com OR site:blackmagicdesign.com OR site:aputure.com OR "
        f"site:godox.com OR site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        f"site:tilta.com OR site:smallrig.com)",
    ]

    def _fc_search(q: str, client) -> list[str]:
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        data = r.json().get("data")
        rows = data if isinstance(data, list) else (data.get("web") if isinstance(data, dict) else None) or []
        urls = []
        for row in rows:
            u = (row.get("url") or "").strip() if isinstance(row, dict) else ""
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                urls.append(u)
        return urls

    def _extract_images_from_page(url: str, client) -> list[str]:
        """Scrapea una página y extrae URLs de imagen (meta + markdown img tags)."""
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers,
                json={"url": url, "formats": ["markdown"], "onlyMainContent": False},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        sd = r.json().get("data") or {}
        meta = sd.get("metadata") or {}
        markdown = sd.get("markdown") or ""

        cands: list[str] = []
        seen: set[str] = set()

        def push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            # Filtrar tracking pixels y svgs decorativos
            if u.lower().endswith(".svg"):
                return
            k = u.lower()
            if k in seen or k in exclude_lc:
                return
            seen.add(k)
            cands.append(u)

        push(meta.get("ogImage") or meta.get("og:image"))
        push(meta.get("twitterImage") or meta.get("twitter:image"))
        # ![alt](url) en markdown
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", markdown):
            push(m.group(1))
        # <img src="..."> en HTML embebido
        for m in re.finditer(r'<img[^>]+src=["\']?([^"\'>\s]+)', markdown):
            push(m.group(1))

        return cands[:10]

    # Validación rápida: HEAD/GET parcial, descarta lo que no sea imagen real
    def _is_valid_image(url: str, client) -> bool:
        try:
            from urllib.parse import urlparse as _up
            host = (_up(url).hostname or "").lower()
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
                "Referer": f"https://{host}/" if host else "",
            }
            try:
                rh = client.head(url, headers=hdrs, follow_redirects=True, timeout=8.0)
                if rh.status_code == 200:
                    ct = rh.headers.get("content-type", "")
                    cl = int(rh.headers.get("content-length", "0") or "0")
                    if ct.startswith("image/") and (cl == 0 or cl > 1024):
                        return True
            except httpx.HTTPError:
                pass
            # Fallback con Range
            hdrs["Range"] = "bytes=0-2048"
            rg = client.get(url, headers=hdrs, follow_redirects=True, timeout=8.0)
            if rg.status_code in (200, 206):
                ct = rg.headers.get("content-type", "")
                if ct.startswith("image/"):
                    return True
        except httpx.HTTPError:
            pass
        return False

    all_cands: list[str] = []
    seen_lc: set[str] = set()

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            for u in _extract_images_from_page(direct_url, client):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
        else:
            for q in PHOTO_QUERIES:
                if len(all_cands) >= 18:
                    break
                for top in _fc_search(q, client)[:2]:
                    for u in _extract_images_from_page(top, client):
                        if u.lower() not in seen_lc:
                            seen_lc.add(u.lower())
                            all_cands.append(u)

        # Validar (paralelo no necesario para 18 imgs)
        with httpx.Client(timeout=10.0) as vc:
            validated = [u for u in all_cands[:18] if _is_valid_image(u, vc)][:10]

    return {"foto_candidates": validated, "total_inspeccionadas": len(all_cands)}


# ── Admin: aplicar resultado de enriquecimiento en una sola llamada ──────────
#
# El frontend manda el preview (parcial o completo) + flags "apply_*" para
# decidir qué piezas grabar. Esto evita N round-trips PATCH equipo + PUT ficha.

class AplicarEnriquecimientoInput(BaseModel):
    # Núcleo equipo
    marca:    Optional[str]   = None
    modelo:   Optional[str]   = None
    foto_url: Optional[str]   = None
    bh_url:   Optional[str]   = None
    # Ficha
    descripcion:   Optional[str] = None
    specs:         Optional[list[dict]] = None
    keywords:      Optional[list[str]]  = None
    peso:          Optional[str]   = None
    dimensiones:   Optional[str]   = None
    montura:       Optional[str]   = None
    formato:       Optional[str]   = None
    resolucion:    Optional[str]   = None
    alimentacion:  Optional[str]   = None
    incluye:        Optional[list[str]] = None
    conectividad:   Optional[list[str]] = None
    compatible_con: Optional[list[str]] = None
    video_url:     Optional[str]   = None
    precio_bh_usd: Optional[float] = None
    fuente_url:    Optional[str]   = None
    fuente_titulo: Optional[str]   = None
    raw:           Optional[dict]  = None
    enriquecido_fuente: Optional[str] = None


@router.post("/admin/equipos/{id}/aplicar-enriquecimiento")
def admin_aplicar_enriquecimiento(id: int, payload: AplicarEnriquecimientoInput, request: Request):
    """
    Toma el resultado del endpoint /enriquecer (parcial o completo) y graba
    en una sola transacción los campos que el cliente decidió aplicar.
    Cualquier campo NO incluido en el body queda como está (no se nullea).
    """
    from admin_guard import require_admin
    require_admin(request)

    import json as _json

    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        body = payload.model_dump(exclude_unset=True)

        # ── Equipos (núcleo) ────────────────────────────────────────────
        eq_fields = {}
        for k in ("marca", "modelo", "foto_url", "bh_url"):
            if k in body and body[k] is not None:
                eq_fields[k] = body[k]
        if eq_fields:
            set_clause = ", ".join(f"{k} = ?" for k in eq_fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipos SET {set_clause} WHERE id = ?",
                list(eq_fields.values()) + [id],
            )

        # ── Ficha (asegurar fila) ───────────────────────────────────────
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id) VALUES (?) ON CONFLICT(equipo_id) DO NOTHING",
            (id,),
        )

        # Mapeo: API → columna DB. Listas/dicts → JSON string.
        ficha_fields: dict = {}
        if "descripcion" in body:
            ficha_fields["descripcion"] = body["descripcion"]
        if "specs" in body and body["specs"] is not None:
            ficha_fields["specs_json"] = _json.dumps(body["specs"], ensure_ascii=False)
        if "keywords" in body and body["keywords"] is not None:
            ficha_fields["keywords_json"] = _json.dumps(body["keywords"], ensure_ascii=False)
        if "incluye" in body and body["incluye"] is not None:
            ficha_fields["incluye_json"] = _json.dumps(body["incluye"], ensure_ascii=False)
        if "conectividad" in body and body["conectividad"] is not None:
            ficha_fields["conectividad_json"] = _json.dumps(body["conectividad"], ensure_ascii=False)
        if "compatible_con" in body and body["compatible_con"] is not None:
            ficha_fields["compatible_con_json"] = _json.dumps(body["compatible_con"], ensure_ascii=False)
        for k in ("peso", "dimensiones", "montura", "formato", "resolucion",
                  "alimentacion", "video_url", "precio_bh_usd",
                  "fuente_url", "fuente_titulo", "enriquecido_fuente"):
            if k in body:
                ficha_fields[k] = body[k]
        if "raw" in body and body["raw"] is not None:
            ficha_fields["raw_json"] = _json.dumps(body["raw"], ensure_ascii=False)

        # Si vino algún dato de ficha, marcar enriquecido_at
        if ficha_fields:
            ficha_fields["enriquecido_at"] = datetime.datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in ficha_fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = ?",
                list(ficha_fields.values()) + [id],
            )

        conn.commit()

        # Devolver equipo + ficha actualizados
        eq_row = conn.execute("SELECT * FROM equipos WHERE id = ?", (id,)).fetchone()
        ficha_row = conn.execute("SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)).fetchone()
        return {
            "equipo": row_to_dict(eq_row),
            "ficha":  row_to_dict(ficha_row) if ficha_row else None,
        }
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Admin: proxy de imágenes (para evitar hotlink-block de B&H/Adorama) ──────

@router.get("/admin/proxy-image")
def admin_proxy_image(url: str, request: Request):
    """
    Descarga una imagen desde una URL externa con un User-Agent normal y la
    devuelve al cliente. Útil porque B&H/Adorama bloquean hotlinking pero el
    frontend necesita los bytes para subirlos a Supabase Storage.
    """
    from admin_guard import require_admin
    require_admin(request)

    import httpx
    from fastapi.responses import Response

    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")

    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()

    def _headers(referer: str | None) -> dict:
        h = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Cache-Control": "no-cache",
        }
        if referer:
            h["Referer"] = referer
        return h

    # Referer "creíble" según el host (B&H, Adorama, Amazon, etc.)
    referer_map = {
        "bhphotovideo.com": "https://www.bhphotovideo.com/",
        "www.bhphotovideo.com": "https://www.bhphotovideo.com/",
        "adorama.com": "https://www.adorama.com/",
        "www.adorama.com": "https://www.adorama.com/",
    }
    primary_referer = next((v for k, v in referer_map.items() if host.endswith(k)), f"https://{host}/")

    last_status = None
    last_body = b""
    r = None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, http2=False) as client:
            # 1º intento: con Referer del propio dominio
            r = client.get(url, headers=_headers(primary_referer))
            last_status, last_body = r.status_code, r.content
            # 2º intento: sin Referer
            if r.status_code == 403:
                r2 = client.get(url, headers=_headers(None))
                if r2.status_code == 200:
                    r = r2
                else:
                    last_status, last_body = r2.status_code, r2.content
            # 3º intento: Referer = google
            if r.status_code == 403:
                r3 = client.get(url, headers=_headers("https://www.google.com/"))
                if r3.status_code == 200:
                    r = r3
                else:
                    last_status, last_body = r3.status_code, r3.content
            # 4º intento: proxy público images.weserv.nl (esquiva hotlink-block)
            if r.status_code in (401, 403, 404, 429) or r.status_code >= 500:
                from urllib.parse import quote
                # weserv requiere la URL sin esquema
                stripped = url.split("://", 1)[1] if "://" in url else url
                weserv_url = f"https://images.weserv.nl/?url={quote(stripped, safe='')}"
                r4 = client.get(weserv_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/*,*/*;q=0.8",
                })
                if r4.status_code == 200 and r4.headers.get("content-type", "").startswith("image/"):
                    r = r4
                else:
                    last_status, last_body = r4.status_code, r4.content
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo descargar la imagen: {e}")

    if r is None or r.status_code != 200:
        snippet = ""
        try:
            snippet = last_body[:200].decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise HTTPException(
            last_status or 502,
            f"Origen devolvió {last_status} para host {host}. {snippet}".strip(),
        )

    ctype = r.headers.get("content-type", "image/jpeg")
    if not ctype.startswith("image/"):
        raise HTTPException(415, f"La URL no devolvió una imagen ({ctype})")

    return Response(
        content=r.content,
        media_type=ctype,
        headers={"Cache-Control": "private, max-age=300"},
    )


# ── Admin: descargar imagen externa y subirla a Supabase Storage ──────────────
#
# El frontend NO sube directamente al bucket porque depende de tener una sesión
# Supabase válida en el browser (que a veces expira o no existe si el admin
# entró con la cookie clásica). Acá lo hacemos en el backend con el
# SUPABASE_SERVICE_ROLE_KEY → bypassa RLS y nunca falla por "rol anon".

def _download_image_bytes(url: str) -> tuple[bytes, str]:
    """Descarga una imagen externa con todos los fallbacks del proxy
    (Referer del host, sin Referer, Referer=google, weserv).
    Devuelve (bytes, content_type). Eleva HTTPException si no se pudo.
    """
    import httpx
    from urllib.parse import urlparse, quote

    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")

    host = (urlparse(url).hostname or "").lower()

    def _headers(referer: str | None) -> dict:
        h = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Cache-Control": "no-cache",
        }
        if referer:
            h["Referer"] = referer
        return h

    referer_map = {
        "bhphotovideo.com": "https://www.bhphotovideo.com/",
        "www.bhphotovideo.com": "https://www.bhphotovideo.com/",
        "adorama.com": "https://www.adorama.com/",
        "www.adorama.com": "https://www.adorama.com/",
    }
    primary_referer = next(
        (v for k, v in referer_map.items() if host.endswith(k)),
        f"https://{host}/",
    )

    last_status = None
    last_body = b""
    r = None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, http2=False) as client:
            r = client.get(url, headers=_headers(primary_referer))
            last_status, last_body = r.status_code, r.content
            if r.status_code == 403:
                r2 = client.get(url, headers=_headers(None))
                if r2.status_code == 200:
                    r = r2
                else:
                    last_status, last_body = r2.status_code, r2.content
            if r.status_code == 403:
                r3 = client.get(url, headers=_headers("https://www.google.com/"))
                if r3.status_code == 200:
                    r = r3
                else:
                    last_status, last_body = r3.status_code, r3.content
            if r.status_code in (401, 403, 404, 429) or r.status_code >= 500:
                stripped = url.split("://", 1)[1] if "://" in url else url
                weserv_url = f"https://images.weserv.nl/?url={quote(stripped, safe='')}"
                r4 = client.get(weserv_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/*,*/*;q=0.8",
                })
                if r4.status_code == 200 and r4.headers.get("content-type", "").startswith("image/"):
                    r = r4
                else:
                    last_status, last_body = r4.status_code, r4.content
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo descargar la imagen: {e}")

    if r is None or r.status_code != 200:
        snippet = ""
        try:
            snippet = last_body[:200].decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise HTTPException(
            502,
            f"Origen devolvió {last_status} para host {host}. {snippet}".strip(),
        )

    ctype = r.headers.get("content-type", "image/jpeg")
    if not ctype.startswith("image/"):
        raise HTTPException(415, f"La URL no devolvió una imagen ({ctype})")

    if len(r.content) < 1024:
        raise HTTPException(415, f"Imagen muy chica ({len(r.content)} bytes)")

    return r.content, ctype


def _ext_from_ctype(ct: str) -> str:
    ct = (ct or "").lower()
    if "png" in ct:  return "png"
    if "webp" in ct: return "webp"
    if "avif" in ct: return "avif"
    if "gif" in ct:  return "gif"
    return "jpg"


def _optimize_image(content: bytes) -> tuple[bytes, str, int, int]:
    """Optimiza la imagen: auto-orient + resize a max 1600px ancho + WebP q=85.
    Devuelve (bytes_optimizados, content_type, width, height).
    Si algo falla, devuelve el contenido original como fallback.
    """
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
    except ImportError:
        return content, "image/jpeg", 0, 0

    try:
        img = Image.open(BytesIO(content))
        img = ImageOps.exif_transpose(img)  # auto-orient

        # Convertir a RGB para WebP (los PNGs con transparencia se conservan en RGBA→WebP soporta)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        # Resize si excede 1600px de ancho
        MAX_WIDTH = 1600
        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            new_size = (MAX_WIDTH, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        out = BytesIO()
        img.save(out, format="WEBP", quality=85, method=6)
        return out.getvalue(), "image/webp", img.width, img.height
    except Exception as e:
        print(f"[optimize_image] fallback (no se pudo optimizar): {e}")
        return content, "image/jpeg", 0, 0


def _r2_config() -> dict:
    """Lee la configuración de Cloudflare R2 desde env. Eleva 500 si falta algo."""
    import os
    cfg = {
        "account_id":      os.getenv("R2_ACCOUNT_ID") or "",
        "access_key_id":   os.getenv("R2_ACCESS_KEY_ID") or "",
        "secret_key":      os.getenv("R2_SECRET_ACCESS_KEY") or "",
        "bucket":          os.getenv("R2_BUCKET") or "equipos-fotos",
        "public_base":     (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/"),
    }
    missing = [k for k in ("account_id", "access_key_id", "secret_key") if not cfg[k]]
    if missing:
        raise HTTPException(
            500,
            f"R2 no configurado: faltan env vars {', '.join('R2_'+m.upper() for m in missing)}. "
            "Configurá en Railway: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
            "R2_BUCKET, R2_PUBLIC_BASE.",
        )
    if not cfg["public_base"]:
        # Default al endpoint público de R2 (sin custom domain) — válido si activaste public bucket
        cfg["public_base"] = f"https://pub-{cfg['account_id']}.r2.dev"
    return cfg


def _upload_to_r2(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket R2 vía S3 API (boto3). Devuelve la URL pública."""
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise HTTPException(500, "boto3 no instalado en el backend")

    cfg = _r2_config()
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )

    try:
        client.put_object(
            Bucket=cfg["bucket"],
            Key=path,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        raise HTTPException(502, f"R2 upload falló: {e}")

    return f"{cfg['public_base']}/{path}"


def _upload_to_supabase_storage(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket equipos-fotos vía REST API usando service role.
    Devuelve la URL pública. Eleva HTTPException si falla.
    """
    import os
    import httpx

    base = (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_PROJECT_URL")
        or "https://ytujjqoffcdsdowfqaex.supabase.co"
    ).rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        raise HTTPException(
            500,
            "Falta SUPABASE_SERVICE_ROLE_KEY en el backend. "
            "Configurala como env var en Railway.",
        )

    bucket = "equipos-fotos"
    upload_url = f"{base}/storage/v1/object/{bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": content_type,
        "x-upsert": "false",
        "Cache-Control": "3600",
    }
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo subir a Storage: {e}")

    if r.status_code not in (200, 201):
        snippet = (r.text or "")[:300]
        raise HTTPException(
            r.status_code if r.status_code >= 400 else 502,
            f"Storage devolvió {r.status_code}: {snippet}",
        )

    return f"{base}/storage/v1/object/public/{bucket}/{path}"


class UploadFotoFromUrlInput(BaseModel):
    url: str


@router.post("/admin/equipos/{equipo_id}/upload-foto-from-url")
def admin_upload_foto_from_url(
    equipo_id: int,
    payload: UploadFotoFromUrlInput,
    request: Request,
):
    """Descarga imagen externa, la optimiza (resize + WebP) y la sube a Cloudflare R2.
    Devuelve {public_url, path, size, content_type}.

    Reemplaza el upload directo desde el browser y el storage de Supabase.
    """
    from admin_guard import require_admin
    require_admin(request)

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    # Si ya es una URL del propio bucket R2 (público), no rehospedamos
    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        return {"public_url": url, "path": None, "skipped": True}

    raw_content, raw_ctype = _download_image_bytes(url)
    # Optimización: resize a max 1600px + WebP q=85
    content, ctype, w, h = _optimize_image(raw_content)
    ext = _ext_from_ctype(ctype)

    import time as _time
    path = f"equipos/{equipo_id}/foto-{int(_time.time() * 1000)}.{ext}"
    public_url = _upload_to_r2(path, content, ctype)

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


# ── Admin: subir bytes de un archivo (multipart) directo a R2 ─────────────

@router.post("/admin/equipos/{equipo_id}/upload-foto")
async def admin_upload_foto_file(
    equipo_id: int,
    request: Request,
):
    """Sube un archivo (multipart/form-data, campo `file`) a R2 después de
    optimizarlo. Devuelve {public_url, path, ...}.
    """
    from admin_guard import require_admin
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(400, "Archivo vacío")
    if len(raw_content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20MB)")

    content, ctype, w, h = _optimize_image(raw_content)
    ext = _ext_from_ctype(ctype)

    import time as _time
    path = f"equipos/{equipo_id}/foto-{int(_time.time() * 1000)}.{ext}"
    public_url = _upload_to_r2(path, content, ctype)

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


# ── Admin: diagnóstico de R2 (sin exponer secretos) ─────────────────────────

@router.get("/admin/storage/diag")
def admin_storage_diag(request: Request):
    """Verifica que R2 esté configurado correctamente. Sólo dice si las vars
    están presentes y si el upload+read end-to-end funciona. NUNCA devuelve
    el contenido del secret."""
    from admin_guard import require_admin
    require_admin(request)

    import time as _time
    import httpx

    vars_status = {
        "R2_ACCOUNT_ID":         bool(os.getenv("R2_ACCOUNT_ID")),
        "R2_ACCESS_KEY_ID":      bool(os.getenv("R2_ACCESS_KEY_ID")),
        "R2_SECRET_ACCESS_KEY":  bool(os.getenv("R2_SECRET_ACCESS_KEY")),
        "R2_BUCKET":             os.getenv("R2_BUCKET") or "equipos-fotos",
        "R2_PUBLIC_BASE":        os.getenv("R2_PUBLIC_BASE") or None,
    }
    missing = [k for k, v in vars_status.items() if v is False]
    if missing:
        return {"ok": False, "vars": vars_status, "missing": missing, "tested": False}

    # Smoke test: subir un blob chico y leerlo
    try:
        sample = b"R2 smoke test " + str(int(_time.time())).encode()
        path = f"diag/smoke-{int(_time.time())}.txt"
        public_url = _upload_to_r2(path, sample, "text/plain")
        verify = httpx.get(public_url, timeout=10.0)
        ok = verify.status_code == 200 and verify.content == sample
        return {
            "ok":         ok,
            "vars":       vars_status,
            "tested":     True,
            "public_url": public_url,
            "verify":     verify.status_code,
        }
    except HTTPException as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": e.detail}
    except Exception as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": str(e)}
