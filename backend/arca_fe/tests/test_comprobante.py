"""Tests del core puro: tipo, importes, payload AFIP."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe import (
    IVA_10_5,
    IVA_21,
    CbteTipo,
    Concepto,
    CondicionIva,
    DocTipo,
    Emisor,
    ItemIva,
    Opcional,
    Receptor,
    Tributo,
    armar_fecae,
    armar_fecae_lote,
    calcular_importes,
    tipo_comprobante,
)
from arca_fe.modelos import CbteAsoc, ComprobanteRequest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# CUITs de prueba con dígito verificador VÁLIDO (mod-11) — desde esta iniciativa `Emisor`/
# `Receptor` lo validan en la construcción; un CUIT inventado sin chequear el dígito ya no sirve
# como fixture.
PABLO = Emisor(cuit=20123456786, punto_venta=1, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
SANTINI = Emisor(cuit=30987654321, punto_venta=2, condicion_iva=CondicionIva.MONOTRIBUTO)

RECEPTOR_RI = Receptor(
    doc_tipo=DocTipo.CUIT,
    doc_nro=27111222334,
    condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO,
)
RECEPTOR_CF = Receptor(
    doc_tipo=DocTipo.CONSUMIDOR_FINAL,
    doc_nro=0,
    condicion_iva=CondicionIva.CONSUMIDOR_FINAL,
)
RECEPTOR_MONO = Receptor(
    doc_tipo=DocTipo.CUIT,
    doc_nro=20987654326,
    condicion_iva=CondicionIva.MONOTRIBUTO,
)
RECEPTOR_EXENTO = Receptor(
    doc_tipo=DocTipo.CUIT,
    doc_nro=33555666778,
    condicion_iva=CondicionIva.EXENTO,
)


def _req(
    emisor: Emisor,
    receptor: Receptor,
    alicuota=IVA_21,
    importe_neto: Decimal = Decimal("1000.00"),
    es_nota_credito: bool = False,
    cbtes_asoc: tuple = (),
    concepto: Concepto = Concepto.SERVICIOS,
    fecha_serv_desde=date(2024, 1, 1),
    fecha_serv_hasta=date(2024, 1, 31),
    fecha_vto_pago=date(2024, 1, 31),
    moneda: str = "PES",
    cotizacion: Decimal = Decimal("1"),
    alicuotas_iva: tuple = (),
    tributos: tuple = (),
    opcionales: tuple = (),
    importe_no_gravado: Decimal = Decimal("0"),
    importe_exento: Decimal = Decimal("0"),
    forzar_cbte_tipo=None,
) -> ComprobanteRequest:
    return ComprobanteRequest(
        emisor=emisor,
        receptor=receptor,
        concepto=concepto,
        importe_neto=importe_neto,
        alicuota=alicuota,
        fecha=date(2024, 1, 15),
        fecha_serv_desde=fecha_serv_desde,
        fecha_serv_hasta=fecha_serv_hasta,
        fecha_vto_pago=fecha_vto_pago,
        es_nota_credito=es_nota_credito,
        cbtes_asoc=cbtes_asoc,
        moneda=moneda,
        cotizacion=cotizacion,
        alicuotas_iva=alicuotas_iva,
        tributos=tributos,
        opcionales=opcionales,
        importe_no_gravado=importe_no_gravado,
        importe_exento=importe_exento,
        forzar_cbte_tipo=forzar_cbte_tipo,
    )


# ---------------------------------------------------------------------------
# tipo_comprobante
# ---------------------------------------------------------------------------

class TestTipoComprobante:
    def test_mono_emite_C(self):
        req = _req(SANTINI, RECEPTOR_CF, alicuota=None)
        assert tipo_comprobante(req) == CbteTipo.FACTURA_C

    def test_mono_nc_emite_NC_C(self):
        req = _req(SANTINI, RECEPTOR_CF, alicuota=None, es_nota_credito=True)
        assert tipo_comprobante(req) == CbteTipo.NOTA_CREDITO_C

    def test_ri_receptor_ri_emite_A(self):
        req = _req(PABLO, RECEPTOR_RI)
        assert tipo_comprobante(req) == CbteTipo.FACTURA_A

    def test_ri_receptor_ri_nc_emite_NC_A(self):
        req = _req(PABLO, RECEPTOR_RI, es_nota_credito=True)
        assert tipo_comprobante(req) == CbteTipo.NOTA_CREDITO_A

    def test_ri_receptor_cf_emite_B(self):
        req = _req(PABLO, RECEPTOR_CF, alicuota=None)
        assert tipo_comprobante(req) == CbteTipo.FACTURA_B

    def test_ri_receptor_mono_emite_B(self):
        req = _req(PABLO, RECEPTOR_MONO, alicuota=None)
        assert tipo_comprobante(req) == CbteTipo.FACTURA_B

    def test_ri_receptor_exento_emite_B(self):
        req = _req(PABLO, RECEPTOR_EXENTO, alicuota=None)
        assert tipo_comprobante(req) == CbteTipo.FACTURA_B

    def test_ri_receptor_cf_nc_emite_NC_B(self):
        req = _req(PABLO, RECEPTOR_CF, alicuota=None, es_nota_credito=True)
        assert tipo_comprobante(req) == CbteTipo.NOTA_CREDITO_B

    def test_todo_codigo_de_cbtetipo_esta_clasificado(self):
        """Invariante de _TIPOS_MONOTRIBUTO/_TIPOS_RI (comprobante.py): si un
        código nuevo se agrega a CbteTipo sin sumarlo a ninguna de las dos
        tuplas, el guardrail de `forzar_cbte_tipo` lo rechazaría siempre (ni
        Monotributo ni RI podrían pedirlo) sin que nada lo señale — este test
        lo detecta apenas pase."""
        from arca_fe.comprobante import _TIPOS_MONOTRIBUTO, _TIPOS_RI

        sin_clasificar = set(CbteTipo) - set(_TIPOS_MONOTRIBUTO) - set(_TIPOS_RI)
        assert sin_clasificar == set(), (
            f"CbteTipo sin clasificar en _TIPOS_MONOTRIBUTO/_TIPOS_RI: {sin_clasificar}"
        )


# ---------------------------------------------------------------------------
# calcular_importes
# ---------------------------------------------------------------------------

class TestCalcularImportes:
    def test_con_iva_21(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        imp = calcular_importes(req)
        assert imp["neto"] == Decimal("1000.00")
        assert imp["iva"] == Decimal("210.00")
        assert imp["total"] == Decimal("1210.00")

    def test_sin_iva_monotributo(self):
        req = _req(SANTINI, RECEPTOR_CF, alicuota=None, importe_neto=Decimal("500.00"))
        imp = calcular_importes(req)
        assert imp["neto"] == Decimal("500.00")
        assert imp["iva"] == Decimal("0.00")
        assert imp["total"] == Decimal("500.00")

    def test_redondeo_half_up(self):
        # 333.33 × 21% = 69.9993 → 70.00
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("333.33"))
        imp = calcular_importes(req)
        assert imp["iva"] == Decimal("70.00")
        assert imp["total"] == imp["neto"] + imp["iva"]

    def test_centavos_exactos(self):
        # 100.01 × 21% = 21.0021 → 21.00
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("100.01"))
        imp = calcular_importes(req)
        assert imp["iva"] == Decimal("21.00")
        assert imp["total"] == imp["neto"] + imp["iva"]

    def test_invariante_total(self):
        for neto_str in ("1.00", "99.99", "9999.99", "0.01"):
            req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal(neto_str))
            imp = calcular_importes(req)
            assert imp["total"] == imp["neto"] + imp["iva"]


# ---------------------------------------------------------------------------
# armar_fecae
# ---------------------------------------------------------------------------

class TestArmarFecae:
    def test_factura_a_cabecera(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        payload = armar_fecae(req, 5)
        cab = payload["FeCabReq"]
        assert cab["CantReg"] == 1
        assert cab["PtoVta"] == 1
        assert cab["CbteTipo"] == CbteTipo.FACTURA_A

    def test_factura_a_importes_con_iva(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["ImpNeto"] == "1000.00"
        assert det["ImpIVA"] == "210.00"
        assert det["ImpTotal"] == "1210.00"
        assert "Iva" in det
        assert det["Iva"]["AlicIva"][0]["Id"] == IVA_21.id
        assert det["Iva"]["AlicIva"][0]["BaseImp"] == "1000.00"
        assert det["Iva"]["AlicIva"][0]["Importe"] == "210.00"

    def test_factura_a_condicion_iva_receptor(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["CondicionIVAReceptorId"] == int(CondicionIva.RESPONSABLE_INSCRIPTO)

    def test_factura_c_sin_iva(self):
        req = _req(SANTINI, RECEPTOR_CF, alicuota=None, importe_neto=Decimal("500.00"))
        payload = armar_fecae(req, 1)
        cab = payload["FeCabReq"]
        assert cab["CbteTipo"] == CbteTipo.FACTURA_C
        det = payload["FeDetReq"]["FECAEDetRequest"][0]
        assert det["ImpNeto"] == "500.00"
        assert det["ImpIVA"] == "0.00"
        assert det["ImpTotal"] == "500.00"
        assert "Iva" not in det
        assert det["CondicionIVAReceptorId"] == int(CondicionIva.CONSUMIDOR_FINAL)

    def test_fechas_servicio(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["FchServDesde"] == "20240101"
        assert det["FchServHasta"] == "20240131"
        assert det["FchVtoPago"] == "20240131"

    def test_cbte_fch_y_numero(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 42)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["CbteFch"] == "20240115"
        assert det["CbteDesde"] == 42
        assert det["CbteHasta"] == 42

    def test_doc_tipo_nro(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["DocTipo"] == int(DocTipo.CUIT)
        assert det["DocNro"] == 27111222334

    def test_nc_con_cbte_asoc(self):
        asoc = CbteAsoc(
            tipo=CbteTipo.FACTURA_A,
            punto_venta=1,
            numero=10,
            cuit=20123456786,
            fecha=date(2024, 1, 1),
        )
        req = _req(PABLO, RECEPTOR_RI, es_nota_credito=True, cbtes_asoc=(asoc,))
        payload = armar_fecae(req, 1)
        assert payload["FeCabReq"]["CbteTipo"] == CbteTipo.NOTA_CREDITO_A
        det = payload["FeDetReq"]["FECAEDetRequest"][0]
        assert "CbtesAsoc" in det
        ca = det["CbtesAsoc"]["CbteAsoc"][0]
        assert ca["Tipo"] == int(CbteTipo.FACTURA_A)
        assert ca["Nro"] == 10
        assert ca["CbteFch"] == "20240101"

    def test_ceros_no_gravado_exento_tributos(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["ImpTotConc"] == "0.00"
        assert det["ImpOpEx"] == "0.00"
        assert det["ImpTrib"] == "0.00"

    def test_moneda_pesos(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["MonId"] == "PES"
        assert det["MonCotiz"] == 1

    def test_factura_c_ptovta_de_santini(self):
        req = _req(SANTINI, RECEPTOR_CF, alicuota=None, importe_neto=Decimal("200.00"))
        cab = armar_fecae(req, 1)["FeCabReq"]
        assert cab["PtoVta"] == 2  # SANTINI.punto_venta

    def test_moneda_extranjera_parametrica(self):
        """MonId/MonCotiz ya no están hardcodeados a PES/1 — un consumidor
        que factura en moneda extranjera pasa su propio código y cotización."""
        req = _req(
            PABLO, RECEPTOR_RI, importe_neto=Decimal("100.00"),
            moneda="DOL", cotizacion=Decimal("1050.50"),
        )
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["MonId"] == "DOL"
        assert det["MonCotiz"] == 1050.50


# ---------------------------------------------------------------------------
# Guardrails (fail fast, sin red — ver docstrings de tipo_comprobante /
# _validar_fechas_servicio en comprobante.py)
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_emisor_con_condicion_iva_no_facturable_levanta_value_error(self):
        """Un Emisor con condicion_iva distinta de RI/Monotributo (el
        dataclass no lo impide en runtime, solo lo documenta en un
        comentario) antes se clasificaba EN SILENCIO como si fuera RI,
        emitiendo Factura A/B con IVA discriminado para un emisor que
        legalmente no corresponde. Ahora levanta ValueError explícito — desde
        esta iniciativa, en la construcción misma del ComprobanteRequest
        (`_validar_estructura` corre en `__post_init__`), no recién al
        llamar `tipo_comprobante`."""
        emisor_invalido = Emisor(
            cuit=20111222339, punto_venta=1, condicion_iva=CondicionIva.EXENTO
        )
        with pytest.raises(ValueError, match="EXENTO"):
            _req(emisor_invalido, RECEPTOR_RI, alicuota=None)

    def test_armar_fecae_tambien_propaga_el_guardrail_de_condicion_iva(self):
        emisor_invalido = Emisor(
            cuit=20111222339, punto_venta=1, condicion_iva=CondicionIva.CONSUMIDOR_FINAL
        )
        with pytest.raises(ValueError, match="CONSUMIDOR_FINAL"):
            _req(emisor_invalido, RECEPTOR_RI, alicuota=None)

    @pytest.mark.parametrize("concepto", [Concepto.SERVICIOS, Concepto.PRODUCTOS_Y_SERVICIOS])
    @pytest.mark.parametrize(
        "campo_ausente",
        ["fecha_serv_desde", "fecha_serv_hasta", "fecha_vto_pago"],
    )
    def test_concepto_servicios_sin_fechas_obligatorias_levanta_value_error(
        self, concepto, campo_ausente
    ):
        """AFIP exige FchServDesde/FchServHasta/FchVtoPago para Concepto
        SERVICIOS/PRODUCTOS_Y_SERVICIOS — no son opcionales. Antes, si un
        caller se los olvidaba, armar_fecae los omitía en silencio y el
        pedido recién fallaba al llegar a AFIP (round-trip + error de
        negocio). Ahora se valida ANTES, sin red."""
        kwargs = {
            "fecha_serv_desde": date(2024, 1, 1),
            "fecha_serv_hasta": date(2024, 1, 31),
            "fecha_vto_pago": date(2024, 1, 31),
        }
        kwargs[campo_ausente] = None
        with pytest.raises(ValueError, match=campo_ausente):
            _req(PABLO, RECEPTOR_RI, concepto=concepto, **kwargs)

    def test_concepto_productos_no_exige_fechas_de_servicio(self):
        """Concepto PRODUCTOS (sin servicio) NO exige estas fechas — el
        guardrail es específico de SERVICIOS/PRODUCTOS_Y_SERVICIOS."""
        req = _req(
            PABLO, RECEPTOR_RI, concepto=Concepto.PRODUCTOS,
            fecha_serv_desde=None, fecha_serv_hasta=None, fecha_vto_pago=None,
        )
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert "FchServDesde" not in det


# ---------------------------------------------------------------------------
# Multi-alícuota de IVA (alicuotas_iva) — WSFEv1 Iva es un array, verificado
# contra el WSDL real de WSFEv1
# ---------------------------------------------------------------------------


class TestMultiAlicuota:
    def test_dos_alicuotas_suman_bien_el_iva_y_el_total(self):
        # 600 al 21% (126.00) + 400 al 10.5% (42.00) = neto 1000, iva 168.00
        req = _req(
            PABLO, RECEPTOR_RI, alicuota=None, importe_neto=Decimal("1000.00"),
            alicuotas_iva=(
                ItemIva(IVA_21, Decimal("600.00")),
                ItemIva(IVA_10_5, Decimal("400.00")),
            ),
        )
        imp = calcular_importes(req)
        assert imp["neto"] == Decimal("1000.00")
        assert imp["iva"] == Decimal("168.00")
        assert imp["total"] == Decimal("1168.00")

    def test_dos_alicuotas_arman_dos_entradas_en_aliciva(self):
        req = _req(
            PABLO, RECEPTOR_RI, alicuota=None, importe_neto=Decimal("1000.00"),
            alicuotas_iva=(
                ItemIva(IVA_21, Decimal("600.00")),
                ItemIva(IVA_10_5, Decimal("400.00")),
            ),
        )
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        alic = det["Iva"]["AlicIva"]
        assert len(alic) == 2
        assert alic[0] == {"Id": IVA_21.id, "BaseImp": "600.00", "Importe": "126.00"}
        assert alic[1] == {"Id": IVA_10_5.id, "BaseImp": "400.00", "Importe": "42.00"}

    def test_suma_de_bases_que_no_cierra_con_neto_levanta_value_error(self):
        """Si las bases de `alicuotas_iva` no suman `importe_neto`, es un
        comprobante mal formado — no se manda a AFIP así."""
        req = _req(
            PABLO, RECEPTOR_RI, alicuota=None, importe_neto=Decimal("1000.00"),
            alicuotas_iva=(ItemIva(IVA_21, Decimal("999.00")),),  # falta 1.00
        )
        with pytest.raises(ValueError, match="no coincide con"):
            calcular_importes(req)

    def test_alicuota_y_alicuotas_iva_juntos_levanta_value_error(self):
        req = _req(
            PABLO, RECEPTOR_RI, alicuota=IVA_21, importe_neto=Decimal("1000.00"),
            alicuotas_iva=(ItemIva(IVA_21, Decimal("1000.00")),),
        )
        with pytest.raises(ValueError, match="mutuamente excluyentes"):
            calcular_importes(req)


# ---------------------------------------------------------------------------
# Tributos/percepciones — array real, ids consultables (no hardcodeados)
# ---------------------------------------------------------------------------


class TestTributos:
    def test_tributo_se_suma_al_total_y_aparece_en_el_payload(self):
        # IIBB 3% sobre 1000 = 30.00 (importe ya calculado por el consumidor)
        req = _req(
            PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"),
            tributos=(
                Tributo(id=7, base_imponible=Decimal("1000.00"), alicuota_pct=Decimal("3"),
                        importe=Decimal("30.00"), desc="Percepción IIBB"),
            ),
        )
        imp = calcular_importes(req)
        assert imp["tributos"] == Decimal("30.00")
        # 1000 neto + 210 iva + 30 tributo = 1240
        assert imp["total"] == Decimal("1240.00")

        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["ImpTrib"] == "30.00"
        assert det["Tributos"]["Tributo"] == [{
            "Id": 7, "Desc": "Percepción IIBB", "BaseImp": "1000.00",
            "Alic": 3.0, "Importe": "30.00",
        }]

    def test_varios_tributos_se_suman(self):
        req = _req(
            PABLO, RECEPTOR_RI, alicuota=None, importe_neto=Decimal("500.00"),
            tributos=(
                Tributo(id=1, base_imponible=Decimal("500.00"), alicuota_pct=Decimal("1"),
                        importe=Decimal("5.00")),
                Tributo(id=7, base_imponible=Decimal("500.00"), alicuota_pct=Decimal("3"),
                        importe=Decimal("15.00")),
            ),
        )
        imp = calcular_importes(req)
        assert imp["tributos"] == Decimal("20.00")

    def test_sin_desc_no_incluye_el_campo(self):
        req = _req(
            PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"),
            tributos=(
                Tributo(id=7, base_imponible=Decimal("1000.00"), alicuota_pct=Decimal("3"),
                        importe=Decimal("30.00")),  # sin desc
            ),
        )
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert "Desc" not in det["Tributos"]["Tributo"][0]


# ---------------------------------------------------------------------------
# Opcionales — transporte genérico (id, valor), sin reglas de negocio propias
# ---------------------------------------------------------------------------


class TestOpcionales:
    def test_opcionales_pasan_tal_cual_al_payload(self):
        req = _req(
            PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"),
            opcionales=(Opcional(id="2101", valor="0000003100012345678"),),
        )
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["Opcionales"]["Opcional"] == [
            {"Id": "2101", "Valor": "0000003100012345678"}
        ]

    def test_sin_opcionales_no_aparece_el_nodo(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert "Opcionales" not in det


# ---------------------------------------------------------------------------
# Conceptos no gravados / operaciones exentas — antes hardcodeados en 0
# ---------------------------------------------------------------------------


class TestNoGravadoYExento:
    def test_importe_no_gravado_y_exento_entran_en_el_total(self):
        req = _req(
            PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"),
            importe_no_gravado=Decimal("50.00"), importe_exento=Decimal("25.00"),
        )
        imp = calcular_importes(req)
        assert imp["totconc"] == Decimal("50.00")
        assert imp["opex"] == Decimal("25.00")
        # 1000 neto + 50 totconc + 25 opex + 210 iva = 1285
        assert imp["total"] == Decimal("1285.00")

        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["ImpTotConc"] == "50.00"
        assert det["ImpOpEx"] == "25.00"

    def test_default_sigue_dando_cero(self):
        req = _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00"))
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert det["ImpTotConc"] == "0.00"
        assert det["ImpOpEx"] == "0.00"


# ---------------------------------------------------------------------------
# forzar_cbte_tipo — bypass explícito de la selección automática A/B/C
# ---------------------------------------------------------------------------


class TestForzarCbteTipo:
    def test_ri_puede_forzar_m(self):
        req = _req(PABLO, RECEPTOR_RI, forzar_cbte_tipo=CbteTipo.FACTURA_M)
        assert tipo_comprobante(req) == CbteTipo.FACTURA_M

    def test_ri_puede_forzar_nota_credito_m(self):
        req = _req(
            PABLO, RECEPTOR_RI, es_nota_credito=True,
            forzar_cbte_tipo=CbteTipo.NOTA_CREDITO_M,
        )
        assert tipo_comprobante(req) == CbteTipo.NOTA_CREDITO_M

    def test_monotributo_no_puede_forzar_m(self):
        """Un Monotributo NUNCA puede discriminar IVA — es una regla legal
        fija, forzar_cbte_tipo no la puede saltear."""
        with pytest.raises(ValueError, match="MONOTRIBUTO"):
            _req(
                SANTINI, RECEPTOR_CF, alicuota=None,
                forzar_cbte_tipo=CbteTipo.FACTURA_M,
            )

    def test_ri_no_puede_forzar_tipo_c(self):
        """Un RI no puede forzar un tipo C — no discrimina IVA, no le corresponde."""
        with pytest.raises(ValueError, match="RESPONSABLE_INSCRIPTO"):
            _req(PABLO, RECEPTOR_RI, forzar_cbte_tipo=CbteTipo.FACTURA_C)

    def test_forzar_cbte_tipo_se_propaga_a_armar_fecae(self):
        req = _req(PABLO, RECEPTOR_RI, forzar_cbte_tipo=CbteTipo.FACTURA_M)
        payload = armar_fecae(req, 1)
        assert payload["FeCabReq"]["CbteTipo"] == int(CbteTipo.FACTURA_M)
        # M discrimina IVA igual que A — el nodo Iva sigue apareciendo
        det = payload["FeDetReq"]["FECAEDetRequest"][0]
        assert "Iva" in det


# ---------------------------------------------------------------------------
# FCE MiPyme — reglas verificadas contra el manual oficial WSFEv1 (no
# hardcodeamos si la operación DEBE ser FCE, solo la estructura si lo es)
# ---------------------------------------------------------------------------


class TestFce:
    def test_fce_factura_a_con_cbu_y_vto_pago_ok(self):
        req = _req(
            PABLO, RECEPTOR_RI,
            forzar_cbte_tipo=CbteTipo.FACTURA_CRED_ELEC_MIPYME_A,
            fecha_vto_pago=date(2024, 2, 15),
            opcionales=(Opcional(id="2101", valor="0000003100012345678"),),
        )
        payload = armar_fecae(req, 1)
        assert payload["FeCabReq"]["CbteTipo"] == int(CbteTipo.FACTURA_CRED_ELEC_MIPYME_A)
        det = payload["FeDetReq"]["FECAEDetRequest"][0]
        assert det["FchVtoPago"] == "20240215"

    def test_fce_factura_con_alias_en_vez_de_cbu_tambien_ok(self):
        req = _req(
            PABLO, RECEPTOR_RI,
            forzar_cbte_tipo=CbteTipo.FACTURA_CRED_ELEC_MIPYME_B,
            fecha_vto_pago=date(2024, 2, 15),
            opcionales=(Opcional(id="2102", valor="mi.alias.cbu"),),
        )
        armar_fecae(req, 1)  # no levanta

    def test_fce_factura_sin_vto_pago_levanta_aunque_concepto_sea_productos(self):
        """A diferencia de _validar_fechas_servicio (solo aplica a Concepto
        SERVICIOS/PRODUCTOS_Y_SERVICIOS), FCE exige FchVtoPago SIEMPRE."""
        with pytest.raises(ValueError, match="fecha_vto_pago"):
            _req(
                PABLO, RECEPTOR_RI,
                concepto=Concepto.PRODUCTOS,
                fecha_serv_desde=None, fecha_serv_hasta=None, fecha_vto_pago=None,
                forzar_cbte_tipo=CbteTipo.FACTURA_CRED_ELEC_MIPYME_A,
                opcionales=(Opcional(id="2101", valor="0000003100012345678"),),
            )

    def test_fce_factura_sin_cbu_alias_ni_transferencia_levanta(self):
        with pytest.raises(ValueError, match="CBU"):
            _req(
                PABLO, RECEPTOR_RI,
                forzar_cbte_tipo=CbteTipo.FACTURA_CRED_ELEC_MIPYME_A,
                fecha_vto_pago=date(2024, 2, 15),
                opcionales=(),
            )

    def test_fce_nota_credito_exige_codigo_anulacion(self):
        with pytest.raises(ValueError, match="Anulación"):
            _req(
                PABLO, RECEPTOR_RI, es_nota_credito=True,
                forzar_cbte_tipo=CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A,
                opcionales=(),
            )

    def test_fce_nota_credito_con_codigo_anulacion_ok(self):
        req = _req(
            PABLO, RECEPTOR_RI, es_nota_credito=True,
            forzar_cbte_tipo=CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A,
            opcionales=(Opcional(id="22", valor="S"),),
        )
        armar_fecae(req, 1)  # no levanta

    def test_fce_nota_credito_no_puede_llevar_cbu(self):
        with pytest.raises(ValueError, match="no puede llevar"):
            _req(
                PABLO, RECEPTOR_RI, es_nota_credito=True,
                forzar_cbte_tipo=CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A,
                opcionales=(
                    Opcional(id="22", valor="S"),
                    Opcional(id="2101", valor="0000003100012345678"),
                ),
            )

    def test_fce_c_permitido_para_monotributo(self):
        """FCE-C es la variante MiPyme para el emisor Monotributo (sin
        discriminar IVA, igual que C común)."""
        req = _req(
            SANTINI, RECEPTOR_CF, alicuota=None,
            forzar_cbte_tipo=CbteTipo.FACTURA_CRED_ELEC_MIPYME_C,
            fecha_vto_pago=date(2024, 2, 15),
            opcionales=(Opcional(id="2101", valor="0000003100012345678"),),
        )
        payload = armar_fecae(req, 1)
        det = payload["FeDetReq"]["FECAEDetRequest"][0]
        assert "Iva" not in det  # C no discrimina IVA, ni siendo FCE

    def test_fce_a_no_permitido_para_monotributo(self):
        with pytest.raises(ValueError, match="MONOTRIBUTO"):
            _req(
                SANTINI, RECEPTOR_CF, alicuota=None,
                forzar_cbte_tipo=CbteTipo.FACTURA_CRED_ELEC_MIPYME_A,
            )


# ---------------------------------------------------------------------------
# _validar_estructura — guardas estructurales fail-fast (gap 10), corren en
# ComprobanteRequest.__post_init__ (construcción) Y en armar_fecae/_lote.
# ---------------------------------------------------------------------------


class TestValidacionEstructural:
    def test_punto_venta_fuera_de_rango_levanta(self):
        emisor_pto_invalido = Emisor(
            cuit=20123456786, punto_venta=10000, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO
        )
        with pytest.raises(ValueError, match="punto_venta"):
            _req(emisor_pto_invalido, RECEPTOR_RI)

    def test_punto_venta_cero_levanta(self):
        emisor_pto_invalido = Emisor(
            cuit=20123456786, punto_venta=0, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO
        )
        with pytest.raises(ValueError, match="punto_venta"):
            _req(emisor_pto_invalido, RECEPTOR_RI)

    def test_importe_neto_negativo_levanta(self):
        with pytest.raises(ValueError, match="importe_neto"):
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("-100.00"))

    def test_importe_no_gravado_negativo_levanta(self):
        with pytest.raises(ValueError, match="importe_no_gravado"):
            _req(PABLO, RECEPTOR_RI, importe_no_gravado=Decimal("-1.00"))

    def test_importe_exento_negativo_levanta(self):
        with pytest.raises(ValueError, match="importe_exento"):
            _req(PABLO, RECEPTOR_RI, importe_exento=Decimal("-1.00"))

    def test_alicuota_iva_base_imponible_negativa_levanta(self):
        with pytest.raises(ValueError, match="base_imponible"):
            _req(
                PABLO, RECEPTOR_RI, alicuota=None,
                alicuotas_iva=(ItemIva(IVA_21, Decimal("-100.00")),),
            )

    def test_tributo_importe_negativo_levanta(self):
        with pytest.raises(ValueError, match="tributos: importe"):
            _req(
                PABLO, RECEPTOR_RI,
                tributos=(
                    Tributo(id=7, base_imponible=Decimal("100.00"), alicuota_pct=Decimal("3"),
                            importe=Decimal("-3.00")),
                ),
            )

    def test_tributo_id_no_positivo_levanta(self):
        with pytest.raises(ValueError, match="tributos: id"):
            _req(
                PABLO, RECEPTOR_RI,
                tributos=(
                    Tributo(id=0, base_imponible=Decimal("100.00"), alicuota_pct=Decimal("3"),
                            importe=Decimal("3.00")),
                ),
            )

    def test_tributo_alicuota_pct_fuera_de_rango_levanta(self):
        with pytest.raises(ValueError, match="alicuota_pct"):
            _req(
                PABLO, RECEPTOR_RI,
                tributos=(
                    Tributo(id=7, base_imponible=Decimal("100.00"), alicuota_pct=Decimal("101"),
                            importe=Decimal("3.00")),
                ),
            )

    def test_opcional_id_vacio_levanta(self):
        with pytest.raises(ValueError, match="opcionales"):
            _req(PABLO, RECEPTOR_RI, opcionales=(Opcional(id="", valor="algo"),))

    def test_opcional_valor_vacio_levanta(self):
        with pytest.raises(ValueError, match="opcionales"):
            _req(PABLO, RECEPTOR_RI, opcionales=(Opcional(id="2101", valor=""),))

    def test_moneda_distinta_de_3_caracteres_levanta(self):
        with pytest.raises(ValueError, match="moneda"):
            _req(PABLO, RECEPTOR_RI, moneda="PESOS")

    def test_moneda_se_normaliza_a_mayuscula(self):
        req = _req(PABLO, RECEPTOR_RI, moneda="pes")
        assert req.moneda == "PES"

    def test_cotizacion_cero_levanta(self):
        with pytest.raises(ValueError, match="cotizacion"):
            _req(PABLO, RECEPTOR_RI, cotizacion=Decimal("0"))

    def test_cotizacion_negativa_levanta(self):
        with pytest.raises(ValueError, match="cotizacion"):
            _req(PABLO, RECEPTOR_RI, cotizacion=Decimal("-1"))

    def test_receptor_consumidor_final_con_doc_nro_distinto_de_cero_levanta(self):
        with pytest.raises(ValueError, match="CONSUMIDOR_FINAL"):
            Receptor(
                doc_tipo=DocTipo.CONSUMIDOR_FINAL, doc_nro=123,
                condicion_iva=CondicionIva.CONSUMIDOR_FINAL,
            )

    def test_caso_valido_no_levanta_nada(self):
        """Contraprueba: un ComprobanteRequest bien formado no dispara ninguna
        de las guardas nuevas."""
        req = _req(PABLO, RECEPTOR_RI)
        assert req.moneda == "PES"


# ---------------------------------------------------------------------------
# armar_fecae_lote — facturación por lote (gap 9): homogeneidad + tope + CAE
# individual por ítem, todo sin red (el armado del payload es puro).
# ---------------------------------------------------------------------------


PABLO_OTRO_PTO_VTA = Emisor(
    cuit=20123456786, punto_venta=99, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO
)


class TestArmarFecaeLote:
    def test_lote_vacio_levanta(self):
        with pytest.raises(ValueError, match="vacía"):
            armar_fecae_lote([], 1)

    def test_lote_homogeneo_arma_cant_reg_y_numeros_consecutivos(self):
        reqs = [
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00")),
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("2000.00")),
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("3000.00")),
        ]
        payload = armar_fecae_lote(reqs, 10)

        assert payload["FeCabReq"]["CantReg"] == 3
        assert payload["FeCabReq"]["PtoVta"] == 1
        detalles = payload["FeDetReq"]["FECAEDetRequest"]
        assert [d["CbteDesde"] for d in detalles] == [10, 11, 12]
        assert [d["CbteHasta"] for d in detalles] == [10, 11, 12]
        assert detalles[0]["ImpNeto"] == "1000.00"
        assert detalles[1]["ImpNeto"] == "2000.00"
        assert detalles[2]["ImpNeto"] == "3000.00"

    def test_lote_con_distinto_cbte_tipo_levanta(self):
        """PABLO (RI) emite A, SANTINI (Monotributo) emite C — mezclar los dos
        en un lote viola la regla de homogeneidad de AFIP."""
        reqs = [
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00")),
            _req(SANTINI, RECEPTOR_CF, alicuota=None, importe_neto=Decimal("500.00")),
        ]
        with pytest.raises(ValueError, match="mismo cbte_tipo"):
            armar_fecae_lote(reqs, 1)

    def test_lote_con_distinto_punto_venta_levanta(self):
        reqs = [
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("1000.00")),
            _req(PABLO_OTRO_PTO_VTA, RECEPTOR_RI, importe_neto=Decimal("500.00")),
        ]
        with pytest.raises(ValueError, match="mismo emisor"):
            armar_fecae_lote(reqs, 1)

    def test_lote_supera_el_tope_levanta(self):
        from arca_fe.comprobante import _MAX_LOTE

        reqs = [
            _req(PABLO, RECEPTOR_RI, importe_neto=Decimal("100.00"))
            for _ in range(_MAX_LOTE + 1)
        ]
        with pytest.raises(ValueError, match="supera el tope"):
            armar_fecae_lote(reqs, 1)
