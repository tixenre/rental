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


# ── Datos legales del emisor: SIEMPRE de la DB, nunca hardcodeados por nombre
# (bug real: un emisor nuevo que no fuera "pablo"/"santini" heredaba en
# silencio la condición IVA / domicilio / IIBB de Santini) ──────────────────


def test_emisor_desconocido_usa_sus_propios_datos_no_los_de_otro(monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.pdf._emisor_row",
        lambda nombre: {
            "razon_social": "Empresa XYZ SRL",
            "cuit": "30-71234567-8",
            "condicion_iva": "exento",
            "domicilio": "Ruta 88 km 12, Mar del Plata",
            "iibb": "IIBB-XYZ-999",
            "inicio_actividades": "01/01/2020",
        },
    )
    f = _factura(emisor="empresa_xyz")
    html = factura_html(f, _pedido(), layout="clasica")

    assert "Empresa XYZ SRL" in html
    assert "Ruta 88 km 12" in html
    assert "IVA Exento" in html
    assert "IIBB-XYZ-999" in html
    # No se cuela ningún dato de otro emisor (el bug viejo hardcodeaba "santini").
    assert "Falucho" not in html
    assert "Monotributo" not in html


def test_emisor_sin_domicilio_configurado_muestra_guion_no_hueco():
    """`domicilio` siempre se muestra (a diferencia de iibb/inicio, que se
    omiten) — sin configurar cae a "—", nunca a un renglón vacío."""
    html = factura_html(_factura(emisor="sin_configurar"), _pedido(), layout="clasica")
    assert "Domicilio Comercial:</span> —" in html


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


# ── Datos de ARCA incompletos: fallar fuerte, nunca un comprobante a medias ──
# (decisión explícita del dueño: mejor un 503 que una factura que "parece"
# válida sin serlo — ni placeholder de QR ni "—" en el CAE)


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_sin_qr_payload_falla_fuerte(layout):
    sin_qr = _factura(qr_payload=None)
    with pytest.raises(RuntimeError, match="qr_payload"):
        factura_html(sin_qr, _pedido(), layout=layout)


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_si_falla_la_generacion_del_qr_propaga_el_error(layout, monkeypatch):
    """Hay payload pero segno/la generación de la imagen falla — tiene que
    propagar el error (el route lo convierte en 503), no devolver un HTML
    con un hueco donde debería ir el QR exigido por RG4892."""
    def _boom(url, size):
        raise RuntimeError("segno no disponible")

    monkeypatch.setattr("arca_fe.qr._build_qr_svg", _boom)
    with pytest.raises(RuntimeError, match="segno no disponible"):
        factura_html(_factura(), _pedido(), layout=layout)


@pytest.mark.parametrize("campo", ["cae", "cbte_nro", "cae_vto", "qr_payload"])
def test_falta_cualquier_dato_de_arca_falla_fuerte(campo):
    incompleta = _factura(**{campo: None})
    with pytest.raises(RuntimeError, match=campo):
        factura_html(incompleta, _pedido())
