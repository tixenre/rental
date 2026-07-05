"""arca_fe.modelos_exportacion — data plana de la Factura de Exportación (WSFEXv1). PORTABLE.

WSFEXv1 (RG 2758, operación `FEXAuthorize`) es un webservice de AFIP/ARCA **distinto** de WSFEv1
(el que ya cubre `modelos.py`/`wsfe.py`) — modelo de datos propio: receptor SIN CUIT/DocTipo
argentino (comprador del exterior, identificado por país destino), permiso de embarque, Incoterm,
idioma del comprobante. Por eso vive en un módulo aparte en vez de extender `CbteTipo`/
`ComprobanteRequest` de `modelos.py` (ver `modelos.py::CbteTipo` — deja documentado por qué no está
ahí): agregar 19/20/21 al enum doméstico arriesgaría que caigan sin querer en una rama de
`tipo_comprobante`/`letra_comprobante` que asume A/B/C/M/FCE.

Mismo criterio de validación fail-fast que `modelos.py`: normalizar lo cosmético, rechazar con
`ValueError` explícito lo realmente inválido, nunca adivinar. Los campos que dependen de un catálogo
VIVO de AFIP (país destino, Incoterm, moneda) solo se validan en FORMATO acá — la vigencia se
consulta con `WsfexClient.param_*` en vivo (`wsfex.py`, fase 3).

Reusa de `modelos.py` lo que es genuinamente compartido: `Emisor` (mismo CUIT/punto de venta/
condición IVA — exportar no cambia quién factura), `Concepto` (productos/servicios), `CaeResult`
(la forma de `Resultado`/`CAE`/`CAEFchVto`/`Cbte` de WSFEXv1 es estructuralmente la misma que
WSFEv1 — reusar en vez de duplicar; si en la fase 3, al integrar contra el WSDL real, resulta que
difiere, se separa recién ahí)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import Optional

from .modelos import CaeResult, Concepto, Emisor, _validar_y_normalizar_cuit


class CbteTipoExportacion(IntEnum):
    """Tipo de comprobante de exportación (tabla AFIP `FEXGetPARAM_Cmp`/`FEParamGetTiposCbte`,
    valores 19/20/21) — enum PROPIO, deliberadamente separado de `modelos.CbteTipo` (ver docstring
    del módulo)."""

    FACTURA_E = 19
    NOTA_DEBITO_E = 20
    NOTA_CREDITO_E = 21


def es_nota_credito_exportacion(cbte_tipo: CbteTipoExportacion) -> bool:
    """`True` si `cbte_tipo` es la nota de crédito de exportación (21)."""
    return CbteTipoExportacion(cbte_tipo) == CbteTipoExportacion.NOTA_CREDITO_E


@dataclass(frozen=True)
class ReceptorExterior:
    """El comprador del exterior. WSFEXv1 no modela el receptor con `DocTipo`/CUIT argentino (no
    aplica a alguien sin CUIT de AFIP) — en cambio, país destino (código de
    `WsfexClient.param_paises_destino()`) + identificación libre del comprador.

    `pais_destino_id`: código de la tabla AFIP `FEXGetPARAM_DST_pais` — el motor valida FORMATO
    (entero positivo), no vigencia (¿ese código existe hoy? — requiere consultar el catálogo vivo).
    `id_impositivo`: identificador fiscal del comprador en su país (tax ID / VAT number / etc.) —
    texto libre, WSFEXv1 no exige un formato fijo como el CUIT argentino."""

    razon_social: str
    pais_destino_id: int
    domicilio: str = ""
    id_impositivo: str = ""

    def __post_init__(self) -> None:
        if not self.razon_social.strip():
            raise ValueError("ReceptorExterior.razon_social no puede estar vacío.")
        if self.pais_destino_id <= 0:
            raise ValueError(
                f"ReceptorExterior.pais_destino_id tiene que ser positivo, recibido: "
                f"{self.pais_destino_id}."
            )


@dataclass(frozen=True)
class DatosExportacion:
    """Datos propios de la operación de exportación — permiso de embarque, Incoterm, idioma del
    comprobante (WSFEXv1 `FEXDetRequest.Permiso_existente`/`Pais_dst_cmp`/`Incoterm`/`Idioma_cbte`,
    nombres de campo tentativos — se confirman contra el WSDL real en la fase 2/3).

    `incoterm`: código de 2-3 letras de la tabla `FEXGetPARAM_Incoterms` (ej. "FOB"/"CIF") —
    normalizado a mayúscula, validado en FORMATO (no vacío), no en vigencia.
    `permiso_existente`: `True` si la operación tiene permiso de embarque (el caso común); `False`
    para los regímenes que WSFEXv1 exime de tenerlo — si es `False`, `permiso_embarque` puede venir
    vacío (no se exige)."""

    incoterm: str
    permiso_embarque: str = ""
    permiso_existente: bool = True
    idioma_cbte: int = 1  # 1 = Español (default WSFEXv1) — confirmar contra el catálogo real

    def __post_init__(self) -> None:
        object.__setattr__(self, "incoterm", self.incoterm.strip().upper())
        if not self.incoterm:
            raise ValueError("DatosExportacion.incoterm no puede estar vacío.")
        if self.permiso_existente and not self.permiso_embarque.strip():
            raise ValueError(
                "DatosExportacion.permiso_embarque no puede estar vacío cuando "
                "permiso_existente=True."
            )


@dataclass(frozen=True)
class CbteAsocExportacion:
    """Comprobante de exportación asociado (para notas de crédito/débito: referencia al comprobante
    origen) — paralelo a `modelos.CbteAsoc`, tipado con `CbteTipoExportacion` en vez de `CbteTipo`
    (no se puede reusar `CbteAsoc` tal cual: su `__post_init__` fuerza `CbteTipo(self.tipo)`)."""

    tipo: CbteTipoExportacion
    punto_venta: int
    numero: int
    cuit: Optional[int] = None
    fecha: Optional[date] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tipo", CbteTipoExportacion(self.tipo))
        if self.cuit is not None:
            object.__setattr__(
                self, "cuit",
                _validar_y_normalizar_cuit(self.cuit, campo="CbteAsocExportacion.cuit"),
            )


@dataclass(frozen=True)
class ComprobanteExportacionRequest:
    """Pedido de emisión de una Factura de Exportación, framework-agnóstico — equivalente de
    `modelos.ComprobanteRequest` para WSFEXv1.

    La exportación está exenta de IVA (no hay desglose de alícuotas como en el comprobante
    doméstico) — `importe_neto` es el importe TOTAL de la operación, ya calculado por el consumidor
    (el motor no calcula plata, mismo criterio que `ComprobanteRequest.importe_neto`).

    `moneda`/`cotizacion`: igual criterio que el motor doméstico — se valida FORMATO (3 caracteres
    mayúscula, cotización positiva), no vigencia contra el catálogo vivo
    (`WsfexClient.param_monedas()`). WSFEXv1 típicamente opera en moneda extranjera (USD u otra) —
    el motor NO fuerza eso, es responsabilidad del consumidor confirmar qué exige el régimen de su
    operación puntual."""

    emisor: Emisor
    receptor: ReceptorExterior
    exportacion: DatosExportacion
    concepto: Concepto
    importe_neto: Decimal
    fecha: date  # CbteFch
    moneda: str
    cotizacion: Decimal
    es_nota_credito: bool = False
    cbtes_asoc: tuple[CbteAsocExportacion, ...] = field(default_factory=tuple)
    forzar_cbte_tipo: Optional[CbteTipoExportacion] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "concepto", Concepto(self.concepto))
        object.__setattr__(self, "moneda", self.moneda.strip().upper())
        if self.forzar_cbte_tipo is not None:
            object.__setattr__(self, "forzar_cbte_tipo", CbteTipoExportacion(self.forzar_cbte_tipo))
        if len(self.moneda) != 3:
            raise ValueError(
                f"ComprobanteExportacionRequest.moneda tiene que ser un código de 3 letras "
                f"(ej. 'USD'), recibido: '{self.moneda}'."
            )
        if self.importe_neto <= 0:
            raise ValueError(
                "ComprobanteExportacionRequest.importe_neto tiene que ser positivo, recibido: "
                f"{self.importe_neto}."
            )
        if self.cotizacion <= 0:
            raise ValueError(
                "ComprobanteExportacionRequest.cotizacion tiene que ser positiva, recibido: "
                f"{self.cotizacion}."
            )
        if self.es_nota_credito and not self.cbtes_asoc:
            raise ValueError(
                "ComprobanteExportacionRequest: una nota de crédito/débito de exportación tiene "
                "que referenciar al menos un comprobante asociado (cbtes_asoc)."
            )


__all__ = [
    "CbteTipoExportacion",
    "es_nota_credito_exportacion",
    "ReceptorExterior",
    "DatosExportacion",
    "CbteAsocExportacion",
    "ComprobanteExportacionRequest",
    "CaeResult",
]
