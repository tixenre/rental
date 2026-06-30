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
import json

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


# ── Settings de horas + ventana de tiempo (primitivas compartidas) ──────────────


def setting_horas(conn, key: str, default: int = 0) -> int:
    """Lee un setting de HORAS (int) de `app_settings` con fallback. Fail-open:
    valor corrupto/ausente/negativo → `default`; nunca negativo. Fuente única para
    todos los settings de horas (lead-time, ventana de modificación, …)."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = %s", (key,)
    ).fetchone()
    try:
        return max(0, int((row["value"] if row and row["value"] else default) or default))
    except (ValueError, TypeError):
        return default


def dentro_de_ventana_horas(inicio: datetime.datetime | None, horas: int) -> bool:
    """True si `inicio` cae DENTRO de las próximas `horas` desde ahora (wall-clock
    AR). Predicado puro reusable: el lead-time pregunta "¿el retiro es demasiado
    pronto?" (esto) y el corte de modificación pregunta lo contrario (su negación).
    `inicio` naive AR, comparable contra `now_ar()`."""
    if inicio is None:
        return False
    return inicio < now_ar() + datetime.timedelta(hours=horas)


# ── Antelación mínima (lead-time configurable, #1126) ───────────────────────────


def antelacion_minima_horas(conn) -> int:
    """Horas mínimas de antelación para que un cliente reserve online
    (`app_settings.antelacion_minima_horas`, default 0 = apagado)."""
    return setting_horas(conn, "antelacion_minima_horas", 0)


def antelacion_insuficiente(conn, inicio: datetime.datetime | None) -> int | None:
    """Si el retiro `inicio` cae dentro de la ventana de antelación mínima, devuelve
    las horas configuradas (para armar el mensaje/disclaimer); si no, None. 0 =
    apagado. Lo usa el portero (UX) y el backstop de creación (defensa en profundidad)."""
    horas = antelacion_minima_horas(conn)
    if horas <= 0:
        return None
    return horas if dentro_de_ventana_horas(inicio, horas) else None


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


# ── Mes actual (wall-clock AR) ──────────────────────────────────────────────────


def mes_actual_ar() -> str:
    """Mes calendario actual en formato 'YYYY-MM', en hora de Argentina. Usar esto
    en vez de `date.today()` (que en CI/servidor corre en UTC y desfasa entre
    00:00–03:00 → puede devolver el mes equivocado a fin de mes)."""
    return now_ar().strftime("%Y-%m")


# ── Horarios habilitados de retiro/devolución (setting `horarios_retiro`) ────────

_DIAS_HORARIO = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]


def validar_horarios_habilitados(conn, fecha_desde, fecha_hasta) -> str | None:
    """Valida que retiro/devolución caigan en días/horas habilitados (setting
    `horarios_retiro`). Sin config → no restringe. Pensado para el flujo del
    cliente, que manda hora real (el admin carga date-only y no se restringe).
    Devuelve un mensaje de error (retiro primero) o None; el route levanta el HTTP."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = %s", ("horarios_retiro",)
    ).fetchone()
    if not row or not row["value"]:
        return None
    try:
        horarios = json.loads(row["value"])
    except (ValueError, TypeError):
        return None
    if not isinstance(horarios, dict) or not horarios:
        return None

    def _check(dt_raw, etiqueta: str) -> str | None:
        if not dt_raw:
            return None
        dt = to_datetime(dt_raw)
        franja = horarios.get(_DIAS_HORARIO[dt.weekday()])
        if not franja:
            return f"El {etiqueta} cae en un día no habilitado"
        hhmm = dt.strftime("%H:%M")
        if hhmm < franja["desde"] or hhmm > franja["hasta"]:
            return (
                f"El horario de {etiqueta} ({hhmm}) está fuera del rango "
                f"habilitado ({franja['desde']}–{franja['hasta']})"
            )
        return None

    return _check(fecha_desde, "retiro") or _check(fecha_hasta, "devolución")
