"""Generación de iCalendar (RFC 5545) — fuente ÚNICA de eventos de calendario.

Lo usan las DOS bocas del calendario de reservas:
  1. el **feed iCal** suscribible (`routes/calendar.py`) — muchas reservas;
  2. el **adjunto `.ics`** del mail de confirmación al cliente
     (`routes/alquileres.py`) — una reserva, estilo "pasaje de avión".
Tener un solo generador garantiza que el evento se vea idéntico en ambos lados
(barra de calidad del proyecto: modularidad a prueba de balas).

Sin dependencias externas: el formato iCal es texto plano y se arma a mano (igual
que `routes/seo.py` arma el sitemap XML). Las fechas de los pedidos se guardan
como wall-clock de Argentina (ver `database.now_ar`/`to_datetime`), así que los
eventos con hora se emiten en **tiempo flotante** (sin sufijo `Z` ni `TZID`): el
cliente de calendario los muestra tal cual, sin reinterpretar husos. Los alquileres
diarios van como eventos **all-day** (`VALUE=DATE`), donde el huso es irrelevante.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from database import to_datetime

PRODID = "-//Rambla Rental//Reservas//ES"
_UID_DOMAIN = "ramblarental.com.ar"


# ── Primitivas de formato (RFC 5545) ─────────────────────────────────────────

def _escape(text) -> str:
    """Escapa un valor de texto iCal (RFC 5545 §3.3.11): `\\`, `;`, `,` y
    saltos de línea (que pasan a `\\n`)."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str) -> str:
    """Pliega una línea lógica a <=75 octetos con continuación (RFC 5545 §3.1).

    Cuenta en bytes UTF-8 y corta entre caracteres (nunca al medio de un
    multibyte). Las líneas de continuación empiezan con un espacio, por eso se
    les presupuesta 1 octeto menos."""
    if len(line.encode("utf-8")) <= 75:
        return line
    pieces: list[str] = []
    cur = ""
    cur_bytes = 0
    first = True
    for ch in line:
        n = len(ch.encode("utf-8"))
        limit = 75 if first else 74  # las continuaciones llevan 1 espacio inicial
        if cur_bytes + n > limit:
            pieces.append(cur)
            first = False
            cur = ch
            cur_bytes = n
        else:
            cur += ch
            cur_bytes += n
    pieces.append(cur)
    return "\r\n ".join(pieces)


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _fmt_dt_floating(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def _fmt_dt_utc(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


# ── Bloques ──────────────────────────────────────────────────────────────────

def build_vevent(
    *,
    uid: str,
    summary: str,
    dtstart: datetime,
    dtend: datetime,
    all_day: bool,
    description: str = "",
    location: str = "",
    dtstamp: datetime | None = None,
) -> str:
    """Construye un `VEVENT` (líneas plegadas, unidas con CRLF).

    `all_day=True` → `DTSTART;VALUE=DATE`/`DTEND;VALUE=DATE` (el caller pasa el
    `dtend` ya exclusivo). `all_day=False` → fecha-hora en tiempo flotante.
    """
    dtstamp = dtstamp or datetime.utcnow()
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_fmt_dt_utc(dtstamp)}",
    ]
    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{_fmt_date(dtstart)}")
        lines.append(f"DTEND;VALUE=DATE:{_fmt_date(dtend)}")
    else:
        lines.append(f"DTSTART:{_fmt_dt_floating(dtstart)}")
        lines.append(f"DTEND:{_fmt_dt_floating(dtend)}")
    lines.append(f"SUMMARY:{_escape(summary)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape(description)}")
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    lines.append("END:VEVENT")
    return "\r\n".join(_fold(ln) for ln in lines)


def build_vcalendar(
    vevents: Sequence[str],
    *,
    method: str = "PUBLISH",
    cal_name: str | None = None,
) -> str:
    """Envuelve N `VEVENT` ya construidos en un `VCALENDAR` completo.

    Devuelve el texto final con terminaciones CRLF y newline final, listo para
    servir como `text/calendar` o adjuntar como `.ics`.
    """
    head = [
        "BEGIN:VCALENDAR",
        f"PRODID:{PRODID}",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
    ]
    if cal_name:
        head.append(f"X-WR-CALNAME:{_escape(cal_name)}")
    chunks = ["\r\n".join(_fold(ln) for ln in head)]
    chunks.extend(v for v in vevents if v)
    chunks.append("END:VCALENDAR")
    return "\r\n".join(chunks) + "\r\n"


# ── Adaptador de dominio: una reserva → un VEVENT ────────────────────────────

def reserva_to_vevent(
    reserva: Mapping,
    items: Sequence[Mapping] | None = None,
    *,
    site_url: str = "",
) -> str:
    """Mapea una fila de `alquileres` (+ sus items opcionales) a un `VEVENT`.

    `reserva` necesita: `id`, `fecha_desde`, `fecha_hasta`, y opcionalmente
    `numero_pedido`, `cliente_nombre`, `estado`, `tipo`. `items` (si se pasan)
    necesitan `nombre`/`marca`/`cantidad` para listar los equipos.

    UID estable (`alquiler-{id}@…`) → editar una reserva **actualiza** su evento,
    no lo duplica. Devuelve `""` si la reserva no tiene fecha de inicio.
    """
    rid = reserva.get("id")
    d0 = to_datetime(reserva.get("fecha_desde"))
    if d0 is None or rid is None:
        return ""
    d1 = to_datetime(reserva.get("fecha_hasta")) or d0

    numero = reserva.get("numero_pedido") or rid
    cliente = (reserva.get("cliente_nombre") or "Cliente").strip()
    estado = reserva.get("estado") or ""
    es_estudio = (reserva.get("tipo") or "diaria") == "estudio"

    prefijo = "🎬 Estudio: " if es_estudio else ""
    summary = f"{prefijo}Pedido #{numero} — {cliente}"

    desc_parts = [f"Estado: {estado}"] if estado else []
    if items:
        equipos = []
        for it in items:
            etiqueta = f"{it.get('marca') or ''} {it.get('nombre') or ''}".strip()
            if not etiqueta:
                continue
            cant = it.get("cantidad") or 1
            equipos.append(f"{cant}× {etiqueta}" if cant and cant != 1 else etiqueta)
        if equipos:
            desc_parts.append("Equipos: " + ", ".join(equipos))
    if site_url and rid:
        desc_parts.append(f"{site_url}/admin/pedidos/{rid}")
    description = "\n".join(desc_parts)

    uid = f"alquiler-{rid}@{_UID_DOMAIN}"
    if es_estudio:
        # Evento con hora; si las horas coinciden, garantizamos 1h de duración.
        return build_vevent(
            uid=uid, summary=summary, description=description,
            dtstart=d0, dtend=d1 if d1 > d0 else d0 + timedelta(hours=1),
            all_day=False,
        )
    # Alquiler diario → all-day; DTEND es exclusivo → día siguiente al fin.
    return build_vevent(
        uid=uid, summary=summary, description=description,
        dtstart=d0, dtend=d1 + timedelta(days=1),
        all_day=True,
    )
