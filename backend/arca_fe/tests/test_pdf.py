"""Tests de arca_fe.pdf — render HTML de los 3 layouts de comprobante. Puros, sin red, sin DB
(portado de `backend/tests/test_facturacion_pdf.py`, construyendo `ComprobanteFiscal` directo en
vez de mockear `database.get_db`/catálogos — ya no hace falta, todo llega resuelto)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe import CbteTipo, CondicionIva, DocTipo, Emisor, Receptor
from arca_fe.modelos import ComprobanteFiscal, ItemFactura
from arca_fe.pdf import (
    _iva_pct_label,
    nombre_fiscal_comprobante,
    page_size_for_layout,
    renderizar_comprobante_html,
)

pytestmark = pytest.mark.unit

_EMISOR = Emisor(cuit=20123456786, punto_venta=2, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
_RECEPTOR_CF = Receptor(doc_tipo=DocTipo.DNI, doc_nro=42289220, condicion_iva=CondicionIva.CONSUMIDOR_FINAL)
_RECEPTOR_RI = Receptor(doc_tipo=DocTipo.CUIT, doc_nro=27111222334, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)

_ITEM = ItemFactura(
    codigo="001", descripcion="Rambla #422", precio_unitario=Decimal("5700"),
    subtotal=Decimal("5700"),
)


def _comprobante(**overrides) -> ComprobanteFiscal:
    base = dict(
        cbte_tipo=CbteTipo.FACTURA_C,
        pto_vta=2,
        numero=1,
        fecha_emision=date(2026, 7, 1),
        cae="86261839900000",
        cae_vto=date(2026, 7, 15),
        qr_url="https://www.afip.gob.ar/fe/qr/?p=xyz",
        emisor=_EMISOR,
        emisor_razon_social="Rambla SRL",
        receptor=_RECEPTOR_CF,
        receptor_nombre="Ignacio Beramendi",
        concepto_label="Servicios",
        doc_tipo_label="DNI",
        condicion_iva_receptor_label="Consumidor Final",
        emisor_condicion_iva_label="Responsable Monotributo",
        items=(_ITEM,),
        importe_neto=Decimal("5700"),
        importe_iva=Decimal("0"),
        importe_total=Decimal("5700"),
        periodo_desde=date(2026, 6, 30),
        periodo_hasta=date(2026, 7, 1),
        vencimiento_pago=date(2026, 6, 30),
    )
    base.update(overrides)
    return ComprobanteFiscal(**base)


# ── nombre_fiscal_comprobante ────────────────────────────────────────────────


def test_nombre_fiscal_comprobante_formato():
    assert nombre_fiscal_comprobante(CbteTipo.FACTURA_C, pto_vta=2, numero=1) == "C-00002-00000001"


def test_nombre_fiscal_comprobante_nota_credito_misma_letra():
    assert nombre_fiscal_comprobante(CbteTipo.NOTA_CREDITO_C, pto_vta=2, numero=1) == "C-00002-00000001"


# ── renderizar_comprobante_html: smoke test de los 3 layouts ────────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_genera_documento_valido(layout):
    html = renderizar_comprobante_html(_comprobante(), layout=layout)
    assert html.startswith("<!DOCTYPE html>")
    assert "86261839900000" in html  # CAE
    assert "5.700,00" in html  # total formateado es-AR


def test_layout_desconocido_cae_al_default_celular():
    html = renderizar_comprobante_html(_comprobante(), layout="no-existe")
    html_celular = renderizar_comprobante_html(_comprobante(), layout="celular")
    assert html == html_celular


def test_page_size_solo_celular_tiene_tamano_propio_4x5_fijo():
    assert page_size_for_layout("clasica") is None
    assert page_size_for_layout("formal") is None
    assert page_size_for_layout("celular") == (688, 860)


# ── QR clickeable — el link real de verificación, no la home de ARCA ───────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_qr_queda_envuelto_en_link_clickeable(layout):
    html = renderizar_comprobante_html(_comprobante(), layout=layout)
    assert '<a href="https://www.afip.gob.ar/fe/qr/?p=xyz"' in html


# ── fonts_css: opcional, la marca nunca es requisito de validez ────────────


def test_sin_fonts_css_sigue_siendo_valido():
    html = renderizar_comprobante_html(_comprobante(), layout="celular", fonts_css="")
    assert html.startswith("<!DOCTYPE html>")
    assert "86261839900000" in html


def test_fonts_css_se_inyecta_tal_cual():
    html = renderizar_comprobante_html(
        _comprobante(), layout="celular", fonts_css="<style>@font-face{font-family:'X'}</style>"
    )
    assert "@font-face{font-family:'X'}" in html


# ── Regresión: NC en celular/formal dice "Nota de Crédito" ─────────────────


@pytest.mark.parametrize("layout", ["celular", "formal"])
def test_nc_en_celular_y_formal_dice_nota_de_credito(layout):
    nc = _comprobante(cbte_tipo=CbteTipo.NOTA_CREDITO_C)
    html = renderizar_comprobante_html(nc, layout=layout).lower()
    assert "nota de crédito" in html
    assert "factura electrónica" not in html


def test_factura_en_formal_dice_factura_electronica():
    html = renderizar_comprobante_html(_comprobante(), layout="formal").lower()
    assert "factura electrónica" in html
    assert "nota de crédito" not in html


def test_clasica_ya_distinguia_nc_del_titulo():
    nc = _comprobante(cbte_tipo=CbteTipo.NOTA_CREDITO_C)
    html = renderizar_comprobante_html(nc, layout="clasica")
    assert "NOTA DE CRÉDITO" in html


# ── IVA discriminado solo en A/B, nunca en C ─────────────────────────────────


def test_factura_c_no_discrimina_iva():
    html = renderizar_comprobante_html(_comprobante(), layout="clasica")
    assert "IVA 21%" not in html


def test_factura_a_discrimina_iva_si_hay_monto():
    fa = _comprobante(
        cbte_tipo=CbteTipo.FACTURA_A, receptor=_RECEPTOR_RI,
        condicion_iva_receptor_label="Responsable Inscripto",
        importe_neto=Decimal("4711"), importe_iva=Decimal("989"), importe_total=Decimal("5700"),
    )
    html = renderizar_comprobante_html(fa, layout="clasica")
    assert "IVA 21%" in html


def test_iva_pct_se_calcula_no_se_hardcodea():
    fa = _comprobante(
        cbte_tipo=CbteTipo.FACTURA_A, receptor=_RECEPTOR_RI,
        importe_neto=Decimal("10000"), importe_iva=Decimal("1050"), importe_total=Decimal("11050"),
    )
    html = renderizar_comprobante_html(fa, layout="clasica")
    assert "IVA 10,5%" in html


def test_iva_pct_27_tambien_se_reconoce():
    assert _iva_pct_label(1000, 270) == "27%"
    assert _iva_pct_label(1000, 210) == "21%"
    assert _iva_pct_label(1000, 105) == "10,5%"
    assert _iva_pct_label(1000, 0) == "0%"


# ── Ley 27.743 / RG 5614 — Transparencia Fiscal al Consumidor ───────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_factura_c_incluye_leyenda_transparencia_fiscal(layout):
    html = renderizar_comprobante_html(_comprobante(), layout=layout)
    assert "Régimen de Transparencia Fiscal al Consumidor (Ley 27.743)" in html
    assert "IVA Contenido" in html
    assert "Otros Impuestos Nacionales Indirectos" in html


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_factura_a_no_lleva_leyenda_transparencia_fiscal(layout):
    fa = _comprobante(
        cbte_tipo=CbteTipo.FACTURA_A, receptor=_RECEPTOR_RI,
        importe_neto=Decimal("4711"), importe_iva=Decimal("989"), importe_total=Decimal("5700"),
    )
    html = renderizar_comprobante_html(fa, layout=layout)
    assert "Transparencia Fiscal" not in html


def test_leyenda_transparencia_fiscal_usa_el_iva_real_no_hardcodeado():
    fb = _comprobante(
        cbte_tipo=CbteTipo.FACTURA_B, receptor=_RECEPTOR_CF,
        importe_neto=Decimal("10000"), importe_iva=Decimal("2100"), importe_total=Decimal("12100"),
    )
    html = renderizar_comprobante_html(fb, layout="clasica")
    assert "IVA Contenido: $ 2.100,00" in html


# ── Emisor/receptor: domicilio faltante muestra guion, no un hueco ──────────


def test_emisor_sin_domicilio_muestra_guion_no_hueco():
    html = renderizar_comprobante_html(_comprobante(emisor_domicilio=""), layout="clasica")
    assert "Domicilio Comercial:</span> —" in html


def test_emisor_con_domicilio_se_muestra():
    html = renderizar_comprobante_html(
        _comprobante(emisor_domicilio="Ruta 88 km 12, Mar del Plata"), layout="clasica"
    )
    assert "Ruta 88 km 12" in html


# ── QR: si falla la generación, propaga el error (no un hueco donde debería
# ir el QR exigido por RG4892) ───────────────────────────────────────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_si_falla_la_generacion_del_qr_propaga_el_error(layout, monkeypatch):
    def _boom(url, size):
        raise RuntimeError("segno no disponible")

    monkeypatch.setattr("arca_fe.pdf._build_qr_svg", _boom)
    with pytest.raises(RuntimeError, match="segno no disponible"):
        renderizar_comprobante_html(_comprobante(), layout=layout)


# ── Concepto/labels: lo que ya llega resuelto se muestra tal cual ──────────


def test_concepto_label_se_muestra_tal_cual():
    html = renderizar_comprobante_html(_comprobante(concepto_label="Productos"), layout="celular")
    assert "Productos" in html


def test_doc_tipo_label_se_muestra_tal_cual():
    html = renderizar_comprobante_html(_comprobante(doc_tipo_label="DNI"), layout="clasica")
    assert "DNI" in html
