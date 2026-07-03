"""Tests de services/facturacion/pdf.py::_conceptos — reconciliación de líneas.

Bug (#1209, M5): con descuento (el caso común — cualquier alquiler de varios
días tiene descuento automático por jornadas), las líneas de la Factura
mostraban el BRUTO (sin descuento) y traían un `bonif` hardcodeado en
`0,00`, mientras el "Importe Neto Gravado"/"Importe Total" declarado ya
tenía el descuento aplicado — el comprobante no cerraba consigo mismo
(bruto de las líneas ≠ neto declarado, sin ningún renglón que explicara la
diferencia). Ahora `_conceptos` reparte la bonificación proporcionalmente
entre las líneas (remanente de redondeo en la última) para que la suma de
`subtotalFmt` cierre EXACTO con `factura.imp_neto` — mismo criterio
bruto→descuento→neto que ya usaba el Presupuesto (`pdf_templates._pedido_html`).
"""
from __future__ import annotations

import pytest

from services.facturacion.pdf import _conceptos, _plain
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit


def _fake_factura(imp_neto: int, imp_iva: int = 0) -> Factura:
    return Factura(
        id=1, pedido_id=1, emisor="santini", ambiente="homologacion",
        cbte_tipo=11, pto_vta=2, cbte_nro=1, cae="86261839900000", cae_vto=None,
        doc_tipo=96, doc_nro="42289220", condicion_iva_receptor=5,
        concepto=2, imp_neto=imp_neto, imp_iva=imp_iva,
        imp_total=imp_neto + imp_iva, moneda="PES",
        cliente_cuit=None, razon_social=None, qr_payload=None, pdf_key=None,
        estado="emitida", nota_credito_de=None, raw_request=None,
        raw_response=None, errores=None, fecha_emision=None,
        created_at=None, created_by=None,
    )


def _neto(concepto: dict) -> float:
    """`subtotalFmt` ('450,00') → 450.0 — reversa exacta de `_plain`."""
    return float(concepto["subtotalFmt"].replace(".", "").replace(",", "."))


class TestConceptosConDescuento:
    def test_reparte_bonificacion_y_cierra_con_el_neto_declarado(self):
        # Ejemplo del hallazgo: 2 ítems de $500 (=$1.000 bruto) + 10% de
        # descuento → monto_total=$900 (imp_neto de la factura).
        pedido = {
            "cantidad_jornadas": 1,
            "items": [
                {"nombre": "Item A", "cantidad": 1, "precio_jornada": 500, "subtotal": 500},
                {"nombre": "Item B", "cantidad": 1, "precio_jornada": 500, "subtotal": 500},
            ],
        }
        factura = _fake_factura(imp_neto=900)

        conceptos = _conceptos(pedido, factura)

        assert len(conceptos) == 2
        # % Bonif. real (ya no hardcodeado en "0,00").
        assert conceptos[0]["bonif"] == "10,00"
        assert conceptos[1]["bonif"] == "10,00"
        # Cada línea muestra el NETO (post-bonif), no el bruto.
        assert conceptos[0]["subtotalFmt"] == _plain(450)
        assert conceptos[1]["subtotalFmt"] == _plain(450)
        # La suma de las líneas cierra EXACTO con el neto declarado.
        assert sum(_neto(c) for c in conceptos) == pytest.approx(900)

    def test_ejemplo_del_mail_una_camara_tres_jornadas(self):
        # $10.000/día × 3 jornadas = $30.000 bruto, 10% de descuento → $27.000.
        pedido = {
            "cantidad_jornadas": 3,
            "items": [
                {"nombre": "Cámara", "cantidad": 1, "precio_jornada": 10000, "subtotal": 30000},
            ],
        }
        factura = _fake_factura(imp_neto=27000)

        conceptos = _conceptos(pedido, factura)

        assert conceptos[0]["bonif"] == "10,00"
        assert conceptos[0]["subtotalFmt"] == _plain(27000)
        assert sum(_neto(c) for c in conceptos) == pytest.approx(27000)

    def test_remanente_de_redondeo_no_deja_centavos_sueltos(self):
        # Brutos que no dividen limpio por el % de descuento: el reparto
        # proporcional per-línea redondea distinto que el total → sin el
        # remanente en la última línea, la suma no cerraría exacto.
        pedido = {
            "cantidad_jornadas": 1,
            "items": [
                {"nombre": "A", "cantidad": 1, "precio_jornada": 333, "subtotal": 333},
                {"nombre": "B", "cantidad": 1, "precio_jornada": 333, "subtotal": 333},
                {"nombre": "C", "cantidad": 1, "precio_jornada": 334, "subtotal": 334},
            ],
        }
        # bruto total = 1000, descuento total = 333 (imp_neto = 667).
        factura = _fake_factura(imp_neto=667)

        conceptos = _conceptos(pedido, factura)

        assert sum(_neto(c) for c in conceptos) == pytest.approx(667)


class TestConceptosSinDescuento:
    def test_bonif_cero_y_subtotal_igual_al_bruto(self):
        # Regresión: un pedido sin descuento no debe verse afectado — el
        # bonif sigue en "0,00" y el subtotal de línea es el bruto tal cual.
        pedido = {
            "cantidad_jornadas": 2,
            "items": [
                {"nombre": "Ítem", "cantidad": 1, "precio_jornada": 1000, "subtotal": 2000},
            ],
        }
        factura = _fake_factura(imp_neto=2000)

        conceptos = _conceptos(pedido, factura)

        assert conceptos[0]["bonif"] == "0,00"
        assert conceptos[0]["subtotalFmt"] == _plain(2000)

    def test_sin_items_cae_a_una_sola_linea_con_el_neto_de_la_factura(self):
        # Comportamiento preexistente, sin tocar: pedidos viejos sin líneas
        # persistidas caen a una sola línea con el neto de la factura.
        factura = _fake_factura(imp_neto=5700)
        conceptos = _conceptos({"items": []}, factura)

        assert len(conceptos) == 1
        assert conceptos[0]["bonif"] == "0,00"
        assert conceptos[0]["subtotalFmt"] == _plain(5700)
