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
from database import row_to_dict, to_datetime
from services.precios import calcular_total, jornadas_periodo


def desglose_de_pedido(conn, pedido: dict) -> dict:
    """Agrega al pedido el desglose canónico del total + IVA derivado (mutación
    in-place; retorna el mismo dict por conveniencia de los callers).

    Fuente de verdad: `services.precios.calcular_total`. `monto_total`
    persistido sigue siendo NETO (con descuento, sin IVA) — acá se computa
    el desglose para mostrar/facturar, nunca se sobreescribe esa columna.
    """
    perfil = pedido.get("cliente_perfil_impuestos")
    if perfil is None and pedido.get("cliente_id"):
        row = conn.execute(
            "SELECT perfil_impuestos FROM clientes WHERE id = %s",
            (pedido["cliente_id"],),
        ).fetchone()
        if row:
            perfil = row_to_dict(row).get("perfil_impuestos")
            pedido["cliente_perfil_impuestos"] = perfil

    d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
    d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
    jornadas = jornadas_periodo(d0, d1)

    items_para_total = [
        {
            "equipo_id": it["equipo_id"],
            "cantidad": it["cantidad"],
            "precio_jornada": it["precio_jornada"],
            "cobro_modo": it.get("cobro_modo") or "jornada",
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

    pedido["bruto"] = desglose["bruto"]
    pedido["descuento_monto"] = desglose["descuento_monto"]
    pedido["monto_neto"] = desglose["neto"]
    pedido["iva_pct"] = desglose["iva_pct"]
    pedido["iva_monto"] = desglose["iva_monto"]
    pedido["total_con_iva"] = desglose["total_final"]
    pedido["con_iva"] = desglose["con_iva"]
    pedido["cantidad_jornadas"] = jornadas
    return pedido
