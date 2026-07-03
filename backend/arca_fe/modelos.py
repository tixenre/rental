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
    """Tipo de comprobante (tabla AFIP `FEParamGetTiposCbte`).

    A/B/C cubiertas de punta a punta (incluida su selección automática en
    `tipo_comprobante`). M/FCE están en la tabla para que un consumidor pueda
    pedirlas explícitamente vía `ComprobanteRequest.forzar_cbte_tipo` — este
    motor NO las selecciona solo:

    - **M (51/52/53)**: verificado contra RG 1575/2003 (AFIP, art. 3/5) — M
      NO es una categoría que el emisor elija por su facturación; es una
      clasificación que **AFIP le IMPONE** al RI por indicadores de riesgo
      (inconsistencias detectadas o solvencia patrimonial no acreditada,
      art. 3(a)/(b)) y se lo comunica directamente. El motor no tiene (ni
      podría tener) esa información — la decisión es 100% del consumidor.
      Tampoco hace falta agregar ningún `Tributo` especial en el comprobante
      por ser M: la retención de IVA/Ganancias del art. 13(a)(1) la aplica
      el COMPRADOR vía SICORE/SIRE, no es un ítem del `FECAESolicitar`.
    - **FCE MiPyme (201-213)**: verificado contra el mismo manual — se emite
      por este MISMO WSFEv1 (no un servicio aparte), pero con reglas propias
      de campos obligatorios (ver `comprobante._validar_fce`). Si es
      LEGALMENTE obligatoria para una operación puntual (Ley 27.440, umbral
      que se actualiza por disposición de SEPYME) es algo que el motor no
      puede determinar —el umbral cambia y no está en ningún WSDL— así que
      es, de nuevo, decisión del consumidor.

    Factura E (exportación, 19/20/21) NO está acá: verificado que AFIP la
    emite por un webservice DISTINTO (WSFEXv1, operación `FEXAuthorize`, RG
    2758) con un modelo de datos propio (permiso de embarque, país destino,
    `Idioma_cbte`) — no es una extensión de este tipo, es un cliente aparte
    que este motor todavía no tiene."""

    FACTURA_A = 1
    NOTA_DEBITO_A = 2
    NOTA_CREDITO_A = 3
    FACTURA_B = 6
    NOTA_DEBITO_B = 7
    NOTA_CREDITO_B = 8
    FACTURA_C = 11
    NOTA_DEBITO_C = 12
    NOTA_CREDITO_C = 13
    FACTURA_M = 51
    NOTA_DEBITO_M = 52
    NOTA_CREDITO_M = 53
    # FCE MiPyme (Ley 27.440) — mismo WSFEv1, reglas propias de Opcionales/
    # FchVtoPago obligatorias (ver comprobante._validar_fce).
    FACTURA_CRED_ELEC_MIPYME_A = 201
    NOTA_DEBITO_CRED_ELEC_MIPYME_A = 202
    NOTA_CREDITO_CRED_ELEC_MIPYME_A = 203
    FACTURA_CRED_ELEC_MIPYME_B = 206
    NOTA_DEBITO_CRED_ELEC_MIPYME_B = 207
    NOTA_CREDITO_CRED_ELEC_MIPYME_B = 208
    FACTURA_CRED_ELEC_MIPYME_C = 211
    NOTA_DEBITO_CRED_ELEC_MIPYME_C = 212
    NOTA_CREDITO_CRED_ELEC_MIPYME_C = 213


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
class ItemIva:
    """Un tramo de IVA para un comprobante con MÁS DE UNA alícuota (WSFEv1
    `FEDetRequest.Iva` es un array — un comprobante real puede facturar, por
    ejemplo, parte al 21% y parte al 10.5%). `base_imponible` es la porción de
    `importe_neto` gravada a `alicuota`; la suma de todas las `base_imponible`
    de un comprobante tiene que dar exactamente `importe_neto` (lo valida
    `comprobante.calcular_importes`, no lo asume)."""

    alicuota: AlicuotaIva
    base_imponible: Decimal


@dataclass(frozen=True)
class Tributo:
    """Un tributo/percepción del comprobante (WSFEv1 `FEDetRequest.Tributos`
    — Impuestos Internos, percepciones de IIBB, etc.). El motor NO calcula
    `importe` (no conoce las reglas de cada jurisdicción/convenio) — lo recibe
    ya calculado del consumidor, mismo criterio que `importe_neto` para IVA.

    `id` es el código de la tabla AFIP `FEParamGetTiposTributos` — consultala
    con `WsfeClient.param_tipos_tributos()` en vez de hardcodear un id a
    mano (mismo motivo que `param_tipos_doc`/`param_tipos_concepto`: que la
    fuente de verdad sea ARCA, no una traducción escrita a mano)."""

    id: int
    base_imponible: Decimal
    alicuota_pct: Decimal
    importe: Decimal
    desc: str = ""


@dataclass(frozen=True)
class Opcional:
    """Un dato opcional del comprobante (WSFEv1 `FEDetRequest.Opcionales`) —
    mecanismo genérico de ARCA para datos extra según el régimen (ej. CBU/
    Alias de una Factura de Crédito Electrónica MiPyme). El motor NO conoce
    los ids/reglas de cada régimen (varían y no están todos en este WSDL) —
    consultá los ids válidos con `WsfeClient.param_tipos_opcional()` y armá
    el valor según la normativa de tu régimen; el motor solo transporta
    (id, valor) tal cual al payload."""

    id: str
    valor: str


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
    alícuota, lo deriva el core de `importe_neto * pct` con ROUND_HALF_UP a 2
    decimales (ver `comprobante.calcular_importes` — NO es redondeo bancario/
    HALF_EVEN, a pesar de lo que decía este docstring antes).

    `moneda`/`cotizacion`: MonId/MonCotiz de WSFEv1 (tabla `FEParamGetTiposMonedas`
    para los códigos válidos). Default "PES"/1 — el caso de Rambla (todo en
    pesos). Un consumidor que factura en moneda extranjera pasa el código ISO/
    ARCA correspondiente y la cotización del día; el motor NO la valida ni la
    busca (eso es responsabilidad del consumidor, como el precio).

    `alicuota`/`importe_neto` siguen siendo el camino de UNA sola alícuota
    (el caso común, el de Rambla). Para MÁS de una alícuota en el mismo
    comprobante, usar `alicuotas_iva` (no combinar los dos — `alicuota` tiene
    que quedar en `None` si se usa `alicuotas_iva`; `calcular_importes` lo
    valida). `tributos`/`opcionales` son arrays opcionales — vacíos por
    default, ningún comportamiento cambia si no se usan. `importe_no_gravado`/
    `importe_exento` sí lo hacían hardcodeados en 0 antes de esta iniciativa
    (ImpTotConc/ImpOpEx en el payload) — ahora son reales.

    `forzar_cbte_tipo`: bypasea la selección automática A/B/C de
    `tipo_comprobante` (que solo mira emisor/receptor.condicion_iva) para
    pedir un tipo explícito (ej. M) — para cuando el CONSUMIDOR sabe algo que
    el motor no puede saber (su propia facturación anual, su régimen). El
    guardrail de "Monotributo únicamente factura C" se sigue enforzando
    incluso con esto seteado."""

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
    moneda: str = "PES"
    cotizacion: Decimal = Decimal("1")
    alicuotas_iva: tuple[ItemIva, ...] = field(default_factory=tuple)
    tributos: tuple[Tributo, ...] = field(default_factory=tuple)
    opcionales: tuple[Opcional, ...] = field(default_factory=tuple)
    importe_no_gravado: Decimal = Decimal("0")
    importe_exento: Decimal = Decimal("0")
    forzar_cbte_tipo: Optional[CbteTipo] = None


@dataclass(frozen=True)
class CaeResult:
    """Resultado de FECAESolicitar, ya parseado."""

    resultado: str  # 'A' aprobado / 'R' rechazado
    cae: Optional[str] = None
    cae_vto: Optional[date] = None
    numero: Optional[int] = None
    observaciones: tuple = ()
    errores: tuple = ()
