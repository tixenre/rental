"""
routes/equipos.py — CRUD de equipos, kits, etiquetas, categorías y fichas.
"""

import calendar as _cal
import datetime
from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict, attach_tags, attach_kit
from routes.auth import get_session

router = APIRouter()


class EquipoCreate(BaseModel):
    nombre:           str
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         int             = 1
    precio_jornada:   Optional[int]   = None
    precio_usd:       Optional[float] = None
    roi_pct:          Optional[float] = None
    valor_reposicion: Optional[float] = None
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = "Rambla"
    visible_catalogo: Optional[int]   = 1
    estado:           Optional[str]   = "operativo"


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
    etiquetas: list[str]


@router.get("/equipos/afuera")
def equipos_afuera():
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


@router.get("/equipos")
def list_equipos(
    request:       Request,
    q:             Optional[str]  = Query(None),
    etiqueta:      Optional[str]  = Query(None),
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
    if etiqueta:
        base_sql += """
          AND e.id IN (
            SELECT ee.equipo_id FROM equipo_etiquetas ee
            JOIN etiquetas et ON et.id = ee.etiqueta_id
            WHERE et.nombre = ?
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


@router.put("/equipos/{id}/etiquetas", status_code=200)
def set_etiquetas(id: int, data: EtiquetasUpdate):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute("DELETE FROM equipo_etiquetas WHERE equipo_id = ?", (id,))
        for orden, nombre in enumerate(data.etiquetas):
            nombre = nombre.strip()
            if not nombre:
                continue
            row = conn.execute("SELECT id FROM etiquetas WHERE nombre = ?", (nombre,)).fetchone()
            if row:
                etiqueta_id = row["id"]
            else:
                cur = conn.execute("INSERT INTO etiquetas (nombre) VALUES (?)", (nombre,))
                etiqueta_id = cur.lastrowid
            conn.execute(
                "INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden) VALUES (?,?,?) ON CONFLICT (equipo_id, etiqueta_id) DO UPDATE SET orden=EXCLUDED.orden",
                (id, etiqueta_id, orden),
            )
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
def get_categorias():
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT ee.equipo_id, et.nombre, ee.orden
            FROM equipo_etiquetas ee
            JOIN etiquetas et ON et.id = ee.etiqueta_id
            ORDER BY ee.equipo_id, ee.orden
        """).fetchall()

        from collections import defaultdict
        tree:        dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        main_counts: dict[str, int]            = defaultdict(int)
        item_main:   dict[int, str]            = {}

        for r in rows:
            if r["orden"] == 0:
                item_main[r["equipo_id"]] = r["nombre"]
                main_counts[r["nombre"]] += 1

        for r in rows:
            if r["orden"] > 0 and r["equipo_id"] in item_main:
                tree[item_main[r["equipo_id"]]][r["nombre"]] += 1

        return [
            {
                "nombre": main,
                "total":  main_counts[main],
                "subtags": [
                    {"nombre": sub, "total": cnt}
                    for sub, cnt in sorted(tree[main].items(), key=lambda x: -x[1])
                ],
            }
            for main in sorted(main_counts.keys())
        ]
    finally:
        conn.close()


@router.get("/equipos/{id}/calendario")
def get_equipo_calendario(id: int, year: int = Query(...), month: int = Query(...)):
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
