"""
routes/pedidos.py — CRUD de pedidos, disponibilidad y generación de PDFs.
"""

import datetime
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from database import get_db, row_to_dict, to_datetime, to_iso, now_ar
from rate_limit import limiter
from pdf import _pedido_html, _albaran_html, _contrato_html, _packing_list_html, _render_pdf, _pedido_filename
from admin_guard import require_admin, is_admin_email
from routes.auth import get_session
from services.email import send_email, send_raw_email, Attachment
from services.email.service import get_admin_to
from services.ical import build_vcalendar, google_calendar_url, reserva_to_vevent
from services.precios import calcular_total, jornadas_periodo, precio_combo
from config import SITE_URL

# Motor de reservas: la fuente única vive en el paquete `reservas`. Acá se
# importan solo los nombres que este módulo usa internamente (el endpoint
# /disponibilidad delega en `calcular_disponibilidad`; las transiciones de
# estado validan con `validar_stock`). `ESTADOS_RESERVADO` se re-exporta porque
# es la constante canónica del dominio. El resto de las primitivas se importan
# directo de `reservas` donde se usan (routes.estudio, routes.cliente_portal).
# Ver issue #501, Fase 1.
from reservas import ESTADOS_RESERVADO
from reservas import (
    calcular_disponibilidad as _calcular_disponibilidad,
    dias_no_disponibles as _dias_no_disponibles,
    validar_stock as _check_stock,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ESTADOS_VALIDOS    = {"borrador", "presupuesto", "confirmado", "retirado", "devuelto", "finalizado", "cancelado"}


def _es_historico(fuente: str | None) -> bool:
    """Pedidos historicos (importados) no validan fechas ni stock.

    Soporta `historico` y prefijos tipo `<sistema>-historico` (ej.
    `booqable-historico` que generan los converters de migracion). Asi un
    converter futuro puede usar su propio prefijo sin tocar el backend.
    """
    return bool(fuente) and fuente.endswith("historico")


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
        SELECT pi.*, e.nombre,
               (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca,
               e.foto_url, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo,
               ef.contenido_incluido_json
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        LEFT JOIN equipo_fichas ef ON ef.equipo_id = e.id
        WHERE pi.pedido_id = ?
    """, (pedido_id,)).fetchall()
    items = [row_to_dict(r) for r in rows]
    if not items:
        return items

    # Batch fetch de componentes de kits: 1 query agregada en lugar de N+1
    # (antes hacía 1 query por cada item del pedido). Para pedidos con 10
    # items con kits, baja de 11 queries a 2.
    equipo_ids = list({item["equipo_id"] for item in items})
    placeholders = ",".join("?" for _ in equipo_ids)
    comp_rows = conn.execute(f"""
        SELECT kc.*, ec.nombre, (SELECT nombre FROM marcas WHERE id = ec.brand_id) AS marca, ec.foto_url, ec.cantidad AS stock_total,
               ec.nombre_publico, ec.nombre_publico_largo
        FROM kit_componentes kc
        JOIN equipos ec ON ec.id = kc.componente_id
        WHERE kc.equipo_id IN ({placeholders})
    """, equipo_ids).fetchall()
    # Group by equipo_id
    componentes_por_equipo: dict[int, list[dict]] = {}
    for c in comp_rows:
        d = row_to_dict(c)
        componentes_por_equipo.setdefault(d["equipo_id"], []).append(d)
    for item in items:
        item["componentes"] = componentes_por_equipo.get(item["equipo_id"], [])

    return items


def _next_numero_pedido(conn) -> int:
    """Devuelve el próximo número de pedido usando una SEQUENCE de PostgreSQL (race-free)."""
    return conn.execute("SELECT nextval('numero_pedido_seq')").fetchone()[0]


def _get_descuento_jornadas(conn, jornadas: int) -> float:
    """Interpolación lineal entre los puntos ancla de descuentos_jornada.

    Con puntos (1, 0%), (2, 3%), (7, 10%):
      - 4 jornadas → interpola entre (2,3%) y (7,10%) → 5.8%
      - 7+ jornadas → 10% (se queda en el último punto)
    """
    rows = conn.execute(
        "SELECT jornadas, pct FROM descuentos_jornada ORDER BY jornadas ASC"
    ).fetchall()
    if not rows:
        return 0.0
    # `pct` es NUMERIC en la DB (migración g1a2b3c4d5e6) → psycopg lo devuelve
    # como Decimal. Se coerce a float acá para que la interpolación
    # (`t * (p1 - p0)` con t float) no rompa con `float * Decimal` → TypeError
    # → cotizar 500 → totales en $0. Pasaba en alquileres de jornadas
    # intermedias (las que interpolan entre puntos ancla).
    puntos = [(int(r["jornadas"]), float(r["pct"])) for r in rows]
    if jornadas <= puntos[0][0]:
        return float(puntos[0][1])
    if jornadas >= puntos[-1][0]:
        return float(puntos[-1][1])
    for i in range(len(puntos) - 1):
        j0, p0 = puntos[i]
        j1, p1 = puntos[i + 1]
        if j0 <= jornadas <= j1:
            t = (jornadas - j0) / (j1 - j0)
            return round(p0 + t * (p1 - p0), 2)
    return 0.0


def _batch_get_alquiler_items(conn, pedido_ids: list[int]) -> dict[int, list[dict]]:
    """Trae items de múltiples pedidos en 2 queries en lugar de N+1.

    Retorna {pedido_id: [items...]} donde cada item ya tiene su lista 'componentes'.
    """
    if not pedido_ids:
        return {}

    ph = ",".join(["?"] * len(pedido_ids))
    rows = conn.execute(f"""
        SELECT pi.*, e.nombre,
               (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca,
               e.foto_url, e.cantidad AS stock_total,
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
            SELECT kc.*, ec.nombre, (SELECT nombre FROM marcas WHERE id = ec.brand_id) AS marca, ec.foto_url, ec.cantidad AS stock_total,
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
    """Recalcula monto_pagado atómicamente desde alquiler_pagos.

    Usa UPDATE con subquery (en lugar de SELECT-luego-UPDATE) para evitar
    race conditions cuando dos pagos llegan en paralelo.

    No hace commit — el caller debe commitear inmediatamente después para que
    el UPDATE no quede huérfano si falla algo posterior en la misma transacción.
    """
    conn.execute(
        """
        UPDATE alquileres
           SET monto_pagado = (
               SELECT COALESCE(SUM(monto), 0)
                 FROM alquiler_pagos
                WHERE pedido_id = ?
           )
         WHERE id = ?
        """,
        (pedido_id, pedido_id),
    )


def _get_alquiler_detail(conn, id: int) -> dict:
    row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Pedido no encontrado")
    pedido = row_to_dict(row)
    pedido["items"] = _get_alquiler_items(conn, id)
    pedido["pagos"] = _get_alquiler_pagos(conn, id)
    pedido["historial_modificaciones"] = _get_historial_modificaciones(conn, id)
    _enriquecer_pedido_con_total(conn, pedido)
    return pedido


def _enriquecer_pedido_con_total(conn, pedido: dict) -> dict:
    """Agrega al pedido el desglose canónico del total + IVA derivado.

    Fuente de verdad: `services/precios.calcular_total`. `monto_total`
    persistido sigue siendo NETO (con descuento, sin IVA). Acá se computa
    el desglose para que admin/portal/listados muestren EXACTAMENTE lo
    mismo, sin reimplementar la fórmula en el frontend.

    Cierra #496. Si el cliente del pedido es Responsable Inscripto, se
    discrimina IVA 21%; el resto ve total = neto.
    """
    # Perfil tributario del cliente (lo usa calcular_total para decidir IVA).
    perfil = pedido.get("cliente_perfil_impuestos")
    if perfil is None and pedido.get("cliente_id"):
        row = conn.execute(
            "SELECT perfil_impuestos FROM clientes WHERE id = ?",
            (pedido["cliente_id"],),
        ).fetchone()
        if row:
            perfil = row_to_dict(row).get("perfil_impuestos")
            pedido["cliente_perfil_impuestos"] = perfil

    # Jornadas vía fórmula única (ceil/24h). Si falta alguna fecha → 1.
    d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
    d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
    jornadas = jornadas_periodo(d0, d1)

    # Items con la forma que espera el helper (precios netos).
    items_para_total = [
        {
            "equipo_id": it["equipo_id"],
            "cantidad": it["cantidad"],
            "precio_jornada": it["precio_jornada"],
        }
        for it in pedido.get("items", [])
    ]

    desglose = calcular_total(
        items=items_para_total,
        jornadas=jornadas,
        descuento_cliente_pct=pedido.get("descuento_pct") or 0,
        descuento_jornadas_pct=pedido.get("descuento_jornadas_pct") or 0,
        perfil_impuestos=perfil,
    )

    # Agregamos el desglose al pedido. El frontend lo lee directo, sin
    # reimplementar la fórmula. NO sobreescribimos `monto_total` (que
    # sigue siendo el neto persistido y la fuente de verdad de la BD).
    pedido["bruto"] = desglose["bruto"]
    pedido["descuento_monto"] = desglose["descuento_monto"]
    pedido["monto_neto"] = desglose["neto"]
    pedido["iva_pct"] = desglose["iva_pct"]
    pedido["iva_monto"] = desglose["iva_monto"]
    pedido["total_con_iva"] = desglose["total_final"]
    pedido["con_iva"] = desglose["con_iva"]
    pedido["cantidad_jornadas"] = jornadas
    return pedido


def _enriquecer_pedido_con_cliente_fiscal(conn, pedido: dict) -> dict:
    """Mergea perfil_impuestos + datos de Factura A del cliente en el pedido.

    Usado por los endpoints de PDF para que `_pedido_html` pueda decidir si
    discriminar IVA (Factura A para Responsable Inscripto).
    """
    cid = pedido.get("cliente_id")
    if not cid:
        return pedido
    row = conn.execute(
        """SELECT perfil_impuestos, razon_social, domicilio_fiscal,
                  email_facturacion
           FROM clientes WHERE id = ?""",
        (cid,),
    ).fetchone()
    if not row:
        return pedido
    c = row_to_dict(row)
    pedido["cliente_perfil_impuestos"] = c.get("perfil_impuestos")
    pedido["cliente_razon_social"] = c.get("razon_social")
    pedido["cliente_domicilio_fiscal"] = c.get("domicilio_fiscal")
    pedido["cliente_email_facturacion"] = c.get("email_facturacion")
    return pedido



def _get_historial_modificaciones(conn, pedido_id: int) -> list[dict]:
    """Timeline de cambios solicitados por el cliente sobre el pedido.

    Incluye tanto solicitudes de aprobación como cambios directos
    (autosave en `presupuesto`) — el admin se beneficia de ver todo.
    `cambios_aplicados` puede diferir de `cambios_json` cuando el admin
    aprobó con contrapropuesta.
    """
    rows = conn.execute("""
        SELECT id, mensaje, estado, respuesta, cambios_json, cambios_aplicados,
               tipo, resolved_at, resolved_by, created_at
        FROM solicitudes_modificacion
        WHERE pedido_id = ?
        ORDER BY created_at DESC
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


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


def _validar_fecha_iso(v):
    """Valida que una fecha sea ISO parseable (o None/''). Se usa como
    field_validator en los modelos de pedido para rechazar fechas malformadas
    en el borde (422) en vez de explotar como 500 más adentro al castear."""
    if v is None or v == "":
        return None
    try:
        datetime.datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        raise ValueError(
            f"fecha inválida: '{v}'. Formato esperado ISO (yyyy-mm-dd o yyyy-mm-ddThh:mm)"
        )
    return str(v)


class PedidoItem(BaseModel):
    equipo_id:      int
    cantidad:       int
    precio_jornada: int = 0

    @field_validator("precio_jornada", mode="before")
    @classmethod
    def coerce_precio(cls, v):
        return _parse_precio(v)

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v is None or v < 1:
            raise ValueError("cantidad debe ser >= 1")
        if v > 999:
            raise ValueError("cantidad demasiado alta (máx 999)")
        return v

    @field_validator("precio_jornada")
    @classmethod
    def validate_precio(cls, v):
        if v is not None and v < 0:
            raise ValueError("precio_jornada no puede ser negativo")
        return v


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

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        return _validar_fecha_iso(v)


class PedidoEstado(BaseModel):
    estado: str


class PagoParcial(BaseModel):
    monto_pagado: int


class PagoCreate(BaseModel):
    monto:    int
    concepto: Optional[str] = None
    fecha:    Optional[str] = None   # YYYY-MM-DD; si no viene usa hoy


class PedidoDatos(BaseModel):
    from pydantic import field_validator
    cliente_id:       Optional[int]   = None
    cliente_nombre:   Optional[str]   = None
    cliente_email:    Optional[str]   = None
    cliente_telefono: Optional[str]   = None
    fecha_desde:      Optional[str]   = None
    fecha_hasta:      Optional[str]   = None
    notas:            Optional[str]   = None
    descuento_pct:    Optional[float] = None

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        return _validar_fecha_iso(v)

    @field_validator("descuento_pct")
    @classmethod
    def validate_descuento(cls, v):
        if v is None:
            return v
        if v < 0 or v > 100:
            raise ValueError("descuento_pct debe estar entre 0 y 100")
        return v


class PedidoItemUpdate(BaseModel):
    items: list[PedidoItem]


# ── Disponibilidad ───────────────────────────────────────────────────────────

_DIAS_HORARIO = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]


def _validar_horarios_habilitados(conn, fecha_desde, fecha_hasta) -> None:
    """Valida que retiro/devolución caigan en días/horas habilitados (setting
    `horarios_retiro`). Sin config → no restringe. Pensado para el flujo del
    cliente, que manda hora real (el admin carga date-only y no se restringe).
    Lanza HTTPException 400 si algo cae fuera."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("horarios_retiro",)
    ).fetchone()
    if not row or not row["value"]:
        return
    try:
        horarios = json.loads(row["value"])
    except (ValueError, TypeError):
        return
    if not isinstance(horarios, dict) or not horarios:
        return

    def _check(dt_raw, etiqueta: str):
        if not dt_raw:
            return
        dt = to_datetime(dt_raw)
        franja = horarios.get(_DIAS_HORARIO[dt.weekday()])
        if not franja:
            raise HTTPException(400, f"El {etiqueta} cae en un día no habilitado")
        hhmm = dt.strftime("%H:%M")
        if hhmm < franja["desde"] or hhmm > franja["hasta"]:
            raise HTTPException(
                400,
                f"El horario de {etiqueta} ({hhmm}) está fuera del rango "
                f"habilitado ({franja['desde']}–{franja['hasta']})",
            )

    _check(fecha_desde, "retiro")
    _check(fecha_hasta, "devolución")


@router.get("/disponibilidad-dias")
def get_disponibilidad_dias(
    items: str = Query(..., description="Lista 'equipo_id:cantidad' separada por coma"),
    desde: str = Query(...),
    hasta: str = Query(...),
):
    """Días sin disponibilidad para los equipos pedidos, en [desde, hasta].
    Lo usa el calendario del cliente para bloquear días según las reservas
    reales de los equipos que tiene en el carrito."""
    parsed: dict[int, int] = {}
    for tok in (items or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        eid_str, _, qty_str = tok.partition(":")
        try:
            eid = int(eid_str)
            qty = int(qty_str) if qty_str else 1
        except ValueError:
            raise HTTPException(400, f"Item inválido: '{tok}' (se espera 'id' o 'id:cantidad')")
        parsed[eid] = max(parsed.get(eid, 0), max(1, qty))
    if not parsed:
        return {"dias_bloqueados": []}
    conn = get_db()
    try:
        return {"dias_bloqueados": _dias_no_disponibles(conn, parsed, desde, hasta)}
    finally:
        conn.close()


@router.get("/disponibilidad")
def get_disponibilidad(
    fecha_desde: str = Query(...),
    fecha_hasta: str = Query(...),
    exclude_pedido_id: int = Query(None),
):
    """Endpoint fino: abre la conexión y delega en la fuente única de lectura
    `reservas.calcular_disponibilidad`. Lo llaman también `routes.estudio` y
    `routes.cliente_portal` con esta misma firma."""
    conn = get_db()
    try:
        return _calcular_disponibilidad(conn, fecha_desde, fecha_hasta, exclude_pedido_id)
    finally:
        conn.close()


@router.post("/admin/recordatorios/retiro/run")
def run_recordatorios_retiro(request: Request, dry_run: bool = Query(True)):
    """Dispara on-demand el barrido de recordatorios de retiro — para probar en
    staging sin esperar al scheduler diario. `dry_run=true` (default) NO manda
    nada: solo devuelve qué pedidos recibirían el recordatorio mañana. Pasar
    `dry_run=false` manda de verdad (gateado igual por el canal de mail activo).

    Import perezoso de `jobs.recordatorios` para no crear ciclo (ese módulo
    importa helpers de este).
    """
    require_admin(request)
    from jobs.recordatorios import enviar_recordatorios_retiro

    conn = get_db()
    try:
        return enviar_recordatorios_retiro(conn, dry_run=dry_run)
    finally:
        conn.close()


# ── Rutas de pedidos ─────────────────────────────────────────────────────────

def _fmt_ars(monto) -> str:
    """Formatea un monto en pesos estilo es-AR: $ 12.500."""
    try:
        n = int(round(float(monto or 0)))
    except (TypeError, ValueError):
        n = 0
    return "$ " + f"{n:,}".replace(",", ".")


def _fmt_fecha_amable(v) -> str:
    """ISO → '15 jun · 10:00' (sin año). Cae al ISO si no parsea."""
    iso = to_iso(v)
    if not iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(str(iso).replace("Z", ""))
    except (ValueError, TypeError):
        return str(iso)
    meses = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]
    fecha = f"{dt.day} {meses[dt.month - 1]}"
    if dt.hour or dt.minute:
        return f"{fecha} · {dt.hour:02d}:{dt.minute:02d}"
    return fecha


def _pedido_email_context(pedido: dict) -> dict:
    """Arma el dict de variables disponibles a todos los templates de
    pedido. Mantener en sincronía con la lista de variables que se muestra
    en el editor del frontend (`/admin/email-templates`).
    """
    from markupsafe import escape

    items = pedido.get("items") or []

    def _nombre(it) -> str:
        return it.get("nombre_publico") or it.get("nombre") or it.get("equipo_nombre") or ""

    items_text = "\n".join(
        f"- {_nombre(it)} × {it.get('cantidad', 1)}" for it in items
    )

    # Tabla estilizada (inline) para el mail. Los nombres (datos dinámicos) se
    # escapan; la estructura HTML es segura → la plantilla la inyecta con |safe.
    filas = ""
    for it in items:
        nombre = escape(_nombre(it))
        cant = escape(str(it.get("cantidad", 1)))
        sub = it.get("subtotal")
        sub_cell = (
            f'<td style="padding:8px 0;text-align:right;white-space:nowrap;color:#2a251e;">{escape(_fmt_ars(sub))}</td>'
            if sub is not None
            else '<td style="padding:8px 0;"></td>'
        )
        filas += (
            '<tr style="border-bottom:1px solid #ececec;">'
            f'<td style="padding:8px 8px 8px 0;color:#2a251e;">{nombre}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#8a8378;white-space:nowrap;">× {cant}</td>'
            f"{sub_cell}</tr>"
        )
    items_html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;font-size:14px;margin:4px 0 8px;">'
        f"{filas}</table>"
        if items
        else ""
    )

    return {
        "cliente_nombre": pedido.get("cliente_nombre") or "",
        "cliente_email": pedido.get("cliente_email") or "",
        "cliente_telefono": pedido.get("cliente_telefono") or "",
        "numero_pedido": pedido.get("numero_pedido") or pedido.get("id"),
        "fecha_desde": _fmt_fecha_amable(pedido.get("fecha_desde")),
        "fecha_hasta": _fmt_fecha_amable(pedido.get("fecha_hasta")),
        "total": _fmt_ars(pedido.get("monto_total")),
        "notas": pedido.get("notas") or "",
        "items_html": items_html,
        "items_text": items_text,
        # URLs absolutas: en un cliente de mail un link relativo no resuelve.
        "admin_url": f"{SITE_URL}/admin/pedidos/{pedido.get('id')}",
        "portal_url": f"{SITE_URL}/cliente/portal",
        # Link "Agregar a Google Calendar" para el cuerpo del mail (complementa
        # al adjunto .ics). Vacío si la reserva no tiene fecha → el template lo
        # renderiza como string vacía (Jinja Undefined) sin romper.
        "gcal_url": google_calendar_url(
            pedido, pedido.get("items") or [], link=f"{SITE_URL}/cliente/portal"
        ),
    }


def _ics_adjunto_pedido(pedido: dict) -> Optional[list[Attachment]]:
    """Genera el adjunto `.ics` de la reserva para el mail (estilo "pasaje de
    avión": el cliente toca "Agregar al calendario"). Best-effort: si algo
    falla, devuelve None y el mail igual sale (la confirmación no se rompe).

    Usa el generador canónico de `services/ical.py` — el mismo que el feed.
    """
    try:
        # Link al portal del cliente (NO al back-office) — el .ics se lo lleva él.
        # with_reminders: su calendario le avisa solo antes del retiro.
        vevent = reserva_to_vevent(
            pedido, pedido.get("items") or [],
            link=f"{SITE_URL}/cliente/portal", with_reminders=True,
        )
        if not vevent:
            return None
        ics = build_vcalendar([vevent], method="PUBLISH")
        numero = pedido.get("numero_pedido") or pedido.get("id")
        return [
            Attachment(
                filename=f"pedido-{numero}.ics",
                content=ics.encode("utf-8"),
                mimetype="text/calendar; method=PUBLISH; charset=utf-8",
            )
        ]
    except Exception:
        logger.warning("No se pudo generar el .ics del pedido %s", pedido.get("id"), exc_info=True)
        return None


def _dispatch_pedido_creado_emails(background: Optional[BackgroundTasks], pedido: dict):
    """Encola los mails de 'pedido creado' (cliente + admin) como
    background tasks. Si no hay BackgroundTasks (llamada desde script),
    los corre síncrono — el send_email() jamás propaga errores."""
    ctx = _pedido_email_context(pedido)
    pedido_id = pedido.get("id")
    cliente_email = pedido.get("cliente_email")

    if cliente_email:
        if background is not None:
            background.add_task(
                send_email, "pedido_creado_cliente", cliente_email, ctx, pedido_id,
            )
        else:
            send_email("pedido_creado_cliente", cliente_email, ctx, pedido_id)

    admin_to = get_admin_to()
    if admin_to:
        if background is not None:
            background.add_task(
                send_email, "pedido_creado_admin", admin_to, ctx, pedido_id,
            )
        else:
            send_email("pedido_creado_admin", admin_to, ctx, pedido_id)


class CotizarItem(BaseModel):
    equipo_id: int
    cantidad: int


class CotizarRequest(BaseModel):
    items: list[CotizarItem] = []
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    # Los dos siguientes SOLO los honra una sesión admin (el builder de pedidos
    # arma para OTRO cliente, no para la sesión):
    #  - cliente_id: de qué cliente tomar el perfil tributario.
    #  - descuento_pct: override del descuento del cliente (el admin lo edita
    #    en vivo en el builder; gana sobre el `clientes.descuento` guardado).
    cliente_id: Optional[int] = None
    descuento_pct: Optional[float] = None


@router.post("/cotizar")
@limiter.limit("30/minute")
def cotizar(data: CotizarRequest, request: Request):
    """Cotización canónica del carrito — fuente única, calculada en el backend.

    El front NO calcula el total: manda solo `items` (equipo_id + cantidad) y,
    si las hay, las fechas. El backend pone TODO lo demás:
    - el `precio_jornada` de cada equipo (de la tabla `equipos`, no se confía
      en lo que mande el front),
    - el perfil tributario y el descuento del cliente (cliente logueado → el
      suyo; admin → el del `cliente_id` que pase; anónimo → `consumidor_final`),
    - el descuento por jornadas.

    **Sin fechas = modo estimado:** jornadas=1, sin descuentos ni IVA (es solo
    referencia de precio mientras el cliente no eligió período). Replica el
    comportamiento histórico del carrito en armado.

    Devuelve el desglose de `services.precios.calcular_total` + `descuento_origen`
    y `subtotal_por_jornada` (para el UI), de modo que el front muestre los
    números tal cual. Reemplaza el cálculo duplicado del front
    (`src/lib/cart-total.ts`). Ver #617.
    """
    conn = get_db()
    try:
        # Jornadas: misma fórmula única (ceil/24h). Sin fechas → 1.
        d0 = to_datetime(data.fecha_desde) if data.fecha_desde else None
        d1 = to_datetime(data.fecha_hasta) if data.fecha_hasta else None
        jornadas = jornadas_periodo(d0, d1)
        tiene_fechas = bool(d0 and d1)

        # Precios desde el backend. Equipos inexistentes/eliminados se ignoran
        # (cotización best-effort: el carrito puede tener algo que ya no está).
        # Fetch por-ítem (lookup por PK indexada): se revirtió el batch `IN (...)`
        # de #643 que devolvía precios_map vacío en prod → total $0 (regresión).
        items_para_total = []
        for it in data.items:
            if it.cantidad <= 0:
                continue
            row = conn.execute(
                "SELECT precio_jornada, tipo FROM equipos WHERE id=? AND eliminado_at IS NULL",
                (it.equipo_id,),
            ).fetchone()
            if not row:
                continue
            # C3 #635: el precio de un COMBO se deriva en vivo de sus componentes
            # (Σ × descuento por línea); kits y simples usan su precio propio.
            if row["tipo"] == "combo":
                precio = precio_combo(conn, it.equipo_id)
            else:
                precio = row["precio_jornada"] or 0
            items_para_total.append({
                "equipo_id": it.equipo_id,
                "cantidad": it.cantidad,
                "precio_jornada": precio,
            })
        subtotal_por_jornada = sum(
            it["precio_jornada"] * it["cantidad"] for it in items_para_total
        )

        # Perfil tributario + descuento del cliente. Solo en modo firme (con
        # fechas): sin fechas es un estimado sin IVA ni descuentos.
        perfil = None
        descuento_cliente_pct = 0.0
        descuento_jornadas_pct = 0.0
        if tiene_fechas:
            # ¿Qué cliente? El logueado (sesión cliente) o, si es admin, el
            # `cliente_id` pedido (el builder admin cotiza para terceros).
            session = get_session(request)
            es_admin = bool(session and is_admin_email(session.get("email")))
            target_cliente_id = None
            if session:
                if session.get("role") == "cliente" and session.get("cliente_id"):
                    target_cliente_id = session["cliente_id"]
                elif es_admin and data.cliente_id:
                    target_cliente_id = data.cliente_id
            if target_cliente_id:
                c = conn.execute(
                    "SELECT perfil_impuestos, descuento FROM clientes WHERE id=?",
                    (target_cliente_id,),
                ).fetchone()
                if c:
                    perfil = c["perfil_impuestos"]
                    descuento_cliente_pct = c["descuento"] or 0.0
            # Override de descuento del admin (lo edita en vivo en el builder).
            if es_admin and data.descuento_pct is not None:
                descuento_cliente_pct = data.descuento_pct
            descuento_jornadas_pct = _get_descuento_jornadas(conn, jornadas)

        desglose = calcular_total(
            items=items_para_total,
            jornadas=jornadas,
            descuento_cliente_pct=descuento_cliente_pct,
            descuento_jornadas_pct=descuento_jornadas_pct,
            perfil_impuestos=perfil,
        )

        # Cuál descuento ganó (para el label del UI), mismo criterio que
        # `descuento_aplicable`: en empate gana el del cliente.
        if descuento_cliente_pct == 0 and descuento_jornadas_pct == 0:
            descuento_origen = "ninguno"
        elif descuento_cliente_pct >= descuento_jornadas_pct:
            descuento_origen = "cliente"
        else:
            descuento_origen = "jornadas"

        return {
            "jornadas": jornadas,
            "subtotal_por_jornada": int(subtotal_por_jornada),
            "descuento_origen": descuento_origen,
            **desglose,
        }
    finally:
        conn.close()  # devuelve la conexión al pool (sin esto se agota: maxconn=10)


@router.post("/alquileres", status_code=201)
def create_pedido_endpoint(data: PedidoCreate, request: Request, background: BackgroundTasks):
    """Endpoint admin para crear pedido. La lógica está en `create_pedido`,
    así el portal cliente (cliente_portal.py) la reutiliza sin pasar por admin guard."""
    require_admin(request)
    return create_pedido(data, background=background)


def create_pedido(data: PedidoCreate, background: Optional[BackgroundTasks] = None):
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

        # Ambas fechas o ninguna: un pedido con una sola fecha es incoherente
        # (no se puede calcular jornadas ni chequear stock).
        if bool(data.fecha_desde) != bool(data.fecha_hasta):
            raise HTTPException(400, "Indicá fecha de retiro y devolución, o ninguna")

        if data.fecha_desde and data.fecha_hasta:
            d0 = to_datetime(data.fecha_desde)
            d1 = to_datetime(data.fecha_hasta)
            hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)

            if d0 >= d1:
                raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
            if d0 < hoy:
                raise HTTPException(400, "fecha_desde no puede ser en el pasado")

            jornadas = jornadas_periodo(d0, d1)
        else:
            jornadas = 1

        items_rows = []
        for it in data.items:
            if not conn.execute("SELECT id FROM equipos WHERE id=?", (it.equipo_id,)).fetchone():
                raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado")
            subtotal = it.precio_jornada * it.cantidad * jornadas
            items_rows.append((it.equipo_id, it.cantidad, it.precio_jornada, subtotal))

        descuento_jornadas_pct = _get_descuento_jornadas(conn, jornadas)
        total_desglose = calcular_total(
            items=[
                {"equipo_id": it.equipo_id, "cantidad": it.cantidad,
                 "precio_jornada": it.precio_jornada}
                for it in data.items
            ],
            jornadas=jornadas,
            descuento_cliente_pct=descuento_pct,
            descuento_jornadas_pct=descuento_jornadas_pct,
            # monto_total se persiste NETO (sin IVA). IVA es derivado al
            # mostrar, no se persiste.
            perfil_impuestos=None,
        )
        monto_total = total_desglose["neto"]

        estado_inicial = data.estado if data.estado in {"borrador", "presupuesto"} else "presupuesto"
        next_num = _next_numero_pedido(conn)
        cur = conn.execute("""
            INSERT INTO alquileres (cliente_nombre, cliente_email, cliente_telefono,
                                 cliente_id, notas, fecha_desde, fecha_hasta,
                                 monto_total, estado, numero_pedido,
                                 descuento_pct, descuento_jornadas_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cliente_nombre, cliente_email, cliente_telefono,
              data.cliente_id, data.notas, data.fecha_desde or None, data.fecha_hasta or None,
              monto_total, estado_inicial, next_num,
              descuento_pct, descuento_jornadas_pct))
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
    except Exception:
        logger.error("Error creando pedido", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

    # Mails fuera del try/finally del DB: si fallan no rollbackean el pedido
    # (igual send_email no propaga, pero por las dudas). Solo se mandan si
    # el pedido salió de borrador — drafts no notifican.
    if pedido and pedido.get("estado") != "borrador":
        _dispatch_pedido_creado_emails(background, pedido)
    return pedido


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
    con_saldo: Optional[bool] = Query(None, description="Si true, solo pedidos con saldo pendiente (monto_pagado < monto_total)"),
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
            where += " AND (p.cliente_nombre LIKE ? OR CAST(p.numero_pedido AS TEXT) LIKE ?)"
            params += [like, like]
        if con_saldo:
            # Pedidos con saldo > 0 y no cancelados. Borrador y presupuesto no
            # aplican porque todavía no se cobra; cancelado tampoco.
            where += " AND (COALESCE(p.monto_pagado, 0) < COALESCE(p.monto_total, 0))"
            where += " AND p.estado IN ('confirmado','retirado','devuelto','finalizado')"

        col = SORT_COLS.get(sort_by, "p.numero_pedido")
        direction = "ASC" if sort_dir == "asc" else "DESC"
        # Poner "Registro manual" (sin número de pedido) al final.
        has_numero = "(p.numero_pedido IS NOT NULL)"
        order = f"{has_numero} DESC, {col} {direction} NULLS LAST"
        # secundario: número descendente para desempate
        if col != "p.numero_pedido":
            order += ", p.numero_pedido DESC NULLS LAST"

        total = conn.execute(f"SELECT COUNT(*) FROM alquileres p {where}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT p.* FROM alquileres p {where} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        pedidos    = [row_to_dict(r) for r in rows]
        items_map  = _batch_get_alquiler_items(conn, [p["id"] for p in pedidos])

        # Pedidos con solicitud de modificación pendiente — para badge en UI.
        pedido_ids = [p["id"] for p in pedidos]
        pendientes: set[int] = set()
        if pedido_ids:
            ph = ",".join(["?"] * len(pedido_ids))
            for r in conn.execute(
                f"""SELECT DISTINCT pedido_id FROM solicitudes_modificacion
                    WHERE estado = 'pendiente' AND pedido_id IN ({ph})""",
                pedido_ids,
            ).fetchall():
                pendientes.add(r["pedido_id"])

        for p in pedidos:
            p["items"] = items_map.get(p["id"], [])
            p["tiene_solicitud_pendiente"] = p["id"] in pendientes

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

# Estados que reservan stock activamente — cualquier transición HACIA uno de
# estos requiere re-validar stock incluso si el destino no exige fechas/items
# (caso típico: borrador → presupuesto).
ESTADOS_QUE_RESERVAN = {"presupuesto", "confirmado", "retirado"}


@router.patch("/alquileres/{id}")
def update_pedido(id: int, data: PedidoEstado, request: Request, background: BackgroundTasks):
    require_admin(request)
    if data.estado not in ESTADOS_VALIDOS:
        raise HTTPException(400, f"Estado inválido. Usar: {', '.join(sorted(ESTADOS_VALIDOS))}")

    conn  = get_db()
    try:
        p_row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not p_row:
            raise HTTPException(404, "Pedido no encontrado")

        # ── Validaciones para estados que requieren fechas y stock ──────────────
        if data.estado in ESTADOS_REQUIEREN_FECHAS and not _es_historico(p_row["fuente"]):
            errores = []
            if not p_row["fecha_desde"] or not p_row["fecha_hasta"]:
                errores.append("El pedido no tiene fechas de inicio y fin.")
            else:
                try:
                    d0 = to_datetime(p_row["fecha_desde"])
                    d1 = to_datetime(p_row["fecha_hasta"])
                    hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)

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

        # Cualquier transición a un estado que reserva stock debe re-validar,
        # incluyendo "presupuesto" (que no exige fechas pero sí reserva si las
        # tiene). Salteamos si la transición no cambia el flag de "reserva"
        # (ej. confirmado → confirmado, o presupuesto → confirmado ya validado
        # arriba).
        elif (
            data.estado in ESTADOS_QUE_RESERVAN
            and p_row["estado"] not in ESTADOS_QUE_RESERVAN
            and not _es_historico(p_row["fuente"])
            and p_row["fecha_desde"] and p_row["fecha_hasta"]
        ):
            sin_stock = _check_stock(conn, id, p_row["fecha_desde"], p_row["fecha_hasta"])
            if sin_stock:
                raise HTTPException(
                    422,
                    {"errores": [f"Sin stock suficiente: {s}" for s in sin_stock]},
                )

        es_historico    = _es_historico(p_row["fuente"])
        estado_anterior = p_row["estado"]
        updates         = {"estado": data.estado}

        if data.estado == "confirmado" and not p_row["numero_pedido"]:
            next_n = _next_numero_pedido(conn)
            updates["numero_pedido"] = next_n

        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE alquileres SET {set_clause} WHERE id=?", (*updates.values(), id))

        # Si el pedido se va a un estado fuera de los modificables, las
        # solicitudes pendientes quedan huérfanas. Las cancelamos en la
        # misma transacción para no confundir al cliente ni al admin.
        # Import diferido para evitar ciclo con cliente_portal.
        from routes.cliente_portal import (
            ESTADOS_MODIFICABLES, _cancelar_solicitudes_pendientes,
        )
        if data.estado not in ESTADOS_MODIFICABLES:
            _cancelar_solicitudes_pendientes(
                conn, id,
                motivo=f"El pedido pasó a estado '{data.estado}'.",
                actor="system",
            )

        _maybe_finalizar(conn, id)
        conn.commit()

        pedido = _get_alquiler_detail(conn, id)
    except Exception:
        logger.error("Error actualizando estado del pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

    # Notif al cliente cuando pasamos a 'confirmado' (solo si veníamos de
    # otro estado — no re-mandamos si ya estaba confirmado).
    if (
        pedido
        and data.estado == "confirmado"
        and estado_anterior != "confirmado"
        and pedido.get("cliente_email")
    ):
        ctx = _pedido_email_context(pedido)
        background.add_task(
            send_email, "pedido_confirmado_cliente",
            pedido["cliente_email"], ctx, pedido.get("id"),
            attachments=_ics_adjunto_pedido(pedido),
        )
    return pedido


@router.patch("/alquileres/{id}/pago")
def registrar_pago(id: int, data: PagoParcial, request: Request):
    require_admin(request)
    """Endpoint legacy: setea monto_pagado directamente (sin registro en tabla pagos)."""
    conn = get_db()
    try:
        p = conn.execute(
            "SELECT id, monto_total FROM alquileres WHERE id=?", (id,)
        ).fetchone()
        if not p:
            raise HTTPException(404, "Pedido no encontrado")
        if data.monto_pagado < 0:
            raise HTTPException(400, "El monto pagado no puede ser negativo")
        monto_total = (p["monto_total"] or 0) if isinstance(p, dict) else (p[1] or 0)
        if data.monto_pagado > monto_total:
            raise HTTPException(
                400,
                f"El monto pagado ({data.monto_pagado}) no puede exceder el "
                f"total del pedido ({monto_total})",
            )
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


def _apply_pedido_datos(conn, id: int, data: "PedidoDatos") -> dict:
    """Aplica un cambio parcial de datos (cliente/fechas/notas/descuento) al pedido.

    Lógica compartida entre el endpoint admin (`update_pedido_datos`) y la
    aplicación de propuestas del cliente (cliente_portal). Recibe una conexión
    abierta; el caller hace commit/rollback y close.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not p:
        raise HTTPException(404, "Pedido no encontrado")

    payload = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    # Columnas TIMESTAMP: '' rompe el cast → normalizar a NULL.
    for _k in ("fecha_desde", "fecha_hasta"):
        if _k in payload and not payload[_k]:
            payload[_k] = None

    cliente_cambio = "cliente_id" in payload and payload["cliente_id"]
    if cliente_cambio:
        c = conn.execute("SELECT * FROM clientes WHERE id=?", (payload["cliente_id"],)).fetchone()
        if c:
            payload.setdefault("cliente_nombre",   f"{c['apellido']}, {c['nombre']}")
            payload.setdefault("cliente_email",    c["email"])
            payload.setdefault("cliente_telefono", c["telefono"])
            if "descuento_pct" not in payload:
                payload["descuento_pct"] = c["descuento"] or 0.0

    if "fecha_desde" in payload or "fecha_hasta" in payload:
        nueva_desde = payload.get("fecha_desde") or p["fecha_desde"]
        nueva_hasta = payload.get("fecha_hasta") or p["fecha_hasta"]
        if nueva_desde and nueva_hasta:
            d0 = to_datetime(nueva_desde)
            d1 = to_datetime(nueva_hasta)
            hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)

            if d0 >= d1:
                raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
            # Históricos importados tienen fechas en el pasado por diseño. El
            # frontend manda fecha_desde junto con cualquier cambio (ej. solo
            # el descuento), así que sin este bypass no se podría editar nada.
            if d0 < hoy and not _es_historico(p["fuente"]):
                raise HTTPException(400, "fecha_desde no puede ser en el pasado")

    if not payload:
        return _get_alquiler_detail(conn, id)

    cols = ", ".join(f"{k}=?" for k in payload)
    conn.execute(f"UPDATE alquileres SET {cols} WHERE id=?", (*payload.values(), id))

    if "fecha_desde" in payload or "fecha_hasta" in payload or cliente_cambio:
        p2 = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        d0 = to_datetime(p2["fecha_desde"]) if p2["fecha_desde"] else None
        d1 = to_datetime(p2["fecha_hasta"]) if p2["fecha_hasta"] else None
        jornadas = jornadas_periodo(d0, d1)
        items = conn.execute(
            "SELECT id, equipo_id, cantidad, precio_jornada FROM alquiler_items WHERE pedido_id=?",
            (id,),
        ).fetchall()
        # Actualizar subtotales persistidos por línea (los usan los visores).
        for it in items:
            sub = it["precio_jornada"] * it["cantidad"] * jornadas
            conn.execute("UPDATE alquiler_items SET subtotal=? WHERE id=?", (sub, it["id"]))
        descuento_jornadas_pct = _get_descuento_jornadas(conn, jornadas)
        total_desglose = calcular_total(
            items=[
                {"equipo_id": it["equipo_id"], "cantidad": it["cantidad"],
                 "precio_jornada": it["precio_jornada"]}
                for it in items
            ],
            jornadas=jornadas,
            descuento_cliente_pct=p2["descuento_pct"] or 0,
            descuento_jornadas_pct=descuento_jornadas_pct,
            perfil_impuestos=None,  # persiste NETO; IVA es derivado al mostrar.
        )
        monto_total = total_desglose["neto"]
        conn.execute(
            "UPDATE alquileres SET monto_total=?, descuento_jornadas_pct=? WHERE id=?",
            (monto_total, descuento_jornadas_pct, id)
        )

    return _get_alquiler_detail(conn, id)


def _apply_pedido_items(conn, id: int, items: list["PedidoItem"]) -> dict:
    """Reemplaza los ítems del pedido por `items`. Recalcula subtotales y monto.

    No valida stock — el caller debe llamar a `_check_stock` si corresponde.
    Lógica compartida entre admin y portal cliente.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not p:
        raise HTTPException(404, "Pedido no encontrado")
    if not items:
        raise HTTPException(400, "Debe tener al menos un ítem")

    d0 = to_datetime(p["fecha_desde"]) if p["fecha_desde"] else None
    d1 = to_datetime(p["fecha_hasta"]) if p["fecha_hasta"] else None
    jornadas = jornadas_periodo(d0, d1)

    # Consolidar duplicados del mismo equipo (sumar cantidades) antes de
    # insertar. Sino dos rows con cantidad=2 cada una pasan el check de
    # stock (que sí consolida) pero quedan 2 rows en `alquiler_items`.
    consolidado: dict[int, dict] = {}
    for it in items:
        key = it.equipo_id
        if key in consolidado:
            consolidado[key]["cantidad"] += it.cantidad
            # Si vienen precios distintos para el mismo equipo, usamos el
            # mayor (defensivo — no debería pasar).
            consolidado[key]["precio_jornada"] = max(
                consolidado[key]["precio_jornada"], it.precio_jornada,
            )
        else:
            consolidado[key] = {
                "equipo_id": it.equipo_id,
                "cantidad": it.cantidad,
                "precio_jornada": it.precio_jornada,
            }

    rows = []
    for it in consolidado.values():
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (it["equipo_id"],)).fetchone():
            raise HTTPException(404, f"Equipo {it['equipo_id']} no encontrado")
        subtotal = it["precio_jornada"] * it["cantidad"] * jornadas
        rows.append((id, it["equipo_id"], it["cantidad"], it["precio_jornada"], subtotal))

    # Re-aplicar AMBOS descuentos (cliente + jornadas), como hacen las
    # otras 2 sedes. Antes solo se aplicaba el del cliente → editar ítems
    # perdía el descuento por jornadas (#500).
    descuento_jornadas_pct = _get_descuento_jornadas(conn, jornadas)
    total_desglose = calcular_total(
        items=list(consolidado.values()),
        jornadas=jornadas,
        descuento_cliente_pct=p["descuento_pct"] or 0,
        descuento_jornadas_pct=descuento_jornadas_pct,
        perfil_impuestos=None,  # persiste NETO; IVA derivado al mostrar.
    )
    monto_total = total_desglose["neto"]

    conn.execute("DELETE FROM alquiler_items WHERE pedido_id=?", (id,))
    conn.executemany("""
        INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
        VALUES (?,?,?,?,?)
    """, rows)
    conn.execute(
        "UPDATE alquileres SET monto_total=?, descuento_jornadas_pct=? WHERE id=?",
        (monto_total, descuento_jornadas_pct, id),
    )

    return _get_alquiler_detail(conn, id)


@router.patch("/alquileres/{id}/datos")
def update_pedido_datos(id: int, data: PedidoDatos, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        pedido = _apply_pedido_datos(conn, id, data)
        conn.commit()
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
        pedido = _apply_pedido_items(conn, id, data.items)

        # Si el pedido está en estado que reserva stock, validar después de
        # aplicar los nuevos items. Sin esto el admin podía sumar cantidades
        # que excedieran el stock disponible y crear doble booking silencioso.
        p = conn.execute(
            "SELECT estado, fecha_desde, fecha_hasta FROM alquileres WHERE id=?", (id,)
        ).fetchone()
        if (
            p["estado"] in {"presupuesto", "confirmado", "retirado"}
            and p["fecha_desde"] and p["fecha_hasta"]
        ):
            problemas = _check_stock(conn, id, p["fecha_desde"], p["fecha_hasta"])
            if problemas:
                raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

        conn.commit()
        return pedido
    except Exception:
        logger.error("Error actualizando items del pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


# ── PDFs ─────────────────────────────────────────────────────────────────────

# Los documentos (remito/albarán/contrato) se generan al vuelo y siempre deben
# reflejar el estado actual del pedido. Sin esto, el navegador cachea la URL
# estática (es la misma siempre) y, tras editar el pedido —p. ej. cambiar el
# cliente—, vuelve a servir el PDF viejo. `no-store` lo fuerza a re-pedirlo.
_DOC_NO_CACHE = {"Cache-Control": "no-store, max-age=0"}

# Documentos del pedido y su etiqueta legible (para la UI de envío por mail).
DOCUMENTOS = {
    "pdf": "Cotización",
    "albaran": "Remito / Albarán",
    "contrato": "Contrato",
    "packing-list": "Packing list",
}


def _add_componentes(conn, items: list[dict]) -> None:
    """Agrega `componentes` a cada item (kits). Compartido por albarán y contrato."""
    for item in items:
        comp_rows = conn.execute("""
            SELECT ec.nombre, (SELECT nombre FROM marcas WHERE id = ec.brand_id) AS marca,
                   ec.modelo, ec.serie, ec.valor_reposicion,
                   ec.nombre_publico, ec.nombre_publico_largo, kc.cantidad
            FROM kit_componentes kc
            JOIN equipos ec ON ec.id = kc.componente_id
            WHERE kc.equipo_id = ?
        """, (item["equipo_id"],)).fetchall()
        item["componentes"] = [row_to_dict(c) for c in comp_rows]


def _doc_html(conn, id: int, kind: str) -> tuple[str, str]:
    """Construye el HTML + filename de un documento del pedido. Fuente ÚNICA
    usada por los GET de descarga y por el envío por mail."""
    if kind == "pdf":
        row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")
        pedido = row_to_dict(row)
        pedido["items"] = _get_alquiler_items(conn, id)
        _enriquecer_pedido_con_cliente_fiscal(conn, pedido)
        _enriquecer_pedido_con_total(conn, pedido)
        return _pedido_html(pedido), _pedido_filename(pedido)

    if kind == "albaran":
        row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")
        pedido = row_to_dict(row)
        items = conn.execute("""
            SELECT pi.cantidad, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo, e.serie, e.valor_reposicion, e.foto_url,
                   e.nombre_publico, e.nombre_publico_largo, pi.equipo_id
            FROM alquiler_items pi
            JOIN equipos e ON e.id = pi.equipo_id
            WHERE pi.pedido_id = ?
            ORDER BY e.nombre
        """, (id,)).fetchall()
        pedido["items"] = [row_to_dict(i) for i in items]
        _add_componentes(conn, pedido["items"])
        return _albaran_html(pedido), _pedido_filename(pedido, suffix="albaran")

    if kind == "packing-list":
        row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")
        pedido = row_to_dict(row)
        _enriquecer_pedido_con_cliente_fiscal(conn, pedido)
        pedido["items"] = _get_alquiler_items(conn, id)
        pedido["items"].sort(key=lambda it: (it.get("nombre") or "").lower())
        return _packing_list_html(pedido), _pedido_filename(pedido, suffix="packing-list")

    if kind == "contrato":
        pedido = _get_alquiler_detail(conn, id)
        _enriquecer_pedido_con_cliente_fiscal(conn, pedido)
        _add_componentes(conn, pedido["items"])
        return _contrato_html(pedido), _pedido_filename(pedido, suffix="contrato")

    raise HTTPException(400, f"Documento inválido: {kind}")


@router.get("/alquileres/{id}/pdf")
async def pedido_pdf(id: int, request: Request, format: str = "pdf"):
    """`format=html` devuelve el preview HTML sin pasar por el renderer."""
    require_admin(request)
    conn = get_db()
    try:
        html, filename = _doc_html(conn, id, "pdf")
    finally:
        conn.close()
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, headers=_DOC_NO_CACHE)
    pdf_bytes = await _render_pdf(html)
    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {"Content-Disposition": f'attachment; filename="{filename}"', **_DOC_NO_CACHE},
    )


@router.get("/alquileres/{id}/albaran")
async def pedido_albaran(id: int, request: Request, format: str = "pdf"):
    """`format=html` devuelve el preview HTML sin pasar por el renderer."""
    require_admin(request)
    conn = get_db()
    try:
        html, filename = _doc_html(conn, id, "albaran")
    finally:
        conn.close()
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, headers=_DOC_NO_CACHE)
    pdf_bytes = await _render_pdf(html)
    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {"Content-Disposition": f'attachment; filename="{filename}"', **_DOC_NO_CACHE},
    )


@router.get("/alquileres/{id}/packing-list")
async def pedido_packing_list(id: int, request: Request, format: str = "pdf"):
    """`format=html` devuelve el preview HTML sin pasar por el renderer."""
    require_admin(request)
    conn = get_db()
    try:
        html_content, filename = _doc_html(conn, id, "packing-list")
    finally:
        conn.close()
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content, headers=_DOC_NO_CACHE)
    pdf_bytes = await _render_pdf(html_content)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', **_DOC_NO_CACHE},
    )


@router.get("/alquileres/{id}/contrato")
async def pedido_contrato(id: int, request: Request, format: str = "pdf"):
    """Genera el PDF del contrato de alquiler."""
    require_admin(request)
    conn    = get_db()
    try:
        html, filename = _doc_html(conn, id, "contrato")
    finally:
        conn.close()
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, headers=_DOC_NO_CACHE)
    pdf_bytes = await _render_pdf(html)
    return Response(
        content    = pdf_bytes,
        media_type = "application/pdf",
        headers    = {"Content-Disposition": f'attachment; filename="{filename}"', **_DOC_NO_CACHE},
    )


# ── Enviar documentos por mail (#725) ─────────────────────────────────────────

class EnviarDocsRequest(BaseModel):
    docs: list[str]                       # subconjunto de DOCUMENTOS
    to: Optional[str] = None              # override del destinatario (default: cliente)
    mensaje: Optional[str] = None         # mensaje opcional del admin


@router.post("/alquileres/{id}/enviar-documentos")
async def enviar_documentos(id: int, data: EnviarDocsRequest, request: Request):
    """Manda al cliente los documentos elegidos (cotización/remito/contrato/
    packing-list) adjuntos en PDF. Reusa el renderer único (`_doc_html`) y el
    mailer (`send_raw_email`)."""
    require_admin(request)

    docs = [d for d in (data.docs or []) if d in DOCUMENTOS]
    if not docs:
        raise HTTPException(400, "Elegí al menos un documento válido.")

    # Resolver destinatario + metadatos del pedido (dentro de la conexión).
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT numero_pedido, cliente_nombre, cliente_email, cliente_id "
            "FROM alquileres WHERE id=?",
            (id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")
        ped = row_to_dict(row)
        destinatario = (data.to or ped.get("cliente_email") or "").strip()
        if not destinatario and ped.get("cliente_id"):
            c = conn.execute(
                "SELECT email FROM clientes WHERE id=?", (ped["cliente_id"],)
            ).fetchone()
            if c and c["email"]:
                destinatario = c["email"].strip()
        if not destinatario or "@" not in destinatario:
            raise HTTPException(400, "El pedido no tiene un email de cliente válido.")

        # Renderizar el HTML de cada documento (con la conexión abierta).
        docs_html = [(kind, *_doc_html(conn, id, kind)) for kind in docs]
    finally:
        conn.close()

    # Renderizar los PDFs fuera de la conexión (Playwright, async).
    adjuntos: list[Attachment] = []
    for _kind, html, filename in docs_html:
        pdf_bytes = await _render_pdf(html)
        adjuntos.append(Attachment(filename=filename, content=pdf_bytes))

    numero = ped.get("numero_pedido") or id
    nombre = (ped.get("cliente_nombre") or "").strip()
    nombres_docs = [DOCUMENTOS[k] for k in docs]
    subject = f"Documentos de tu pedido #{numero}"

    saludo = f"Hola {nombre}," if nombre else "Hola,"
    mensaje_html = ""
    if data.mensaje and data.mensaje.strip():
        # Escapado básico: el mensaje lo escribe el admin, pero por las dudas.
        import html as _html_mod
        mensaje_html = f"<p>{_html_mod.escape(data.mensaje.strip())}</p>"
    lista_docs = "".join(f"<li>{d}</li>" for d in nombres_docs)
    body_html = (
        f"<p>{saludo}</p>"
        f"<p>Te adjuntamos los siguientes documentos de tu pedido <strong>#{numero}</strong>:</p>"
        f"<ul>{lista_docs}</ul>"
        f"{mensaje_html}"
        f"<p>Cualquier duda, respondé este mail. ¡Gracias!</p>"
    )
    text = (
        f"{saludo}\n\nTe adjuntamos los documentos de tu pedido #{numero}: "
        f"{', '.join(nombres_docs)}.\n\n"
        f"{(data.mensaje.strip() + chr(10) + chr(10)) if (data.mensaje and data.mensaje.strip()) else ''}"
        f"Cualquier duda, respondé este mail. ¡Gracias!"
    )

    res = send_raw_email(
        to=destinatario,
        subject=subject,
        body_html=body_html,
        text=text,
        attachments=adjuntos,
        alquiler_id=id,
        log_key="documentos_cliente",
    )
    if not res.get("ok"):
        raise HTTPException(502, f"No se pudo enviar el mail: {res.get('error', 'error desconocido')}")
    return {"ok": True, "to": destinatario, "docs": docs, "provider": res.get("provider")}


# ── Descuentos por jornadas ───────────────────────────────────────────────────

class DescuentoJornadaIn(BaseModel):
    jornadas: int
    pct: float


@router.get("/descuentos-jornada")
def get_descuentos_jornada():
    """Devuelve los puntos ancla de descuentos por jornadas (público — lo usa el carrito)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, jornadas, pct FROM descuentos_jornada ORDER BY jornadas ASC"
        ).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/admin/descuentos-jornada", status_code=201)
def create_descuento_jornada(data: DescuentoJornadaIn, request: Request):
    require_admin(request)
    if data.jornadas < 1:
        raise HTTPException(400, "jornadas debe ser >= 1")
    if not (0 <= data.pct <= 100):
        raise HTTPException(400, "pct debe estar entre 0 y 100")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO descuentos_jornada (jornadas, pct) VALUES (?, ?) "
            "ON CONFLICT (jornadas) DO UPDATE SET pct = EXCLUDED.pct",
            (data.jornadas, data.pct)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, jornadas, pct FROM descuentos_jornada WHERE jornadas = ?",
            (data.jornadas,)
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.delete("/admin/descuentos-jornada/{id}", status_code=204)
def delete_descuento_jornada(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        conn.execute("DELETE FROM descuentos_jornada WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
