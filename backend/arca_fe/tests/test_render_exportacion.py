"""Tests de arca_fe.render_exportacion — HTML de la Factura de Exportación (WSFEXv1). Puros, sin
red, sin DB."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe.modelos import ItemFactura
from arca_fe.modelos_exportacion import CbteTipoExportacion, ComprobanteFiscalExportacion
from arca_fe.render_exportacion import renderizar_factura_exportacion_html

pytestmark = pytest.mark.unit

_ITEM = ItemFactura(
    codigo="001", descripcion="Cámara XYZ", precio_unitario=Decimal("1000"),
    subtotal=Decimal("1000"),
)


def _comprobante(**overrides) -> ComprobanteFiscalExportacion:
    base = dict(
        cbte_tipo=CbteTipoExportacion.FACTURA_E,
        pto_vta=3,
        numero=1,
        fecha_emision=date(2026, 7, 5),
        emisor_cuit="20300000003",
        emisor_razon_social="Santini SRL",
        emisor_condicion_iva_label="Responsable Monotributo",
        emisor_domicilio="Calle Falsa 123",
        receptor_razon_social="Acme Corp",
        receptor_pais_destino_label="Estados Unidos",
        receptor_domicilio="5th Ave",
        receptor_id_impositivo="US-123456",
        incoterm="FOB",
        permiso_embarque="X123",
        moneda="USD",
        cotizacion=Decimal("1000"),
        items=(_ITEM,),
        importe_total=Decimal("1000"),
        cae="70012345670000",
        cae_vto=date(2030, 1, 1),
        qr_url="https://www.afip.gob.ar/fe/qr/?p=xyz",
    )
    base.update(overrides)
    return ComprobanteFiscalExportacion(**base)


def test_renderiza_html_con_datos_clave():
    html = renderizar_factura_exportacion_html(_comprobante())
    assert "FACTURA E" in html
    assert "Acme Corp" in html
    assert "Estados Unidos" in html
    assert "FOB" in html
    assert "X123" in html
    assert "70012345670000" in html
    assert "USD" in html
    # Sin discriminación de IVA — no hay renglón de desglose (solo la condición IVA del emisor,
    # que es un dato fiscal del emisor, no un renglón de importe)
    assert "Importe Neto Gravado" not in html
    assert "IVA 21%" not in html


def test_nota_credito_muestra_titulo_correcto():
    html = renderizar_factura_exportacion_html(
        _comprobante(cbte_tipo=CbteTipoExportacion.NOTA_CREDITO_E)
    )
    assert "NOTA DE CRÉDITO E" in html


def test_falla_sin_cae():
    with pytest.raises(ValueError, match="cae"):
        _comprobante(cae="")


def test_falla_sin_qr_url():
    with pytest.raises(ValueError, match="qr_url"):
        _comprobante(qr_url="")
