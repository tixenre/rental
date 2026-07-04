"""Tests de arca_fe.modelos — ComprobanteFiscal/ItemFactura/letra_comprobante/es_nota_credito.
Puros, sin red, sin DB."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe import CbteTipo, CondicionIva, DocTipo, Receptor
from arca_fe.modelos import ComprobanteFiscal, ItemFactura, es_nota_credito, letra_comprobante

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
