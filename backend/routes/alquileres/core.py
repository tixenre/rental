"""routes/alquileres/core.py — spine del paquete de alquileres (#501).

El `router` compartido + los modelos del pedido + los helpers reusables
(`create_pedido`, `_apply_pedido_*`, enriquecimiento, recálculo de total). Las
superficies HTTP (pedidos CRUD, cotización, disponibilidad, pagos, documentos,
descuentos) viven en submódulos que registran sus rutas sobre este router.
"""

import datetime
import logging
import time
from typing import Optional

import psycopg.errors

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from database import get_db, row_to_dict, to_datetime, to_iso, MARCA_SUBQUERY, marca_subquery
from routes.clientes import nombre_completo_cliente
# _batch_get_alquiler_items/_enriquecer_pedido_con_cliente_fiscal/_enriquecer_pedido_con_cliente/
# _enriquecer_pedidos_con_cliente viven en services.pedidos_enriquecimiento (auditoría cruzada de
# plata, 2026-07-02) — reexportados acá tal cual para no tocar los ~8 call-sites existentes (este
# paquete + routes/cliente_portal). Código nuevo debería importar de
# services.pedidos_enriquecimiento directo.
from services.pedidos_enriquecimiento import (
    _batch_get_alquiler_items,  # noqa: F401 — re-export, ver comentario arriba
    _enriquecer_pedido_con_cliente_fiscal,  # noqa: F401 — re-export, ver comentario arriba
    _enriquecer_pedido_con_cliente,
    _enriquecer_pedidos_con_cliente,  # noqa: F401 — re-export, ver comentario arriba
)
from services.email import send_email, Attachment
from services.email.service import get_admin_to
from services.ical import build_vcalendar, google_calendar_url, reserva_to_vevent
from services.precios import bruto_linea, calcular_total, jornadas_periodo, tipos_equipo_batch
from services.fechas import validar_rango_fechas, validar_fecha_iso
from descuentos.queries.jornadas import obtener_descuento_jornadas
from descuentos.queries.cliente import obtener_descuento_cliente
from config import SITE_URL

# Motor de reservas: la fuente única vive en el paquete `reservas`. Acá se
# importan solo los nombres que este módulo usa internamente (las transiciones
# de estado validan con `validar_stock`). `ESTADOS_RESERVADO` se re-exporta
# porque es la constante canónica del dominio. El resto de las primitivas se
# importan directo de `reservas` donde se usan (routes.estudio,
# routes.cliente_portal, routes.alquileres.disponibilidad). Ver issue #501, Fase 1.
from reservas import (
    ESTADOS_RESERVADO,  # noqa: F401 — re-export canónico (guard: test_reservas_sql_safety)
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
        "SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=%s", (pedido_id,)
    ).fetchone()
    if not p:
        return
    if (p["estado"] == "devuelto"
            and (p["monto_pagado"] or 0) >= (p["monto_total"] or 0)
            and (p["monto_total"] or 0) > 0):
        conn.execute("UPDATE alquileres SET estado='finalizado' WHERE id=%s", (pedido_id,))


def _get_alquiler_items(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute(f"""
        SELECT pi.*, COALESCE(e.nombre, pi.nombre_libre) AS nombre,
               {MARCA_SUBQUERY},
               e.modelo, e.serie, e.valor_reposicion,
               e.foto_url, e.foto_url_sm, e.foto_url_thumb, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo, e.tipo AS equipo_tipo,
               ef.contenido_incluido_json
        FROM alquiler_items pi
        LEFT JOIN equipos e ON e.id = pi.equipo_id
        LEFT JOIN equipo_fichas ef ON ef.equipo_id = e.id
        WHERE pi.pedido_id = %s
        ORDER BY pi.orden, pi.id
    """, (pedido_id,)).fetchall()
    items = [row_to_dict(r) for r in rows]
    if not items:
        return items

    # Batch fetch de componentes de kits: 1 query agregada en lugar de N+1
    # (antes hacía 1 query por cada item del pedido). Para pedidos con 10
    # items con kits, baja de 11 queries a 2. Las líneas personalizadas (#805)
    # no tienen equipo → se excluyen del set (equipo_id None).
    equipo_ids = list({item["equipo_id"] for item in items if item["equipo_id"] is not None})
    for item in items:
        item.setdefault("componentes", [])
    if not equipo_ids:
        return items
    placeholders = ",".join("%s" for _ in equipo_ids)
    comp_rows = conn.execute(f"""
        SELECT kc.*, ec.nombre, {marca_subquery('ec')}, ec.foto_url, ec.foto_url_sm, ec.foto_url_thumb, ec.cantidad AS stock_total,
               ec.modelo, ec.serie, ec.valor_reposicion,
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


def _get_alquiler_pagos(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM alquiler_pagos WHERE pedido_id = %s ORDER BY fecha, created_at
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def _get_alquiler_detail(conn, id: int) -> dict:
    row = conn.execute("SELECT * FROM alquileres WHERE id=%s", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Pedido no encontrado")
    pedido = row_to_dict(row)
    pedido["items"] = _get_alquiler_items(conn, id)
    pedido["pagos"] = _get_alquiler_pagos(conn, id)
    pedido["historial_modificaciones"] = _get_historial_modificaciones(conn, id)
    _enriquecer_pedido_con_cliente(conn, pedido)
    _enriquecer_pedido_con_total(conn, pedido)
    return pedido


def _enriquecer_pedido_con_total(conn, pedido: dict) -> dict:
    """Wrapper de compatibilidad — la lógica real vive en
    `services.finanzas_flujo.pedido.desglose_de_pedido` (fuente única del
    desglose de plata de un pedido: bruto/descuento/neto/IVA por línea,
    `cobro_modo`-aware). Código nuevo debería importar de ahí directo; este
    wrapper solo evita tocar los 6 call-sites existentes en la migración
    (auditoría cruzada de plata, 2026-07-02). Cierra #496.
    """
    from services.finanzas_flujo.pedido import desglose_de_pedido
    return desglose_de_pedido(conn, pedido)


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
        WHERE pedido_id = %s
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


# La validación de formato vive en la puerta única `services/fechas.py`. Se
# mantiene el nombre `_validar_fecha_iso` como alias para los field_validators de
# este módulo y la re-exportación de `routes/alquileres/__init__.py`.
_validar_fecha_iso = validar_fecha_iso


class PedidoItem(BaseModel):
    # equipo_id None = línea personalizada (#805): no es del catálogo, no reserva
    # stock; lleva `nombre_libre`. `cobro_modo`: 'jornada' (× jornadas, default) |
    # 'fijo' (monto único).
    equipo_id:      Optional[int] = None
    cantidad:       int
    precio_jornada: int = 0
    nombre_libre:   Optional[str] = None
    cobro_modo:     str = "jornada"

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

    @field_validator("cobro_modo")
    @classmethod
    def validate_cobro_modo(cls, v):
        if v not in ("jornada", "fijo"):
            raise ValueError("cobro_modo debe ser 'jornada' o 'fijo'")
        return v

    @model_validator(mode="after")
    def validate_linea_libre(self):
        # Una línea personalizada (sin equipo_id) necesita un nombre; una de
        # catálogo no puede cobrarse 'fijo' (eso es solo para líneas libres).
        if self.equipo_id is None:
            if not (self.nombre_libre or "").strip():
                raise ValueError("una línea personalizada necesita un nombre")
        elif self.cobro_modo != "jornada":
            raise ValueError("solo las líneas personalizadas pueden cobrarse 'fijo'")
        return self


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
    # #1240: a nombre de quién se factura este pedido — mutuamente excluyentes
    # (validado por el caller, ej. `cliente_crear_pedido`), NULL/NULL = perfil
    # default de la cuenta. El admin (builder de pedidos) no los usa hoy.
    perfil_fiscal_id: Optional[int] = None
    productora_id:    Optional[int] = None

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        return _validar_fecha_iso(v)


class PedidoEstado(BaseModel):
    estado: str


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
    # Override manual en % o en $ fijo (Fase C-2, #1219): mismo campo de la UI,
    # un selector al lado. `descuento_manual_tipo` decide cuál de los dos
    # honra la jerarquía — "pct" (default, usa `descuento_pct` de arriba) o
    # "monto" (usa `descuento_manual_monto`, pesos fijos).
    descuento_manual_tipo:  Optional[str]   = None
    descuento_manual_monto: Optional[float] = None

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

    @field_validator("descuento_manual_tipo")
    @classmethod
    def validate_descuento_manual_tipo(cls, v):
        if v is None:
            return v
        if v not in ("pct", "monto"):
            raise ValueError("descuento_manual_tipo debe ser 'pct' o 'monto'")
        return v

    @field_validator("descuento_manual_monto")
    @classmethod
    def validate_descuento_manual_monto(cls, v):
        if v is None:
            return v
        if v < 0:
            raise ValueError("descuento_manual_monto no puede ser negativo")
        # `alquileres.descuento_manual_monto` es INTEGER — sin este tope, un
        # valor fuera de rango llega crudo a Postgres como `NumericValueOutOfRange`
        # (mismo gap que cerró la auditoría de contabilidad, 2026-07-02).
        if v >= 2_147_483_647:
            raise ValueError("descuento_manual_monto demasiado alto")
        return v


class PedidoItemUpdate(BaseModel):
    items: list[PedidoItem]


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
    # escapan; la estructura/estilo la pone el helper canónico de branding
    # (`services/email/branding.py`, fuente única del look de mail) → la plantilla
    # la inyecta con |safe.
    from services.email import branding as _eb

    filas = ""
    for it in items:
        nombre = escape(_nombre(it))
        cant = escape(str(it.get("cantidad", 1)))
        sub = it.get("subtotal")
        sub_html = escape(_fmt_ars(sub)) if sub is not None else None
        filas += _eb.item_row(nombre, cant, sub_html)

    # Fila de descuento (mismo criterio bruto→descuento→neto que el
    # Presupuesto, `pdf_templates._pedido_html`): las líneas de arriba
    # muestran el bruto por ítem y el "Total" del mail es el NETO (con
    # descuento por jornadas ya aplicado, el caso común en cualquier
    # alquiler de varios días) — sin esta fila el cliente veía un ítem en
    # $X y un total menor sin ninguna aclaración de por qué.
    descuento = int(pedido.get("descuento_monto") or 0)
    if descuento > 0:
        # `descuento_efectivo_pct` (el % GANADOR, expuesto por `desglose_de_pedido`)
        # — no el `descuento_pct` crudo, que desde la Fase C-1 (#1219) es solo el
        # override manual (0 = sin override) y puede no coincidir con lo que ganó.
        desc_pct = float(pedido.get("descuento_efectivo_pct") or 0)
        label = "Descuento" + (f" ({desc_pct:g}%)" if desc_pct else "")
        filas += _eb.discount_row(
            escape(label), escape(f"− {_fmt_ars(descuento)}")
        )

    items_html = _eb.items_table(filas)

    # Jornadas: si el pedido ya viene enriquecido (`_enriquecer_pedido_con_total`)
    # lo reusamos; si no, lo derivamos con la fórmula única (mismo helper).
    jornadas = pedido.get("cantidad_jornadas")
    if jornadas is None:
        d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
        d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
        jornadas = jornadas_periodo(d0, d1)

    # Estado de pago (info "estilo pasaje": total, lo abonado y el saldo). La
    # plata sigue siendo NETO persistido — no se recalcula acá, solo se formatea.
    def _num(v) -> float:
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    total_num = _num(pedido.get("monto_total"))
    pagado_num = _num(pedido.get("monto_pagado"))
    saldo_num = max(total_num - pagado_num, 0.0)
    total_pagado = _fmt_ars(pagado_num)
    saldo_pendiente = _fmt_ars(saldo_num)
    if total_num <= 0:
        pago_estado = ""
    elif saldo_num <= 0:
        pago_estado = "Pago completo ✓"
    elif pagado_num > 0:
        pago_estado = f"Pagado {total_pagado} · saldo pendiente {saldo_pendiente}"
    else:
        pago_estado = "Pendiente de pago"

    return {
        "cliente_nombre": pedido.get("cliente_nombre") or "",
        "cliente_email": pedido.get("cliente_email") or "",
        "cliente_telefono": pedido.get("cliente_telefono") or "",
        "numero_pedido": pedido.get("numero_pedido") or pedido.get("id"),
        "fecha_desde": _fmt_fecha_amable(pedido.get("fecha_desde")),
        "fecha_hasta": _fmt_fecha_amable(pedido.get("fecha_hasta")),
        "cantidad_jornadas": jornadas,
        "total": _fmt_ars(pedido.get("monto_total")),
        "total_pagado": total_pagado,
        "saldo_pendiente": saldo_pendiente,
        "pago_estado": pago_estado,
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


# Namespace (clave1 de `pg_advisory_xact_lock`) para serializar creación de
# pedidos por equipo. Arbitrario y privado de este flujo; evita colisión con
# otros advisory locks de la app.
_ADVISORY_NS_PEDIDO = 5390412


def create_pedido(data: PedidoCreate, background: Optional[BackgroundTasks] = None,
                  es_admin: bool = False):
    """Lógica interna de creación de pedido. Llamada por el endpoint admin
    (`create_pedido_endpoint`) y también por `cliente_portal.cliente_crear_pedido`
    que tiene su propio `require_cliente`."""
    if not data.items and data.estado != "borrador":
        raise HTTPException(400, "El pedido debe tener al menos un ítem")
    # Defense-in-depth (#1240, hallazgo de revisión): `cliente_crear_pedido` ya
    # valida esto antes de llamar acá, pero esta es la ÚNICA puerta real de
    # creación — sin este chequeo acá, cualquier caller futuro que sete ambos
    # campos rompería el `CHECK chk_alquileres_facturacion_target` sin capturar
    # (el único except de abajo es `DeadlockDetected`) → 500 crudo en vez de 400.
    if data.perfil_fiscal_id and data.productora_id:
        raise HTTPException(400, "Un pedido no puede facturar a un perfil personal y a una productora a la vez.")

    cliente_nombre   = data.cliente_nombre
    cliente_email    = data.cliente_email
    cliente_telefono = data.cliente_telefono

    with get_db() as conn:
        try:
            # `descuento_pct` (override manual del pedido) arranca en 0 = "sin
            # override, seguí al cliente en vivo" (Fase C-1, #1219) — YA NO se
            # copia el descuento del cliente acá; `_apply_pedido_items` (más
            # abajo) lo resuelve en vivo vía `obtener_descuento_cliente`.
            descuento_pct = 0.0
            if data.cliente_id:
                c = conn.execute("SELECT * FROM clientes WHERE id=%s", (data.cliente_id,)).fetchone()
                if c:
                    cliente_nombre   = nombre_completo_cliente(c["nombre"], c["apellido"])
                    cliente_email    = cliente_email    or c["email"]
                    cliente_telefono = cliente_telefono or c["telefono"]

            # Ambas fechas o ninguna: un pedido con una sola fecha es incoherente
            # (no se puede calcular jornadas ni chequear stock).
            if bool(data.fecha_desde) != bool(data.fecha_hasta):
                raise HTTPException(400, "Indicá fecha de retiro y devolución, o ninguna")

            if data.fecha_desde and data.fecha_hasta:
                # Criterio de fechas por la fuente única `validar_rango_fechas`.
                # El admin puede crear con fecha pasada (carga retroactiva); el
                # cliente no (la distinción la pasa `create_pedido_endpoint`).
                msg = validar_rango_fechas(
                    data.fecha_desde, data.fecha_hasta, permitir_pasado=es_admin
                )
                if msg:
                    raise HTTPException(400, msg)

            # Serializar la creación sobre cada equipo del pedido ANTES de
            # insertar los ítems. El insert de `alquiler_items` toma un FK
            # KEY-SHARE sobre la fila de `equipos`; el gate de stock pide luego
            # FOR UPDATE (exclusivo) sobre la misma fila → dos pedidos concurrentes
            # del mismo equipo se deadlockean en el upgrade de lock (salía 500).
            # El advisory lock (xact-scoped, tomado en orden de id para no
            # deadlockear entre transacciones) los pone en fila: cada uno espera
            # su turno y corre limpio (201 o 409 real por falta de stock). NO toca
            # el FOR UPDATE del gate (motor de reservas = sagrado); se libera solo
            # al commit/rollback. `create_pedido_retry` queda de backstop.
            for _eid in sorted({it.equipo_id for it in data.items
                                if getattr(it, "equipo_id", None)}):
                conn.execute("SELECT pg_advisory_xact_lock(%s, %s)",
                             (_ADVISORY_NS_PEDIDO, _eid))

            estado_inicial = data.estado if data.estado in {"borrador", "presupuesto"} else "presupuesto"
            next_num = _next_numero_pedido(conn)
            # `fuente`: distingue quién originó el pedido para que el label del admin
            # ("back-office" vs "portal del cliente") sea confiable — antes esta columna
            # nunca se escribía acá y todo caía al default 'sistema' de la tabla, así que
            # un pedido creado por un cliente vía `cliente_crear_pedido` (es_admin=False)
            # se mostraba igual que uno cargado a mano desde el back-office.
            fuente = "sistema" if es_admin else "portal"
            # Cabecera primero con totales en 0; los ítems se aplican vía el helper
            # canónico, que recalcula monto_total y descuento_jornadas_pct.
            pedido_id = conn.insert_returning("""
                INSERT INTO alquileres (cliente_nombre, cliente_email, cliente_telefono,
                                     cliente_id, notas, fecha_desde, fecha_hasta,
                                     monto_total, estado, numero_pedido,
                                     descuento_pct, descuento_jornadas_pct, fuente,
                                     perfil_fiscal_id, productora_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (cliente_nombre, cliente_email, cliente_telefono,
                  data.cliente_id, data.notas, data.fecha_desde or None, data.fecha_hasta or None,
                  0, estado_inicial, next_num,
                  descuento_pct, 0.0, fuente,
                  data.perfil_fiscal_id, data.productora_id))

            # Ítems vía la fuente única `_apply_pedido_items` (#805): preserva las
            # líneas personalizadas (equipo_id None → nombre_libre/cobro_modo/orden),
            # consolida las de catálogo y respeta cobro_modo='fijo' (no × jornadas).
            # El armado inline anterior asumía equipo_id válido → 404 al crear con una
            # línea libre, y descartaba nombre_libre/cobro_modo. Borradores: sin ítems.
            if data.items:
                _apply_pedido_items(conn, pedido_id, data.items)

            if estado_inicial == "presupuesto" and data.fecha_desde and data.fecha_hasta:
                problemas = _check_stock(conn, pedido_id, data.fecha_desde, data.fecha_hasta)
                if problemas:
                    raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

            conn.commit()
            pedido = _get_alquiler_detail(conn, pedido_id)
        except psycopg.errors.DeadlockDetected:
            # Deadlock transitorio por upgrade de lock bajo concurrencia (FK
            # KEY-SHARE del insert de ítems + FOR UPDATE del gate sobre la misma
            # fila de `equipos`). PG aborta una de las transacciones. NO es un
            # error nuestro: el caller (`create_pedido_retry`) reintenta. No lo
            # logueamos como error para no ensuciar; sólo rollback + propagar.
            conn.rollback()
            raise
        except Exception:
            logger.error("Error creando pedido", exc_info=True)
            conn.rollback()
            raise

    # Mails fuera del try/finally del DB: si fallan no rollbackean el pedido
    # (igual send_email no propaga, pero por las dudas). Solo se mandan si
    # el pedido salió de borrador — drafts no notifican.
    if pedido and pedido.get("estado") != "borrador":
        _dispatch_pedido_creado_emails(background, pedido)
    return pedido


def create_pedido_retry(data: PedidoCreate, background: Optional[BackgroundTasks] = None,
                        es_admin: bool = False, intentos: int = 5):
    """Crea un pedido reintentando ante deadlock de Postgres (concurrencia).

    Bajo reservas concurrentes del mismo equipo, dos transacciones se bloquean
    mutuamente — el insert de `alquiler_items` toma un FK KEY-SHARE sobre la fila
    de `equipos` y el gate de stock pide FOR UPDATE (exclusivo) sobre esa misma
    fila → PG detecta el deadlock y aborta una (`DeadlockDetected`), que sin esto
    salía como **500**. Reintentar es el patrón estándar: serializa y resuelve,
    SIN tocar el lock (el motor de reservas es sagrado), sin overbooking (el gate
    corre íntegro en cada intento) ni pedidos huérfanos (rollback antes de cada
    reintento). Agotados los intentos → **503** (carga puntual), nunca 500.

    Es la ÚNICA puerta de creación de pedidos para los endpoints (cliente y
    back-office): centraliza el reintento en una sola fuente.
    """
    for i in range(intentos):
        try:
            return create_pedido(data, background=background, es_admin=es_admin)
        except psycopg.errors.DeadlockDetected:
            if i == intentos - 1:
                logger.warning("Pedido: deadlock persistente tras %d intentos → 503", intentos)
                raise HTTPException(
                    503, "Hay mucha demanda sobre ese equipo en este momento. "
                         "Reintentá en unos segundos.")
            time.sleep(0.04 * (i + 1))   # backoff corto; el scheduling rompe el ciclo
    # Inalcanzable con intentos >= 1 (la última vuelta siempre retorna o tira 503);
    # blindaje por si se invocara con intentos <= 0.
    raise HTTPException(503, "No se pudo crear el pedido")


def _recalcular_total_pedido(conn, id: int) -> None:
    """Recalcula y persiste el total de un pedido desde su estado YA guardado.

    Fuente ÚNICA del recálculo "desde lo que hay en la base": subtotales por
    línea, `descuento_jornadas_pct` (derivado de las jornadas) y `monto_total`
    (neto). Lee los ítems, las fechas y el `descuento_pct` del propio pedido —
    no recibe nada de afuera. No toca stock.

    Jerarquía de descuento (Fase C-1, #1219): `alquileres.descuento_pct` es el
    override MANUAL del pedido (0 = sin override). El descuento de
    cliente/jornadas se lee EN VIVO **solo mientras el pedido sigue en
    `presupuesto`** (así el builder sigue al cliente en vivo, comportamiento
    de siempre); una vez que pasa a `confirmado`/`retirado`/etc. se REUSA el
    snapshot ya persistido en la fila — se sigue recalculando `monto_total`
    (los ítems SÍ se pueden corregir post-confirmado) pero con el % YA
    CONGELADO, nunca uno recién leído de `clientes`/`descuentos_jornada`.

    Bug real (encontrado auditando un pedido con un descuento "que no
    existía"): antes de este guard, CUALQUIER guardado del pedido —aunque
    fuera una nota, no algo relacionado al descuento— disparaba esta función,
    que releía `obtener_descuento_cliente` en vivo y pisaba el snapshot
    congelado sin mirar el estado. Eso viola "plata congelada" (MEMORIA
    2026-06-06): un pedido ya confirmado/retirado podía cambiar de total solo
    porque alguien tocó cualquier otro campo del formulario admin.

    Lo usan `_apply_pedido_datos` (editar fechas/cliente/descuento) y la
    edición de ítems. `propagar_descuento_a_presupuestos` también dispara esto
    cuando cambia el descuento de un cliente — pero solo alcanza presupuestos
    (columna `estado='presupuesto'` en su propio WHERE), así que el guard de
    acá nunca lo bloquea a él.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=%s", (id,)).fetchone()
    if not p:
        return
    d0 = to_datetime(p["fecha_desde"]) if p["fecha_desde"] else None
    d1 = to_datetime(p["fecha_hasta"]) if p["fecha_hasta"] else None
    jornadas = jornadas_periodo(d0, d1)
    items = conn.execute(
        "SELECT id, equipo_id, cantidad, precio_jornada, cobro_modo FROM alquiler_items WHERE pedido_id=%s",
        (id,),
    ).fetchall()
    # Subtotales persistidos por línea (los usan los visores). `bruto_linea`
    # respeta el modo de cobro (las líneas 'fijo' no multiplican por jornadas).
    for it in items:
        sub = bruto_linea(
            {"precio_jornada": it["precio_jornada"], "cantidad": it["cantidad"],
             "cobro_modo": it["cobro_modo"]},
            jornadas,
        )
        conn.execute("UPDATE alquiler_items SET subtotal=%s WHERE id=%s", (sub, it["id"]))
    if p["estado"] == "presupuesto":
        descuento_jornadas_pct = obtener_descuento_jornadas(conn, jornadas)
        descuento_cliente_pct = obtener_descuento_cliente(conn, p["cliente_id"])
    else:
        descuento_jornadas_pct = p["descuento_jornadas_pct"] or 0
        descuento_cliente_pct = p["descuento_cliente_pct"] or 0
    # `es_combo` (Fase C-3, #1219): resuelve qué líneas quedan afuera del
    # descuento global de cliente/jornadas/manual — ya traen el suyo propio.
    tipos = tipos_equipo_batch(conn, [it["equipo_id"] for it in items if it["equipo_id"]])
    total_desglose = calcular_total(
        items=[
            {"equipo_id": it["equipo_id"], "cantidad": it["cantidad"],
             "precio_jornada": it["precio_jornada"], "cobro_modo": it["cobro_modo"],
             "es_combo": tipos.get(it["equipo_id"]) == "combo"}
            for it in items
        ],
        jornadas=jornadas,
        descuento_cliente_pct=descuento_cliente_pct,
        descuento_jornadas_pct=descuento_jornadas_pct,
        descuento_manual_pct=p["descuento_pct"] or 0,
        descuento_manual_tipo=p["descuento_manual_tipo"] or "pct",
        descuento_manual_monto=p["descuento_manual_monto"] or 0,
        perfil_impuestos=None,  # persiste NETO; IVA es derivado al mostrar.
    )
    # `descuento_cliente_pct` se persiste como SNAPSHOT (igual que jornadas) —
    # sin esto, mostrar el desglose de un pedido ya confirmado tendría que
    # volver a consultar `clientes.descuento` EN VIVO, y si el cliente cambió
    # su descuento después de confirmar, el desglose mostrado divergiría de
    # `monto_total` ya persistido (bug clase #405). Ver `desglose_de_pedido`.
    conn.execute(
        "UPDATE alquileres SET monto_total=%s, descuento_jornadas_pct=%s, "
        "descuento_cliente_pct=%s WHERE id=%s",
        (total_desglose["neto"], descuento_jornadas_pct, descuento_cliente_pct, id),
    )


def propagar_descuento_a_presupuestos(conn, cliente_id: int) -> int:
    """Recotiza los presupuestos del cliente que SIGUEN su descuento en vivo
    (sin override manual) cuando el descuento del cliente cambia. Devuelve
    cuántos presupuestos tocó.

    Jerarquía de descuento (Fase C-1, #1219): ya no sobreescribe
    `alquileres.descuento_pct` — ese campo es el override MANUAL del pedido
    (0 = sin override, sigue al cliente en vivo). Antes, esta función pisaba
    ese campo sin condición en cada presupuesto abierto, lo que de paso
    clobbereaba cualquier override manual que ya existiera (bug real
    encontrado auditando #1219). Ahora solo dispara `_recalcular_total_pedido`
    (que ya lee el descuento del cliente EN VIVO) y solo para los presupuestos
    que efectivamente no tienen override — el resto no depende del cliente,
    no hace falta tocarlos.

    Solo afecta el estado `presupuesto` (no confirmado): los pedidos confirmados
    o cerrados conservan el snapshot del descuento con que se crearon — es un
    lock de precio deliberado (un pedido confirmado/facturado no debe cambiar de
    importe porque después se editó el perfil del cliente). Recibe una conexión
    abierta; el caller hace commit.
    """
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM alquileres WHERE cliente_id=%s AND estado='presupuesto' "
            "AND (descuento_pct IS NULL OR descuento_pct = 0)",
            (cliente_id,),
        ).fetchall()
    ]
    for pid in ids:
        _recalcular_total_pedido(conn, pid)
    return len(ids)


def _apply_pedido_datos(conn, id: int, data: "PedidoDatos", es_admin: bool = False) -> dict:
    """Aplica un cambio parcial de datos (cliente/fechas/notas/descuento) al pedido.

    Lógica compartida entre el endpoint admin (`update_pedido_datos`) y la
    aplicación de propuestas del cliente (cliente_portal). Recibe una conexión
    abierta; el caller hace commit/rollback y close.

    `es_admin=True` permite fecha de retiro en el pasado (carga retroactiva del
    back-office). Las propuestas del cliente (cliente_portal) usan el default
    `False` → el cliente sigue sin poder fechar en el pasado.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=%s", (id,)).fetchone()
    if not p:
        raise HTTPException(404, "Pedido no encontrado")

    payload = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    # Columnas TIMESTAMP: '' rompe el cast → normalizar a NULL.
    for _k in ("fecha_desde", "fecha_hasta"):
        if _k in payload and not payload[_k]:
            payload[_k] = None

    cliente_cambio = "cliente_id" in payload and payload["cliente_id"]
    if cliente_cambio:
        c = conn.execute("SELECT * FROM clientes WHERE id=%s", (payload["cliente_id"],)).fetchone()
        if c:
            payload.setdefault("cliente_nombre",   nombre_completo_cliente(c["nombre"], c["apellido"]))
            payload.setdefault("cliente_email",    c["email"])
            payload.setdefault("cliente_telefono", c["telefono"])
            # `descuento_pct` (override manual) YA NO se copia acá (Fase C-1,
            # #1219) — 0 = "sin override, seguí al cliente en vivo" y el nuevo
            # cliente se resuelve en vivo en `_recalcular_total_pedido`. Si el
            # pedido ya tenía un override explícito, asignar OTRO cliente no
            # debería resetearlo solo — el admin lo cambia a mano si quiere.

    if "fecha_desde" in payload or "fecha_hasta" in payload:
        nueva_desde = payload.get("fecha_desde") or p["fecha_desde"]
        nueva_hasta = payload.get("fecha_hasta") or p["fecha_hasta"]
        if nueva_desde and nueva_hasta:
            # Históricos importados tienen fechas en el pasado por diseño. El
            # frontend manda fecha_desde junto con cualquier cambio (ej. solo
            # el descuento), así que sin este bypass no se podría editar nada.
            # El admin además puede fijar fechas pasadas (carga retroactiva); el
            # cliente (es_admin=False) sigue sin poder. Criterio por la fuente
            # única `validar_rango_fechas`.
            permitir_pasado = es_admin or _es_historico(p["fuente"])
            msg = validar_rango_fechas(
                nueva_desde, nueva_hasta, permitir_pasado=permitir_pasado
            )
            if msg:
                raise HTTPException(400, msg)

    if not payload:
        return _get_alquiler_detail(conn, id)

    cols = ", ".join(f"{k}=%s" for k in payload)
    conn.execute(f"UPDATE alquileres SET {cols} WHERE id=%s", (*payload.values(), id))

    if (
        "fecha_desde" in payload
        or "fecha_hasta" in payload
        or "descuento_pct" in payload
        or "descuento_manual_tipo" in payload
        or "descuento_manual_monto" in payload
        or cliente_cambio
    ):
        _recalcular_total_pedido(conn, id)

    return _get_alquiler_detail(conn, id)


def _apply_pedido_items(conn, id: int, items: list["PedidoItem"]) -> dict:
    """Reemplaza los ítems del pedido por `items`. Recalcula subtotales y monto.

    No valida stock — el caller debe llamar a `_check_stock` si corresponde.
    Lógica compartida entre admin y portal cliente.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=%s", (id,)).fetchone()
    if not p:
        raise HTTPException(404, "Pedido no encontrado")
    if not items:
        raise HTTPException(400, "Debe tener al menos un ítem")

    d0 = to_datetime(p["fecha_desde"]) if p["fecha_desde"] else None
    d1 = to_datetime(p["fecha_hasta"]) if p["fecha_hasta"] else None
    jornadas = jornadas_periodo(d0, d1)

    # Armar las líneas preservando el orden de llegada (= el orden que arma el
    # front, incl. drag-reorder #806). Las de catálogo se CONSOLIDAN por equipo
    # (sumar cantidades) — sino dos rows del mismo equipo pasan el gate (que
    # consolida) pero quedan dos filas. Las líneas personalizadas (#805, sin
    # equipo_id) NO se consolidan: cada una es única (nombre/precio/modo propios).
    lineas: list[dict] = []
    equipo_idx: dict[int, int] = {}  # equipo_id → índice en `lineas`
    for it in items:
        if it.equipo_id is None:
            lineas.append({
                "equipo_id": None,
                "cantidad": it.cantidad,
                "precio_jornada": it.precio_jornada,
                "nombre_libre": (it.nombre_libre or "").strip(),
                "cobro_modo": it.cobro_modo or "jornada",
            })
        elif it.equipo_id in equipo_idx:
            e = lineas[equipo_idx[it.equipo_id]]
            e["cantidad"] += it.cantidad
            # Precios distintos para el mismo equipo: usamos el mayor (defensivo).
            e["precio_jornada"] = max(e["precio_jornada"], it.precio_jornada)
        else:
            equipo_idx[it.equipo_id] = len(lineas)
            lineas.append({
                "equipo_id": it.equipo_id,
                "cantidad": it.cantidad,
                "precio_jornada": it.precio_jornada,
                "nombre_libre": None,
                "cobro_modo": "jornada",
            })

    # `orden` por posición; subtotal por línea vía `bruto_linea` (respeta cobro_modo).
    rows = []
    for orden, ln in enumerate(lineas):
        if ln["equipo_id"] is not None:
            eq = conn.execute(
                "SELECT id, tipo FROM equipos WHERE id=%s", (ln["equipo_id"],)
            ).fetchone()
            if not eq:
                raise HTTPException(404, f"Equipo {ln['equipo_id']} no encontrado")
            # `es_combo` (Fase C-3, #1219): no acumula el descuento global — ya
            # trae el suyo propio horneado en `precio_jornada`.
            ln["es_combo"] = eq["tipo"] == "combo"
        subtotal = bruto_linea(ln, jornadas)
        rows.append((
            id, ln["equipo_id"], ln["cantidad"], ln["precio_jornada"],
            subtotal, orden, ln["nombre_libre"], ln["cobro_modo"],
        ))

    # Re-aplicar la jerarquía completa (manual > cliente-en-vivo > jornadas),
    # como hacen las otras 2 sedes. Antes solo se aplicaba el del cliente →
    # editar ítems perdía el descuento por jornadas (#500). Acá se calcula
    # desde los ítems en memoria (los que estamos por insertar), no desde la base.
    #
    # Mismo guard que `_recalcular_total_pedido`: una vez que el pedido pasa de
    # `presupuesto`, el % de cliente/jornadas queda CONGELADO (se reusa el
    # snapshot ya persistido) — editar ítems de un pedido confirmado no debe
    # poder cambiar el % de descuento, solo el bruto/monto que ese % multiplica.
    if p["estado"] == "presupuesto":
        descuento_jornadas_pct = obtener_descuento_jornadas(conn, jornadas)
        descuento_cliente_pct = obtener_descuento_cliente(conn, p["cliente_id"])
    else:
        descuento_jornadas_pct = p["descuento_jornadas_pct"] or 0
        descuento_cliente_pct = p["descuento_cliente_pct"] or 0
    total_desglose = calcular_total(
        items=lineas,  # incluye cobro_modo por línea (líneas 'fijo' no × jornadas)
        jornadas=jornadas,
        descuento_cliente_pct=descuento_cliente_pct,
        descuento_jornadas_pct=descuento_jornadas_pct,
        descuento_manual_pct=p["descuento_pct"] or 0,
        descuento_manual_tipo=p["descuento_manual_tipo"] or "pct",
        descuento_manual_monto=p["descuento_manual_monto"] or 0,
        perfil_impuestos=None,  # persiste NETO; IVA derivado al mostrar.
    )
    monto_total = total_desglose["neto"]

    conn.execute("DELETE FROM alquiler_items WHERE pedido_id=%s", (id,))
    conn.executemany("""
        INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal, orden, nombre_libre, cobro_modo)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, rows)
    conn.execute(
        "UPDATE alquileres SET monto_total=%s, descuento_jornadas_pct=%s, "
        "descuento_cliente_pct=%s WHERE id=%s",
        (monto_total, descuento_jornadas_pct, descuento_cliente_pct, id),
    )

    return _get_alquiler_detail(conn, id)


