"""Tests del armado del QR fiscal RG4892."""
from __future__ import annotations

import base64
import json
from datetime import date
from decimal import Decimal

import pytest

from arca_fe import armar_qr
from arca_fe.modelos import DocTipo


def _decode_qr(url: str) -> dict:
    """Extrae y decodifica el payload base64 de la URL del QR."""
    assert "?p=" in url, f"URL sin parámetro p: {url}"
    b64 = url.split("?p=")[1]
    return json.loads(base64.b64decode(b64).decode())


def test_url_prefix():
    url = armar_qr(
        cuit_emisor=20123456789,
        pto_vta=1,
        cbte_tipo=1,
        nro_cmp=5,
        importe_total=Decimal("1210.00"),
        doc_tipo_rec=int(DocTipo.CUIT),
        doc_nro_rec=27111222333,
        cae="70417054367476",
        fecha=date(2024, 1, 15),
    )
    assert url.startswith("https://www.afip.gob.ar/fe/qr/?p=")


def test_payload_campos():
    url = armar_qr(
        cuit_emisor=20123456789,
        pto_vta=1,
        cbte_tipo=1,
        nro_cmp=5,
        importe_total=Decimal("1210.00"),
        doc_tipo_rec=int(DocTipo.CUIT),
        doc_nro_rec=27111222333,
        cae="70417054367476",
        fecha=date(2024, 1, 15),
    )
    p = _decode_qr(url)
    assert p["ver"] == 1
    assert p["fecha"] == "2024-01-15"
    assert p["cuit"] == 20123456789
    assert p["ptoVta"] == 1
    assert p["tipoCmp"] == 1
    assert p["nroCmp"] == 5
    assert p["importe"] == pytest.approx(1210.00)
    assert p["moneda"] == "PES"
    assert p["ctz"] == 1
    assert p["tipoDocRec"] == int(DocTipo.CUIT)
    assert p["nroDocRec"] == 27111222333
    assert p["tipoCodAut"] == "E"
    assert p["codAut"] == 70417054367476


def test_payload_decodifica_base64_valido():
    url = armar_qr(
        cuit_emisor=30987654321,
        pto_vta=2,
        cbte_tipo=11,  # Factura C
        nro_cmp=1,
        importe_total=Decimal("500.00"),
        doc_tipo_rec=int(DocTipo.CONSUMIDOR_FINAL),
        doc_nro_rec=0,
        cae="12345678901234",
        fecha=date(2024, 6, 30),
    )
    p = _decode_qr(url)
    assert p["tipoCmp"] == 11
    assert p["importe"] == pytest.approx(500.00)
    assert p["fecha"] == "2024-06-30"


def test_importe_dos_decimales():
    # El importe debe tener 2 decimales; sin overflow de float en el JSON
    url = armar_qr(
        cuit_emisor=20123456789,
        pto_vta=1,
        cbte_tipo=1,
        nro_cmp=1,
        importe_total=Decimal("333.33"),
        doc_tipo_rec=int(DocTipo.CUIT),
        doc_nro_rec=27111222333,
        cae="99999999999999",
        fecha=date(2024, 1, 1),
    )
    p = _decode_qr(url)
    assert p["importe"] == pytest.approx(333.33)


# ── SVG vectorial: sin resolución nativa fija, no se pixela en ningún zoom ──
# (bug real: un PNG con resolución fija se veía pixelado al hacer zoom o al
# pasar por la compresión de WhatsApp — la misma imagen se reusaba achicada
# en las 3 facturas, la más chica (celular) la mostraba a 78px)


def test_qr_es_svg_vectorial_no_bitmap():
    from arca_fe.qr import _build_qr_svg

    svg = _build_qr_svg("https://www.afip.gob.ar/fe/qr/?p=" + "x" * 180, size=150)
    assert svg.startswith("<svg ")
    assert "<path" in svg  # vectorial: dibujado con paths, no un <image>/bitmap
    assert 'width="150"' in svg
    assert 'height="150"' in svg
    assert "viewBox=" in svg  # preserva la proporción interna al escalar


