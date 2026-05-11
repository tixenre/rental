"""
routes/pedidos.py — CRUD de pedidos, disponibilidad y generación de PDFs.
"""

import datetime
import logging
from math import ceil
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from database import get_db, row_to_dict
from pdf import _pedido_html, _albaran_html, _contrato_html, _render_pdf, _pedido_filename
from admin_guard import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

ESTADOS_VALIDOS    = {"borrador", "presupuesto", "confirmado", "retirado", "devuelto", "finalizado", "cancelado"}
ESTADOS_RESERVADO  = "('presupuesto','confirmado','retirado')"   # usado en SQL IN clauses


# ── Helpers internos ─────────────────────────────────────────────────────────

def _maybe_finalizar(conn, pedido_id: int):
    """Si el pedido está 'devuelto' y monto_pagado >= monto_total → 'finalizado'."""
    p = conn.execute(
        "SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=?", (pedido_id,)
    ).fetchone()
    if not p:
        return
    if (p["estado"] == "devuelto"
            and (p["monto_pagado"] or 0) >= (p["monto_total"] or 0)
            and (p["monto_total"] or 0) > 0):
        conn.execute("UPDATE alquileres SET estado='finalizado' WHERE id=?", (pedido_id,))




def _get_alquiler_items(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT pi.*, e.nombre, e.marca, e.foto_url, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id = ?
    """, (pedido_id,)).fetchall()
    items = [row_to_dict(r) for r in rows]

    # Agregar componentes (kits) a cada item
    for item in items:
        comp_rows = conn.execute("""
            SELECT kc.*, ec.nombre, ec.marca, ec.foto_url, ec.cantidad AS stock_total,
                   ec.nombre_publico, ec.nombre_publico_largo
            FROM kit_componentes kc
            JOIN equipos ec ON ec.id = kc.componente_id
            WHERE kc.equipo_id = ?
        """, (item['equipo_id'],)).fetchall()
        item['componentes'] = [row_to_dict(c) for c in comp_rows]

    return items


def _next_numero_pedido(conn) -> int:
    """Devuelve el próximo número de pedido usando una SEQUENCE de PostgreSQL (race-free)."""
    return conn.execute("SELECT nextval('numero_pedido_seq')").fetchone()[0]


def _aplicar_descuento(bruto: float, pct: float) -> int:
    """Aplica un descuento porcentual y devuelve el monto neto redondeado."""
    if not pct:
        return int(bruto)
    return int(round(bruto * (1 - pct / 100)))


def _batch_get_alquiler_items(conn, pedido_ids: list[int]) -> dict[int, list[dict]]:
    """Trae items de múltiples pedidos en 2 queries en lugar de N+1.

    Retorna {pedido_id: [items...]} donde cada item ya tiene su lista 'componentes'.
    """
    if not pedido_ids:
        return {}

    ph = ",".join(["?"] * len(pedido_ids))
    rows = conn.execute(f"""
        SELECT pi.*, e.nombre, e.marca, e.foto_url, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id IN ({ph})
    """, pedido_ids).fetchall()

    all_items   = [row_to_dict(r) for r in rows]
    equipo_ids  = list({item["equipo_id"] for item in all_items})
    comp_map: dict[int, list[dict]] = {eid: [] for eid in equipo_ids}

    if equipo_ids:
        cph = ",".join(["?"] * len(equipo_ids))
        comp_rows = conn.execute(f"""
            SELECT kc.*, ec.nombre, ec.marca, ec.foto_url, ec.cantidad AS stock_total,
                   ec.nombre_publico, ec.nombre_publico_largo
            FROM kit_componentes kc
            JOIN equipos ec ON ec.id = kc.componente_id
            WHERE kc.equipo_id IN ({cph})
        """, equipo_ids).fetchall()
        for c in comp_rows:
            cd = row_to_dict(c)
            comp_map[cd["equipo_id"]].append(cd)

    result: dict[int, list[dict]] = {pid: [] for pid in pedido_ids}
    for item in all_items:
        item["componentes"] = comp_map.get(item["equipo_id"], [])
        result[item["pedido_id"]].append(item)

    return result


def _get_alquiler_pagos(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM alquiler_pagos WHERE pedido_id = ? ORDER BY fecha, created_at
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def _recalcular_monto_pagado(conn, pedido_id: int):
    """Suma todos los pagos del registro y actualiza monto_pagado en pedidos.

    No hace commit — el caller debe commitear inmediatamente después para que
    el UPDATE no quede huérfano si falla algo posterior en la misma transacción.
    """
    total = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM alquiler_pagos WHERE pedido_id=?", (pedido_id,)
    ).fetchone()[0]
    conn.execute("UPDATE alquileres SET monto_pagado=? WHERE id=?", (total, pedido_id))


def _get_alquiler_detail(conn, id: int) -> dict:
    row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Pedido no encontrado")
    pedido = row_to_dict(row)
    pedido["items"] = _get_alquiler_items(conn, id)
    pedido["pagos"] = _get_alquiler_pagos(conn, id)
    return pedido


# ── Modelos ──────────────────────────────────────────────────────────────────

def _parse_precio(v) -> int:
    """Acepta int, float o string con formato '$15.000' → 15000."""
    if v is None:
        return 0
    s = str(v).replace("$", "").replace(".", "").replace(",", "").strip()
    try:
        return int(float(s)) if s else 0
    except (ValueError, TypeError):
        return 0


class PedidoItem(BaseModel):
    from pydantic import field_validator
    equipo_id:      int
    cantidad:       int
    precio_jornada: int = 0

    @field_validator("precio_jornada", mode="before")
    @classmethod
    def coerce_precio(cls, v):
        return _parse_precio(v)


class PedidoCreate(BaseModel):
    cliente_nombre:   Optional[str] = ""
    cliente_email:    Optional[str] = None
    cliente_telefono: Optional[str] = None
    cliente_id:       Optional[int] = None
    notas:            Optional[str] = None
    fecha_desde:      Optional[str] = None
    fecha_hasta:      Optional[str] = None
    items:            list[PedidoItem] = []
    estado:           Optional[str] = "presupuesto"


class PedidoEstado(BaseModel):
    estado: str


class PagoParcial(BaseModel):
    monto_pagado: int


class PagoCreate(BaseModel):
    monto:    int
    concepto: Optional[str] = None
    fecha:    Optional[str] = None   # YYYY-MM-DD; si no viene usa hoy


class PedidoDatos(BaseModel):
    cliente_id:       Optional[int]   = None
    cliente_nombre:   Optional[str]   = None
    cliente_email:    Optional[str]   = None
    cliente_telefono: Optional[str]   = None
    fecha_desde:      Optional[str]   = None
    fecha_hasta:      Optional[str]   = None
    notas:            Optional[str]   = None
    descuento_pct:    Optional[float] = None


class PedidoItemUpdate(BaseModel):
    items: list[PedidoItem]


# ── Disponibilidad ───────────────────────────────────────────────────────────

@router.get("/disponibilidad")
def get_disponibilidad(
    fecha_desde: str = Query(...),
    fecha_hasta: str = Query(...),
    exclude_pedido_id: int = Query(None),
):
    conn = get_db()
    # exclude_pedido_id como NULL en SQL → (NULL IS NULL) = TRUE → no filtra nada
    excl = exclude_pedido_id  # None o int, ambos seguros como parámetro

    try:
        directas = conn.execute(f"""
            SELECT e.id, e.cantidad,
                   COALESCE(SUM(CASE
                     WHEN p.estado IN {ESTADOS_RESERVADO}
                          AND p.fecha_desde < ?
                          AND p.fecha_hasta > ?
                          AND (? IS NULL OR p.id != ?)
                     THEN pi.cantidad ELSE 0
                   END), 0) AS reservado
            FROM equipos e
            LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
            LEFT JOIN alquileres p ON p.id = pi.pedido_id
            GROUP BY e.id
        """, (fecha_hasta, fecha_desde, excl, excl)).fetchall()

        reservado = {r["id"]: r["reservado"] for r in directas}
        cantidad  = {r["id"]: r["cantidad"]  for r in directas}

        via_kit = conn.execute(f"""
            SELECT kc.componente_id,
                   SUM(pi.cantidad * kc.cantidad) AS extra
            FROM kit_componentes kc
            JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE p.estado IN {ESTADOS_RESERVADO}
              AND p.fecha_desde < ?
              AND p.fecha_hasta > ?
              AND (? IS NULL OR p.id != ?)
            GROUP BY kc.componente_id
        """, (fecha_hasta, fecha_desde, excl, excl)).fetchall()

        for r in via_kit:
            reservado[r["componente_id"]] = reservado.get(r["componente_id"], 0) + r["extra"]

        return {
            str(eid): max(0, cantidad.get(eid, 0) - reservado.get(eid, 0))
            for eid in cantidad
        }
    finally:
        conn.close()


# ── Rutas de pedidos ─────────────────────────────────────────────────────────

@router.post("/alquileres", status_code=201)
def create_pedido_endpoint(data: PedidoCreate, request: Request):
    """Endpoint admin para crear pedido. La lógica está en `create_pedido`,
    así el portal cliente (cliente_portal.py) la reutiliza sin pasar por admin guard."""
    require_admin(request)
    return create_pedido(data)


def create_pedido(data: PedidoCreate):
    """Lógica interna de creación de pedido. Llamada por el endpoint admin
    (`create_pedido_endpoint`) y también por `cliente_portal.cliente_crear_pedido`
    que tiene su propio `require_cliente`."""
    if not data.items and data.estado != "borrador":
        raise HTTPException(400, "El pedido debe tener al menos un ítem")

    conn = get_db()
    cliente_nombre   = data.cliente_nombre
    cliente_email    = data.cliente_email
    cliente_telefono = data.cliente_telefono

    try:
        descuento_pct = 0.0
        if data.cliente_id:
            c = conn.execute("SELECT * FROM clientes WHERE id=?", (data.cliente_id,)).fetchone()
            if c:
                cliente_nombre   = f"{c['apellido']}, {c['nombre']}"
                cliente_email    = cliente_email    or c["email"]
                cliente_telefono = cliente_telefono or c["telefono"]
                descuento_pct    = c["descuento"] or 0.0

        if data.fecha_desde and data.fecha_hasta:
            d0 = datetime.datetime.fromisoformat(data.fecha_desde)
            d1 = datetime.datetime.fromisoformat(data.fecha_hasta)
            hoy = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            if d0 >= d1:
                raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
            if d0 < hoy:
                raise HTTPException(400, "fecha_desde no puede ser en el pasado")

            jornadas = max(1, ceil((d1 - d0).total_seconds() / 3600 / 24))
        else:
            jornadas = 1

        bruto = 0
        items_rows  = []
        for it in data.items:
            if not conn.execute("SELECT id FROM equipos WHERE id=?", (it.equipo_id,)).fetchone():
                raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado")
            subtotal = it.precio_jornada * it.cantidad * jornadas
            bruto += subtotal
            items_rows.append((it.equipo_id, it.cantidad, it.precio_jornada, subtotal))
        monto_total = _aplicar_descuento(bruto, descuento_pct)

        estado_inicial = data.estado if data.estado in {"borrador", "presupuesto"} else "presupuesto"
        next_num = _next_numero_pedido(conn)
        cur = conn.execute("""
            INSERT INTO alquileres (cliente_nombre, cliente_email, cliente_telefono,
                                 cliente_id, notas, fecha_desde, fecha_hasta,
                                 monto_total, estado, numero_pedido, numero_remito, descuento_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cliente_nombre, cliente_email, cliente_telefono,
              data.cliente_id, data.notas, data.fecha_desde, data.fecha_hasta,
              monto_total, estado_inicial, next_num, str(next_num), descuento_pct))
        pedido_id = cur.lastrowid

        conn.executemany("""
            INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
            VALUES (?,?,?,?,?)
        """, [(pedido_id, *row) for row in items_rows])

        if estado_inicial == "presupuesto" and data.fecha_desde and data.fecha_hasta:
            problemas = _check_stock(conn, pedido_id, data.fecha_desde, data.fecha_hasta)
            if problemas:
                raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

        conn.commit()
        pedido = _get_alquiler_detail(conn, pedido_id)
        return pedido
    except Exception:
        logger.error("Error creando pedido", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


SORT_COLS = {
    "numero":  "p.numero_pedido",
    "cliente": "p.cliente_nombre",
    "monto":   "p.monto_total",
    "fecha":   "p.fecha_desde",
    "estado":  "p.estado",
}

@router.get("/alquileres")
def list_pedidos(
    request: Request,
    estado:   Optional[str] = Query(None),
    fuente:   Optional[str] = Query(None),
    q:        Optional[str] = Query(None),
    page:     int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    sort_by:  Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
):
    require_admin(request)
    conn   = get_db()
    offset = (page - 1) * per_page
    params: list = []
    where  = "WHERE 1=1"

    try:
        if estado:
            where += " AND p.estado = ?"
            params.append(estado)
        if fuente:
            where += " AND p.fuente = ?"
            params.append(fuente)
        if q:
            like = f"%{q}%"
            where += " AND (p.cliente_nombre LIKE ? OR p.numero_remito LIKE ? OR CAST(p.numero_pedido AS TEXT) LIKE ?)"
            params += [like, like, like]

        col = SORT_COLS.get(sort_by, "p.numero_pedido")
        direction = "ASC" if sort_dir == "asc" else "DESC"
        # Poner "Registro manual" (numero_remito IS NULL) al final
        order = f"p.numero_remito IS NOT NULL DESC, {col} {direction}"
        # secundario: número descendente para desempate
        if col != "p.numero_pedido":
            order += ", p.numero_pedido DESC"

        total = conn.execute(f"SELECT COUNT(*) FROM alquileres p {where}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT p.* FROM alquileres p {where} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        pedidos    = [row_to_dict(r) for r in rows]
        items_map  = _batch_get_alquiler_items(conn, [p["id"] for p in pedidos])
        for p in pedidos:
            p["items"] = items_map.get(p["id"], [])

        return {"total": total, "page": page, "per_page": per_page, "items": pedidos}
    finally:
        conn.close()


@router.get("/alquileres/{id}")
def get_pedido(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        pedido = _get_alquiler_detail(conn, id)
    finally:
        conn.close()
    return pedido


@router.delete("/alquileres/{id}", status_code=204)
def delete_pedido(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM alquileres WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Pedido no encontrado")
        # Borrar ítems, pagos e historicos asociados (FK cascade si está activada, pero por las dudas)
        conn.execute("DELETE FROM alquiler_items  WHERE pedido_id=?", (id,))
        conn.execute("DELETE FROM alquiler_pagos  WHERE pedido_id=?", (id,))
        conn.execute("DELETE FROM alquileres       WHERE id=?",        (id,))
        conn.commit()
    except Exception:
        logger.error("Error eliminando pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


ESTADOS_REQUIEREN_FECHAS = {"confirmado", "retirado", "devuelto", "finalizado"}


def _check_stock(conn, pedido_id: int, fecha_desde: str, fecha_hasta: str) -> list[str]:
    """Devuelve lista de nombres de equipos sin stock suficiente para el rango dado.

    Usa SELECT ... FOR UPDATE en equipos para evitar race conditions de concurrencia.
    """
    items = conn.execute("""
        SELECT pi.equipo_id, pi.cantidad, e.nombre, e.cantidad AS stock_total
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id = ?
    """, (pedido_id,)).fetchall()

    problemas = []
    for it in items:
        # Lock la fila de equipo durante el chequeo para evitar race conditions.
        # SELECT ... FOR UPDATE evita que otra transacción concurrente lea el stock
        # mientras estamos validando.
        lock_result = conn.execute(
            "SELECT cantidad FROM equipos WHERE id = ? FOR UPDATE",
            (it["equipo_id"],)
        ).fetchone()

        if not lock_result:
            problemas.append(f"{it['nombre']} (equipo no encontrado)")
            continue

        stock_total = lock_result["cantidad"]

        # Cuánto está reservado para ese equipo en el rango (excluyendo este pedido)
        reservado = conn.execute(f"""
            SELECT COALESCE(SUM(pi2.cantidad), 0)
            FROM alquiler_items pi2
            JOIN alquileres p ON p.id = pi2.pedido_id
            WHERE pi2.equipo_id = ?
              AND p.id != ?
              AND p.estado IN {ESTADOS_RESERVADO}
              AND p.fecha_desde < ?
              AND p.fecha_hasta > ?
        """, (it["equipo_id"], pedido_id, fecha_hasta, fecha_desde)).fetchone()[0]

        disponible = stock_total - reservado
        if disponible < it["cantidad"]:
            problemas.append(
                f"{it['nombre']} (necesitás {it['cantidad']}, disponible: {max(0, disponible)})"
            )
    return problemas


@router.patch("/alquileres/{id}")
def update_pedido(id: int, data: PedidoEstado, request: Request):
    require_admin(request)
    if data.estado not in ESTADOS_VALIDOS:
        raise HTTPException(400, f"Estado inválido. Usar: {', '.join(sorted(ESTADOS_VALIDOS))}")

    conn  = get_db()
    try:
        p_row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not p_row:
            raise HTTPException(404, "Pedido no encontrado")

        # ── Validaciones para estados que requieren fechas y stock ──────────────
        if data.estado in ESTADOS_REQUIEREN_FECHAS and p_row["fuente"] != "historico":
            errores = []
            if not p_row["fecha_desde"] or not p_row["fecha_hasta"]:
                errores.append("El pedido no tiene fechas de inicio y fin.")
            else:
                try:
                    d0 = datetime.datetime.fromisoformat(p_row["fecha_desde"])
                    d1 = datetime.datetime.fromisoformat(p_row["fecha_hasta"])
                    hoy = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                    if d0 >= d1:
                        errores.append("fecha_hasta debe ser posterior a fecha_desde")
                    if d0 < hoy:
                        errores.append("fecha_desde no puede ser en el pasado")
                except ValueError:
                    errores.append("Las fechas tienen formato inválido")

            if not conn.execute(
                "SELECT 1 FROM alquiler_items WHERE pedido_id=?", (id,)
            ).fetchone():
                errores.append("El pedido no tiene equipos cargados.")
            if p_row["fecha_desde"] and p_row["fecha_hasta"] and not errores:
                sin_stock = _check_stock(conn, id, p_row["fecha_desde"], p_row["fecha_hasta"])
                for s in sin_stock:
                    errores.append(f"Sin stock suficiente: {s}")
            if errores:
                raise HTTPException(422, {"errores": errores})

        es_historico    = p_row["fuente"] == "historico"
        estado_anterior = p_row["estado"]
        updates         = {"estado": data.estado}

        if data.estado == "confirmado" and not p_row["numero_pedido"]:
            next_n = _next_numero_pedido(conn)
            updates["numero_pedido"] = next_n
            updates["numero_remito"] = str(next_n)

        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE alquileres SET {set_clause} WHERE id=?", (*updates.values(), id))

        _maybe_finalizar(conn, id)
        conn.commit()

        pedido = _get_alquiler_detail(conn, id)
        return pedido
    except Exception:
        logger.error("Error actualizando estado del pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/alquileres/{id}/pago")
def registrar_pago(id: int, data: PagoParcial, request: Request):
    require_admin(request)
    """Endpoint legacy: setea monto_pagado directamente (sin registro en tabla pagos)."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM alquileres WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Pedido no encontrado")
        if data.monto_pagado < 0:
            raise HTTPException(400, "El monto pagado no puede ser negativo")
        conn.execute("UPDATE alquileres SET monto_pagado=? WHERE id=?", (data.monto_pagado, id))
        _maybe_finalizar(conn, id)
        conn.commit()
        pedido = _get_alquiler_detail(conn, id)
        return pedido
    except Exception:
        logger.error("Error actualizando monto_pagado del pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Registro de pagos ────────────────────────────────────────────────────────

@router.get("/alquileres/{id}/pagos")
def list_pagos(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM alquileres WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Pedido no encontrado")
        pagos = _get_alquiler_pagos(conn, id)
        return pagos
    finally:
        conn.close()


@router.post("/alquileres/{id}/pagos", status_code=201)
def agregar_pago(id: int, data: PagoCreate, request: Request):
    """Agrega una entrada de pago y recalcula monto_pagado."""
    require_admin(request)
    if data.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")
    conn = get_db()
    try:
        p = conn.execute("SELECT estado FROM alquileres WHERE id=?", (id,)).fetchone()
        if not p:
            raise HTTPException(404, "Pedido no encontrado")
        if p["estado"] in ("cancelado",):
            raise HTTPException(400, "No se pueden agregar pagos a un pedido cancelado")

        fecha = data.fecha or datetime.date.today().isoformat()
        conn.execute("""
            INSERT INTO alquiler_pagos (pedido_id, monto, concepto, fecha)
            VALUES (?,?,?,?)
        """, (id, data.monto, data.concepto, fecha))

        _recalcular_monto_pagado(conn, id)
        _maybe_finalizar(conn, id)
        conn.commit()

        pedido = _get_alquiler_detail(conn, id)
        return pedido
    except Exception:
        logger.error("Error agregando pago al pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/alquileres/{id}/pagos/{pago_id}", status_code=200)
def eliminar_pago(id: int, pago_id: int, request: Request):
    require_admin(request)
    """Elimina una entrada de pago y recalcula monto_pagado."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM alquileres WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Pedido no encontrado")
        if not conn.execute(
            "SELECT id FROM alquiler_pagos WHERE id=? AND pedido_id=?", (pago_id, id)
        ).fetchone():
            raise HTTPException(404, "Pago no encontrado")

        conn.execute("DELETE FROM alquiler_pagos WHERE id=?", (pago_id,))
        _recalcular_monto_pagado(conn, id)

        # Si se quitó pago, puede que ya no esté finalizado → revertir si aplica
        p = conn.execute("SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=?", (id,)).fetchone()
        if p and p["estado"] == "finalizado" and (p["monto_pagado"] or 0) < (p["monto_total"] or 0):
            conn.execute("UPDATE alquileres SET estado='devuelto' WHERE id=?", (id,))

        conn.commit()
        pedido = _get_alquiler_detail(conn, id)
        return pedido
    except Exception:
        logger.error("Error registrando pago en pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/alquileres/{id}/datos")
def update_pedido_datos(id: int, data: PedidoDatos, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not p:
            raise HTTPException(404, "Pedido no encontrado")

        payload = {k: v for k, v in data.model_dump(exclude_unset=True).items()}

        cliente_cambio = "cliente_id" in payload and payload["cliente_id"]
        if cliente_cambio:
            c = conn.execute("SELECT * FROM clientes WHERE id=?", (payload["cliente_id"],)).fetchone()
            if c:
                payload.setdefault("cliente_nombre",   f"{c['apellido']}, {c['nombre']}")
                payload.setdefault("cliente_email",    c["email"])
                payload.setdefault("cliente_telefono", c["telefono"])
                # Solo usar descuento del cliente si no vino uno manual en el payload
                if "descuento_pct" not in payload:
                    payload["descuento_pct"] = c["descuento"] or 0.0

        # Validar fechas si se están actualizando
        if "fecha_desde" in payload or "fecha_hasta" in payload:
            nueva_desde = payload.get("fecha_desde") or p["fecha_desde"]
            nueva_hasta = payload.get("fecha_hasta") or p["fecha_hasta"]
            if nueva_desde and nueva_hasta:
                d0 = datetime.datetime.fromisoformat(nueva_desde)
                d1 = datetime.datetime.fromisoformat(nueva_hasta)
                hoy = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                if d0 >= d1:
                    raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
                if d0 < hoy:
                    raise HTTPException(400, "fecha_desde no puede ser en el pasado")

        if payload:
            cols = ", ".join(f"{k}=?" for k in payload)
            conn.execute(f"UPDATE alquileres SET {cols} WHERE id=?", (*payload.values(), id))

            if "fecha_desde" in payload or "fecha_hasta" in payload or cliente_cambio:
                p2 = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
                if p2["fecha_desde"] and p2["fecha_hasta"]:
                    d0 = datetime.datetime.fromisoformat(p2["fecha_desde"])
                    d1 = datetime.datetime.fromisoformat(p2["fecha_hasta"])
                    jornadas = max(1, ceil((d1 - d0).total_seconds() / 3600 / 24))
                else:
                    jornadas = 1
                items = conn.execute(
                    "SELECT id, cantidad, precio_jornada FROM alquiler_items WHERE pedido_id=?", (id,)
                ).fetchall()
                bruto = 0
                for it in items:
                    sub = it["precio_jornada"] * it["cantidad"] * jornadas
                    conn.execute("UPDATE alquiler_items SET subtotal=? WHERE id=?", (sub, it["id"]))
                    bruto += sub
                monto_total = _aplicar_descuento(bruto, p2["descuento_pct"] or 0)
                conn.execute("UPDATE alquileres SET monto_total=? WHERE id=?", (monto_total, id))

            conn.commit()

        pedido = _get_alquiler_detail(conn, id)
        return pedido
    except Exception:
        logger.error("Error actualizando datos del pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


@router.put("/alquileres/{id}/items")
def update_alquiler_items(id: int, data: PedidoItemUpdate, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not p:
            raise HTTPException(404, "Pedido no encontrado")
        if not data.items:
            raise HTTPException(400, "Debe tener al menos un ítem")

        if p["fecha_desde"] and p["fecha_hasta"]:
            d0 = datetime.datetime.fromisoformat(p["fecha_desde"])
            d1 = datetime.datetime.fromisoformat(p["fecha_hasta"])
            jornadas = max(1, ceil((d1 - d0).total_seconds() / 3600 / 24))
        else:
            jornadas = 1

        bruto = 0
        rows = []
        for it in data.items:
            if not conn.execute("SELECT id FROM equipos WHERE id=?", (it.equipo_id,)).fetchone():
                raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado")
            subtotal = it.precio_jornada * it.cantidad * jornadas
            bruto += subtotal
            rows.append((id, it.equipo_id, it.cantidad, it.precio_jornada, subtotal))
        monto_total = _aplicar_descuento(bruto, p["descuento_pct"] or 0)

        conn.execute("DELETE FROM alquiler_items WHERE pedido_id=?", (id,))
        conn.executemany("""
            INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
            VALUES (?,?,?,?,?)
        """, rows)
        conn.execute("UPDATE alquileres SET monto_total=? WHERE id=?", (monto_total, id))
        conn.commit()

        pedido = _get_alquiler_detail(conn, id)
        return pedido
    except Exception:
        logger.error("Error actualizando items del pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


# ── PDFs ─────────────────────────────────────────────────────────────────────

@router.get("/alquileres/{id}/pdf")
async def pedido_pdf(id: int, request: Request, format: str = "pdf"):
    """`format=html` devuelve el preview HTML sin pasar por el renderer."""
    require_admin(request)
    conn = get_db()
    try:
        row  = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")
        pedido = row_to_dict(row)
        pedido["items"] = _get_alquiler_items(conn, id)
    finally:
        conn.close()

    html = _pedido_html(pedido)
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    pdf_bytes = await _render_pdf(html)
    filename  = _pedido_filename(pedido)
    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alquileres/{id}/albaran")
async def pedido_albaran(id: int, request: Request, format: str = "pdf"):
    """`format=html` devuelve el preview HTML sin pasar por el renderer."""
    require_admin(request)
    conn = get_db()
    try:
        row  = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")
        pedido = row_to_dict(row)
        items  = conn.execute("""
            SELECT pi.cantidad, e.nombre, e.marca, e.modelo, e.serie, e.valor_reposicion, e.foto_url,
                   e.nombre_publico, e.nombre_publico_largo, pi.equipo_id
            FROM alquiler_items pi
            JOIN equipos e ON e.id = pi.equipo_id
            WHERE pi.pedido_id = ?
            ORDER BY e.nombre
        """, (id,)).fetchall()
        pedido["items"] = [row_to_dict(i) for i in items]

        # Agregar componentes a cada item
        for item in pedido["items"]:
            comp_rows = conn.execute("""
                SELECT ec.nombre, ec.marca, ec.modelo, ec.serie, ec.valor_reposicion,
                       ec.nombre_publico, ec.nombre_publico_largo, kc.cantidad
                FROM kit_componentes kc
                JOIN equipos ec ON ec.id = kc.componente_id
                WHERE kc.equipo_id = ?
            """, (item['equipo_id'],)).fetchall()
            item['componentes'] = [row_to_dict(c) for c in comp_rows]
    finally:
        conn.close()

    html = _albaran_html(pedido)
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    pdf_bytes = await _render_pdf(html)
    filename  = _pedido_filename(pedido, suffix="albaran")
    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alquileres/{id}/contrato")
async def pedido_contrato(id: int, request: Request, format: str = "pdf"):
    """Genera el PDF del contrato de alquiler."""
    require_admin(request)
    conn    = get_db()
    try:
        pedido  = _get_alquiler_detail(conn, id)

        # Agregar componentes a cada item
        for item in pedido["items"]:
            comp_rows = conn.execute("""
                SELECT ec.nombre, ec.marca, ec.modelo, ec.serie, ec.valor_reposicion,
                       ec.nombre_publico, ec.nombre_publico_largo, kc.cantidad
                FROM kit_componentes kc
                JOIN equipos ec ON ec.id = kc.componente_id
                WHERE kc.equipo_id = ?
            """, (item['equipo_id'],)).fetchall()
            item['componentes'] = [row_to_dict(c) for c in comp_rows]
    finally:
        conn.close()

    html = _contrato_html(pedido)
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    pdf_bytes = await _render_pdf(html)
    filename  = _pedido_filename(pedido, suffix="contrato")
    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )
