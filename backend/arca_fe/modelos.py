"""arca_fe.modelos — data plana del core (dataclasses + enums). PORTABLE.

No importa nada de `backend.*` ni de frameworks. El consumidor arma estos objetos
y se los pasa al core.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import Optional


class CondicionIva(IntEnum):
    """Condición frente al IVA (códigos `CondicionIVAReceptorId`, RG 5616)."""

    RESPONSABLE_INSCRIPTO = 1
    EXENTO = 4
    CONSUMIDOR_FINAL = 5
    MONOTRIBUTO = 6


class DocTipo(IntEnum):
    """Tipo de documento del receptor (tabla AFIP `FEParamGetTiposDoc`)."""

    CUIT = 80
    CUIL = 86
    DNI = 96
    CONSUMIDOR_FINAL = 99  # sin identificar (sólo válido en B/C, importes chicos)


class CbteTipo(IntEnum):
    """Tipo de comprobante (tabla AFIP `FEParamGetTiposCbte`)."""

    FACTURA_A = 1
    NOTA_DEBITO_A = 2
    NOTA_CREDITO_A = 3
    FACTURA_B = 6
    NOTA_DEBITO_B = 7
    NOTA_CREDITO_B = 8
    FACTURA_C = 11
    NOTA_DEBITO_C = 12
    NOTA_CREDITO_C = 13


class Concepto(IntEnum):
    PRODUCTOS = 1
    SERVICIOS = 2
    PRODUCTOS_Y_SERVICIOS = 3


@dataclass(frozen=True)
class AlicuotaIva:
    """Alícuota de IVA: `id` del WS + porcentaje. `None` en un request = sin IVA."""

    id: int
    pct: Decimal


# Tabla canónica de alícuotas (tabla AFIP `FEParamGetTiposIva`).
IVA_0 = AlicuotaIva(3, Decimal("0"))
IVA_10_5 = AlicuotaIva(4, Decimal("10.5"))
IVA_21 = AlicuotaIva(5, Decimal("21"))
IVA_27 = AlicuotaIva(6, Decimal("27"))


@dataclass(frozen=True)
class Emisor:
    """Quién factura. `condicion_iva` decide la letra del comprobante."""

    cuit: int
    punto_venta: int
    condicion_iva: CondicionIva  # RESPONSABLE_INSCRIPTO o MONOTRIBUTO


@dataclass(frozen=True)
class Receptor:
    """A quién se factura."""

    doc_tipo: DocTipo
    doc_nro: int
    condicion_iva: CondicionIva


@dataclass(frozen=True)
class CbteAsoc:
    """Comprobante asociado (para notas de crédito: referencia a la factura origen)."""

    tipo: CbteTipo
    punto_venta: int
    numero: int
    cuit: Optional[int] = None
    fecha: Optional[date] = None


@dataclass(frozen=True)
class ComprobanteRequest:
    """Pedido de emisión, framework-agnóstico.

    `importe_neto` es la base gravada; para un emisor Monotributo (Factura C) es
    el importe total (no se discrimina IVA → pasar `alicuota=None`). El core NO
    decide el precio: lo recibe ya calculado por el consumidor (regla de Rambla
    "el front/los demás no calculan plata, una sola fuente"). El IVA, si hay
    alícuota, lo deriva el core de `importe_neto * pct` con redondeo bancario a 2
    decimales.
    """

    emisor: Emisor
    receptor: Receptor
    concepto: Concepto
    importe_neto: Decimal
    alicuota: Optional[AlicuotaIva]
    fecha: date  # CbteFch (= fecha de emisión, no la del pedido)
    fecha_serv_desde: Optional[date] = None
    fecha_serv_hasta: Optional[date] = None
    fecha_vto_pago: Optional[date] = None
    es_nota_credito: bool = False
    cbtes_asoc: tuple[CbteAsoc, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CaeResult:
    """Resultado de FECAESolicitar, ya parseado."""

    resultado: str  # 'A' aprobado / 'R' rechazado
    cae: Optional[str] = None
    cae_vto: Optional[date] = None
    numero: Optional[int] = None
    observaciones: tuple = ()
    errores: tuple = ()
