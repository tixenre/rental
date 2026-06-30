"""Fechas y horas de alquiler — puerta única de TODA la lógica de fechas.

Cualquier cosa que sea una DECISIÓN sobre fechas/horas vive acá, para que todos
los caminos usen los mismos valores y reglas (no más copias divergentes):

  - `validar_fecha_iso(v)` → valida el FORMATO ISO en el borde (field_validator → 422)
  - `validar_rango_fechas(fd, fh, *, permitir_pasado, max_dias)` → criterio (orden /
    no-pasado / tope de días) → mensaje | None
  - `antelacion_minima_horas(conn)` → horas de lead-time configuradas (app_settings)
  - `antelacion_insuficiente(conn, inicio)` → horas si viola el lead-time | None
  - `inicio_desde_fecha_hora(fecha, hora)` → combina fecha + hora en un datetime

Antes el criterio de rango estaba duplicado byte-por-byte en 4 lugares
(`create_pedido`, `_apply_pedido_datos`, `_validar_fechas_propuestas`, el cap de
120 días) y el formato (`validar_fecha_iso`) vivía aparte en `routes/alquileres`.
Ahora todo eso es este módulo.

Se construye sobre dos PRIMITIVAS de bajo nivel que viven en el DAL
(`database/core.py`, decisión _2026-06-27 — DAL wrapper fino_) y ya son fuente
única: `now_ar()` (reloj wall-clock de Argentina, no `date.today()` que en CI
corre en UTC y desfasa entre 00:00–03:00) y `to_datetime()` (coerción de los
date/datetime que devuelve psycopg). Este módulo es el dueño de las REGLAS;
el DAL, de esas dos primitivas.
"""

import datetime

from database import now_ar, to_datetime


# ── Validación de formato (borde → 422) ─────────────────────────────────────────


def validar_fecha_iso(v):
    """Valida que una fecha sea ISO parseable (o None/''). Se usa como
    field_validator en los modelos de pedido para rechazar fechas malformadas
    en el borde (422) en vez de explotar como 500 más adentro al castear.
    Acepta 'yyyy-mm-dd' o 'yyyy-mm-ddThh:mm'. Devuelve el str original (sin
    normalizar) o None."""
    if v is None or v == "":
        return None
    try:
        datetime.datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        raise ValueError(
            f"fecha inválida: '{v}'. Formato esperado ISO (yyyy-mm-dd o yyyy-mm-ddThh:mm)"
        )
    return str(v)


# ── Validación de rango (criterio) ──────────────────────────────────────────────


def validar_rango_fechas(
    fecha_desde,
    fecha_hasta,
    *,
    permitir_pasado: bool = False,
    max_dias: int | None = None,
) -> str | None:
    """Valida el criterio de un rango de fechas. Devuelve None si es válido, o un
    mensaje en lenguaje claro listo para mostrar/levantar.

    - permitir_pasado: el admin (carga retroactiva) y los pedidos históricos
      pueden tener inicio en el pasado; el cliente no.
    - max_dias: tope de duración en días (regla solo-cliente, ej. 120). None = sin tope.

    La granularidad (día vs. día+hora) la define el VALOR que entra: si el caller
    pasa 'YYYY-MM-DD' compara por día; si pasa 'YYYY-MM-DDThh:mm' compara con hora.
    El helper no la impone — preserva el comportamiento de cada llamador.
    """
    d0 = to_datetime(fecha_desde)
    d1 = to_datetime(fecha_hasta)
    if d0 is None or d1 is None:
        # "ambas o ninguna" lo decide el caller; sin ambas no hay rango que validar.
        return None
    if d0 >= d1:
        return "La fecha de devolución debe ser posterior a la de retiro."
    if not permitir_pasado:
        hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)
        if d0 < hoy:
            return "La fecha de inicio no puede ser en el pasado."
    if max_dias is not None and (d1 - d0).days > max_dias:
        return f"El rango del alquiler no puede superar los {max_dias} días."
    return None


# ── Antelación mínima (lead-time configurable, #1126) ───────────────────────────


def antelacion_minima_horas(conn) -> int:
    """Horas mínimas de antelación para que un cliente pueda reservar online.

    Se administra desde el back-office (`app_settings.antelacion_minima_horas`).
    Default 0 = apagado. Fail-open: un valor corrupto/ausente cae a 0 (no bloquea
    a nadie por un setting mal cargado).
    """
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = %s",
        ("antelacion_minima_horas",),
    ).fetchone()
    try:
        return max(0, int((row["value"] if row and row["value"] else "0") or "0"))
    except (ValueError, TypeError):
        return 0


def antelacion_insuficiente(conn, inicio: datetime.datetime | None) -> int | None:
    """Si el retiro `inicio` cae dentro de la ventana de antelación mínima, devuelve
    las horas configuradas (para armar el mensaje/disclaimer); si no, None.

    Predicado único: lo usa el portero (UX) y el backstop de creación (defensa en
    profundidad). `inicio` es wall-clock AR (naive), comparable contra `now_ar()`.
    """
    horas = antelacion_minima_horas(conn)
    if horas <= 0 or inicio is None:
        return None
    limite = now_ar() + datetime.timedelta(hours=horas)
    return horas if inicio < limite else None


def inicio_desde_fecha_hora(fecha, hora) -> datetime.datetime | None:
    """Combina una fecha ('YYYY-MM-DD' o date) + una hora opcional ('HH:MM' o None)
    en un datetime naive (wall-clock AR). Hora ausente/ inválida → 00:00 (el momento
    más temprano del día = el más conservador para el lead-time)."""
    d = to_datetime(fecha)
    if d is None:
        return None
    t = datetime.time(0, 0)
    if hora:
        try:
            t = datetime.time.fromisoformat(str(hora))
        except (ValueError, TypeError):
            t = datetime.time(0, 0)
    return datetime.datetime.combine(d.date(), t)
