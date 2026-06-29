"""Solicitudes de modificación de pedido (#501 — extraído del god-module
`routes/cliente_portal.py`).

Flujo completo de modificación de un pedido: el cliente pide cambios
(fechas/ítems), el sistema valida (ventanas de corte, stock hipotético) y manda
mails, y el admin las ve y resuelve. Registra sus rutas en el router compartido
del paquete `routes.cliente_portal`. Los helpers compartidos (`require_cliente`,
`_modificacion_ventana_horas`, `_ventana_cumple`, `ESTADOS_MODIFICABLES`) viven en
`core`.
"""
import json
import logging
from typing import Optional

from fastapi import BackgroundTasks, Request, HTTPException
from pydantic import BaseModel, Field, field_validator

from database import get_db, row_to_dict, to_datetime, now_ar
from auth.guards import require_admin
from routes.cliente_portal.core import (
    router,
    require_cliente,
    _modificacion_ventana_horas,
    _ventana_cumple,
    ESTADOS_MODIFICABLES,
)

logger = logging.getLogger(__name__)


# ── Solicitud de modificación ─────────────────────────────────────────────────

class ModificacionItemIn(BaseModel):
    from pydantic import field_validator as _fv
    equipo_id: int
    cantidad:  int

    @_fv("cantidad")
    @classmethod
    def _cantidad_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("cantidad debe ser mayor a 0")
        return v


class ModificacionIn(BaseModel):
    """Cambio que el cliente propone aplicar al pedido.

    Si el pedido está en `presupuesto`, los cambios se aplican directo.
    Si está en `confirmado`, se guarda como propuesta pendiente de aprobación.
    """
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       list[ModificacionItemIn] = Field(..., max_length=100)
    mensaje:     Optional[str] = Field(None, max_length=2000)

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        from routes.alquileres import _validar_fecha_iso
        return _validar_fecha_iso(v)


def _validar_fechas_propuestas(
    fecha_desde: Optional[str], fecha_hasta: Optional[str],
    fallback_desde: Optional[str], fallback_hasta: Optional[str],
) -> None:
    """Valida que las fechas propuestas sean coherentes: futuras y bien ordenadas.

    Usa los valores actuales del pedido como fallback si el cliente no las envía.
    """
    nueva_desde = fecha_desde if fecha_desde is not None else fallback_desde
    nueva_hasta = fecha_hasta if fecha_hasta is not None else fallback_hasta
    if not nueva_desde or not nueva_hasta:
        return  # Pedido sin fechas (caso raro de borrador) — no validamos
    try:
        d0 = to_datetime(nueva_desde)
        d1 = to_datetime(nueva_hasta)
    except ValueError:
        raise HTTPException(400, "Formato de fechas inválido")
    if d0 >= d1:
        raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
    hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)
    if d0 < hoy:
        raise HTTPException(400, "fecha_desde no puede ser en el pasado")


def _validar_modificacion_estado(estado: str) -> None:
    if estado not in ESTADOS_MODIFICABLES:
        raise HTTPException(
            400,
            f"Este pedido no se puede modificar en estado '{estado}'. "
            "Solo se pueden modificar pedidos en presupuesto o confirmado."
        )


def _validar_ventana_corte(
    conn,
    fecha_desde_actual: Optional[str],
    fecha_desde_propuesta: Optional[str] = None,
) -> int:
    """Valida la ventana de corte para cambios en el pedido.

    Pull-out (empujar `fecha_desde` hacia más adelante) está permitido aún
    dentro de la ventana: el cliente avisa que no necesita el equipo tan
    pronto, lo que descongestiona logística. Pull-in (acercar la fecha) sí
    se bloquea.

    Retorna las horas configuradas (útil para mensajes).
    """
    ventana = _modificacion_ventana_horas(conn)

    if fecha_desde_propuesta and fecha_desde_actual:
        try:
            d_prop = to_datetime(fecha_desde_propuesta)
            d_act = to_datetime(fecha_desde_actual)
            if d_prop >= d_act:
                return ventana  # pull-out: permitido sin chequeo
        except (ValueError, TypeError):
            pass

    if not _ventana_cumple(fecha_desde_actual, ventana):
        raise HTTPException(
            400,
            f"No se puede modificar a menos de {ventana} h del retiro. "
            "Contactanos directamente para coordinar."
        )
    return ventana


def _check_solicitud_pendiente(conn, pedido_id: int) -> None:
    pendiente = conn.execute(
        "SELECT id FROM solicitudes_modificacion WHERE pedido_id = %s AND estado = 'pendiente'",
        (pedido_id,)
    ).fetchone()
    if pendiente:
        raise HTTPException(409, "Ya hay una solicitud pendiente para este pedido")


def _check_stock_hipotetico(
    conn, pedido_id: int, fecha_desde: str, fecha_hasta: str,
    items: "list",
) -> list[str]:
    """Pre-chequeo en SECO (dry-run) de stock para un set HIPOTÉTICO de items +
    fechas (la propuesta del cliente que todavía no se guardó).

    Usado en el path `confirmado`/propose: el cliente envía una propuesta y
    queremos rechazarla si no hay stock, sin pasar antes por aplicar nada.

    Delega en el motor único `reservas.validar_stock_hipotetico` — la MISMA pieza
    que usa el gate AUTORITATIVO `validar_stock`, así el dry-run del portal y el
    gate real NO pueden divergir (MEMORIA 2026-05-30 / 2026-05-31). Antes esta
    función re-implementaba la expansión "en seco" importando internos del motor
    (`expandir_demanda`, `parientes_de`, `reservado_total`, ...) y se
    desincronizaba en silencio si el gate cambiaba.
    """
    from reservas import validar_stock_hipotetico
    return validar_stock_hipotetico(conn, pedido_id, fecha_desde, fecha_hasta, items)


def _cancelar_solicitudes_pendientes(
    conn, pedido_id: int, motivo: str, actor: str = "system",
) -> int:
    """Cancela todas las solicitudes pendientes de un pedido. Retorna
    cuántas se cancelaron. Usado cuando el pedido cambia a un estado no
    modificable o se cancela: las solicitudes pendientes quedan huérfanas
    y debemos limpiarlas para no confundir al cliente y al admin.
    """
    rows = conn.execute(
        """UPDATE solicitudes_modificacion
           SET estado = 'cancelada', respuesta = %s,
               resolved_at = CURRENT_TIMESTAMP, resolved_by = %s
           WHERE pedido_id = %s AND estado = 'pendiente'
           RETURNING id""",
        (motivo, actor, pedido_id)
    ).fetchall()
    return len(rows)


def _items_payload_to_pedido_items(items: list[ModificacionItemIn], precios: dict[int, int]) -> list:
    """Convierte items del cliente a `PedidoItem` (rellenando precio_jornada
    desde el pedido actual / equipo: el cliente nunca decide el precio)."""
    from routes.alquileres import PedidoItem
    return [
        PedidoItem(
            equipo_id=it.equipo_id,
            cantidad=it.cantidad,
            precio_jornada=precios.get(it.equipo_id, 0),
        )
        for it in items
    ]


def _lineas_libres_actuales(conn, pedido_id: int) -> list:
    """Líneas personalizadas (#805, equipo_id NULL) ya guardadas en el pedido,
    como `PedidoItem`. El portal del cliente NO las maneja (solo ítems de
    catálogo) → hay que preservarlas al reaplicar los ítems. Sin esto, el
    DELETE+reinsert de `_apply_pedido_items` las borraría en silencio cuando el
    cliente edita su pedido: un flete/servicio que agregó el admin desaparecería
    y cambiaría el total cobrado (pérdida de plata)."""
    from routes.alquileres import PedidoItem
    rows = conn.execute(
        "SELECT cantidad, precio_jornada, nombre_libre, cobro_modo "
        "FROM alquiler_items WHERE pedido_id=%s AND equipo_id IS NULL "
        "ORDER BY orden, id",
        (pedido_id,),
    ).fetchall()
    return [
        PedidoItem(
            equipo_id=None,
            cantidad=r["cantidad"],
            precio_jornada=r["precio_jornada"],
            nombre_libre=r["nombre_libre"],
            cobro_modo=r["cobro_modo"],
        )
        for r in rows
    ]


def _precios_actuales(conn, pedido_id: int) -> dict[int, int]:
    """Mapa equipo_id → precio_jornada usado actualmente en el pedido.

    Para equipos nuevos que no estaban en el pedido, devuelve el `precio_jornada`
    del catálogo (`equipos.precio_jornada`) como fallback.
    """
    rows = conn.execute(
        "SELECT equipo_id, precio_jornada FROM alquiler_items WHERE pedido_id=%s",
        (pedido_id,)
    ).fetchall()
    return {r["equipo_id"]: r["precio_jornada"] for r in rows}


def _equipo_precio_catalogo(conn, equipo_id: int) -> int:
    row = conn.execute(
        "SELECT precio_jornada FROM equipos WHERE id=%s", (equipo_id,)
    ).fetchone()
    return int(row["precio_jornada"] or 0) if row else 0


@router.post("/api/cliente/pedidos/{id}/modificacion")
def cliente_modificar_pedido(
    id: int, data: ModificacionIn, request: Request, background: BackgroundTasks,
):
    """Aplica una modificación (directo o como propuesta de aprobación).

    - En `presupuesto`: aplica al pedido (valida stock, fechas, ventana).
    - En `confirmado`: guarda `solicitudes_modificacion` con `cambios_json`
      y dispara email al admin. El pedido no se toca.
    """
    from reservas import validar_stock as _check_stock
    from routes.alquileres import (
        PedidoDatos, _apply_pedido_datos, _apply_pedido_items,
        _get_alquiler_detail,
    )

    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un ítem")

    with get_db() as conn:
        try:
            pedido = conn.execute(
                "SELECT * FROM alquileres WHERE id = %s AND cliente_id = %s",
                (id, cliente_id)
            ).fetchone()
            if not pedido:
                raise HTTPException(404, "Pedido no encontrado")

            _validar_modificacion_estado(pedido["estado"])
            _validar_ventana_corte(conn, pedido["fecha_desde"], data.fecha_desde)
            _check_solicitud_pendiente(conn, id)
            _validar_fechas_propuestas(
                data.fecha_desde, data.fecha_hasta,
                pedido["fecha_desde"], pedido["fecha_hasta"],
            )
            # Horarios habilitados: solo si el cliente propone fechas nuevas (no
            # bloqueamos ediciones de solo-items aunque el admin haya cambiado los
            # horarios después de creado el pedido).
            if data.fecha_desde is not None or data.fecha_hasta is not None:
                from routes.alquileres import _validar_horarios_habilitados
                _validar_horarios_habilitados(
                    conn,
                    data.fecha_desde if data.fecha_desde is not None else pedido["fecha_desde"],
                    data.fecha_hasta if data.fecha_hasta is not None else pedido["fecha_hasta"],
                )

            # Rellenar precios desde el pedido actual o catálogo (el cliente no
            # puede definir precios).
            precios = _precios_actuales(conn, id)
            for it in data.items:
                if it.equipo_id not in precios:
                    precios[it.equipo_id] = _equipo_precio_catalogo(conn, it.equipo_id)

            # ── Caso `presupuesto`: aplicar directo ──────────────────────────
            if pedido["estado"] == "presupuesto":
                # Sólo enviamos fechas si vinieron en el payload (evita pisar a null).
                datos_kwargs = {}
                if data.fecha_desde is not None:
                    datos_kwargs["fecha_desde"] = data.fecha_desde
                if data.fecha_hasta is not None:
                    datos_kwargs["fecha_hasta"] = data.fecha_hasta
                if datos_kwargs:
                    _apply_pedido_datos(conn, id, PedidoDatos(**datos_kwargs))

                # Preservar las líneas personalizadas (#805): el portal solo manda
                # ítems de catálogo; sin esto el reinsert las borraría.
                pedido_items = _items_payload_to_pedido_items(data.items, precios)
                pedido_items += _lineas_libres_actuales(conn, id)
                _apply_pedido_items(conn, id, pedido_items)

                # Re-validar stock con el rango nuevo
                p2 = conn.execute("SELECT fecha_desde, fecha_hasta FROM alquileres WHERE id=%s", (id,)).fetchone()
                if p2["fecha_desde"] and p2["fecha_hasta"]:
                    problemas = _check_stock(conn, id, p2["fecha_desde"], p2["fecha_hasta"])
                    if problemas:
                        raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

                # Auditoría: dedup. Si hay un row `directo` reciente para este
                # pedido (≤ 5 min), lo actualizamos en lugar de insertar uno
                # nuevo — sino el autosave llena la tabla con N rows por sesión.
                actor = session.get("email") or "cliente"
                reciente = conn.execute(
                    """SELECT id FROM solicitudes_modificacion
                       WHERE pedido_id = %s AND cliente_id = %s AND tipo = 'directo'
                         AND resolved_at >= CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                       ORDER BY resolved_at DESC LIMIT 1""",
                    (id, cliente_id)
                ).fetchone()
                cambios_str = json.dumps(data.model_dump())
                if reciente:
                    conn.execute(
                        """UPDATE solicitudes_modificacion
                           SET mensaje = %s, cambios_json = %s,
                               resolved_at = CURRENT_TIMESTAMP, resolved_by = %s
                           WHERE id = %s""",
                        (data.mensaje, cambios_str, actor, reciente["id"])
                    )
                else:
                    conn.execute(
                        """INSERT INTO solicitudes_modificacion
                           (pedido_id, cliente_id, mensaje, cambios_json, tipo, estado, resolved_at, resolved_by)
                           VALUES (%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,%s)""",
                        (id, cliente_id, data.mensaje, cambios_str,
                         "directo", "aprobada", actor)
                    )
                conn.commit()

                pedido_actualizado = _get_alquiler_detail(conn, id)
                return {"ok": True, "tipo": "directo", "pedido": pedido_actualizado}

            # ── Caso `confirmado`: guardar propuesta ─────────────────────────
            # Validar stock hipotéticamente: rechazar antes de que el admin la vea
            # si la propuesta es imposible. Las fechas a chequear son las que el
            # cliente propone, con fallback a las actuales del pedido.
            fd = data.fecha_desde or pedido["fecha_desde"]
            fh = data.fecha_hasta or pedido["fecha_hasta"]
            problemas = _check_stock_hipotetico(conn, id, fd, fh, data.items)
            if problemas:
                raise HTTPException(409, "Sin stock para tu propuesta: " + "; ".join(problemas))

            try:
                conn.execute(
                    """INSERT INTO solicitudes_modificacion
                       (pedido_id, cliente_id, mensaje, cambios_json, tipo, estado)
                       VALUES (%s,%s,%s,%s,%s,'pendiente')""",
                    (id, cliente_id, data.mensaje, json.dumps(data.model_dump()),
                     "aprobacion")
                )
                conn.commit()
            except Exception as e:
                # Si el partial unique index agarra una race con otra pestaña del
                # mismo cliente, devolvemos 409 igual que el pre-check optimista.
                # Re-mapeamos para que la respuesta sea consistente.
                msg = str(e).lower()
                if "uniq_solicitud_pendiente_por_pedido" in msg or "unique" in msg:
                    raise HTTPException(409, "Ya hay una solicitud pendiente para este pedido")
                raise

            background.add_task(_enviar_email_solicitud_admin, id, data.model_dump())

            return {"ok": True, "tipo": "aprobacion"}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            logger.error("Error en modificación cliente pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.delete("/api/cliente/pedidos/{id}/modificacion/{sm_id}")
def cliente_cancelar_solicitud(
    id: int, sm_id: int, request: Request, background: BackgroundTasks,
):
    """El cliente cancela su propia solicitud pendiente."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        # Lock + filtro atómico: si dos pestañas cancelan a la vez, sólo
        # una ve `estado='pendiente'`.
        sm = conn.execute(
            """SELECT sm.id, sm.estado, sm.pedido_id,
                      a.numero_pedido, c.nombre AS cliente_nombre,
                      c.email AS cliente_email
               FROM solicitudes_modificacion sm
               JOIN alquileres a ON a.id = sm.pedido_id
               JOIN clientes c ON c.id = sm.cliente_id
               WHERE sm.id = %s AND sm.pedido_id = %s AND sm.cliente_id = %s
               FOR UPDATE OF sm""",
            (sm_id, id, cliente_id)
        ).fetchone()
        if not sm:
            raise HTTPException(404, "Solicitud no encontrada")
        if sm["estado"] != "pendiente":
            raise HTTPException(400, "Esta solicitud ya fue resuelta")
        conn.execute(
            """UPDATE solicitudes_modificacion
               SET estado = 'cancelada', resolved_at = CURRENT_TIMESTAMP, resolved_by = %s
               WHERE id = %s""",
            (session.get("email") or "cliente", sm_id)
        )
        conn.commit()

        # Notificar al admin para cerrar el loop (no propaga si falla).
        background.add_task(
            _enviar_email_cancelacion_admin,
            sm["pedido_id"], sm["numero_pedido"],
            sm["cliente_nombre"], sm["cliente_email"],
        )
        return {"ok": True}


def _enviar_email_cancelacion_admin(
    pedido_id: int, numero_pedido, cliente_nombre: str, cliente_email: str,
) -> None:
    """Background task: notifica al admin que el cliente canceló su solicitud."""
    from config import SITE_URL
    from services.email import send_email
    from services.email.service import get_admin_to
    admin_to = get_admin_to()
    if not admin_to:
        return
    ctx = {
        "cliente_nombre": cliente_nombre or "",
        "cliente_email":  cliente_email or "",
        "numero_pedido":  numero_pedido or pedido_id,
        "admin_url":      f"{SITE_URL}/admin/pedidos/{pedido_id}",
    }
    send_email("modificacion_cancelada_admin", admin_to, ctx, pedido_id)


@router.get("/api/cliente/pedidos/{id}/disponibilidad")
def cliente_disponibilidad(
    id: int, request: Request, fecha_desde: str, fecha_hasta: str,
):
    """Wrapper de /api/disponibilidad con validación de ownership y
    `exclude_pedido_id` automático."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        owned = conn.execute(
            "SELECT id FROM alquileres WHERE id = %s AND cliente_id = %s",
            (id, cliente_id)
        ).fetchone()
        if not owned:
            raise HTTPException(404, "Pedido no encontrado")
    from routes.alquileres import get_disponibilidad
    return get_disponibilidad(
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, exclude_pedido_id=id,
    )


@router.get("/api/cliente/modificacion-config")
def cliente_modificacion_config(request: Request):
    """Devuelve la ventana de corte para que el frontend pueda mostrar/ocultar
    el botón de modificar sin tener que tocar settings."""
    require_cliente(request)
    with get_db() as conn:
        return {"ventana_horas": _modificacion_ventana_horas(conn)}


# ── Emails de solicitud/resolución ────────────────────────────────────────────

def _build_diff_payload(pedido_actual: dict, cambios: dict) -> dict:
    """Arma un dict con 'antes vs después' para los templates de email."""
    items_actuales = pedido_actual.get("items") or []
    nombres = {it["equipo_id"]: it.get("nombre") or "—" for it in items_actuales}
    actual_qty = {it["equipo_id"]: it.get("cantidad", 0) for it in items_actuales}
    propuesta_qty = {it["equipo_id"]: it["cantidad"] for it in cambios.get("items") or []}

    todos = set(actual_qty.keys()) | set(propuesta_qty.keys())
    lineas_html, lineas_text = [], []
    for eq_id in todos:
        a = actual_qty.get(eq_id, 0)
        b = propuesta_qty.get(eq_id, 0)
        if a == b:
            continue
        nombre = nombres.get(eq_id, f"equipo #{eq_id}")
        flecha = f"{a} → {b}"
        lineas_html.append(f"<li>{nombre}: {flecha}</li>")
        lineas_text.append(f"  - {nombre}: {flecha}")

    return {
        "fecha_desde_actual":   pedido_actual.get("fecha_desde") or "—",
        "fecha_hasta_actual":   pedido_actual.get("fecha_hasta") or "—",
        "fecha_desde_propuesta": cambios.get("fecha_desde") or "—",
        "fecha_hasta_propuesta": cambios.get("fecha_hasta") or "—",
        "total_actual": pedido_actual.get("monto_total") or 0,
        "diff_html": "<ul>" + "".join(lineas_html) + "</ul>" if lineas_html else "<p>Sin cambios de equipos.</p>",
        "diff_text": "\n".join(lineas_text) if lineas_text else "  (sin cambios de equipos)",
        "mensaje": cambios.get("mensaje") or "",
    }


def _enviar_email_solicitud_admin(pedido_id: int, cambios: dict) -> None:
    """Background task: notifica al admin de una nueva solicitud."""
    from config import SITE_URL
    from services.email import send_email
    from services.email.service import get_admin_to
    from routes.alquileres import _get_alquiler_detail

    admin_to = get_admin_to()
    if not admin_to:
        return

    with get_db() as conn:
        try:
            pedido = _get_alquiler_detail(conn, pedido_id)
        except Exception:
            return

    ctx = {
        "cliente_nombre":  pedido.get("cliente_nombre") or "",
        "cliente_email":   pedido.get("cliente_email") or "",
        "numero_pedido":   pedido.get("numero_pedido") or pedido_id,
        "admin_url":       f"{SITE_URL}/admin/pedidos/{pedido_id}",
        **_build_diff_payload(pedido, cambios),
    }
    send_email("modificacion_solicitada_admin", admin_to, ctx, pedido_id)


def _enviar_email_resolucion_cliente(
    pedido_id: int, cliente_email: str, cliente_nombre: str,
    numero_pedido, estado: str, respuesta: str,
) -> None:
    """Background task: notifica al cliente cuando se resuelve su solicitud."""
    from config import SITE_URL
    from services.email import send_email
    estado_label = "aprobada" if estado == "aprobada" else "rechazada"
    ctx = {
        "cliente_nombre": cliente_nombre or "",
        "numero_pedido":  numero_pedido or pedido_id,
        "estado":         estado,
        "estado_label":   estado_label,
        "respuesta":      respuesta or "",
        "portal_url":     f"{SITE_URL}/cliente/portal",
    }
    send_email("modificacion_resuelta_cliente", cliente_email, ctx, pedido_id)


# ── Admin: ver solicitudes y resolverlas ─────────────────────────────────────

@router.get("/api/admin/solicitudes")
def admin_solicitudes(request: Request):
    """Lista de solicitudes de modificación (solo admins)."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sm.id, sm.pedido_id, sm.mensaje, sm.estado, sm.respuesta,
                   sm.cambios_json, sm.cambios_aplicados, sm.tipo,
                   sm.resolved_at, sm.resolved_by, sm.created_at,
                   c.nombre AS cliente_nombre, c.apellido AS cliente_apellido,
                   c.email AS cliente_email,
                   a.numero_pedido, a.fecha_desde AS pedido_fecha_desde,
                   a.fecha_hasta AS pedido_fecha_hasta, a.monto_total
            FROM solicitudes_modificacion sm
            JOIN clientes c ON c.id = sm.cliente_id
            JOIN alquileres a ON a.id = sm.pedido_id
            ORDER BY
              CASE WHEN sm.estado = 'pendiente' THEN 0 ELSE 1 END,
              sm.created_at DESC
        """).fetchall()
        return [row_to_dict(r) for r in rows]


class SolicitudOverrideItem(BaseModel):
    from pydantic import field_validator as _fv
    equipo_id: int
    cantidad:  int

    @_fv("cantidad")
    @classmethod
    def _cantidad_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("cantidad debe ser mayor a 0 (para quitar un equipo, omitilo del array)")
        return v


class SolicitudOverride(BaseModel):
    """Contrapropuesta del admin. Si se envía al aprobar, se aplica en lugar
    de la propuesta original del cliente."""
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       list[SolicitudOverrideItem] = Field(..., max_length=100)


class SolicitudRespuesta(BaseModel):
    estado: str     # aprobada / rechazada
    respuesta: str = Field("", max_length=2000)
    cambios_override: Optional[SolicitudOverride] = None


@router.patch("/api/admin/solicitudes/{id}")
def admin_responder_solicitud(
    id: int, data: SolicitudRespuesta, request: Request, background: BackgroundTasks,
):
    """Resuelve una solicitud de modificación.

    - Si `estado='aprobada'` y la solicitud tiene `cambios_json` (`tipo='aprobacion'`),
      aplica los cambios al pedido reusando los helpers de `routes/alquileres`.
    - Si `estado='rechazada'`, sólo marca y notifica.
    """
    from reservas import validar_stock as _check_stock
    from routes.alquileres import (
        PedidoDatos, _apply_pedido_datos, _apply_pedido_items,
    )

    admin = require_admin(request)
    admin_email = admin.get("email") or "admin"
    if data.estado not in ("aprobada", "rechazada"):
        raise HTTPException(400, "Estado debe ser 'aprobada' o 'rechazada'")

    with get_db() as conn:
        try:
            # Lock pesimista de la fila para evitar que dos admins (o admin +
            # cancelación del cliente) corran en paralelo sobre la misma
            # solicitud y ambos pasen el check de "pendiente".
            sm = conn.execute(
                """SELECT sm.*, a.cliente_id, a.fecha_desde, a.fecha_hasta,
                          a.estado AS pedido_estado, a.numero_pedido,
                          c.email AS cliente_email, c.nombre AS cliente_nombre
                   FROM solicitudes_modificacion sm
                   JOIN alquileres a ON a.id = sm.pedido_id
                   JOIN clientes c ON c.id = sm.cliente_id
                   WHERE sm.id = %s
                   FOR UPDATE OF sm""",
                (id,)
            ).fetchone()
            if not sm:
                raise HTTPException(404, "Solicitud no encontrada")
            if sm["estado"] != "pendiente":
                raise HTTPException(400, "Esta solicitud ya fue resuelta")

            cambios_aplicados_str: Optional[str] = None

            if data.estado == "aprobada" and sm["tipo"] == "aprobacion":
                if sm["pedido_estado"] not in ESTADOS_MODIFICABLES:
                    raise HTTPException(
                        400, f"El pedido está en estado '{sm['pedido_estado']}' y ya no admite cambios"
                    )

                cambios_pre = sm["cambios_json"] or {}
                if isinstance(cambios_pre, str):
                    cambios_pre = json.loads(cambios_pre)

                # Contrapropuesta del admin: si se envió, sobreescribe la del cliente.
                if data.cambios_override is not None:
                    cambios = data.cambios_override.model_dump()
                    if not cambios.get("items"):
                        raise HTTPException(400, "La contrapropuesta debe incluir items")
                    _validar_fechas_propuestas(
                        cambios.get("fecha_desde"), cambios.get("fecha_hasta"),
                        sm["fecha_desde"], sm["fecha_hasta"],
                    )
                else:
                    cambios = cambios_pre

                _validar_ventana_corte(
                    conn, sm["fecha_desde"], cambios.get("fecha_desde"),
                )

                precios = _precios_actuales(conn, sm["pedido_id"])
                for it in cambios.get("items") or []:
                    eq_id = it["equipo_id"]
                    if eq_id not in precios:
                        precios[eq_id] = _equipo_precio_catalogo(conn, eq_id)

                datos_kwargs = {}
                if cambios.get("fecha_desde") is not None:
                    datos_kwargs["fecha_desde"] = cambios["fecha_desde"]
                if cambios.get("fecha_hasta") is not None:
                    datos_kwargs["fecha_hasta"] = cambios["fecha_hasta"]
                if datos_kwargs:
                    _apply_pedido_datos(conn, sm["pedido_id"], PedidoDatos(**datos_kwargs))

                # Preservar las líneas personalizadas (#805) — ver nota en el caso directo.
                pedido_items = _items_payload_to_pedido_items(
                    [ModificacionItemIn(**it) for it in cambios.get("items") or []],
                    precios,
                )
                pedido_items += _lineas_libres_actuales(conn, sm["pedido_id"])
                _apply_pedido_items(conn, sm["pedido_id"], pedido_items)

                # Re-validar stock con el rango nuevo
                p2 = conn.execute(
                    "SELECT fecha_desde, fecha_hasta FROM alquileres WHERE id=%s",
                    (sm["pedido_id"],)
                ).fetchone()
                if p2["fecha_desde"] and p2["fecha_hasta"]:
                    problemas = _check_stock(conn, sm["pedido_id"], p2["fecha_desde"], p2["fecha_hasta"])
                    if problemas:
                        raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

                # Snapshot de lo que efectivamente se aplicó (≠ a la propuesta del
                # cliente si admin usó override). Para auditoría.
                cambios_aplicados_str = json.dumps(cambios)

            conn.execute(
                """UPDATE solicitudes_modificacion
                   SET estado = %s, respuesta = %s, cambios_aplicados = %s,
                       resolved_at = CURRENT_TIMESTAMP, resolved_by = %s
                   WHERE id = %s""",
                (data.estado, data.respuesta, cambios_aplicados_str, admin_email, id)
            )
            conn.commit()

            if sm["cliente_email"]:
                background.add_task(
                    _enviar_email_resolucion_cliente,
                    sm["pedido_id"], sm["cliente_email"], sm["cliente_nombre"],
                    sm["numero_pedido"], data.estado, data.respuesta or "",
                )
            return {"ok": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            logger.error("Error resolviendo solicitud %s", id, exc_info=True)
            conn.rollback()
            raise
