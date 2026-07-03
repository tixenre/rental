"""arca_fe.comprobante — lógica fiscal pura (testeable sin red).

Reglas de tipo de comprobante, cálculo de importes y armado del payload FECAESolicitar.
Sin estado, sin IO, sin imports de backend.*

Alcance actual (explícito, no asumido): solo emisor RESPONSABLE_INSCRIPTO o
MONOTRIBUTO (Factura A/B/C — sin Factura M ni E); UNA sola alícuota de IVA por
comprobante (`ComprobanteRequest.alicuota`, no un array — WSFEv1 soporta
múltiples `AlicIva` por comprobante, este motor no); moneda/cotización
paramétricas (`moneda`/`cotizacion`) pero sin tabla de validación de códigos.
Un consumidor con esas necesidades extiende este módulo — no las asuma cubiertas.
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

_EMISOR_CONDICIONES_VALIDAS = (CondicionIva.RESPONSABLE_INSCRIPTO, CondicionIva.MONOTRIBUTO)


def tipo_comprobante(req: ComprobanteRequest) -> CbteTipo:
    """Determina el tipo de comprobante a partir del emisor y el receptor.

    Emisor Monotributo → C (o NC C).
    Emisor RI + receptor RI → A (o NC A).
    Emisor RI + receptor no-RI → B (o NC B).

    Levanta ValueError si `emisor.condicion_iva` no es RESPONSABLE_INSCRIPTO
    ni MONOTRIBUTO (el ÚNICO par que este motor sabe facturar) — el
    dataclass `Emisor` documenta esa restricción en un comentario, pero
    Python no la fuerza en runtime; sin este chequeo, un tercer valor caía
    por el `else` y se clasificaba EN SILENCIO como si fuera RI, emitiendo
    Factura A/B con IVA discriminado para un emisor que legalmente no
    corresponde — el peor tipo de bug para un motor de facturación."""
    if req.emisor.condicion_iva not in _EMISOR_CONDICIONES_VALIDAS:
        raise ValueError(
            f"condicion_iva del emisor '{req.emisor.condicion_iva.name}' no soportada: "
            f"este motor solo factura como RESPONSABLE_INSCRIPTO o MONOTRIBUTO."
        )
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


def _validar_fechas_servicio(req: ComprobanteRequest) -> None:
    """AFIP EXIGE FchServDesde/FchServHasta/FchVtoPago cuando Concepto es
    SERVICIOS o PRODUCTOS_Y_SERVICIOS (manual WSFEv1) — no son opcionales
    para esos conceptos. El código las agregaba solo `if` estaban presentes,
    así que un caller que se las olvidara armaba un pedido incompleto que
    recién fallaba al pegarle a AFIP (round-trip + ArcaBusinessError). Fail
    fast acá: mismo motivo, sin el viaje de red."""
    if req.concepto not in (Concepto.SERVICIOS, Concepto.PRODUCTOS_Y_SERVICIOS):
        return
    faltantes = [
        nombre
        for nombre, valor in (
            ("fecha_serv_desde", req.fecha_serv_desde),
            ("fecha_serv_hasta", req.fecha_serv_hasta),
            ("fecha_vto_pago", req.fecha_vto_pago),
        )
        if valor is None
    ]
    if faltantes:
        raise ValueError(
            f"Concepto {req.concepto.name} exige {', '.join(faltantes)} — "
            f"AFIP los rechaza si faltan (no son opcionales para este concepto)."
        )


def armar_fecae(req: ComprobanteRequest, numero: int) -> dict:
    """Arma el dict FECAEReq para FECAESolicitar (sin el nodo Auth).

    Retorna:
        {
          "FeCabReq": {"CantReg": 1, "PtoVta": ..., "CbteTipo": ...},
          "FeDetReq": {"FECAEDetRequest": [det]},
        }

    Levanta ValueError (fail fast, sin red) si el request es incompleto para
    su Concepto (ver `_validar_fechas_servicio`) o si `emisor.condicion_iva`
    no es facturable (ver `tipo_comprobante`)."""
    _validar_fechas_servicio(req)
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
        # ImpTotConc/ImpOpEx/ImpTrib fijos en 0: este motor no modela conceptos
        # no gravados, operaciones exentas del propio comprobante, ni otros
        # tributos (percepciones IIBB, etc.) — limitación real y explícita,
        # no un default silencioso. Un consumidor que los necesite tiene que
        # extender `ComprobanteRequest`/`armar_fecae`, no asumir que ya están.
        "ImpTotConc": "0.00",
        "ImpNeto": _fmt(neto),
        "ImpOpEx": "0.00",
        "ImpIVA": _fmt(iva),
        "ImpTrib": "0.00",
        "MonId": req.moneda,
        "MonCotiz": float(req.cotizacion),
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
