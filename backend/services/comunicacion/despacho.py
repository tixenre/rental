"""services.comunicacion.despacho — armado de contexto/adjunto + fan-out multi-canal.

`notificar_pedido(evento, pedido, ctx)` lee el registro (`eventos.REGISTRO`) y despacha
el evento a los canales activos, **reusando** los senders de cada canal (mail:
`services.email.send_email`; WhatsApp: `services.whatsapp.enviar_evento_pedido`) — no
reimplementa el envío. Cada sender ya es fail-safe (nunca propaga, loguea, idempotente),
así que el despacho tampoco propaga.

El armado del contexto (`pedido_email_context`) y del `.ics` (`ics_adjunto_pedido`) vivía
en `services/pedidos_notificaciones.py` (move-verbatim); es presentación específica del
pedido, compartida por todos los canales/eventos.
"""
from __future__ import annotations

import datetime
import logging
from typing import Optional

from fastapi import BackgroundTasks

from config import SITE_URL
from database import to_datetime, to_iso
from services.comunicacion.eventos import REGISTRO, CanalMail
from services.email import Attachment, send_email
from services.email.service import get_admin_to
from services.ical import build_vcalendar, google_calendar_url, reserva_to_vevent
from services.precios import jornadas_periodo

logger = logging.getLogger(__name__)


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


def pedido_email_context(pedido: dict) -> dict:
    """Arma el dict de variables disponibles a todos los templates de pedido.
    Mantener en sincronía con la lista de variables que se muestra en el editor del
    frontend (`/admin/email-templates`)."""
    from markupsafe import escape

    items = pedido.get("items") or []

    def _nombre(it) -> str:
        return it.get("nombre_publico") or it.get("nombre") or it.get("equipo_nombre") or ""

    items_text = "\n".join(
        f"- {_nombre(it)} × {it.get('cantidad', 1)}" for it in items
    )

    # Tabla estilizada (inline) para el mail. Los nombres (datos dinámicos) se
    # escapan; la estructura/estilo la pone el helper canónico de branding
    # (`services/email/branding.py`, fuente única del look de mail).
    from services.email import branding as _eb

    filas = ""
    for it in items:
        nombre = escape(_nombre(it))
        cant = escape(str(it.get("cantidad", 1)))
        sub = it.get("subtotal")
        sub_html = escape(_fmt_ars(sub)) if sub is not None else None
        filas += _eb.item_row(nombre, cant, sub_html)

    # Fila de descuento (mismo criterio bruto→descuento→neto que el Presupuesto).
    descuento = int(pedido.get("descuento_monto") or 0)
    if descuento > 0:
        desc_pct = float(pedido.get("descuento_efectivo_pct") or 0)
        label = "Descuento" + (f" ({desc_pct:g}%)" if desc_pct else "")
        filas += _eb.discount_row(
            escape(label), escape(f"− {_fmt_ars(descuento)}")
        )

    items_html = _eb.items_table(filas)

    jornadas = pedido.get("cantidad_jornadas")
    if jornadas is None:
        d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
        d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
        jornadas = jornadas_periodo(d0, d1)

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
        "admin_url": f"{SITE_URL}/admin/pedidos/{pedido.get('id')}",
        "portal_url": f"{SITE_URL}/cliente/portal",
        "gcal_url": google_calendar_url(
            pedido, pedido.get("items") or [], link=f"{SITE_URL}/cliente/portal"
        ),
    }


def ics_adjunto_pedido(pedido: dict) -> Optional[list[Attachment]]:
    """Genera el adjunto `.ics` de la reserva para el mail ("agregar al calendario").
    Best-effort: si algo falla, devuelve None y el mail igual sale."""
    try:
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


# ── fan-out ─────────────────────────────────────────────────────────────
def _send_mail(background, template, to, ctx, alquiler_id, attachments):
    """Encola (o corre síncrono si `background is None`) un mail. Devuelve el
    resultado en modo síncrono, o None si se encoló."""
    if not to:
        return None
    if background is not None:
        background.add_task(send_email, template, to, ctx, alquiler_id, attachments=attachments)
        return None
    return send_email(template, to, ctx, alquiler_id, attachments=attachments)


def _despachar_mail(canal: CanalMail, pedido: dict, ctx: dict, background) -> list:
    pedido_id = pedido.get("id")
    resultados = []
    if canal.template_cliente:
        cliente_email = pedido.get("cliente_email")
        if cliente_email:
            # El `.ics` se calcula solo si hay a quién mandárselo (best-effort).
            attachments = ics_adjunto_pedido(pedido) if canal.con_adjunto_ics else None
            resultados.append(
                _send_mail(background, canal.template_cliente, cliente_email, ctx, pedido_id, attachments)
            )
    if canal.template_admin:
        admin_to = get_admin_to()
        if admin_to:
            resultados.append(
                _send_mail(background, canal.template_admin, admin_to, ctx, pedido_id, None)
            )
    return resultados


def _despachar_whatsapp(template_key: str, pedido: dict, ctx: dict, background):
    # Import perezoso: no acopla el despacho al canal WhatsApp al importar.
    from services.whatsapp import enviar_evento_pedido

    if background is not None:
        background.add_task(enviar_evento_pedido, template_key, pedido, ctx)
        return None
    return enviar_evento_pedido(template_key, pedido, ctx)


def notificar_pedido(
    evento_key: str, pedido: dict, ctx: Optional[dict] = None, *,
    background: Optional[BackgroundTasks] = None, canales=None,
) -> dict:
    """Despacha el evento de comunicación de un pedido a sus canales activos.

    Lee `eventos.REGISTRO[evento_key]` y hace fan-out: mail (cliente + admin + `.ics`
    según el evento) y/o WhatsApp. `ctx` opcional: si es None se arma con
    `pedido_email_context(pedido)` (los jobs lo pasan armado con extras como
    `dias_antes`). `canales` (default: los del evento) permite forzar un subconjunto
    (ej. solo mail). `background=None` corre síncrono (uso de scripts/jobs) y devuelve
    los resultados; con `BackgroundTasks` encola. Nunca propaga.

    Devuelve `{"mail": [resultados|None...], "whatsapp": resultado|None}`."""
    evento = REGISTRO.get(evento_key)
    if evento is None:
        logger.warning("comunicacion: evento desconocido %r", evento_key)
        return {"mail": [], "whatsapp": None}

    if ctx is None:
        ctx = pedido_email_context(pedido)
    activos = set(canales) if canales is not None else set(evento.canales)
    out: dict = {"mail": [], "whatsapp": None}
    if evento.mail and "mail" in activos:
        out["mail"] = _despachar_mail(evento.mail, pedido, ctx, background)
    if evento.whatsapp and "whatsapp" in activos:
        out["whatsapp"] = _despachar_whatsapp(evento.whatsapp, pedido, ctx, background)
    return out
