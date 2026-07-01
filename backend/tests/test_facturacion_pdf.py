"""Tests de services.facturacion.pdf — templates HTML de la factura (3 layouts).

Sin red, sin Playwright: solo la construcción del contexto (`_build_ctx`) y el
HTML resultante. Cubre la regresión de la NC en celular/formal (el banner de
tipo de documento estaba hardcodeado a "Factura electrónica" en los dos,
incluso para una Nota de Crédito).
"""
from __future__ import annotations

from datetime import date

import pytest

from services.facturacion.pdf import factura_filename, factura_html, page_size_for_layout
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit


def _factura(**overrides) -> Factura:
    base = dict(
        id=14, pedido_id=422, emisor="santini", ambiente="produccion",
        cbte_tipo=11, pto_vta=2, cbte_nro=1, cae="86261839900000",
        cae_vto=date(2026, 7, 15), doc_tipo=96, doc_nro="42289220",
        condicion_iva_receptor=5, concepto=2, imp_neto=5700, imp_iva=0,
        imp_total=5700, moneda="PES", cliente_cuit=None, razon_social=None,
        qr_payload="https://www.afip.gob.ar/fe/qr/?p=xyz", pdf_key=None,
        estado="emitida", nota_credito_de=None, raw_request=None,
        raw_response=None, errores=None, fecha_emision=date(2026, 7, 1),
        created_at=None, created_by=None,
    )
    base.update(overrides)
    return Factura(**base)


def _pedido(**overrides) -> dict:
    base = dict(
        id=422, numero_pedido="422", cliente_nombre="Ignacio Beramendi",
        cliente_domicilio_fiscal=None, fecha_desde="2026-06-30",
        fecha_hasta="2026-07-01", cantidad_jornadas=1,
        monto_total=5700, monto_pagado=5700, items=[],
    )
    base.update(overrides)
    return base


# ── factura_filename ─────────────────────────────────────────────────────────


def test_filename_clasica_sin_sufijo():
    f = _factura()
    assert factura_filename(f) == "Factura-C-00002-00000001.pdf"


def test_filename_celular_con_sufijo():
    f = _factura()
    assert factura_filename(f, layout="celular") == "Factura-C-00002-00000001-celular.pdf"


def test_filename_nc_usa_prefijo_nc():
    f = _factura(cbte_tipo=13)  # NOTA_CREDITO_C
    assert factura_filename(f) == "NC-C-00002-00000001.pdf"


# ── factura_html: smoke test de los 3 layouts ───────────────────────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_factura_html_genera_documento_valido(layout):
    html = factura_html(_factura(), _pedido(), layout=layout)
    assert html.startswith("<!DOCTYPE html>")
    assert "86261839900000" in html  # CAE
    assert "5.700,00" in html  # total formateado es-AR


def test_layout_desconocido_cae_a_clasica():
    html = factura_html(_factura(), _pedido(), layout="no-existe")
    html_clasica = factura_html(_factura(), _pedido(), layout="clasica")
    assert html == html_clasica


def test_page_size_solo_celular_tiene_ancho_propio():
    assert page_size_for_layout("clasica") is None
    assert page_size_for_layout("formal") is None
    assert page_size_for_layout("celular") == (392, None)


# ── Regresión: NC en celular/formal tiene que decir "Nota de crédito" ───────
# (estaba hardcodeado a "Factura electrónica" en los dos, sin importar es_nc)


@pytest.mark.parametrize("layout", ["celular", "formal"])
def test_nc_en_celular_y_formal_dice_nota_de_credito(layout):
    nc = _factura(cbte_tipo=13, nota_credito_de=1)  # NOTA_CREDITO_C
    html = factura_html(nc, _pedido(), layout=layout)
    assert "Nota de crédito" in html
    assert "Factura electrónica" not in html


@pytest.mark.parametrize("layout", ["celular", "formal"])
def test_factura_en_celular_y_formal_dice_factura_electronica(layout):
    html = factura_html(_factura(), _pedido(), layout=layout)
    assert "Factura electrónica" in html
    assert "Nota de crédito" not in html


def test_clasica_ya_distinguia_nc_del_titulo():
    """La clásica no tenía el bug (usa `titulo`, no un banner hardcodeado)."""
    nc = _factura(cbte_tipo=13, nota_credito_de=1)
    html = factura_html(nc, _pedido(), layout="clasica")
    assert "NOTA DE CRÉDITO" in html


# ── IVA discriminado solo en A/B, nunca en C ─────────────────────────────────


def test_factura_c_no_discrimina_iva():
    html = factura_html(_factura(cbte_tipo=11, imp_iva=0), _pedido(), layout="clasica")
    assert "IVA 21%" not in html


def test_factura_a_discrimina_iva_si_hay_monto():
    fa = _factura(cbte_tipo=1, imp_neto=4711, imp_iva=989, imp_total=5700, condicion_iva_receptor=1)
    html = factura_html(fa, _pedido(), layout="clasica")
    assert "IVA 21%" in html


# ── QR ausente: placeholder, nunca un hueco en blanco ───────────────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_sin_qr_payload_muestra_placeholder(layout):
    sin_qr = _factura(qr_payload=None)
    html = factura_html(sin_qr, _pedido(), layout=layout)
    assert "<img" not in html or "QR AFIP" not in html


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_si_falla_la_generacion_del_qr_no_deja_un_hueco_en_blanco(layout, monkeypatch):
    """Hay payload (has=True) pero segno/la generación de la imagen falla —
    tiene que caer al placeholder, no a un <img> roto o un div vacío."""
    def _boom(url):
        raise RuntimeError("segno no disponible")

    monkeypatch.setattr("arca_fe.qr._build_qr_image_data_uri", _boom)
    html = factura_html(_factura(), _pedido(), layout=layout)
    assert "<img" not in html
