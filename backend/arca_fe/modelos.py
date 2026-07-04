"""arca_fe.modelos — data plana del core (dataclasses + enums). PORTABLE.

No importa nada de `backend.*` ni de frameworks. El consumidor arma estos objetos
y se los pasa al core.

**Validación fail-fast en la construcción** (no solo al armar el payload SOAP): los dataclasses de
acá normalizan/validan lo que la librería puede resolver sola, para que un dato mal formado se
note al construir el objeto, no tres pasos después contra AFIP. Criterio de ingesta — normalizar
sin preguntar lo cosmético/no-ambiguo (CUIT con o sin guiones, moneda en minúscula), rechazar con
`ValueError` explícito lo que es realmente inválido (dígito verificador mal, importe negativo).
Nunca "adivinar" un dato mal formado. Los campos que dependen de un catálogo VIVO de AFIP (moneda/
tributos/opcionales/condición IVA del receptor) solo se validan en FORMATO (forma fija del WSDL),
nunca en vigencia (¿este código existe hoy? — eso requiere consultar `WsfeClient.param_*` en vivo,
no se puede resolver sin red)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import Optional

from .validadores import cuit_valido, normalizar_cuit


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
    """Qué se factura (código WSFEv1 `FEDetRequest.Concepto`, tabla `FEParamGetTiposConcepto`).

    Determina qué campos exige AFIP además de los básicos: `SERVICIOS`/`PRODUCTOS_Y_SERVICIOS`
    requieren `fecha_serv_desde`/`fecha_serv_hasta`/`fecha_vto_pago` en `ComprobanteRequest`
    (ver `_validar_fechas_servicio` en `comprobante.py`) — `PRODUCTOS` no."""

    PRODUCTOS = 1
    SERVICIOS = 2
    PRODUCTOS_Y_SERVICIOS = 3


@dataclass(frozen=True)
class AlicuotaIva:
    """Alícuota de IVA: `id` del WS + porcentaje. `None` en un request = sin IVA."""

    id: int
    pct: Decimal


# Tabla canónica de alícuotas (tabla AFIP `FEParamGetTiposIva`) — el `id` (primer
# argumento) es el código que WSFEv1 espera en `Iva.AlicIva[].Id`, NO inventado. No hay
# `WsfeClient.param_tipos_iva()` (a diferencia de tipos_cbte/tipos_doc/etc.) — si hace falta
# confirmar que un `id` sigue vigente, hay que agregar ese wrapper (no existe todavía).
IVA_0 = AlicuotaIva(3, Decimal("0"))       # exento/no gravado dentro de un comprobante con IVA discriminado
IVA_10_5 = AlicuotaIva(4, Decimal("10.5"))  # alícuota reducida
IVA_21 = AlicuotaIva(5, Decimal("21"))      # alícuota general (el caso común)
IVA_27 = AlicuotaIva(6, Decimal("27"))      # alícuota incrementada (servicios públicos, etc.)


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
    """Quién factura. `condicion_iva` decide la letra del comprobante.

    `cuit` acepta guiones/espacios en la entrada (ej. "20-30123456-3") — se normaliza y valida el
    dígito verificador al construir; queda guardado como `int` sin guiones (lo que espera el
    payload de AFIP). `ValueError` si no normaliza a 11 dígitos o el dígito verificador da mal."""

    cuit: int
    punto_venta: int
    condicion_iva: CondicionIva  # RESPONSABLE_INSCRIPTO o MONOTRIBUTO

    def __post_init__(self) -> None:
        object.__setattr__(self, "cuit", _validar_y_normalizar_cuit(self.cuit, campo="Emisor.cuit"))
        object.__setattr__(self, "condicion_iva", CondicionIva(self.condicion_iva))


@dataclass(frozen=True)
class Receptor:
    """A quién se factura.

    `doc_nro` acepta guiones/espacios en la entrada cuando `doc_tipo == DocTipo.CUIT` (mismo
    criterio que `Emisor.cuit`) — DNI/CUIL/Consumidor Final no son CUIT, no se les exige el dígito
    verificador mod-11 (no aplica)."""

    doc_tipo: DocTipo
    doc_nro: int
    condicion_iva: CondicionIva

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_tipo", DocTipo(self.doc_tipo))
        object.__setattr__(self, "condicion_iva", CondicionIva(self.condicion_iva))
        if self.doc_tipo == DocTipo.CUIT:
            object.__setattr__(
                self, "doc_nro", _validar_y_normalizar_cuit(self.doc_nro, campo="Receptor.doc_nro")
            )
        elif self.doc_tipo == DocTipo.CONSUMIDOR_FINAL and int(self.doc_nro) != 0:
            raise ValueError(
                "Receptor.doc_nro tiene que ser 0 cuando doc_tipo=CONSUMIDOR_FINAL "
                f"(recibido: {self.doc_nro})."
            )


@dataclass(frozen=True)
class CbteAsoc:
    """Comprobante asociado (para notas de crédito: referencia a la factura origen).

    `cuit`, si se pasa, acepta guiones/espacios (mismo criterio que `Emisor.cuit`)."""

    tipo: CbteTipo
    punto_venta: int
    numero: int
    cuit: Optional[int] = None
    fecha: Optional[date] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tipo", CbteTipo(self.tipo))
        if self.cuit is not None:
            object.__setattr__(
                self, "cuit", _validar_y_normalizar_cuit(self.cuit, campo="CbteAsoc.cuit")
            )


def _validar_y_normalizar_cuit(raw: int | str, *, campo: str) -> int:
    """Normaliza (tolera guiones/espacios) y valida el dígito verificador — helper compartido por
    `Emisor`/`Receptor`/`CbteAsoc`. `ValueError` con el motivo puntual si no normaliza a 11 dígitos
    o el dígito verificador da mal (nunca un mensaje genérico)."""
    normalizado = normalizar_cuit(raw)
    if normalizado is None:
        raise ValueError(f"{campo}: '{raw}' no normaliza a un CUIT de 11 dígitos.")
    if not cuit_valido(normalizado):
        raise ValueError(f"{campo}: '{raw}' tiene el dígito verificador inválido.")
    return int(normalizado)


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
    ARCA correspondiente y la cotización del día; el motor valida el FORMATO
    (`moneda` normalizada a mayúscula, 3 caracteres; `cotizacion` positiva) pero
    NO la VIGENCIA (¿ese código en particular existe hoy en el catálogo de
    AFIP? — eso requiere consultar `WsfeClient.param_tipos_monedas()` en vivo,
    es responsabilidad del consumidor, como el precio).

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

    def __post_init__(self) -> None:
        object.__setattr__(self, "concepto", Concepto(self.concepto))
        if self.forzar_cbte_tipo is not None:
            object.__setattr__(self, "forzar_cbte_tipo", CbteTipo(self.forzar_cbte_tipo))
        object.__setattr__(self, "moneda", self.moneda.strip().upper())

        # Import diferido: `comprobante.py` importa de este módulo — un import a
        # nivel de módulo acá crearía un ciclo. En tiempo de construcción (no de
        # definición de clase) el ciclo no existe.
        from .comprobante import _validar_estructura

        _validar_estructura(self)


def letra_comprobante(cbte_tipo: CbteTipo) -> str:
    """Letra (A/B/C) de un `CbteTipo` — deriva del código WSFEv1, no la vuelvas a hardcodear en
    un dict aparte (mismo esquema fijo de `FEParamGetTiposCbte` que ya modela `CbteTipo`).

    M y FCE MiPyme también resuelven a su letra base (M→ninguna letra propia, ver abajo; FCE
    A/B/C→A/B/C) porque comparten el mismo esquema visual de comprobante que su letra homóloga.
    `ValueError` si `cbte_tipo` no es ninguno de los valores conocidos de `CbteTipo`."""
    cbte_tipo = CbteTipo(cbte_tipo)
    if cbte_tipo in (CbteTipo.FACTURA_A, CbteTipo.NOTA_DEBITO_A, CbteTipo.NOTA_CREDITO_A,
                     CbteTipo.FACTURA_CRED_ELEC_MIPYME_A, CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_A,
                     CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A):
        return "A"
    if cbte_tipo in (CbteTipo.FACTURA_B, CbteTipo.NOTA_DEBITO_B, CbteTipo.NOTA_CREDITO_B,
                     CbteTipo.FACTURA_CRED_ELEC_MIPYME_B, CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_B,
                     CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_B):
        return "B"
    if cbte_tipo in (CbteTipo.FACTURA_C, CbteTipo.NOTA_DEBITO_C, CbteTipo.NOTA_CREDITO_C,
                     CbteTipo.FACTURA_CRED_ELEC_MIPYME_C, CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_C,
                     CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_C):
        return "C"
    if cbte_tipo in (CbteTipo.FACTURA_M, CbteTipo.NOTA_DEBITO_M, CbteTipo.NOTA_CREDITO_M):
        return "M"
    raise ValueError(f"letra_comprobante: no hay letra definida para {cbte_tipo!r}.")


def es_nota_credito(cbte_tipo: CbteTipo) -> bool:
    """`True` si `cbte_tipo` es una nota de crédito (A/B/C/M o FCE MiPyme) — para decidir un
    prefijo/título distinto ("Nota de Crédito" vs. "Factura") sin repetir el mismo set de códigos
    en cada consumidor."""
    return CbteTipo(cbte_tipo) in (
        CbteTipo.NOTA_CREDITO_A, CbteTipo.NOTA_CREDITO_B, CbteTipo.NOTA_CREDITO_C,
        CbteTipo.NOTA_CREDITO_M, CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A,
        CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_B, CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_C,
    )


# ---------------------------------------------------------------------------
# Labels ESTRUCTURALES (default) para armar un ComprobanteFiscal — Concepto/DocTipo/CondicionIva
# son enums FIJOS (no dependen de un catálogo vivo de AFIP, a diferencia de moneda/tributos), así
# que un texto default acá es seguro. Si tu integración ya cachea el catálogo vivo de ARCA
# (`WsfeClient.param_tipos_doc`/`param_tipos_concepto`/`param_condicion_iva_receptor` — más preciso
# si AFIP agrega un código nuevo), pasá ESE texto en su lugar; estos defaults son para quien no
# tiene esa infraestructura y solo necesita el texto correcto para los códigos ya conocidos.
# ---------------------------------------------------------------------------

_CONCEPTO_LABEL: dict["Concepto", str] = {
    Concepto.PRODUCTOS: "Productos",
    Concepto.SERVICIOS: "Servicios",
    Concepto.PRODUCTOS_Y_SERVICIOS: "Productos y Servicios",
}

_DOC_TIPO_LABEL: dict["DocTipo", str] = {
    DocTipo.CUIT: "CUIT",
    DocTipo.CUIL: "CUIL",
    DocTipo.DNI: "DNI",
    DocTipo.CONSUMIDOR_FINAL: "Consumidor Final",
}

_CONDICION_IVA_LABEL: dict["CondicionIva", str] = {
    CondicionIva.RESPONSABLE_INSCRIPTO: "IVA Responsable Inscripto",
    CondicionIva.EXENTO: "IVA Exento",
    CondicionIva.CONSUMIDOR_FINAL: "Consumidor Final",
    CondicionIva.MONOTRIBUTO: "Responsable Monotributo",
}


def label_concepto(concepto: Concepto) -> str:
    """Texto para mostrar de un `Concepto` ("Servicios", "Productos", ...) — ver nota de labels
    estructurales arriba. `ValueError` si `concepto` no es un `Concepto` válido."""
    return _CONCEPTO_LABEL[Concepto(concepto)]


def label_doc_tipo(doc_tipo: DocTipo) -> str:
    """Texto para mostrar de un `DocTipo` ("CUIT", "DNI", ...) — ver nota de labels estructurales
    arriba. `ValueError` si `doc_tipo` no es un `DocTipo` válido."""
    return _DOC_TIPO_LABEL[DocTipo(doc_tipo)]


def label_condicion_iva(condicion_iva: CondicionIva) -> str:
    """Texto para mostrar de una `CondicionIva` ("IVA Responsable Inscripto", ...) — ver nota de
    labels estructurales arriba. `ValueError` si `condicion_iva` no es una `CondicionIva` válida."""
    return _CONDICION_IVA_LABEL[CondicionIva(condicion_iva)]


@dataclass(frozen=True)
class ItemFactura:
    """Una línea de detalle de un comprobante ya emitido (para mostrar en el documento — no
    confundir con `ItemIva`, que es el desglose de IVA por alícuota).

    `precio_unitario`/`subtotal` son montos ya resueltos por el caller (mismo criterio que
    `ComprobanteRequest.importe_neto`: el motor no calcula plata, la recibe calculada)."""

    codigo: str
    descripcion: str
    precio_unitario: Decimal
    subtotal: Decimal
    cantidad: Decimal = Decimal("1")
    unidad_medida: str = "unidad"
    bonificacion_pct: Decimal = Decimal("0")
    detalle: str = ""


@dataclass(frozen=True)
class ComprobanteFiscal:
    """La foto final de un comprobante YA EMITIDO — todo lo que hace falta para renderizar el
    documento (`arca_fe.pdf.renderizar_comprobante_html`), ya resuelto. Distinto de
    `ComprobanteRequest` (el pedido, antes del CAE) y de `CaeResult` (resultado transitorio de la
    llamada SOAP) — este es el registro persistido/completo.

    Reusa `Receptor` para lo estrictamente fiscal del receptor (doc.tipo/doc.nro, condición IVA) —
    ese dato viene de la MISMA `ComprobanteRequest` ya validada con la que se pidió el CAE, así que
    reconstruirlo acá con la clase estricta es seguro (ya pasó esa validación una vez). El CUIT del
    EMISOR en cambio se recibe como `emisor_cuit: str` plano, no como `Emisor` — viene de una
    consulta de configuración APARTE (nombre del emisor → fila en la base del caller), que puede
    fallar o estar incompleta independientemente de la validez del comprobante ya emitido (un
    emisor renombrado/desconfigurado después de facturar no debería romper el render de una
    factura vieja — degrada a "—", no ValueError). Los campos `*_label` (concepto/doc.tipo/
    condición IVA) vienen de catálogos de AFIP que dependen de una consulta viva o un cache propio
    del caller — `arca_fe` no los resuelve solo, los recibe ya resueltos como texto. Igual con razón
    social/domicilio del emisor: son datos de negocio, no fiscales.

    `ValueError` en la construcción si falta `cae`/`numero`/`cae_vto`/`qr_url` — un comprobante sin
    esos 4 datos no se puede renderizar como válido, se rechaza antes de intentarlo (reemplaza el
    `RuntimeError` que antes vivía en el adapter Rambla — validación de input del programador, ver
    criterio de `arca_fe.errores`)."""

    cbte_tipo: CbteTipo
    pto_vta: int
    numero: int
    fecha_emision: date
    cae: str
    cae_vto: date
    qr_url: str

    receptor: Receptor
    receptor_nombre: str

    concepto_label: str
    doc_tipo_label: str
    condicion_iva_receptor_label: str
    emisor_condicion_iva_label: str

    items: tuple[ItemFactura, ...] = field(default_factory=tuple)

    importe_neto: Decimal = Decimal("0")
    importe_iva: Decimal = Decimal("0")
    importe_total: Decimal = Decimal("0")
    importe_otros_tributos: Decimal = Decimal("0")

    emisor_cuit: str = ""
    emisor_razon_social: str = ""
    emisor_domicilio: str = ""
    emisor_iibb: str = ""
    emisor_inicio_actividades: Optional[date] = None
    receptor_domicilio: str = ""
    condicion_venta: str = "Contado"

    periodo_desde: Optional[date] = None
    periodo_hasta: Optional[date] = None
    vencimiento_pago: Optional[date] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cbte_tipo", CbteTipo(self.cbte_tipo))
        faltantes = [
            campo
            for campo, valor in (
                ("cae", self.cae),
                ("numero", self.numero),
                ("cae_vto", self.cae_vto),
                ("qr_url", self.qr_url),
            )
            if not valor
        ]
        if faltantes:
            raise ValueError(
                f"ComprobanteFiscal incompleto, faltan: {', '.join(faltantes)} "
                "— no se puede renderizar un comprobante sin esos datos."
            )


def comprobante_fiscal_desde(
    comprobante: ComprobanteRequest,
    cbte_tipo: CbteTipo,
    cae_result: CaeResult,
    qr_url: str,
    importe_neto: Decimal,
    importe_iva: Decimal,
    importe_total: Decimal,
    fecha_emision: date,
    *,
    items: tuple[ItemFactura, ...] = (),
    importe_otros_tributos: Decimal = Decimal("0"),
    emisor_cuit: str = "",
    emisor_razon_social: str = "",
    emisor_domicilio: str = "",
    emisor_iibb: str = "",
    emisor_inicio_actividades: Optional[date] = None,
    receptor_nombre: str = "",
    receptor_domicilio: str = "",
    condicion_venta: str = "Contado",
    concepto_label: Optional[str] = None,
    doc_tipo_label: Optional[str] = None,
    condicion_iva_receptor_label: Optional[str] = None,
    emisor_condicion_iva_label: Optional[str] = None,
    periodo_desde: Optional[date] = None,
    periodo_hasta: Optional[date] = None,
    vencimiento_pago: Optional[date] = None,
) -> ComprobanteFiscal:
    """Arma un `ComprobanteFiscal` a partir del `ComprobanteRequest` ya emitido + su `CaeResult` —
    reduce el copy manual de campo a campo (pto_vta/receptor ya están en `comprobante`, cae/cae_vto/
    numero ya están en `cae_result`) a solo lo que `arca_fe` no puede resolver sola: importes ya
    calculados (`calcular_importes`), datos de negocio del emisor/receptor (razón social,
    domicilio) y, opcionalmente, los `*_label` (si no los pasás, usa los defaults ESTRUCTURALES de
    `label_concepto`/`label_doc_tipo`/`label_condicion_iva` — ver esas funciones para cuándo
    conviene pasar el texto del catálogo vivo de AFIP en su lugar).

    `cbte_tipo`: el tipo YA resuelto (de `tipo_comprobante(comprobante)` o
    `comprobante.forzar_cbte_tipo`) — esta función no lo rederiva.
    `cae_result.resultado` tiene que ser `'A'` (aprobado) — `ValueError` si no (un comprobante
    rechazado o parcial no tiene los datos para armar un `ComprobanteFiscal` válido)."""
    if cae_result.resultado != "A":
        raise ValueError(
            f"comprobante_fiscal_desde: cae_result.resultado tiene que ser 'A' (aprobado), "
            f"vino '{cae_result.resultado}'."
        )
    return ComprobanteFiscal(
        cbte_tipo=cbte_tipo,
        pto_vta=comprobante.emisor.punto_venta,
        numero=cae_result.numero,
        fecha_emision=fecha_emision,
        cae=cae_result.cae,
        cae_vto=cae_result.cae_vto,
        qr_url=qr_url,
        receptor=comprobante.receptor,
        receptor_nombre=receptor_nombre,
        concepto_label=concepto_label or label_concepto(comprobante.concepto),
        doc_tipo_label=doc_tipo_label or label_doc_tipo(comprobante.receptor.doc_tipo),
        condicion_iva_receptor_label=(
            condicion_iva_receptor_label or label_condicion_iva(comprobante.receptor.condicion_iva)
        ),
        emisor_condicion_iva_label=(
            emisor_condicion_iva_label or label_condicion_iva(comprobante.emisor.condicion_iva)
        ),
        items=items,
        importe_neto=importe_neto,
        importe_iva=importe_iva,
        importe_total=importe_total,
        importe_otros_tributos=importe_otros_tributos,
        emisor_cuit=emisor_cuit,
        emisor_razon_social=emisor_razon_social,
        emisor_domicilio=emisor_domicilio,
        emisor_iibb=emisor_iibb,
        emisor_inicio_actividades=emisor_inicio_actividades,
        receptor_domicilio=receptor_domicilio,
        condicion_venta=condicion_venta,
        periodo_desde=periodo_desde,
        periodo_hasta=periodo_hasta,
        vencimiento_pago=vencimiento_pago,
    )


@dataclass(frozen=True)
class CaeResult:
    """Resultado de `FECAESolicitar`, ya parseado (`WsfeClient.solicitar_cae`/`solicitar_cae_lote`).

    `resultado`: `'A'` aprobado, `'R'` rechazado, `'P'` parcial (solo posible en un lote — ver
    `solicitar_cae_lote`, un comprobante individual siempre es 'A' o 'R').
    `cae`/`cae_vto`/`numero`: solo poblados cuando `resultado == 'A'` — el CAE, su fecha de
    vencimiento, y el número de comprobante que AFIP autorizó (puede diferir del pedido si hubo
    un `recuperado` por idempotencia — no aplica acá, eso es responsabilidad del caller).
    `observaciones`: tupla de strings `"CODIGO: mensaje"` — avisos NO fatales que AFIP adjunta
    igual con `resultado == 'A'` (ej. un campo opcional que no hacía falta pero no se rechaza).
    `errores`: tupla de strings `"CODIGO: mensaje"` — motivo del rechazo cuando
    `resultado == 'R'` (o, para `solicitar_cae` de un comprobante suelto, también puede incluir
    errores de cabecera del pedido completo)."""

    resultado: str
    cae: Optional[str] = None
    cae_vto: Optional[date] = None
    numero: Optional[int] = None
    observaciones: tuple = ()
    errores: tuple = ()
