"""arca_fe.comprobante — lógica fiscal pura (testeable sin red).

Reglas de tipo de comprobante, cálculo de importes y armado del payload FECAESolicitar.
Sin estado, sin IO, sin imports de backend.*

Alcance verificado contra el WSDL real de WSFEv1 (`FEDetRequest`, homologación
y producción, mismo schema) Y contra el "Manual para el desarrollador WSFEv1"
oficial (COMPG v4.0) para las reglas que el WSDL no expresa: emisor
RESPONSABLE_INSCRIPTO o MONOTRIBUTO (Factura A/B/C automáticas; **M** y
**FCE MiPyme** disponibles vía `forzar_cbte_tipo` — ver su docstring y el de
`CbteTipo`, el motor no adivina cuándo corresponde ninguna de las dos);
**múltiples alícuotas de IVA** por comprobante (`alicuotas_iva`, ver
`ItemIva`); **tributos/percepciones** (`tributos`, ver `Tributo` — ids
consultables con `WsfeClient.param_tipos_tributos()`, NUNCA hardcodeados: el
manual oficial confirma que ARCA los expone como catálogo vivo, sin tabla
fija); **datos opcionales** (`opcionales`, ver `Opcional`); conceptos no
gravados y operaciones exentas (`importe_no_gravado`/`importe_exento`); moneda/
cotización paramétricas (`moneda`/`cotizacion`, tabla consultable con
`param_tipos_monedas()`/`param_cotizacion()`).

**FCE MiPyme (201-213)**, a diferencia de M, SÍ tiene reglas estructurales
verificadas que este módulo valida (`_validar_fce`): `FchVtoPago` obligatorio
y al menos un `Opcional` de {CBU=2101, Alias=2102, Transferencia=27} en las
subclases "Factura" (201/206/211); código de Anulación (Id=22) en las
subclases Nota de Débito/Crédito (202/203/207/208/212/213), sin CBU/Alias/
Transferencia. Lo que el motor NO valida (no puede, cambia con disposiciones
de SEPYME): si la operación puntual está LEGALMENTE OBLIGADA a ser FCE
(umbral de facturación, Ley 27.440) — esa determinación es del consumidor.

Explícitamente FUERA de este módulo (no es una extensión, es un servicio
aparte de AFIP con su propio modelo de datos): **Factura E de exportación**
(WSFEXv1 — operación `FEXAuthorize`, RG 2758 — permiso de embarque, país
destino, `Idioma_cbte`, sin `DocTipo` argentino) y los campos de régimen
agropecuario/periódico `Compradores`/`PeriodoAsoc`/`Actividades` del WSDL
(existen, no se modelan — sin demanda real todavía; agregarlos es mecánico
si hace falta, mismo patrón que el resto).
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
_TIPOS_MONOTRIBUTO = (
    CbteTipo.FACTURA_C, CbteTipo.NOTA_DEBITO_C, CbteTipo.NOTA_CREDITO_C,
    CbteTipo.FACTURA_CRED_ELEC_MIPYME_C, CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_C,
    CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_C,
)
_TIPOS_RI = (
    CbteTipo.FACTURA_A, CbteTipo.NOTA_DEBITO_A, CbteTipo.NOTA_CREDITO_A,
    CbteTipo.FACTURA_B, CbteTipo.NOTA_DEBITO_B, CbteTipo.NOTA_CREDITO_B,
    CbteTipo.FACTURA_M, CbteTipo.NOTA_DEBITO_M, CbteTipo.NOTA_CREDITO_M,
    CbteTipo.FACTURA_CRED_ELEC_MIPYME_A, CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_A,
    CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A,
    CbteTipo.FACTURA_CRED_ELEC_MIPYME_B, CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_B,
    CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_B,
)

# FCE MiPyme — subclases "Factura" (exigen CBU/Alias/Transferencia + FchVtoPago)
# vs. Nota de Débito/Crédito (exigen el código de Anulación, prohíben las otras).
_FCE_FACTURA = (
    CbteTipo.FACTURA_CRED_ELEC_MIPYME_A,
    CbteTipo.FACTURA_CRED_ELEC_MIPYME_B,
    CbteTipo.FACTURA_CRED_ELEC_MIPYME_C,
)
_FCE_ND_NC = (
    CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_A, CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A,
    CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_B, CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_B,
    CbteTipo.NOTA_DEBITO_CRED_ELEC_MIPYME_C, CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_C,
)
_OPCIONAL_CBU = "2101"
_OPCIONAL_ALIAS = "2102"
_OPCIONAL_TRANSFERENCIA = "27"
_OPCIONAL_ANULACION = "22"


# ---------------------------------------------------------------------------
# Tipo de comprobante
# ---------------------------------------------------------------------------

_EMISOR_CONDICIONES_VALIDAS = (CondicionIva.RESPONSABLE_INSCRIPTO, CondicionIva.MONOTRIBUTO)


def tipo_comprobante(req: ComprobanteRequest) -> CbteTipo:
    """Determina el tipo de comprobante a partir del emisor y el receptor.

    Emisor Monotributo → C (o NC C).
    Emisor RI + receptor RI → A (o NC A).
    Emisor RI + receptor no-RI → B (o NC B).

    `req.forzar_cbte_tipo`, si está seteado, reemplaza esta selección
    automática (ej. para pedir M en vez de A) — el motor no decide SOLO
    cuándo corresponde M: esa decisión depende de datos que no tiene (la
    facturación anual del emisor, RG específica de su régimen), así que la
    deja en manos de quien SÍ los conoce. Lo que el motor SIGUE enforzando
    incluso con `forzar_cbte_tipo` seteado: un Monotributo NUNCA puede emitir
    un tipo que no sea C (no discrimina IVA, es una regla legal fija, no una
    preferencia) — y viceversa, un RI no puede forzar un tipo C.

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

    if req.forzar_cbte_tipo is not None:
        forzado = req.forzar_cbte_tipo
        if mono and forzado not in _TIPOS_MONOTRIBUTO:
            raise ValueError(
                f"forzar_cbte_tipo={forzado.name} inválido: un emisor MONOTRIBUTO "
                f"solo puede emitir {[t.name for t in _TIPOS_MONOTRIBUTO]} (no "
                f"discrimina IVA — regla legal fija, no una preferencia)."
            )
        if not mono and forzado not in _TIPOS_RI:
            raise ValueError(
                f"forzar_cbte_tipo={forzado.name} inválido: un emisor "
                f"RESPONSABLE_INSCRIPTO no puede emitir un tipo C (no discrimina IVA)."
            )
        return forzado

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

def _iva_de_item(base: Decimal, pct: Decimal) -> Decimal:
    return (base * pct / Decimal("100")).quantize(_DOS, rounding=ROUND_HALF_UP)


def calcular_importes(req: ComprobanteRequest) -> dict[str, Decimal]:
    """Devuelve {neto, iva, totconc, opex, tributos, total} como Decimal con
    2 decimales, ROUND_HALF_UP. `total` sigue la fórmula real de WSFEv1 —
    ImpTotal = ImpNeto + ImpTotConc + ImpOpEx + ImpIVA + ImpTrib, los 5
    componentes de un comprobante, no solo neto+iva (eso alcanzaba mientras
    los otros 3 estaban hardcodeados en 0; dejaron de estarlo).

    IVA: `alicuota` (una sola, el caso común) o `alicuotas_iva` (varias — no
    ambos a la vez, y si se usa `alicuotas_iva` la suma de sus
    `base_imponible` tiene que dar EXACTO `importe_neto`, si no ValueError —
    mejor fallar acá que mandarle a AFIP un comprobante con el neto y el IVA
    calculados sobre bases que no cierran entre sí).

    Tributos: `t.importe` de cada uno se suma tal cual (el motor no lo
    recalcula — mismo criterio que el IVA de una alícuota simple: viene ya
    calculado del consumidor, que es quien conoce las reglas de cada tributo).
    """
    if req.alicuota is not None and req.alicuotas_iva:
        raise ValueError(
            "ComprobanteRequest no puede tener `alicuota` y `alicuotas_iva` "
            "seteados a la vez — son dos formas mutuamente excluyentes de "
            "expresar el IVA del comprobante."
        )

    neto = req.importe_neto.quantize(_DOS, rounding=ROUND_HALF_UP)

    if req.alicuotas_iva:
        suma_bases = sum(
            (item.base_imponible.quantize(_DOS, rounding=ROUND_HALF_UP) for item in req.alicuotas_iva),
            start=Decimal("0.00"),
        )
        if suma_bases != neto:
            raise ValueError(
                f"La suma de `base_imponible` de `alicuotas_iva` ({suma_bases}) "
                f"no coincide con `importe_neto` ({neto}) — un comprobante con "
                f"neto e IVA calculados sobre bases que no cierran entre sí es "
                f"un comprobante mal formado, no se envía a AFIP así."
            )
        iva = sum(
            (_iva_de_item(item.base_imponible, item.alicuota.pct) for item in req.alicuotas_iva),
            start=Decimal("0.00"),
        )
    elif req.alicuota is not None:
        iva = _iva_de_item(neto, req.alicuota.pct)
    else:
        iva = Decimal("0.00")

    totconc = req.importe_no_gravado.quantize(_DOS, rounding=ROUND_HALF_UP)
    opex = req.importe_exento.quantize(_DOS, rounding=ROUND_HALF_UP)
    tributos = sum(
        (t.importe.quantize(_DOS, rounding=ROUND_HALF_UP) for t in req.tributos),
        start=Decimal("0.00"),
    )
    total = neto + totconc + opex + iva + tributos
    return {
        "neto": neto, "iva": iva, "totconc": totconc, "opex": opex,
        "tributos": tributos, "total": total,
    }


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


def _validar_estructura(req: ComprobanteRequest) -> None:
    """Valida todo lo que es ESTRUCTURAL/fijo por especificación AFIP (nunca lo que depende de un
    catálogo VIVO de AFIP — moneda/tributos/opcionales/condición IVA solo se validan en FORMATO
    acá, nunca en vigencia; ver el docstring del módulo `modelos.py`).

    La llama TANTO `ComprobanteRequest.__post_init__` (fail-fast en la construcción, antes de
    esta iniciativa esto corría recién acá) COMO `armar_fecae`/`armar_fecae_lote` (mismo chequeo,
    sin duplicar la lógica — el dataclass es `frozen`, así que si pasó por `__post_init__` una
    vez ya está validado, pero repetir la llamada es barato y no asume que nadie construyó el
    objeto sin pasar por ahí)."""
    cbte_tipo = tipo_comprobante(req)
    _validar_fechas_servicio(req)
    _validar_fce(req, cbte_tipo)

    if not (1 <= req.emisor.punto_venta <= 9999):
        raise ValueError(
            f"emisor.punto_venta fuera de rango (1-9999): {req.emisor.punto_venta}"
        )

    for nombre, valor in (
        ("importe_neto", req.importe_neto),
        ("importe_no_gravado", req.importe_no_gravado),
        ("importe_exento", req.importe_exento),
    ):
        if valor < 0:
            raise ValueError(f"{nombre} no puede ser negativo: {valor}")

    for item in req.alicuotas_iva:
        if item.base_imponible < 0:
            raise ValueError(
                f"alicuotas_iva: base_imponible no puede ser negativo: {item.base_imponible}"
            )

    for t in req.tributos:
        if t.importe < 0:
            raise ValueError(f"tributos: importe no puede ser negativo: {t.importe}")
        if t.id <= 0:
            raise ValueError(f"tributos: id tiene que ser un entero positivo: {t.id}")
        if not (0 <= t.alicuota_pct <= 100):
            raise ValueError(f"tributos: alicuota_pct fuera de rango (0-100): {t.alicuota_pct}")

    for o in req.opcionales:
        if not o.id or not o.valor:
            raise ValueError("opcionales: id/valor no pueden venir vacíos")

    # Formato de MonId/MonCotiz (WSFEv1) — nunca vigencia (ver docstring de arriba).
    if len(req.moneda) != 3 or not req.moneda.isalnum():
        raise ValueError(
            f"moneda (MonId) tiene que ser exactamente 3 caracteres alfanuméricos: '{req.moneda}'"
        )
    if req.cotizacion <= 0:
        raise ValueError(f"cotizacion (MonCotiz) tiene que ser positiva: {req.cotizacion}")


def _validar_fce(req: ComprobanteRequest, cbte_tipo: CbteTipo) -> None:
    """Reglas estructurales de Factura de Crédito Electrónica MiPyme
    (verificadas contra el manual oficial WSFEv1 — NO decide si la operación
    tiene que ser FCE, eso es del consumidor, ver docstring del módulo):

    - Subclases "Factura" (201/206/211): `fecha_vto_pago` obligatoria (más
      allá del Concepto — a diferencia de `_validar_fechas_servicio`, acá
      aplica SIEMPRE) + al menos un `Opcional` de CBU(2101)/Alias(2102)/
      Transferencia(27).
    - Subclases Nota de Débito/Crédito (202/203/207/208/212/213): exigen el
      código de Anulación (22) y PROHÍBEN CBU/Alias/Transferencia."""
    if cbte_tipo in _FCE_FACTURA:
        if req.fecha_vto_pago is None:
            raise ValueError(
                f"{cbte_tipo.name} (FCE) exige fecha_vto_pago siempre, "
                f"más allá del Concepto — AFIP la rechaza si falta."
            )
        ids = {o.id for o in req.opcionales}
        if not ids & {_OPCIONAL_CBU, _OPCIONAL_ALIAS, _OPCIONAL_TRANSFERENCIA}:
            raise ValueError(
                f"{cbte_tipo.name} (FCE) exige al menos un Opcional de "
                f"CBU (id={_OPCIONAL_CBU}), Alias (id={_OPCIONAL_ALIAS}) o "
                f"Transferencia (id={_OPCIONAL_TRANSFERENCIA})."
            )
    elif cbte_tipo in _FCE_ND_NC:
        ids = {o.id for o in req.opcionales}
        if _OPCIONAL_ANULACION not in ids:
            raise ValueError(
                f"{cbte_tipo.name} (FCE) exige el Opcional de Código de "
                f"Anulación (id={_OPCIONAL_ANULACION})."
            )
        if ids & {_OPCIONAL_CBU, _OPCIONAL_ALIAS, _OPCIONAL_TRANSFERENCIA}:
            raise ValueError(
                f"{cbte_tipo.name} (FCE, Nota de Débito/Crédito) no puede "
                f"llevar CBU/Alias/Transferencia — esos son exclusivos de la "
                f"Factura FCE original."
            )


def _armar_detalle(req: ComprobanteRequest, numero: int) -> dict:
    """Arma UN `FECAEDetRequest` (el detalle de un comprobante individual dentro del array que
    espera `FeDetReq`). Lo reusan `armar_fecae` (arma un array de 1) y `armar_fecae_lote` (arma
    un array de N) — cero duplicación de la lógica de importes/IVA/FCE entre las dos.

    Asume que `req` ya pasó `_validar_estructura` (lo llama el caller UNA vez para todo el lote,
    no acá por ítem — evita recalcular `tipo_comprobante`/`calcular_importes` dos veces)."""
    cbte_tipo = tipo_comprobante(req)
    imp = calcular_importes(req)
    neto, iva, totconc, opex, tributos_total, total = (
        imp["neto"], imp["iva"], imp["totconc"], imp["opex"], imp["tributos"], imp["total"],
    )

    det: dict = {
        "Concepto": int(req.concepto),
        "DocTipo": int(req.receptor.doc_tipo),
        "DocNro": req.receptor.doc_nro,
        "CbteDesde": numero,
        "CbteHasta": numero,
        "CbteFch": req.fecha.strftime("%Y%m%d"),
        "ImpTotal": _fmt(total),
        "ImpTotConc": _fmt(totconc),
        "ImpNeto": _fmt(neto),
        "ImpOpEx": _fmt(opex),
        "ImpIVA": _fmt(iva),
        "ImpTrib": _fmt(tributos_total),
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

    # IVA: solo en facturas con IVA discriminado (A/B/M, no C). Una alícuota
    # (`alicuota`) o varias (`alicuotas_iva`) — calcular_importes ya valida
    # que no vengan las dos a la vez.
    if cbte_tipo not in _TIPOS_MONOTRIBUTO:
        if req.alicuotas_iva:
            det["Iva"] = {
                "AlicIva": [
                    {
                        "Id": item.alicuota.id,
                        "BaseImp": _fmt(item.base_imponible),
                        "Importe": _fmt(_iva_de_item(item.base_imponible, item.alicuota.pct)),
                    }
                    for item in req.alicuotas_iva
                ]
            }
        elif req.alicuota is not None:
            det["Iva"] = {
                "AlicIva": [{
                    "Id": req.alicuota.id,
                    "BaseImp": _fmt(neto),
                    "Importe": _fmt(iva),
                }]
            }

    # Tributos/percepciones (Impuestos Internos, IIBB, etc.) — ids consultables
    # con WsfeClient.param_tipos_tributos(), no hardcodeados acá.
    if req.tributos:
        det["Tributos"] = {
            "Tributo": [
                {
                    "Id": t.id,
                    **({"Desc": t.desc} if t.desc else {}),
                    "BaseImp": _fmt(t.base_imponible),
                    "Alic": float(t.alicuota_pct),
                    "Importe": _fmt(t.importe),
                }
                for t in req.tributos
            ]
        }

    # Datos opcionales (ej. CBU/Alias de una Factura de Crédito Electrónica
    # MiPyme) — ids consultables con WsfeClient.param_tipos_opcional().
    if req.opcionales:
        det["Opcionales"] = {
            "Opcional": [{"Id": o.id, "Valor": o.valor} for o in req.opcionales]
        }

    # Comprobantes asociados (notas de crédito referencian la factura origen)
    if req.cbtes_asoc:
        det["CbtesAsoc"] = {
            "CbteAsoc": [_cbte_asoc_dict(a) for a in req.cbtes_asoc]
        }

    return det


def armar_fecae(req: ComprobanteRequest, numero: int) -> dict:
    """Arma el dict FECAEReq para FECAESolicitar (sin el nodo Auth) — UN solo comprobante.

    Retorna:
        {
          "FeCabReq": {"CantReg": 1, "PtoVta": ..., "CbteTipo": ...},
          "FeDetReq": {"FECAEDetRequest": [det]},
        }

    Levanta ValueError (fail fast, sin red) si el request es incompleto para su Concepto (ver
    `_validar_fechas_servicio`), si es FCE y le faltan sus campos obligatorios (ver
    `_validar_fce`), si `emisor.condicion_iva`/`forzar_cbte_tipo` no son facturables (ver
    `tipo_comprobante`), o cualquiera de las guardas estructurales de `_validar_estructura` —
    en la práctica esto ya corrió una vez en `ComprobanteRequest.__post_init__` (fail-fast en la
    construcción); repetirlo acá es barato y no asume que nadie construyó el objeto sin pasar por
    ahí."""
    _validar_estructura(req)
    cbte_tipo = tipo_comprobante(req)
    det = _armar_detalle(req, numero)
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


_MAX_LOTE = 250  # tope de FECAESolicitar por lote, manual oficial WSFEv1


def armar_fecae_lote(comprobantes: "list[ComprobanteRequest]", numero_desde: int) -> dict:
    """Arma el dict FECAEReq para pedir CAE de VARIOS comprobantes CONSECUTIVOS en una sola
    llamada `FECAESolicitar` (`FeDetReq.FECAEDetRequest` es un array — AFIP soporta hasta
    `_MAX_LOTE` comprobantes por lote, manual oficial WSFEv1).

    Todos los `comprobantes` tienen que compartir el MISMO emisor (`cuit`/`punto_venta`) y el
    MISMO `cbte_tipo` resuelto (`tipo_comprobante`) — es una regla dura del WSDL (un lote es
    homogéneo), no una preferencia de este motor. `ValueError` si no son homogéneos, si la lista
    viene vacía, o si supera `_MAX_LOTE` (la librería NO auto-particiona un lote grande en
    varios — mismo criterio "predecible, no mágico" del resto del diseño; el consumidor arma sus
    propios lotes de a lo sumo `_MAX_LOTE`).

    Los números de comprobante son CONSECUTIVOS desde `numero_desde` (uno por cada elemento de
    `comprobantes`, en orden)."""
    if not comprobantes:
        raise ValueError("armar_fecae_lote: la lista de comprobantes no puede estar vacía.")
    if len(comprobantes) > _MAX_LOTE:
        raise ValueError(
            f"armar_fecae_lote: {len(comprobantes)} comprobantes supera el tope de "
            f"{_MAX_LOTE} por lote (manual WSFEv1) — partí en más de un lote."
        )

    primero = comprobantes[0]
    for req in comprobantes:
        _validar_estructura(req)

    tipos = {tipo_comprobante(req) for req in comprobantes}
    if len(tipos) > 1:
        raise ValueError(
            f"armar_fecae_lote: los comprobantes tienen que compartir el mismo cbte_tipo "
            f"resuelto — se encontraron: {[t.name for t in tipos]}."
        )
    cuits = {req.emisor.cuit for req in comprobantes}
    ptos_venta = {req.emisor.punto_venta for req in comprobantes}
    if len(cuits) > 1 or len(ptos_venta) > 1:
        raise ValueError(
            "armar_fecae_lote: los comprobantes tienen que compartir el mismo "
            "emisor.cuit y emisor.punto_venta — un lote homogéneo, no una mezcla."
        )

    cbte_tipo = tipos.pop()
    detalles = [
        _armar_detalle(req, numero_desde + i) for i, req in enumerate(comprobantes)
    ]
    return {
        "FeCabReq": {
            "CantReg": len(detalles),
            "PtoVta": primero.emisor.punto_venta,
            "CbteTipo": int(cbte_tipo),
        },
        "FeDetReq": {
            "FECAEDetRequest": detalles
        },
    }
