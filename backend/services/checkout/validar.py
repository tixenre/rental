"""services/checkout/validar.py — el portero del checkout.

Valida TODAS las precondiciones antes de crear un pedido. No falla rápido:
corre todos los checks y devuelve la lista completa de lo que falta para que
la UI pueda mostrar exactamente qué resolver. La misma lista `faltan` es la
fuente de verdad de qué muestra el UI en la pantalla de checkout.

Contrato de respuesta:
    {
        "listo": bool,
        "faltan": [{"check": str, "mensaje": str, "accion": str | None}]
    }

El portero NO crea pedidos. La creación es exclusiva de `create_pedido_retry`
(advisory lock por equipo, motor sagrado). El route hace:
    1. validar_checkout() → si listo, 2. create_pedido_retry().

La sesión del cliente (autenticación) la verifica el guard del route (`require_cliente`)
ANTES de llegar al portero. El portero recibe `cliente_id` ya autenticado.

Ver `docs/SISTEMA_CHECKOUT.md` para el flujo completo.
"""

import datetime
import json

from fastapi import HTTPException

from auth.guards import cliente_verificado
from identity.contacts import email_comunicacion
from reservas.disponibilidad import calcular_disponibilidad
from services.carrito.readiness import precios_catalogo_para_reserva
from services.checkout.tyc import TYC_VERSION_ACTUAL, ya_acepto
from services.fechas import (
    antelacion_insuficiente,
    inicio_desde_fecha_hora,
    validar_rango_fechas,
)


class _Item:
    """Proxy liviano para que las funciones del motor reciban .equipo_id y .cantidad."""

    __slots__ = ("equipo_id", "cantidad")

    def __init__(self, equipo_id: int, cantidad: int) -> None:
        self.equipo_id = equipo_id
        self.cantidad = cantidad


def _falta(check: str, mensaje: str, accion: str | None = None) -> dict:
    return {"check": check, "mensaje": mensaje, "accion": accion}


def _date_str(v) -> str | None:
    """Normaliza un valor de fecha (date, datetime, str, None) a 'YYYY-MM-DD'."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


# ── Portero principal ─────────────────────────────────────────────────────────


def validar_checkout(
    conn,
    cliente_id: int,
    session_id: str,
    firma_ok: bool = False,
    es_admin: bool = False,
) -> dict:
    """Portero del checkout: valida todos los requisitos y devuelve {listo, faltan}.

    Parámetros:
        conn        — conexión de BD abierta por el route (transacción del request).
        cliente_id  — del guard de auth del route (ya validado, nunca confiar en el body).
        session_id  — identificador del carrito activo del cliente (de cookie/request).
        firma_ok    — el route pre-computa has_recent_stepup() OR confirmed_by_session.
        es_admin    — los admins pueden usar fechas pasadas.
    """
    faltan: list[dict] = []

    # ── Leer el carrito (owner-scoped: session + cliente) ────────────────────
    carrito = _leer_carrito(conn, session_id, cliente_id)
    if carrito is None:
        return {
            "listo": False,
            "faltan": [_falta("carrito", "No encontramos tu carrito. Recargá la página.")],
        }

    raw_json = carrito.get("items_json") or []
    if isinstance(raw_json, str):
        raw_json = json.loads(raw_json)
    items = [_Item(r["equipo_id"], r["cantidad"]) for r in raw_json if r.get("equipo_id")]

    fd = _date_str(carrito.get("fecha_desde"))
    fh = _date_str(carrito.get("fecha_hasta"))
    hora_desde = carrito.get("hora_desde")

    # ── Checks (todos corren, nunca fail-fast) ───────────────────────────────
    _check_identidad(conn, cliente_id, faltan)
    _check_carrito(conn, items, faltan)
    _check_fechas(fd, fh, es_admin, faltan)
    if items and fd and fh:
        _check_stock_preflight(conn, items, fd, fh, faltan)
    if items:
        _check_precio(conn, items, faltan)
    _check_contacto(conn, cliente_id, faltan)
    _check_tyc(conn, cliente_id, faltan)
    _check_firma(firma_ok, faltan)
    _check_bloqueo(conn, cliente_id, faltan)   # cableado-apagado #1125
    if fd:
        _check_antelacion(conn, fd, hora_desde, faltan)   # lead-time configurable #1126

    return {"listo": len(faltan) == 0, "faltan": faltan}


# ── Gate de CREACIÓN (cliente-scoped, sin carrito) ────────────────────────────
# El portero `validar_checkout` (arriba) lee el carrito de `carritos_activos` — es el
# pre-flight advisory para pintar la UI. El GATE DE CREACIÓN real (`POST /api/cliente/
# pedidos`) NO puede depender de eso: el carrito no siempre está sincronizado ahí. Así que
# reusa SOLO los checks cliente-scoped (T&C + firma), corriendo las MISMAS funciones del
# portero (`_check_tyc`, `_check_firma`) → una sola fuente, sin re-implementar. El stock/
# precio los sigue enforzando `create_pedido_retry` (motor sagrado), no hace falta acá.

# ⏰ LEGACY: la firma del checkout queda CABLEADO-APAGADO hasta que la UI del checkout (el
# paso de firma con passkey / "Confirmo") shippee y mande la señal. Flip a True en el MISMO
# PR que enchufa ese paso (si no, el create actual —sin señal de firma— daría 422). Espeja
# el patrón cableado-apagado del portero (#1125/#1126).
FIRMA_CHECKOUT_OBLIGATORIA = False


def faltan_firma_tyc(conn, cliente_id: int, firma_ok: bool) -> list[dict]:
    """Precondiciones cliente-scoped del checkout (T&C + firma) para el GATE DE CREACIÓN,
    sin depender del carrito. Corre los MISMOS checks del portero → una sola fuente.
    Devuelve la lista `faltan` (vacía = OK), mismo contrato que `validar_checkout`."""
    faltan: list[dict] = []
    _check_tyc(conn, cliente_id, faltan)
    _check_firma(firma_ok, faltan)
    return faltan


# ── Helpers de lectura ────────────────────────────────────────────────────────


def _leer_carrito(conn, session_id: str, cliente_id: int) -> dict | None:
    """Carrito activo del cliente (owner-scoped: session_id + cliente_id).
    Devuelve None si el `session_id` no existe para este cliente.

    NO filtra por `confirmado`: el `session_id` del cart-store se persiste en
    localStorage y sobrevive a un pedido ya creado (`marcar_confirmado` lo deja
    en `confirmado=TRUE` para el funnel de conversión del admin) — si el mismo
    cliente arma OTRO pedido en la misma pestaña, el heartbeat sigue
    refrescando `items_json`/fechas de esa fila igual, así que sigue siendo el
    estado vigente del carrito. Filtrar acá rompía el portero con "No
    encontramos tu carrito" para cualquier segundo pedido en la misma sesión."""
    row = conn.execute(
        """SELECT items_json, fecha_desde, fecha_hasta, hora_desde, hora_hasta
           FROM carritos_activos
           WHERE session_id = %s AND cliente_id = %s""",
        (session_id, cliente_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "items_json":   row["items_json"],
        "fecha_desde":  row["fecha_desde"],
        "fecha_hasta":  row["fecha_hasta"],
        "hora_desde":   row["hora_desde"],
        "hora_hasta":   row["hora_hasta"],
    }


# ── Checks ────────────────────────────────────────────────────────────────────


def _check_identidad(conn, cliente_id: int, faltan: list) -> None:
    if not cliente_verificado(conn, cliente_id):
        faltan.append(_falta(
            "identidad",
            "Necesitás verificar tu identidad antes de hacer un pedido.",
            "/cliente/identidad",
        ))


def _check_carrito(conn, items: list, faltan: list) -> None:
    """Verifica: carrito no vacío + todos los ítems en el catálogo visible."""
    if not items:
        faltan.append(_falta("carrito", "Tu carrito está vacío.", "/"))
        return
    for it in items:
        row = conn.execute(
            "SELECT 1 FROM equipos WHERE id = %s AND visible_catalogo = 1",
            (it.equipo_id,),
        ).fetchone()
        if not row:
            faltan.append(_falta(
                "carrito",
                "Uno o más equipos de tu carrito ya no están disponibles en el catálogo.",
                "/carrito",
            ))
            return


def _check_fechas(fd: str | None, fh: str | None, es_admin: bool, faltan: list) -> None:
    if not fd or not fh:
        faltan.append(_falta("fechas", "Elegí las fechas de tu alquiler.", "/carrito"))
        return
    try:
        datetime.date.fromisoformat(fd)
        datetime.date.fromisoformat(fh)
    except (ValueError, TypeError):
        faltan.append(_falta("fechas", "Las fechas del alquiler no son válidas."))
        return
    # Criterio (orden + no-pasado) por la fuente única `validar_rango_fechas`.
    msg = validar_rango_fechas(fd, fh, permitir_pasado=es_admin)
    if msg:
        faltan.append(_falta("fechas", msg, "/carrito"))


def _check_stock_preflight(
    conn, items: list, fd: str, fh: str, faltan: list
) -> None:
    """Pre-chequeo READ-ONLY de disponibilidad (sin lock FOR UPDATE).

    Es un estimado: el gate definitivo es create_pedido_retry. El resultado puede
    dar 'stock OK' y que el gate falle si alguien reservó mientras tanto (race
    condition normal de un sistema de reservas concurrente).
    """
    disp = calcular_disponibilidad(conn, fd, fh)
    sin_stock = [it for it in items if disp.get(str(it.equipo_id), 0) < it.cantidad]
    if sin_stock:
        faltan.append(_falta(
            "stock",
            "Algunos equipos no tienen disponibilidad para las fechas seleccionadas. "
            "Revisá tu carrito.",
            "/carrito",
        ))


def _check_precio(conn, items: list, faltan: list) -> None:
    """Verifica que todos los ítems tengan precio visible en el catálogo."""
    try:
        precios_catalogo_para_reserva(conn, items)
    except HTTPException:
        faltan.append(_falta(
            "precio",
            "Uno o más equipos de tu carrito no tienen precio asignado. "
            "Actualizá tu carrito.",
            "/carrito",
        ))


def _check_contacto(conn, cliente_id: int, faltan: list) -> None:
    """Verifica que haya un email de contacto para enviar la confirmación."""
    if not email_comunicacion(conn, cliente_id):
        faltan.append(_falta(
            "contacto",
            "No tenemos un email de contacto para tu cuenta. "
            "Verificá tu identidad para completar tus datos.",
            "/cliente/identidad",
        ))


def _check_tyc(conn, cliente_id: int, faltan: list) -> None:
    if not ya_acepto(conn, cliente_id, TYC_VERSION_ACTUAL):
        faltan.append(_falta(
            "tyc",
            f"Aceptá los Términos y Condiciones (versión {TYC_VERSION_ACTUAL}) "
            "para continuar.",
            "aceptar_tyc",
        ))


def _check_firma(firma_ok: bool, faltan: list) -> None:
    if not firma_ok:
        faltan.append(_falta(
            "firma",
            "Confirmá el pedido con tu Face ID, huella o clave de pantalla.",
            "firmar",
        ))


# ── Checks cableado-apagado ──────────────────────────────────────────────────
# Siempre retornan OK. Activar descomentando la lógica y el falta correspondiente.


def _check_bloqueo(conn, cliente_id: int, faltan: list) -> None:
    """Bloqueo por administrador. Cableado-apagado hasta implementar #1125."""
    # TODO (#1125): activar cuando se agregue la columna `bloqueado` a `clientes`:
    # row = conn.execute("SELECT bloqueado FROM clientes WHERE id=%s", (cliente_id,)).fetchone()
    # if row and row["bloqueado"]:
    #     faltan.append(_falta("bloqueo", "Tu cuenta no puede hacer pedidos en este momento."))


def _check_antelacion(conn, fd: str, hora_desde, faltan: list) -> None:
    """Lead-time: el cliente no puede reservar con menos de X horas de antelación
    (#1126). X se administra desde el back-office (`antelacion_minima_horas`,
    default 0 = apagado). Usa fecha + hora del carrito para precisión horaria; el
    predicado `antelacion_insuficiente` es la fuente única (lo comparte el backstop
    de creación). Es regla solo-cliente: el portero nunca corre con es_admin."""
    inicio = inicio_desde_fecha_hora(fd, hora_desde)
    horas = antelacion_insuficiente(conn, inicio)
    if horas:
        faltan.append(_falta(
            "antelacion",
            f"Tu retiro es en menos de {horas} h. Por la antelación mínima no podemos "
            "confirmar el pedido online — escribinos para coordinar una urgencia.",
        ))
