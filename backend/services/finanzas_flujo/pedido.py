"""El desglose de plata de un pedido — cuánto sale, línea por línea.

OWNA: nada nuevo, delega en `services.precios.calcular_total`/`jornadas_periodo`.
Fixea el bug de `cobro_modo` (auditoría cruzada de plata, 2026-07-02): antes,
`routes/alquileres/core.py::_enriquecer_pedido_con_total` armaba los ítems para
`calcular_total` SIN pasarle `cobro_modo` — una línea 'fijo' (ej. flete, #805)
se multiplicaba igual por jornadas al mostrar/facturar, aunque `bruto_linea` ya
sabía manejarlo bien. Ahora hay un solo punto que arma el desglose para los 6
consumidores reales: detalle admin, PDF/mail, portal cliente, y el motor de
facturación (`services/facturacion/engine.py`).
"""
from database import to_datetime
from services.precios import calcular_total, jornadas_periodo


def desglose_de_pedido(conn, pedido: dict) -> dict:
    """Agrega al pedido el desglose canónico del total + IVA derivado (mutación
    in-place; retorna el mismo dict por conveniencia de los callers).

    Fuente de verdad: `services.precios.calcular_total`. `monto_total`
    persistido sigue siendo NETO (con descuento, sin IVA) — acá se computa
    el desglose para mostrar/facturar, nunca se sobreescribe esa columna.

    Jerarquía de descuento (Fase C-1, #1219): `pedido["descuento_pct"]` es el
    override MANUAL (0 = sin override); `pedido["descuento_cliente_pct"]` es el
    SNAPSHOT del descuento del cliente al último recálculo (persistido por
    `_recalcular_total_pedido`/`_apply_pedido_items`, NO se re-consulta en vivo
    acá) — leerlo en vivo divergiría de `monto_total` ya persistido para un
    pedido confirmado cuyo cliente cambió de descuento después (bug clase
    #405). `perfil_impuestos` sí se resuelve en vivo si falta (comportamiento
    preexistente, sin cambios). Expone `descuento_efectivo_pct`/
    `descuento_origen` (el % y la fuente que GANARON) para que los consumidores
    de display (mail/PDF) dejen de leer el campo crudo `descuento_pct` como si
    fuera el % aplicado — misma ambigüedad que causó el bug #1209 en otro lugar.

    Override en % o en $ fijo (Fase C-2, #1219): `pedido["descuento_manual_tipo"]`
    ("pct"/"monto") + `pedido["descuento_manual_monto"]` son columnas directas
    del pedido (no un snapshot aparte — el override ES el valor persistido,
    igual que `descuento_pct`), leídas tal cual están en la fila.

    Combos no acumulables (Fase C-3, #1219): `es_combo` por línea sale de
    `equipo_tipo` EN VIVO (join con `equipos.tipo` al armar `pedido["items"]`,
    ver `_get_alquiler_items`/`_batch_get_alquiler_items`), NO de un snapshot
    por línea. Limitación aceptada (hallazgo del supervisor, PR #1220): si un
    equipo se reclasifica de `combo` a `simple` (o viceversa) DESPUÉS de que
    un pedido confirmado lo usó, el desglose de ESE pedido puede moverse. Muy
    baja probabilidad (reclasificar el tipo de un equipo es una acción manual
    rara del catálogo, no un flujo de uso normal) — se acepta sin snapshot
    dedicado; si algún día se materializa, agregar `es_combo` congelado a
    `alquiler_items` sería la solución, mismo patrón que `descuento_cliente_pct`.
    """
    perfil = pedido.get("cliente_perfil_impuestos")
    if perfil is None and pedido.get("cliente_id"):
        # #1240: si el pedido eligió una productora o un perfil personal alternativo
        # (`productora_id`/`perfil_fiscal_id`, columnas reales de `alquileres`), ese
        # target gana sobre el perfil default de `clientes` — mismo criterio que
        # `services.pedidos_enriquecimiento._resolver_datos_fiscales_pedido`.
        from services.pedidos_enriquecimiento import _resolver_datos_fiscales_pedido

        c = _resolver_datos_fiscales_pedido(
            conn,
            pedido["cliente_id"],
            pedido.get("perfil_fiscal_id"),
            pedido.get("productora_id"),
        )
        if c:
            perfil = c.get("perfil_impuestos")
            pedido["cliente_perfil_impuestos"] = perfil

    descuento_cliente_pct = pedido.get("descuento_cliente_pct") or 0.0

    d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
    d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
    jornadas = jornadas_periodo(d0, d1)

    items_para_total = [
        {
            "equipo_id": it["equipo_id"],
            "cantidad": it["cantidad"],
            "precio_jornada": it["precio_jornada"],
            "cobro_modo": it.get("cobro_modo") or "jornada",
            # Fase C-3 (#1219): no acumula el descuento global — ya trae el
            # suyo propio (`kit_componentes.descuento_pct`) horneado en el precio.
            "es_combo": it.get("equipo_tipo") == "combo",
        }
        for it in pedido.get("items", [])
    ]

    descuento_jornadas_pct = pedido.get("descuento_jornadas_pct") or 0
    descuento_manual_pct = pedido.get("descuento_pct") or 0
    descuento_manual_tipo = pedido.get("descuento_manual_tipo") or "pct"
    descuento_manual_monto = pedido.get("descuento_manual_monto") or 0
    desglose = calcular_total(
        items=items_para_total,
        jornadas=jornadas,
        descuento_cliente_pct=descuento_cliente_pct,
        descuento_jornadas_pct=descuento_jornadas_pct,
        descuento_manual_pct=descuento_manual_pct,
        descuento_manual_tipo=descuento_manual_tipo,
        descuento_manual_monto=descuento_manual_monto,
        perfil_impuestos=perfil,
    )

    pedido["bruto"] = desglose["bruto"]
    pedido["descuento_monto"] = desglose["descuento_monto"]
    pedido["monto_neto"] = desglose["neto"]
    pedido["iva_pct"] = desglose["iva_pct"]
    pedido["iva_monto"] = desglose["iva_monto"]
    pedido["total_con_iva"] = desglose["total_final"]
    pedido["con_iva"] = desglose["con_iva"]
    pedido["cantidad_jornadas"] = jornadas
    pedido["descuento_efectivo_pct"] = desglose["descuento_pct"]
    from descuentos.queries.decision import resolver_origen_pedido_monto
    pedido["descuento_origen"] = resolver_origen_pedido_monto(
        descuento_manual_tipo, descuento_manual_pct, descuento_manual_monto,
        descuento_cliente_pct, descuento_jornadas_pct,
    )
    return pedido
