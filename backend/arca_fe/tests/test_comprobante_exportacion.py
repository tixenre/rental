"""Tests de arca_fe.comprobante_exportacion — payload FEXAuthorize. Puros, sin red, sin DB."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe.comprobante_exportacion import (
    armar_fexauthorize,
    tipo_comprobante_exportacion,
)
from arca_fe.modelos import CondicionIva, Concepto, Emisor
from arca_fe.modelos_exportacion import (
    CbteAsocExportacion,
    CbteTipoExportacion,
    ComprobanteExportacionRequest,
    DatosExportacion,
    ReceptorExterior,
)

pytestmark = pytest.mark.unit

_EMISOR_RI = Emisor(cuit=20123456786, punto_venta=1, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
_EMISOR_MONO = Emisor(cuit=30987654321, punto_venta=2, condicion_iva=CondicionIva.MONOTRIBUTO)
_RECEPTOR = ReceptorExterior(razon_social="Acme Corp", pais_destino_id=203, domicilio="123 Main St")
_EXPORTACION = DatosExportacion(incoterm="FOB", permiso_embarque="24001EC01000123X")


def _request(**overrides) -> ComprobanteExportacionRequest:
    base = dict(
        emisor=_EMISOR_RI,
        receptor=_RECEPTOR,
        exportacion=_EXPORTACION,
        concepto=Concepto.PRODUCTOS,
        importe_neto=Decimal("1000"),
        fecha=date(2026, 7, 1),
        moneda="USD",
        cotizacion=Decimal("1000"),
    )
    base.update(overrides)
    return ComprobanteExportacionRequest(**base)


class TestTipoComprobanteExportacion:
    def test_default_es_factura_e(self):
        assert tipo_comprobante_exportacion(_request()) == CbteTipoExportacion.FACTURA_E

    def test_nota_credito_resuelve_nota_credito_e(self):
        asoc = CbteAsocExportacion(tipo=CbteTipoExportacion.FACTURA_E, punto_venta=1, numero=42)
        req = _request(es_nota_credito=True, cbtes_asoc=(asoc,))
        assert tipo_comprobante_exportacion(req) == CbteTipoExportacion.NOTA_CREDITO_E

    def test_forzar_cbte_tipo_gana(self):
        req = _request(forzar_cbte_tipo=CbteTipoExportacion.NOTA_DEBITO_E)
        assert tipo_comprobante_exportacion(req) == CbteTipoExportacion.NOTA_DEBITO_E


class TestArmarFexauthorize:
    def test_estructura_basica(self):
        payload = armar_fexauthorize(_request(), numero=1)
        cmp = payload["Cmp"]
        assert cmp["Cbte_tipo"] == CbteTipoExportacion.FACTURA_E
        assert cmp["Punto_vta"] == 1
        assert cmp["Cbte_nro"] == 1
        assert cmp["Fecha_cbte"] == "20260701"
        assert cmp["Pais_dst_cmp"] == 203
        assert cmp["Nombre_cliente"] == "Acme Corp"
        assert cmp["Moneda_id"] == "USD"
        assert cmp["Moneda_ctz"] == 1000.0
        assert cmp["Imp_total"] == "1000.00"
        assert cmp["Incoterm"] == "FOB"

    def test_permiso_existente_arma_nodo_permisos(self):
        payload = armar_fexauthorize(_request(), numero=1)
        assert payload["Cmp"]["Permiso_existente"] == "S"
        assert payload["Cmp"]["Permisos"]["Permiso"][0]["Id_permiso"] == "24001EC01000123X"

    def test_sin_permiso_no_arma_nodo_permisos(self):
        exportacion = DatosExportacion(incoterm="FOB", permiso_existente=False)
        payload = armar_fexauthorize(_request(exportacion=exportacion), numero=1)
        assert payload["Cmp"]["Permiso_existente"] == "N"
        assert "Permisos" not in payload["Cmp"]

    def test_cbtes_asoc_se_incluyen(self):
        asoc = CbteAsocExportacion(tipo=CbteTipoExportacion.FACTURA_E, punto_venta=1, numero=42)
        req = _request(es_nota_credito=True, cbtes_asoc=(asoc,))
        payload = armar_fexauthorize(req, numero=2)
        assert payload["Cmp"]["Cbte_tipo"] == CbteTipoExportacion.NOTA_CREDITO_E
        assert payload["Cmp"]["Cbtes_asoc"]["Cbte_asoc"][0]["Cbte_nro"] == 42

    def test_emisor_condicion_iva_invalida_falla(self):
        emisor_exento = Emisor(cuit=20123456786, punto_venta=1, condicion_iva=CondicionIva.EXENTO)
        with pytest.raises(ValueError, match="no soportada"):
            _request(emisor=emisor_exento)

    def test_emisor_monotributo_ok(self):
        payload = armar_fexauthorize(_request(emisor=_EMISOR_MONO), numero=1)
        assert payload["Cmp"]["Punto_vta"] == 2
