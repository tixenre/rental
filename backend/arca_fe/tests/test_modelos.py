"""Tests de arca_fe.modelos — ComprobanteFiscal/ItemFactura/letra_comprobante/es_nota_credito.
Puros, sin red, sin DB."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe import CbteTipo, CondicionIva, DocTipo, Emisor, Receptor
from arca_fe.modelos import (
    CaeResult,
    ComprobanteFiscal,
    ComprobanteRequest,
    Concepto,
    ItemFactura,
    comprobante_fiscal_desde,
    es_nota_credito,
    label_concepto,
    label_condicion_iva,
    label_doc_tipo,
    letra_comprobante,
)

pytestmark = pytest.mark.unit

_RECEPTOR = Receptor(
    doc_tipo=DocTipo.CUIT, doc_nro=27111222334, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO
)


def _comprobante(**overrides) -> ComprobanteFiscal:
    base = dict(
        cbte_tipo=CbteTipo.FACTURA_A,
        pto_vta=1,
        numero=42,
        fecha_emision=date(2026, 7, 1),
        cae="71234567890123",
        cae_vto=date(2026, 7, 11),
        qr_url="https://www.afip.gob.ar/fe/qr/?p=abc123",
        emisor_cuit="20123456786",
        emisor_razon_social="Rambla SRL",
        receptor=_RECEPTOR,
        receptor_nombre="Juan Pérez",
        concepto_label="Productos",
        doc_tipo_label="CUIT",
        condicion_iva_receptor_label="Responsable Inscripto",
        emisor_condicion_iva_label="Responsable Inscripto",
    )
    base.update(overrides)
    return ComprobanteFiscal(**base)


class TestLetraComprobante:
    @pytest.mark.parametrize(
        "cbte_tipo,letra",
        [
            (CbteTipo.FACTURA_A, "A"),
            (CbteTipo.NOTA_CREDITO_A, "A"),
            (CbteTipo.FACTURA_B, "B"),
            (CbteTipo.NOTA_DEBITO_B, "B"),
            (CbteTipo.FACTURA_C, "C"),
            (CbteTipo.NOTA_CREDITO_C, "C"),
            (CbteTipo.FACTURA_M, "M"),
            (CbteTipo.FACTURA_CRED_ELEC_MIPYME_A, "A"),
            (CbteTipo.FACTURA_CRED_ELEC_MIPYME_B, "B"),
            (CbteTipo.FACTURA_CRED_ELEC_MIPYME_C, "C"),
        ],
    )
    def test_deriva_la_letra_correcta(self, cbte_tipo, letra):
        assert letra_comprobante(cbte_tipo) == letra

    def test_acepta_el_valor_int_crudo(self):
        assert letra_comprobante(1) == "A"


class TestEsNotaCredito:
    @pytest.mark.parametrize(
        "cbte_tipo,es_nc",
        [
            (CbteTipo.FACTURA_A, False),
            (CbteTipo.NOTA_DEBITO_A, False),
            (CbteTipo.NOTA_CREDITO_A, True),
            (CbteTipo.NOTA_CREDITO_B, True),
            (CbteTipo.NOTA_CREDITO_C, True),
            (CbteTipo.NOTA_CREDITO_M, True),
            (CbteTipo.NOTA_CREDITO_CRED_ELEC_MIPYME_A, True),
            (CbteTipo.FACTURA_M, False),
        ],
    )
    def test_clasifica_nota_de_credito(self, cbte_tipo, es_nc):
        assert es_nota_credito(cbte_tipo) is es_nc


class TestItemFactura:
    def test_defaults_razonables(self):
        item = ItemFactura(
            codigo="001", descripcion="Alquiler", precio_unitario=Decimal("100"),
            subtotal=Decimal("100"),
        )
        assert item.cantidad == Decimal("1")
        assert item.unidad_medida == "unidad"
        assert item.bonificacion_pct == Decimal("0")


class TestComprobanteFiscal:
    def test_completo_no_falla(self):
        comp = _comprobante()
        assert comp.cbte_tipo == CbteTipo.FACTURA_A
        assert comp.cae == "71234567890123"

    def test_cbte_tipo_se_normaliza_a_enum(self):
        comp = _comprobante(cbte_tipo=1)
        assert comp.cbte_tipo is CbteTipo.FACTURA_A

    @pytest.mark.parametrize("campo", ["cae", "numero", "cae_vto", "qr_url"])
    def test_sin_cae_o_derivados_falla_fuerte(self, campo):
        overrides = {campo: "" if campo in ("cae", "qr_url") else None}
        with pytest.raises(ValueError, match=campo):
            _comprobante(**overrides)

    def test_items_default_vacio(self):
        comp = _comprobante()
        assert comp.items == ()

    def test_items_explicitos(self):
        item = ItemFactura(
            codigo="001", descripcion="Rambla #123", precio_unitario=Decimal("1000"),
            subtotal=Decimal("1000"),
        )
        comp = _comprobante(items=(item,))
        assert comp.items == (item,)

    def test_es_frozen(self):
        comp = _comprobante()
        with pytest.raises(Exception):
            comp.cae = "otro"


class TestLabelsEstructurales:
    def test_label_concepto(self):
        assert label_concepto(Concepto.SERVICIOS) == "Servicios"
        assert label_concepto(Concepto.PRODUCTOS) == "Productos"
        assert label_concepto(Concepto.PRODUCTOS_Y_SERVICIOS) == "Productos y Servicios"

    def test_label_concepto_acepta_el_valor_int_crudo(self):
        assert label_concepto(2) == "Servicios"

    def test_label_doc_tipo(self):
        assert label_doc_tipo(DocTipo.CUIT) == "CUIT"
        assert label_doc_tipo(DocTipo.DNI) == "DNI"
        assert label_doc_tipo(DocTipo.CONSUMIDOR_FINAL) == "Consumidor Final"

    def test_label_condicion_iva(self):
        assert label_condicion_iva(CondicionIva.RESPONSABLE_INSCRIPTO) == "IVA Responsable Inscripto"
        assert label_condicion_iva(CondicionIva.MONOTRIBUTO) == "Responsable Monotributo"

    def test_label_con_valor_invalido_falla_fuerte(self):
        with pytest.raises(ValueError):
            label_doc_tipo(999)


class TestComprobanteFiscalDesde:
    def _request(self, **overrides) -> ComprobanteRequest:
        base = dict(
            emisor=Emisor(cuit=20123456786, punto_venta=1, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO),
            receptor=_RECEPTOR,
            concepto=Concepto.PRODUCTOS,
            importe_neto=Decimal("1000"),
            alicuota=None,
            fecha=date(2026, 7, 1),
        )
        base.update(overrides)
        return ComprobanteRequest(**base)

    def _cae_aprobado(self, **overrides) -> CaeResult:
        base = dict(resultado="A", cae="71234567890123", cae_vto=date(2026, 7, 11), numero=42)
        base.update(overrides)
        return CaeResult(**base)

    def test_copia_los_campos_comunes_sin_pedirlos_de_nuevo(self):
        req = self._request()
        cae = self._cae_aprobado()
        comp = comprobante_fiscal_desde(
            req, CbteTipo.FACTURA_A, cae, "https://www.afip.gob.ar/fe/qr/?p=x",
            Decimal("1000"), Decimal("210"), Decimal("1210"), date(2026, 7, 1),
        )
        assert comp.pto_vta == 1  # de comprobante.emisor.punto_venta
        assert comp.numero == 42  # de cae_result.numero
        assert comp.cae == "71234567890123"
        assert comp.receptor is req.receptor  # reusado tal cual, no reconstruido

    def test_labels_default_a_los_estructurales_si_no_se_pasan(self):
        req = self._request()
        comp = comprobante_fiscal_desde(
            req, CbteTipo.FACTURA_A, self._cae_aprobado(), "https://x",
            Decimal("1000"), Decimal("210"), Decimal("1210"), date(2026, 7, 1),
        )
        assert comp.concepto_label == "Productos"
        assert comp.doc_tipo_label == "CUIT"
        assert comp.condicion_iva_receptor_label == "IVA Responsable Inscripto"
        assert comp.emisor_condicion_iva_label == "IVA Responsable Inscripto"

    def test_labels_explicitos_pisan_el_default(self):
        req = self._request()
        comp = comprobante_fiscal_desde(
            req, CbteTipo.FACTURA_A, self._cae_aprobado(), "https://x",
            Decimal("1000"), Decimal("210"), Decimal("1210"), date(2026, 7, 1),
            concepto_label="Servicios (catálogo vivo)",
        )
        assert comp.concepto_label == "Servicios (catálogo vivo)"

    def test_cae_no_aprobado_falla_fuerte(self):
        req = self._request()
        rechazado = self._cae_aprobado(resultado="R", cae=None, cae_vto=None, numero=None)
        with pytest.raises(ValueError, match="'A'"):
            comprobante_fiscal_desde(
                req, CbteTipo.FACTURA_A, rechazado, "https://x",
                Decimal("1000"), Decimal("210"), Decimal("1210"), date(2026, 7, 1),
            )
