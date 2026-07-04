"""Tests de arca_fe.render — arma el HTML de los 3 layouts de comprobante (oficial/detallada/
simplificada). Puros, sin red, sin DB (portado de `backend/tests/test_comprobante_render.py`,
construyendo `ComprobanteFiscal` directo en vez de mockear `database.get_db`/catálogos — ya no hace
falta, todo llega resuelto)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe import CbteTipo, CondicionIva, DocTipo, Receptor
from arca_fe.modelos import ComprobanteFiscal, ItemFactura
from arca_fe.render import (
    _iva_pct_label,
    nombre_fiscal_comprobante,
    tamano_pagina_layout,
    renderizar_comprobante_html,
    LAYOUTS_INFO,
    LAYOUTS_VALIDOS,
)

pytestmark = pytest.mark.unit

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
        emisor_cuit="20123456786",
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


@pytest.mark.parametrize("layout", ["oficial", "simplificada", "detallada"])
def test_genera_documento_valido(layout):
    html = renderizar_comprobante_html(_comprobante(), layout=layout)
    assert html.startswith("<!DOCTYPE html>")
    assert "86261839900000" in html  # CAE
    assert "5.700,00" in html  # total formateado es-AR


def test_layout_desconocido_cae_al_default_simplificada():
    html = renderizar_comprobante_html(_comprobante(), layout="no-existe")
    html_simplificada = renderizar_comprobante_html(_comprobante(), layout="simplificada")
    assert html == html_simplificada


def test_page_size_solo_simplificada_tiene_tamano_propio_4x5_minimo_1080x1350():
    assert tamano_pagina_layout("oficial") is None
    assert tamano_pagina_layout("detallada") is None
    ancho, alto = tamano_pagina_layout("simplificada")
    assert (ancho, alto) == (1080, 1350)
    assert ancho >= 1080 and alto >= 1350
    assert ancho * 5 == alto * 4  # proporción 4:5 exacta


# ── QR clickeable — el link real de verificación, no la home de ARCA ───────


@pytest.mark.parametrize("layout", ["oficial", "simplificada", "detallada"])
def test_qr_queda_envuelto_en_link_clickeable(layout):
    html = renderizar_comprobante_html(_comprobante(), layout=layout)
    assert '<a href="https://www.afip.gob.ar/fe/qr/?p=xyz"' in html


# ── fonts_css: opcional, la marca nunca es requisito de validez ────────────


def test_sin_fonts_css_sigue_siendo_valido():
    html = renderizar_comprobante_html(_comprobante(), layout="simplificada", fonts_css="")
    assert html.startswith("<!DOCTYPE html>")
    assert "86261839900000" in html


def test_fonts_css_se_inyecta_tal_cual():
    html = renderizar_comprobante_html(
        _comprobante(), layout="simplificada", fonts_css="<style>@font-face{font-family:'X'}</style>"
    )
    assert "@font-face{font-family:'X'}" in html


# ── Regresión: NC en simplificada/detallada dice "Nota de Crédito" ─────────


@pytest.mark.parametrize("layout", ["simplificada", "detallada"])
def test_nc_en_simplificada_y_detallada_dice_nota_de_credito(layout):
    nc = _comprobante(cbte_tipo=CbteTipo.NOTA_CREDITO_C)
    html = renderizar_comprobante_html(nc, layout=layout).lower()
    assert "nota de crédito" in html
    assert "factura electrónica" not in html


def test_factura_en_detallada_dice_factura_electronica():
    html = renderizar_comprobante_html(_comprobante(), layout="detallada").lower()
    assert "factura electrónica" in html
    assert "nota de crédito" not in html


def test_oficial_ya_distinguia_nc_del_titulo():
    nc = _comprobante(cbte_tipo=CbteTipo.NOTA_CREDITO_C)
    html = renderizar_comprobante_html(nc, layout="oficial")
    assert "NOTA DE CRÉDITO" in html


# ── IVA discriminado solo en A/B, nunca en C ─────────────────────────────────


def test_factura_c_no_discrimina_iva():
    html = renderizar_comprobante_html(_comprobante(), layout="oficial")
    assert "IVA 21%" not in html


def test_factura_a_discrimina_iva_si_hay_monto():
    fa = _comprobante(
        cbte_tipo=CbteTipo.FACTURA_A, receptor=_RECEPTOR_RI,
        condicion_iva_receptor_label="Responsable Inscripto",
        importe_neto=Decimal("4711"), importe_iva=Decimal("989"), importe_total=Decimal("5700"),
    )
    html = renderizar_comprobante_html(fa, layout="oficial")
    assert "IVA 21%" in html


def test_iva_pct_se_calcula_no_se_hardcodea():
    fa = _comprobante(
        cbte_tipo=CbteTipo.FACTURA_A, receptor=_RECEPTOR_RI,
        importe_neto=Decimal("10000"), importe_iva=Decimal("1050"), importe_total=Decimal("11050"),
    )
    html = renderizar_comprobante_html(fa, layout="oficial")
    assert "IVA 10,5%" in html


def test_iva_pct_27_tambien_se_reconoce():
    assert _iva_pct_label(1000, 270) == "27%"
    assert _iva_pct_label(1000, 210) == "21%"
    assert _iva_pct_label(1000, 105) == "10,5%"
    assert _iva_pct_label(1000, 0) == "0%"


# ── Ley 27.743 / RG 5614 — Transparencia Fiscal al Consumidor ───────────────


@pytest.mark.parametrize("layout", ["oficial", "simplificada", "detallada"])
def test_factura_c_incluye_leyenda_transparencia_fiscal(layout):
    html = renderizar_comprobante_html(_comprobante(), layout=layout)
    assert "Régimen de Transparencia Fiscal al Consumidor (Ley 27.743)" in html
    assert "IVA Contenido" in html
    assert "Otros Impuestos Nacionales Indirectos" in html


@pytest.mark.parametrize("layout", ["oficial", "simplificada", "detallada"])
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
    html = renderizar_comprobante_html(fb, layout="oficial")
    assert "IVA Contenido: $ 2.100,00" in html


# ── Emisor/receptor: domicilio faltante muestra guion, no un hueco ──────────


def test_emisor_sin_domicilio_muestra_guion_no_hueco():
    html = renderizar_comprobante_html(_comprobante(emisor_domicilio=""), layout="oficial")
    assert "Domicilio Comercial:</span> —" in html


def test_emisor_con_domicilio_se_muestra():
    html = renderizar_comprobante_html(
        _comprobante(emisor_domicilio="Ruta 88 km 12, Mar del Plata"), layout="oficial"
    )
    assert "Ruta 88 km 12" in html


def test_emisor_sin_cuit_configurado_no_rompe_muestra_guion():
    """El CUIT del emisor viene de una consulta de configuración APARTE (no de la
    ComprobanteFiscal ya validada) — un emisor mal configurado o renombrado después de emitir NO
    debe romper el render de una factura vieja, solo mostrar '—'."""
    html = renderizar_comprobante_html(_comprobante(emisor_cuit=""), layout="oficial")
    assert "CUIT:</span> —" in html


def test_emisor_con_cuit_valido_se_formatea_con_guiones():
    html = renderizar_comprobante_html(_comprobante(emisor_cuit="20123456786"), layout="oficial")
    assert "20-12345678-6" in html


def test_emisor_con_cuit_malformado_muestra_crudo_no_rompe():
    html = renderizar_comprobante_html(_comprobante(emisor_cuit="no-es-un-cuit"), layout="oficial")
    assert "no-es-un-cuit" in html


# ── QR: si falla la generación, propaga el error (no un hueco donde debería
# ir el QR exigido por RG4892) ───────────────────────────────────────────────


@pytest.mark.parametrize("layout", ["oficial", "simplificada", "detallada"])
def test_si_falla_la_generacion_del_qr_propaga_el_error(layout, monkeypatch):
    def _boom(url, size):
        raise RuntimeError("segno no disponible")

    monkeypatch.setattr("arca_fe.render.qr_svg", _boom)
    with pytest.raises(RuntimeError, match="segno no disponible"):
        renderizar_comprobante_html(_comprobante(), layout=layout)


# ── Concepto/labels: lo que ya llega resuelto se muestra tal cual ──────────


def test_concepto_label_se_muestra_tal_cual():
    html = renderizar_comprobante_html(_comprobante(concepto_label="Productos"), layout="simplificada")
    assert "Productos" in html


def test_doc_tipo_label_se_muestra_tal_cual():
    html = renderizar_comprobante_html(_comprobante(doc_tipo_label="DNI"), layout="oficial")
    assert "DNI" in html


# ── LAYOUTS_INFO: metadata para que el consumidor arme un selector real ────


def test_layouts_info_ids_coinciden_con_layouts_validos():
    assert tuple(info.id for info in LAYOUTS_INFO) == LAYOUTS_VALIDOS
    assert set(LAYOUTS_VALIDOS) == {"oficial", "detallada", "simplificada"}


def test_layouts_info_todos_tienen_nombre_y_descripcion():
    for info in LAYOUTS_INFO:
        assert info.nombre
        assert info.descripcion


def test_solo_simplificada_lleva_advertencia():
    """La advertencia de 'no es para varios ítems con detalle' es específica de la simplificada —
    oficial/detallada sí muestran cantidad/precio unitario, no necesitan la salvedad."""
    por_id = {info.id: info for info in LAYOUTS_INFO}
    assert por_id["simplificada"].advertencia
    assert por_id["oficial"].advertencia == ""
    assert por_id["detallada"].advertencia == ""


# ── Regresión: solo oficial/detallada muestran cantidad y precio unitario;
# simplificada resume el ítem a descripción + importe (la limitación real que
# motiva la advertencia de arriba) ──────────────────────────────────────────


_ITEM_CON_DETALLE = ItemFactura(
    codigo="001", descripcion="Cámara Sony FX3", precio_unitario=Decimal("4.5"),
    cantidad=Decimal("2"), unidad_medida="caja", subtotal=Decimal("9"),
)


def test_simplificada_no_muestra_cantidad_ni_precio_unitario_ni_unidad():
    html = renderizar_comprobante_html(
        _comprobante(items=(_ITEM_CON_DETALLE,)), layout="simplificada"
    )
    assert "Cámara Sony FX3" in html
    assert "caja" not in html  # unidad de medida
    assert "4,50" not in html  # precio unitario


def test_oficial_muestra_cantidad_precio_unitario_y_unidad():
    html = renderizar_comprobante_html(_comprobante(items=(_ITEM_CON_DETALLE,)), layout="oficial")
    assert "Cámara Sony FX3" in html
    assert "caja" in html
    assert "4,50" in html


def test_detallada_muestra_cantidad_y_precio_unitario():
    """`detallada` no repite la unidad de medida (columna propia de `oficial`) pero sí cantidad y
    precio unitario — el nivel de detalle que `simplificada` explícitamente no ofrece."""
    html = renderizar_comprobante_html(_comprobante(items=(_ITEM_CON_DETALLE,)), layout="detallada")
    assert "Cámara Sony FX3" in html
    assert "4,50" in html
