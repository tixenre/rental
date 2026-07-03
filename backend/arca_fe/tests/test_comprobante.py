"""Tests del core puro: tipo, importes, payload AFIP."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe import (
    IVA_21,
    CbteTipo,
    Concepto,
    CondicionIva,
    DocTipo,
    Emisor,
    Receptor,
    armar_fecae,
    calcular_importes,
    tipo_comprobante,
)
from arca_fe.modelos import CbteAsoc, ComprobanteRequest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PABLO = Emisor(cuit=20123456789, punto_venta=1, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
SANTINI = Emisor(cuit=30987654321, punto_venta=2, condicion_iva=CondicionIva.MONOTRIBUTO)

RECEPTOR_RI = Receptor(
    doc_tipo=DocTipo.CUIT,
    doc_nro=27111222333,
    condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO,
)
RECEPTOR_CF = Receptor(
    doc_tipo=DocTipo.CONSUMIDOR_FINAL,
    doc_nro=0,
    condicion_iva=CondicionIva.CONSUMIDOR_FINAL,
)
RECEPTOR_MONO = Receptor(
    doc_tipo=DocTipo.CUIT,
    doc_nro=20987654321,
    condicion_iva=CondicionIva.MONOTRIBUTO,
)
RECEPTOR_EXENTO = Receptor(
    doc_tipo=DocTipo.CUIT,
    doc_nro=33555666777,
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
        assert det["DocNro"] == 27111222333

    def test_nc_con_cbte_asoc(self):
        asoc = CbteAsoc(
            tipo=CbteTipo.FACTURA_A,
            punto_venta=1,
            numero=10,
            cuit=20123456789,
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
        legalmente no corresponde. Ahora levanta ValueError explícito."""
        emisor_invalido = Emisor(
            cuit=20111222333, punto_venta=1, condicion_iva=CondicionIva.EXENTO
        )
        req = _req(emisor_invalido, RECEPTOR_RI, alicuota=None)
        with pytest.raises(ValueError, match="EXENTO"):
            tipo_comprobante(req)

    def test_armar_fecae_tambien_propaga_el_guardrail_de_condicion_iva(self):
        emisor_invalido = Emisor(
            cuit=20111222333, punto_venta=1, condicion_iva=CondicionIva.CONSUMIDOR_FINAL
        )
        req = _req(emisor_invalido, RECEPTOR_RI, alicuota=None)
        with pytest.raises(ValueError, match="CONSUMIDOR_FINAL"):
            armar_fecae(req, 1)

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
        req = _req(PABLO, RECEPTOR_RI, concepto=concepto, **kwargs)
        with pytest.raises(ValueError, match=campo_ausente):
            armar_fecae(req, 1)

    def test_concepto_productos_no_exige_fechas_de_servicio(self):
        """Concepto PRODUCTOS (sin servicio) NO exige estas fechas — el
        guardrail es específico de SERVICIOS/PRODUCTOS_Y_SERVICIOS."""
        req = _req(
            PABLO, RECEPTOR_RI, concepto=Concepto.PRODUCTOS,
            fecha_serv_desde=None, fecha_serv_hasta=None, fecha_vto_pago=None,
        )
        det = armar_fecae(req, 1)["FeDetReq"]["FECAEDetRequest"][0]
        assert "FchServDesde" not in det
