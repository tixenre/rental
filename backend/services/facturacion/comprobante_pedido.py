"""services.facturacion.comprobante_pedido — mapea un pedido Rambla a ComprobanteRequest.

Punto único: arca_fe.ComprobanteRequest se construye acá, no en el engine ni en el route.
La plata viene de `services.precios.calcular_total` (ya guardada en `alquileres.monto_total`);
este módulo solo la lee y transforma — NO recalcula (regla "el backend no recalcula").
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from arca_fe import (
    CbteTipo,
    Concepto,
    CondicionIva,
    DocTipo,
    Emisor,
    IVA_21,
    ComprobanteRequest,
    Receptor,
    CbteAsoc,
)
from services.facturacion.emisores import emisor_para


# Condición IVA por perfil_impuestos del receptor (fuente única)
_PERFIL_A_COND_IVA: dict[str, CondicionIva] = {
    "responsable_inscripto": CondicionIva.RESPONSABLE_INSCRIPTO,
    "exento": CondicionIva.EXENTO,
    "monotributo": CondicionIva.MONOTRIBUTO,
    "consumidor_final": CondicionIva.CONSUMIDOR_FINAL,
}


def _condicion_iva_receptor(perfil: Optional[str]) -> CondicionIva:
    return _PERFIL_A_COND_IVA.get((perfil or "").strip().lower(), CondicionIva.CONSUMIDOR_FINAL)


def _doc_tipo_y_nro(pedido: dict) -> tuple[DocTipo, int]:
    """Decide DocTipo / doc_nro a partir de los datos del cliente en el pedido.

    Fallback: si no hay CUIT pero el pedido es RI → degradar a CF con DNI.
    """
    cuit = (pedido.get("cliente_cuit") or "").strip().replace("-", "").replace(" ", "")
    dni = (pedido.get("cliente_dni") or "").strip()
    perfil = (pedido.get("cliente_perfil_impuestos") or "").strip().lower()

    if perfil == "responsable_inscripto" and cuit and cuit.isdigit():
        return DocTipo.CUIT, int(cuit)
    if cuit and cuit.isdigit() and len(cuit) == 11:
        return DocTipo.CUIT, int(cuit)
    if dni and dni.isdigit():
        return DocTipo.DNI, int(dni)
    return DocTipo.CONSUMIDOR_FINAL, 0


def construir_comprobante(
    pedido: dict,
    emisor_obj: Emisor,
    emisor_cond: CondicionIva,
    *,
    fecha: date,
    es_nota_credito: bool = False,
    cbtes_asoc: tuple[CbteAsoc, ...] = (),
) -> ComprobanteRequest:
    """Arma un ComprobanteRequest desde los datos del pedido enriquecido fiscalmente.

    `pedido` debe haber pasado por:
    - `_enriquecer_pedido_con_cliente_fiscal` (perfil/cuit)
    - `_enriquecer_pedido_con_total` (neto/iva ya calculados)

    La plata que se usa:
    - Para RI (Factura A): `neto = pedido['monto_total']`, alicuota=IVA_21 (21%)
    - Para Mono/CF (Factura C): `neto = total_con_iva` (incluye IVA si lo hay; no se discrimina)
    """
    perfil_receptor = (pedido.get("cliente_perfil_impuestos") or "").strip().lower()
    cond_receptor = _condicion_iva_receptor(perfil_receptor)
    doc_tipo, doc_nro = _doc_tipo_y_nro(pedido)

    # Fallback: RI sin CUIT → degradar a Factura B/C (no puede emitir A)
    if (
        perfil_receptor == "responsable_inscripto"
        and doc_tipo != DocTipo.CUIT
    ):
        cond_receptor = CondicionIva.CONSUMIDOR_FINAL

    receptor = Receptor(
        doc_tipo=doc_tipo,
        doc_nro=doc_nro,
        condicion_iva=cond_receptor,
    )

    # --- importes ---
    # `monto_total` es SIEMPRE el neto (sin IVA), persistido por calcular_total.
    neto_int = int(pedido.get("monto_total") or 0)
    iva_int = int(pedido.get("iva_monto") or 0)

    # Emisor Monotributo → no discrimina IVA; el total va como "neto"
    if emisor_cond == CondicionIva.MONOTRIBUTO:
        importe_neto = Decimal(neto_int + iva_int)
        alicuota = None
    else:
        importe_neto = Decimal(neto_int)
        alicuota = IVA_21 if iva_int > 0 else None

    # --- fechas de servicio ---
    # Concepto = SERVICIOS (2) → requiere FchServDesde/Hasta/VtoPago
    fecha_desde = _parse_fecha(pedido.get("fecha_desde"))
    fecha_hasta = _parse_fecha(pedido.get("fecha_hasta"))
    fecha_vto_pago = fecha_hasta  # vencimiento = fin del servicio

    return ComprobanteRequest(
        emisor=emisor_obj,
        receptor=receptor,
        concepto=Concepto.SERVICIOS,
        importe_neto=importe_neto,
        alicuota=alicuota,
        fecha=fecha,
        fecha_serv_desde=fecha_desde,
        fecha_serv_hasta=fecha_hasta,
        fecha_vto_pago=fecha_vto_pago,
        es_nota_credito=es_nota_credito,
        cbtes_asoc=cbtes_asoc,
    )


def _parse_fecha(s) -> Optional[date]:
    if not s:
        return None
    if isinstance(s, date):
        return s
    s = str(s)[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None
