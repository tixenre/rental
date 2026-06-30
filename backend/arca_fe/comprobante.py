"""arca_fe.comprobante — lógica fiscal pura (testeable sin red).

Reglas de tipo de comprobante, cálculo de importes y armado del payload FECAESolicitar.
Sin estado, sin IO, sin imports de backend.*
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .modelos import (
    CbteAsoc,
    CbteTipo,
    ComprobanteRequest,
    Concepto,
    CondicionIva,
)

_DOS = Decimal("0.01")


# ---------------------------------------------------------------------------
# Tipo de comprobante
# ---------------------------------------------------------------------------

def tipo_comprobante(req: ComprobanteRequest) -> CbteTipo:
    """Determina el tipo de comprobante a partir del emisor y el receptor.

    Emisor Monotributo → C (o NC C).
    Emisor RI + receptor RI → A (o NC A).
    Emisor RI + receptor no-RI → B (o NC B).
    """
    mono = req.emisor.condicion_iva == CondicionIva.MONOTRIBUTO
    nc = req.es_nota_credito
    if mono:
        return CbteTipo.NOTA_CREDITO_C if nc else CbteTipo.FACTURA_C
    # emisor RI
    if req.receptor.condicion_iva == CondicionIva.RESPONSABLE_INSCRIPTO:
        return CbteTipo.NOTA_CREDITO_A if nc else CbteTipo.FACTURA_A
    # emisor RI + receptor no-RI
    return CbteTipo.NOTA_CREDITO_B if nc else CbteTipo.FACTURA_B


# ---------------------------------------------------------------------------
# Cálculo de importes
# ---------------------------------------------------------------------------

def calcular_importes(req: ComprobanteRequest) -> dict[str, Decimal]:
    """Devuelve {neto, iva, total} como Decimal con 2 decimales, ROUND_HALF_UP.

    Para Factura C (alicuota=None): neto=importe_neto, iva=0, total=neto.
    Para Factura A/B (alicuota no None): iva = neto * pct / 100 redondeado.
    Garantía: total == neto + iva al centavo.
    """
    neto = req.importe_neto.quantize(_DOS, rounding=ROUND_HALF_UP)
    if req.alicuota is not None:
        iva = (neto * req.alicuota.pct / Decimal("100")).quantize(_DOS, rounding=ROUND_HALF_UP)
    else:
        iva = Decimal("0.00")
    total = neto + iva
    assert total == neto + iva  # Decimal aritmético exacto; guard de regresión
    return {"neto": neto, "iva": iva, "total": total}


# ---------------------------------------------------------------------------
# Armado del payload FECAESolicitar
# ---------------------------------------------------------------------------

def _fmt(d: Decimal) -> str:
    return str(d.quantize(_DOS, rounding=ROUND_HALF_UP))


def _cbte_asoc_dict(a: CbteAsoc) -> dict:
    d: dict = {
        "Tipo": int(a.tipo),
        "PtoVta": a.punto_venta,
        "Nro": a.numero,
    }
    if a.cuit is not None:
        d["Cuit"] = a.cuit
    if a.fecha is not None:
        d["CbteFch"] = a.fecha.strftime("%Y%m%d")
    return d


def armar_fecae(req: ComprobanteRequest, numero: int) -> dict:
    """Arma el dict FECAEReq para FECAESolicitar (sin el nodo Auth).

    Retorna:
        {
          "FeCabReq": {"CantReg": 1, "PtoVta": ..., "CbteTipo": ...},
          "FeDetReq": {"FECAEDetRequest": [det]},
        }
    """
    cbte_tipo = tipo_comprobante(req)
    imp = calcular_importes(req)
    neto, iva, total = imp["neto"], imp["iva"], imp["total"]

    det: dict = {
        "Concepto": int(req.concepto),
        "DocTipo": int(req.receptor.doc_tipo),
        "DocNro": req.receptor.doc_nro,
        "CbteDesde": numero,
        "CbteHasta": numero,
        "CbteFch": req.fecha.strftime("%Y%m%d"),
        "ImpTotal": _fmt(total),
        "ImpTotConc": "0.00",   # no gravado
        "ImpNeto": _fmt(neto),
        "ImpOpEx": "0.00",      # operaciones exentas
        "ImpIVA": _fmt(iva),
        "ImpTrib": "0.00",      # otros tributos
        "MonId": "PES",
        "MonCotiz": 1,
        "CondicionIVAReceptorId": int(req.receptor.condicion_iva),  # RG5616 obligatorio
    }

    # Servicios y Productos+Servicios exigen fechas de período
    if req.concepto in (Concepto.SERVICIOS, Concepto.PRODUCTOS_Y_SERVICIOS):
        if req.fecha_serv_desde:
            det["FchServDesde"] = req.fecha_serv_desde.strftime("%Y%m%d")
        if req.fecha_serv_hasta:
            det["FchServHasta"] = req.fecha_serv_hasta.strftime("%Y%m%d")
        if req.fecha_vto_pago:
            det["FchVtoPago"] = req.fecha_vto_pago.strftime("%Y%m%d")

    # Alícuota IVA solo en facturas con IVA discriminado (A/B, no C)
    if req.alicuota is not None and cbte_tipo not in (CbteTipo.FACTURA_C, CbteTipo.NOTA_CREDITO_C):
        det["Iva"] = {
            "AlicIva": [{
                "Id": req.alicuota.id,
                "BaseImp": _fmt(neto),
                "Importe": _fmt(iva),
            }]
        }

    # Comprobantes asociados (notas de crédito referencian la factura origen)
    if req.cbtes_asoc:
        det["CbtesAsoc"] = {
            "CbteAsoc": [_cbte_asoc_dict(a) for a in req.cbtes_asoc]
        }

    return {
        "FeCabReq": {
            "CantReg": 1,
            "PtoVta": req.emisor.punto_venta,
            "CbteTipo": int(cbte_tipo),
        },
        "FeDetReq": {
            "FECAEDetRequest": [det]
        },
    }
