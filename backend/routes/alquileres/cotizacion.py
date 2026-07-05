"""Cotización canónica del carrito (#501 — extraído del god-module `routes/alquileres.py`).

Fuente única del total del carrito: el front manda solo `items` (equipo_id +
cantidad) y fechas; el backend pone los precios (de `equipos`), el perfil/descuento
del cliente y devuelve el desglose de `services.precios.calcular_total`. Registra su
ruta sobre el router compartido del paquete `routes.alquileres`.
"""
from typing import Optional

from fastapi import Request
from pydantic import BaseModel, field_validator

from database import get_db, to_datetime
from rate_limit import limiter
from auth.guards import is_admin_email
from auth.session import dev_bypass_enabled, get_session
from services.precios import (
    bruto_linea,
    calcular_total,
    jornadas_periodo,
    precio_jornada_efectivo,
    tipos_equipo_batch,
)
from descuentos.queries.decision import resolver_origen_pedido_monto
from descuentos.queries.jornadas import obtener_descuento_jornadas
from routes.alquileres.core import router


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
    # Override manual en % o en $ fijo (Fase C-2, #1219): mismo par que
    # `PedidoDatos` (routes/alquileres/core.py) — el builder los edita en vivo
    # para que el preview coincida con lo que se va a persistir.
    descuento_manual_tipo: Optional[str] = None
    descuento_manual_monto: Optional[float] = None
    # Fase C-4 (#1231): fuerza el override manual a ganar aunque valga 0 — el
    # builder lo edita en vivo para que el preview coincida con lo que
    # persiste `_apply_pedido_datos`/`_recalcular_total_pedido` al guardar.
    descuento_manual_activo: Optional[bool] = None
    # Solo lo honra una sesión admin: respeta el `precio_jornada` que manda cada
    # ítem de catálogo (el snapshot congelado del pedido que se está editando)
    # en vez de re-buscarlo en `equipos`. Sin esto, el editor de pedidos admin
    # mostraba un total "en vivo" con el precio de HOY del catálogo — distinto
    # al que persiste `_recalcular_total_pedido` al guardar (que sí respeta el
    # precio de línea) → dos totales del mismo pedido que podían no coincidir.
    # Ver MEMORIA 2026-06-06 "Datos del pedido: plata congelada".
    respetar_precio_item: Optional[bool] = False

    # Mismo validador que `PedidoDatos.descuento_pct` (routes/alquileres/core.py)
    # — este override vivía sin cota de rango (hallazgo de la Fase A del split
    # de descuentos/, #1184): un admin podía mandar un negativo al preview en
    # vivo sin que nada lo rechazara.
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
        # Mismo tope que `PedidoDatos` (routes/alquileres/core.py) — preview y
        # guardado no deberían divergir en qué rechazan.
        if v >= 2_147_483_647:
            raise ValueError("descuento_manual_monto demasiado alto")
        return v


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

        session = get_session(request)
        # Mismo criterio que `require_admin` (auth/guards.py): el bypass de
        # dev (ADMIN_BYPASS_AUTH=1, nunca en prod) también cuenta como admin
        # acá — si no, el preview en vivo ignora el override de descuento
        # aunque el guardado (que sí pasa por require_admin) lo haya aceptado.
        es_admin = dev_bypass_enabled() or bool(session and is_admin_email(session.get("email")))
        respetar_precio_item = es_admin and bool(data.respetar_precio_item)

        # Precios desde el backend. Equipos inexistentes/eliminados se ignoran
        # (cotización best-effort: el carrito puede tener algo que ya no está).
        # Fetch por-ítem (lookup por PK indexada): se revirtió el batch `IN (...)`
        # de #643 que devolvía precios_map vacío en prod → total $0 (regresión).
        # `tipos_equipo_batch` (solo id+tipo, query aparte) SÍ va en batch — no
        # toca el precio, resuelve `es_combo` para el descuento no-acumulable
        # (Fase C-3, #1219).
        tipos = tipos_equipo_batch(
            conn, [it.equipo_id for it in data.items if it.equipo_id is not None]
        )
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
            # Admin editando un pedido existente (`respetar_precio_item`): usa el
            # precio de línea que manda el front (el snapshot congelado del
            # pedido, editable por el admin) en vez de recotizar contra el
            # catálogo — así el total "en vivo" del editor coincide siempre con
            # el que persiste `_recalcular_total_pedido` al guardar.
            if respetar_precio_item and it.precio_jornada is not None:
                precio = int(it.precio_jornada)
            else:
                # Precio efectivo por jornada (combo → derivado de componentes
                # C3 #635; kit/simple → su precio propio), fuente única.
                precio = precio_jornada_efectivo(conn, it.equipo_id)
                if precio is None:
                    continue
            items_para_total.append({
                "equipo_id": it.equipo_id,
                "cantidad": it.cantidad,
                "precio_jornada": precio,
                "cobro_modo": "jornada",
                "es_combo": tipos.get(it.equipo_id) == "combo",
            })
        subtotal_por_jornada = sum(
            it["precio_jornada"] * it["cantidad"] for it in items_para_total
        )

        # Perfil tributario + descuento del cliente. Solo en modo firme (con
        # fechas): sin fechas es un estimado sin IVA ni descuentos.
        perfil = None
        descuento_cliente_pct = 0.0
        descuento_jornadas_pct = 0.0
        descuento_manual_pct = 0.0
        descuento_manual_tipo = "pct"
        descuento_manual_monto = 0.0
        descuento_manual_activo = False
        if tiene_fechas:
            # ¿Para qué cliente se cotiza?
            #   - Admin (back-office): SIEMPRE el cliente del pedido (`data.cliente_id`),
            #     nunca la ficha de la propia sesión. La admin-ness la da el EMAIL
            #     (`require_admin`/`is_admin_email`), no el `role` — un dueño que se
            #     logueó por el portal de cliente tiene una sesión `role="cliente"` +
            #     su propio `cliente_id` Y además es admin. Con la precedencia vieja
            #     (rama `role=="cliente"` primero) el builder cotizaba con el descuento
            #     de la ficha del PROPIO admin para TODOS los pedidos, no la del pedido
            #     → "descuento fantasma" (#1231). El camino que PERSISTE la plata
            #     (`_recalcular_total_pedido`) ya usaba el cliente del pedido, así que
            #     esto era solo el preview mintiendo, no datos corruptos.
            #   - Cliente puro (portal): su propia ficha.
            #   - Anónimo (sin sesión): sin descuento de cliente.
            target_cliente_id = None
            if es_admin:
                target_cliente_id = data.cliente_id
            elif session and session.get("role") == "cliente" and session.get("cliente_id"):
                target_cliente_id = session["cliente_id"]
            if target_cliente_id:
                c = conn.execute(
                    "SELECT perfil_impuestos, descuento FROM clientes WHERE id=%s",
                    (target_cliente_id,),
                ).fetchone()
                if c:
                    perfil = c["perfil_impuestos"]
                    descuento_cliente_pct = c["descuento"] or 0.0
            # Override MANUAL del admin (lo edita en vivo en el builder del
            # pedido) — jerarquía (Fase C-1, #1219): gana OUTRIGHT sobre
            # cliente/jornadas, ya NO reemplaza el descuento del cliente para
            # que compita por tamaño. Fase C-2 (#1219): el override puede ser
            # % (de siempre) o $ fijo, mismo campo de la UI.
            if es_admin and data.descuento_pct:
                descuento_manual_pct = data.descuento_pct
            if es_admin and data.descuento_manual_tipo:
                descuento_manual_tipo = data.descuento_manual_tipo
            if es_admin and data.descuento_manual_monto:
                descuento_manual_monto = data.descuento_manual_monto
            if es_admin:
                descuento_manual_activo = bool(data.descuento_manual_activo)
            descuento_jornadas_pct = obtener_descuento_jornadas(conn, jornadas)

        desglose = calcular_total(
            items=items_para_total,
            jornadas=jornadas,
            descuento_cliente_pct=descuento_cliente_pct,
            descuento_jornadas_pct=descuento_jornadas_pct,
            descuento_manual_pct=descuento_manual_pct,
            descuento_manual_tipo=descuento_manual_tipo,
            descuento_manual_monto=descuento_manual_monto,
            descuento_manual_activo=descuento_manual_activo,
            perfil_impuestos=perfil,
        )

        # Cuál descuento ganó (para el label del UI) — misma jerarquía que
        # decidió el pct en `calcular_total`, así nunca puede divergir.
        descuento_origen = resolver_origen_pedido_monto(
            descuento_manual_tipo, descuento_manual_pct, descuento_manual_monto,
            descuento_cliente_pct, descuento_jornadas_pct, descuento_manual_activo,
        )

        # Desglose POR LÍNEA para que el front MUESTRE (no calcule) el detalle por
        # equipo: `subtotal_por_jornada` (siempre, el "$X/día" del ítem) + `bruto`/`neto`
        # del período (cuando hay fechas). El neto por línea reparte el descuento ganado
        # con el mismo redondeo por línea que usaba el front; la suma de netos por línea
        # puede diferir del neto total por unos pesos (redondeo independiente por línea)
        # → el TOTAL autoritativo es `neto` (top-level), las líneas son detalle de display.
        # `equipo_id` None = línea personalizada (#805). Combos (`es_combo`, Fase
        # C-3 #1219) no reciben el % ganador — ya vienen con su propio descuento
        # de componente horneado en `precio_jornada`.
        pct_aplicado = desglose["descuento_pct"]
        lineas = []
        for it in items_para_total:
            bruto = bruto_linea(it, jornadas)
            dto = 0 if it.get("es_combo") else int(round(bruto * pct_aplicado / 100))
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
