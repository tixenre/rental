"""Tests de services.facturacion.comprobante_render — el mapeo Factura+pedido → ComprobanteFiscal
y su delegación a arca_fe. Sin red, sin Playwright.

El contenido/HTML de los 3 layouts (clásica/celular/formal) ya está cubierto en
`arca_fe/tests/test_pdf.py` (construyendo `ComprobanteFiscal` directo) — acá solo se prueba lo que
es responsabilidad de ESTE adapter: resolver el emisor (`emisores_arca`), los catálogos ARCA
(`services.facturacion.catalogos`), el nombre de archivo, y la propagación de errores (fail-fast).
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from services.facturacion.comprobante_render import (
    CONCEPTO_MARCA,
    factura_filename,
    factura_html,
)
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit


# ── Catálogos ARCA (doc_tipo/concepto/condición IVA receptor): en tests se simula que YA se corrió
# "Actualizar catálogos ARCA" (ver services.facturacion.catalogos) con los valores reales vigentes.
_CATALOGOS_SEED = {
    "arca_catalogo_doc_tipo": [
        {"id": 80, "desc": "CUIT"}, {"id": 86, "desc": "CUIL"},
        {"id": 96, "desc": "DNI"}, {"id": 99, "desc": "Documento"},
    ],
    "arca_catalogo_concepto": [
        {"id": 1, "desc": "Productos"}, {"id": 2, "desc": "Servicios"},
        {"id": 3, "desc": "Productos y Servicios"},
    ],
    "arca_catalogo_condicion_iva_receptor": [
        {"id": 1, "desc": "IVA Responsable Inscripto"}, {"id": 4, "desc": "IVA Exento"},
        {"id": 5, "desc": "Consumidor Final"}, {"id": 6, "desc": "Responsable Monotributo"},
    ],
}


class _FakeCatalogConn:
    """Fake de `database.get_db()` — solo entiende el SELECT de `app_settings` que usan los
    catálogos (`_emisor_row` se mockea aparte, por test, cuando hace falta)."""

    def execute(self, sql, params=None):
        key = params[0] if params else None
        value = json.dumps(_CATALOGOS_SEED[key]) if key in _CATALOGOS_SEED else None

        class _R:
            def fetchone(self_inner):
                return {"value": value} if value is not None else None

        return _R()

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _fake_arca_catalogos(monkeypatch):
    monkeypatch.setattr("database.get_db", lambda: _FakeCatalogConn())


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


# ── Datos legales del emisor: SIEMPRE de la DB, nunca hardcodeados por nombre (bug real: un
# emisor nuevo que no fuera "pablo"/"santini" heredaba en silencio la condición IVA / domicilio /
# IIBB de Santini) ────────────────────────────────────────────────────────────


def test_emisor_desconocido_usa_sus_propios_datos_no_los_de_otro(monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.comprobante_render._emisor_row",
        lambda nombre, conn: {
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
    """`domicilio` siempre se muestra (a diferencia de iibb/inicio, que se omiten) — sin
    configurar cae a "—", nunca a un renglón vacío."""
    html = factura_html(_factura(emisor="sin_configurar"), _pedido(), layout="clasica")
    assert "Domicilio Comercial:</span> —" in html


def test_emisor_no_configurado_en_absoluto_no_rompe_muestra_guion():
    """Emisor que ni siquiera tiene fila en `emisores_arca` (renombrado/borrado después de
    facturar) — el render tiene que degradar a "—", no romper (regresión del bug de diseño donde
    `ComprobanteFiscal.emisor` exigía un CUIT ya validado)."""
    html = factura_html(_factura(emisor="no-existe-en-la-base"), _pedido(), layout="clasica")
    assert "CUIT:</span> —" in html


# ── factura_filename ─────────────────────────────────────────────────────────


def test_filename_celular_es_el_default_de_rambla_sin_sufijo():
    f = _factura()
    assert factura_filename(f) == "Factura-C-00002-00000001.pdf"
    assert factura_filename(f, layout="celular") == "Factura-C-00002-00000001.pdf"


def test_filename_clasica_explicita_lleva_sufijo():
    f = _factura()
    assert factura_filename(f, layout="clasica") == "Factura-C-00002-00000001-clasica.pdf"


def test_filename_nc_usa_prefijo_nc():
    f = _factura(cbte_tipo=13)  # NOTA_CREDITO_C
    assert factura_filename(f) == "NC-C-00002-00000001.pdf"


# ── factura_html: smoke test de los 3 layouts (el HTML detallado ya está cubierto en
# arca_fe/tests/test_pdf.py) ─────────────────────────────────────────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_factura_html_genera_documento_valido(layout):
    html = factura_html(_factura(), _pedido(), layout=layout)
    assert html.startswith("<!DOCTYPE html>")
    assert "86261839900000" in html  # CAE
    assert "5.700,00" in html  # total formateado es-AR


def test_layout_desconocido_cae_al_default_de_rambla_celular():
    html = factura_html(_factura(), _pedido(), layout="no-existe")
    html_celular = factura_html(_factura(), _pedido(), layout="celular")
    assert html == html_celular


# ── Concepto: default de Rambla = una sola línea "Rambla #N", sin desglose ──


def test_concepto_es_marca_mas_numero_de_pedido_sin_desglose():
    html = factura_html(_factura(), _pedido(numero_pedido="231"), layout="celular")
    assert "Rambla #231" in html


def test_concepto_ignora_el_desglose_por_equipo_del_pedido():
    """Aunque el pedido tenga varios ítems, la factura muestra una sola línea (decisión de
    negocio de Rambla — no un límite de ARCA)."""
    pedido = _pedido(numero_pedido="231", items=[
        {"nombre": "Cámara Sony FX3", "cantidad": 1, "subtotal": 3000},
        {"nombre": "Trípode Manfrotto", "cantidad": 1, "subtotal": 2700},
    ])
    html = factura_html(_factura(), pedido, layout="celular")
    assert "Rambla #231" in html
    assert "Cámara Sony FX3" not in html
    assert "Trípode Manfrotto" not in html


def test_concepto_marca_es_configurable(monkeypatch):
    monkeypatch.setenv("FACTURACION_CONCEPTO_MARCA", "Otro Negocio")
    import importlib

    import services.facturacion.comprobante_render as render_mod
    importlib.reload(render_mod)
    try:
        html = render_mod.factura_html(_factura(), _pedido(numero_pedido="9"), layout="celular")
        assert "Otro Negocio #9" in html
    finally:
        monkeypatch.delenv("FACTURACION_CONCEPTO_MARCA", raising=False)
        importlib.reload(render_mod)


def test_concepto_marca_default_es_rambla():
    assert CONCEPTO_MARCA == "Rambla"


# ── Datos de ARCA incompletos: fallar fuerte, nunca un comprobante a medias (decisión explícita
# del dueño: mejor un 503 que una factura que "parece" válida sin serlo) ────────────────────────


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_sin_qr_payload_falla_fuerte(layout):
    sin_qr = _factura(qr_payload=None)
    with pytest.raises(ValueError, match="qr_url"):
        factura_html(sin_qr, _pedido(), layout=layout)


@pytest.mark.parametrize("layout", ["clasica", "celular", "formal"])
def test_si_falla_la_generacion_del_qr_propaga_el_error(layout, monkeypatch):
    """Hay payload pero segno/la generación de la imagen falla — tiene que propagar el error (el
    route lo convierte en 503), no devolver un HTML con un hueco donde debería ir el QR exigido
    por RG4892."""
    def _boom(url, size):
        raise RuntimeError("segno no disponible")

    monkeypatch.setattr("arca_fe.pdf._build_qr_svg", _boom)
    with pytest.raises(RuntimeError, match="segno no disponible"):
        factura_html(_factura(), _pedido(), layout=layout)


@pytest.mark.parametrize("campo", ["cae", "cbte_nro", "cae_vto", "qr_payload"])
def test_falta_cualquier_dato_de_arca_falla_fuerte(campo):
    incompleta = _factura(**{campo: None})
    with pytest.raises(ValueError, match="ComprobanteFiscal incompleto"):
        factura_html(incompleta, _pedido())


# ── Etiquetas de doc_tipo/concepto/condición IVA: salen del catálogo de ARCA (cacheado), no de
# una traducción escrita a mano — ver services.facturacion.catalogos ────────────────────────────


def test_doc_tipo_y_condicion_iva_salen_del_catalogo_no_de_un_diccionario_fijo():
    html = factura_html(_factura(doc_tipo=96, condicion_iva_receptor=5), _pedido())
    assert "DNI" in html
    assert "Consumidor Final" in html


def test_catalogo_nunca_refrescado_falla_fuerte_no_completa_con_texto_fijo():
    """Si nadie corrió "Actualizar catálogos ARCA" todavía, el PDF tiene que fallar (503, vía
    RuntimeError de `services.facturacion.catalogos`) en vez de mostrar una traducción inventada."""
    original = dict(_CATALOGOS_SEED)
    _CATALOGOS_SEED.clear()
    try:
        with pytest.raises(RuntimeError, match="todavía no se consultó"):
            factura_html(_factura(), _pedido())
    finally:
        _CATALOGOS_SEED.update(original)
