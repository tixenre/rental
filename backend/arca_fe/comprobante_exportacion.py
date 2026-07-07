"""arca_fe.comprobante_exportacion — lógica fiscal pura de la Factura de Exportación (WSFEXv1).

Paralelo a `comprobante.py` (WSFEv1) — sin estado, sin IO, sin imports de `backend.*`. Arma el
payload de `FEXAuthorize` a partir de un `ComprobanteExportacionRequest`.

**Alcance NO verificado contra el WSDL real de WSFEXv1** (a diferencia de `comprobante.py`, que sí
está confirmado contra el WSDL/manual oficial de WSFEv1) — los nombres de nodo de abajo (`Cmp`,
`Permisos`, `Cbtes_asoc`, `Moneda_id`/`Moneda_ctz`, `Idioma_cbte`) son la mejor referencia disponible
sin acceso al WSDL de homologación, pero se confirman/ajustan contra AFIP real antes de que esta
fase se considere cerrada para producción (ver `wsfex.py`, fase 3, para el cliente SOAP que
efectivamente llama a AFIP)."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .modelos import CondicionIva
from .modelos_exportacion import (
    CbteAsocExportacion,
    CbteTipoExportacion,
    ComprobanteExportacionRequest,
)

_DOS = Decimal("0.01")
_EMISOR_CONDICIONES_VALIDAS = (CondicionIva.RESPONSABLE_INSCRIPTO, CondicionIva.MONOTRIBUTO)


def _fmt(d: Decimal) -> str:
    return str(d.quantize(_DOS, rounding=ROUND_HALF_UP))


def _validar_estructura_exportacion(req: ComprobanteExportacionRequest) -> None:
    """Valida lo estructural que `ComprobanteExportacionRequest.__post_init__` no cubre (mismo
    criterio de `comprobante._validar_estructura`: la llama tanto el `__post_init__` del dataclass
    COMO `armar_fexauthorize`, repetir es barato, no asume que nadie construyó el objeto sin pasar
    por ahí)."""
    if req.emisor.condicion_iva not in _EMISOR_CONDICIONES_VALIDAS:
        raise ValueError(
            f"condicion_iva del emisor '{req.emisor.condicion_iva.name}' no soportada: "
            f"este motor solo factura exportación como RESPONSABLE_INSCRIPTO o MONOTRIBUTO."
        )
    if not (1 <= req.emisor.punto_venta <= 9999):
        raise ValueError(
            f"emisor.punto_venta fuera de rango (1-9999): {req.emisor.punto_venta}"
        )


def tipo_comprobante_exportacion(req: ComprobanteExportacionRequest) -> CbteTipoExportacion:
    """Determina el tipo de comprobante de exportación — a diferencia del doméstico
    (`comprobante.tipo_comprobante`, que ramifica por condición IVA de emisor/receptor), acá no hay
    letra A/B/C: siempre es "E". `req.forzar_cbte_tipo` (ej. para pedir Nota de Débito explícita)
    reemplaza la selección automática (Factura E por default, Nota de Crédito E si
    `es_nota_credito`)."""
    if req.forzar_cbte_tipo is not None:
        return req.forzar_cbte_tipo
    return CbteTipoExportacion.NOTA_CREDITO_E if req.es_nota_credito else CbteTipoExportacion.FACTURA_E


def _cbte_asoc_exportacion_dict(a: CbteAsocExportacion) -> dict:
    d: dict = {
        "Cbte_tipo": int(a.tipo),
        "Cbte_punto_vta": a.punto_venta,
        "Cbte_nro": a.numero,
    }
    if a.cuit is not None:
        d["Cuit"] = a.cuit
    if a.fecha is not None:
        d["Cbte_fecha"] = a.fecha.strftime("%Y%m%d")
    return d


def armar_fexauthorize(req: ComprobanteExportacionRequest, numero: int) -> dict:
    """Arma el dict del payload de `FEXAuthorize` (sin el nodo `Auth`) para UN solo comprobante de
    exportación.

    La exportación está exenta de IVA — no hay desglose de alícuotas ni de tributos como en el
    comprobante doméstico; `req.importe_neto` es el importe TOTAL de la operación.

    Retorna un dict con la forma tentativa (a confirmar contra el WSDL real, ver docstring del
    módulo):
        {"Cmp": {...}}

    Levanta `ValueError` (fail-fast, sin red) si `emisor.condicion_iva`/`punto_venta` no son
    válidos para facturar (ver `_validar_estructura_exportacion`) — en la práctica esto ya corrió
    una vez en `ComprobanteExportacionRequest.__post_init__`."""
    _validar_estructura_exportacion(req)
    cbte_tipo = tipo_comprobante_exportacion(req)

    cmp: dict = {
        "Cbte_tipo": int(cbte_tipo),
        "Punto_vta": req.emisor.punto_venta,
        "Cbte_nro": numero,
        "Fecha_cbte": req.fecha.strftime("%Y%m%d"),
        "Permiso_existente": "S" if req.exportacion.permiso_existente else "N",
        "Pais_dst_cmp": req.receptor.pais_destino_id,
        "Nombre_cliente": req.receptor.razon_social,
        "Domicilio_cliente": req.receptor.domicilio,
        "Id_impositivo": req.receptor.id_impositivo,
        "Moneda_id": req.moneda,
        "Moneda_ctz": float(req.cotizacion),
        "Imp_total": _fmt(req.importe_neto),
        "Idioma_cbte": req.exportacion.idioma_cbte,
        "Incoterm": req.exportacion.incoterm,
    }
    if req.exportacion.permiso_existente:
        cmp["Permisos"] = {
            "Permiso": [
                {"Id_permiso": req.exportacion.permiso_embarque, "Dst_merc": req.receptor.pais_destino_id}
            ]
        }
    if req.cbtes_asoc:
        cmp["Cbtes_asoc"] = {
            "Cbte_asoc": [_cbte_asoc_exportacion_dict(a) for a in req.cbtes_asoc]
        }
    return {"Cmp": cmp}
