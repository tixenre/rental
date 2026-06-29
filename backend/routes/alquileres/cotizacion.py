"""Cotización canónica del carrito (#501 — extraído del god-module `routes/alquileres.py`).

Fuente única del total del carrito: el front manda solo `items` (equipo_id +
cantidad) y fechas; el backend pone los precios (de `equipos`), el perfil/descuento
del cliente y devuelve el desglose de `services.precios.calcular_total`. Registra su
ruta sobre el router compartido del paquete `routes.alquileres`.
"""
from typing import Optional

from fastapi import Request
from pydantic import BaseModel

from database import get_db, to_datetime
from rate_limit import limiter
from auth.guards import is_admin_email
from auth.session import get_session
from services.precios import (
    bruto_linea,
    calcular_total,
    jornadas_periodo,
    precio_jornada_efectivo,
)
from routes.alquileres.core import router, _get_descuento_jornadas


class CotizarItem(BaseModel):
    # equipo_id None = línea personalizada (#805): su precio y modo de cobro
    # vienen del front (el admin la edita libre); no se busca en `equipos`.
    equipo_id: Optional[int] = None
    cantidad: int
    precio_jornada: Optional[int] = None
    cobro_modo: Optional[str] = None


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
    with get_db() as conn:
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
            # Línea personalizada (#805): no es del catálogo → su precio y modo de
            # cobro los pone el front (el admin la edita libre, igual que ya confía
            # el precio editable por línea en PUT /items). No reserva stock.
            if it.equipo_id is None:
                items_para_total.append({
                    "equipo_id": None,
                    "cantidad": it.cantidad,
                    "precio_jornada": int(it.precio_jornada or 0),
                    "cobro_modo": it.cobro_modo or "jornada",
                })
                continue
            # Precio efectivo por jornada (combo → derivado de componentes C3 #635;
            # kit/simple → su precio propio), resuelto en la fuente única.
            precio = precio_jornada_efectivo(conn, it.equipo_id)
            if precio is None:
                continue
            items_para_total.append({
                "equipo_id": it.equipo_id,
                "cantidad": it.cantidad,
                "precio_jornada": precio,
                "cobro_modo": "jornada",
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
                    "SELECT perfil_impuestos, descuento FROM clientes WHERE id=%s",
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

        # Desglose POR LÍNEA para que el front MUESTRE (no calcule) el detalle por
        # equipo: `subtotal_por_jornada` (siempre, el "$X/día" del ítem) + `bruto`/`neto`
        # del período (cuando hay fechas). El neto por línea reparte el descuento ganado
        # con el mismo redondeo por línea que usaba el front; la suma puede diferir del
        # neto total por ±1 peso → el TOTAL autoritativo es `neto` (top-level), las líneas
        # son detalle de display. `equipo_id` None = línea personalizada (#805).
        pct_aplicado = desglose["descuento_pct"]
        lineas = []
        for it in items_para_total:
            bruto = bruto_linea(it, jornadas)
            dto = int(round(bruto * pct_aplicado / 100))
            lineas.append({
                "equipo_id": it["equipo_id"],
                "cantidad": it["cantidad"],
                "precio_jornada": it["precio_jornada"],
                "subtotal_por_jornada": it["precio_jornada"] * it["cantidad"],
                "bruto": bruto,
                "neto": bruto - dto,
            })

        return {
            "jornadas": jornadas,
            "subtotal_por_jornada": int(subtotal_por_jornada),
            "descuento_origen": descuento_origen,
            "lineas": lineas,
            **desglose,
        }
