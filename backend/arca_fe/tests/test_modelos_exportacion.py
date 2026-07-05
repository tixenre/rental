"""Tests de arca_fe.modelos_exportacion — Factura de Exportación (WSFEXv1).
Puros, sin red, sin DB."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from arca_fe.modelos import CondicionIva, Concepto, Emisor
from arca_fe.modelos_exportacion import (
    CbteAsocExportacion,
    CbteTipoExportacion,
    ComprobanteExportacionRequest,
    DatosExportacion,
    ReceptorExterior,
    es_nota_credito_exportacion,
)

pytestmark = pytest.mark.unit

_EMISOR = Emisor(
    cuit=20123456786, punto_venta=1, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO
)
_RECEPTOR = ReceptorExterior(razon_social="Acme Corp", pais_destino_id=203)
_EXPORTACION = DatosExportacion(incoterm="fob", permiso_embarque="24001EC01000123X")


def _request(**overrides) -> ComprobanteExportacionRequest:
    base = dict(
        emisor=_EMISOR,
        receptor=_RECEPTOR,
        exportacion=_EXPORTACION,
        concepto=Concepto.PRODUCTOS,
        importe_neto=Decimal("1000"),
        fecha=date(2026, 7, 1),
        moneda="usd",
        cotizacion=Decimal("1000"),
    )
    base.update(overrides)
    return ComprobanteExportacionRequest(**base)


class TestCbteTipoExportacion:
    def test_valores_correctos(self):
        assert CbteTipoExportacion.FACTURA_E == 19
        assert CbteTipoExportacion.NOTA_DEBITO_E == 20
        assert CbteTipoExportacion.NOTA_CREDITO_E == 21

    def test_es_nota_credito_exportacion(self):
        assert es_nota_credito_exportacion(CbteTipoExportacion.NOTA_CREDITO_E) is True
        assert es_nota_credito_exportacion(CbteTipoExportacion.FACTURA_E) is False
        assert es_nota_credito_exportacion(CbteTipoExportacion.NOTA_DEBITO_E) is False


class TestReceptorExterior:
    def test_construccion_valida(self):
        r = ReceptorExterior(razon_social="Acme Corp", pais_destino_id=203, domicilio="123 Main St")
        assert r.razon_social == "Acme Corp"
        assert r.pais_destino_id == 203

    def test_razon_social_vacia_falla(self):
        with pytest.raises(ValueError, match="razon_social"):
            ReceptorExterior(razon_social="   ", pais_destino_id=203)

    def test_pais_destino_invalido_falla(self):
        with pytest.raises(ValueError, match="pais_destino_id"):
            ReceptorExterior(razon_social="Acme Corp", pais_destino_id=0)
        with pytest.raises(ValueError, match="pais_destino_id"):
            ReceptorExterior(razon_social="Acme Corp", pais_destino_id=-1)


class TestDatosExportacion:
    def test_normaliza_incoterm_a_mayuscula(self):
        d = DatosExportacion(incoterm="fob", permiso_embarque="X")
        assert d.incoterm == "FOB"

    def test_incoterm_vacio_falla(self):
        with pytest.raises(ValueError, match="incoterm"):
            DatosExportacion(incoterm="  ", permiso_embarque="X")

    def test_permiso_embarque_obligatorio_si_existe(self):
        with pytest.raises(ValueError, match="permiso_embarque"):
            DatosExportacion(incoterm="FOB", permiso_embarque="")

    def test_permiso_embarque_no_obligatorio_si_no_existe(self):
        d = DatosExportacion(incoterm="FOB", permiso_embarque="", permiso_existente=False)
        assert d.permiso_embarque == ""


class TestCbteAsocExportacion:
    def test_construccion_valida_sin_cuit(self):
        c = CbteAsocExportacion(tipo=CbteTipoExportacion.FACTURA_E, punto_venta=1, numero=42)
        assert c.tipo == CbteTipoExportacion.FACTURA_E
        assert c.cuit is None

    def test_normaliza_cuit_con_guiones(self):
        c = CbteAsocExportacion(
            tipo=CbteTipoExportacion.FACTURA_E, punto_venta=1, numero=42, cuit="20-12345678-6"
        )
        assert c.cuit == 20123456786

    def test_cuit_invalido_falla(self):
        with pytest.raises(ValueError, match="CbteAsocExportacion.cuit"):
            CbteAsocExportacion(
                tipo=CbteTipoExportacion.FACTURA_E, punto_venta=1, numero=42, cuit=11111111111
            )


class TestComprobanteExportacionRequest:
    def test_construccion_valida(self):
        req = _request()
        assert req.moneda == "USD"
        assert req.concepto == Concepto.PRODUCTOS

    def test_normaliza_moneda_a_mayuscula(self):
        req = _request(moneda="usd")
        assert req.moneda == "USD"

    def test_moneda_longitud_invalida_falla(self):
        with pytest.raises(ValueError, match="moneda"):
            _request(moneda="dolares")

    def test_importe_neto_no_positivo_falla(self):
        with pytest.raises(ValueError, match="importe_neto"):
            _request(importe_neto=Decimal("0"))
        with pytest.raises(ValueError, match="importe_neto"):
            _request(importe_neto=Decimal("-100"))

    def test_cotizacion_no_positiva_falla(self):
        with pytest.raises(ValueError, match="cotizacion"):
            _request(cotizacion=Decimal("0"))

    def test_nota_credito_sin_comprobante_asociado_falla(self):
        with pytest.raises(ValueError, match="comprobante asociado"):
            _request(es_nota_credito=True)

    def test_nota_credito_con_comprobante_asociado_ok(self):
        asoc = CbteAsocExportacion(tipo=CbteTipoExportacion.FACTURA_E, punto_venta=1, numero=42)
        req = _request(es_nota_credito=True, cbtes_asoc=(asoc,))
        assert req.es_nota_credito is True
        assert req.cbtes_asoc == (asoc,)

    def test_forzar_cbte_tipo_normaliza_a_enum(self):
        req = _request(forzar_cbte_tipo=20)
        assert req.forzar_cbte_tipo == CbteTipoExportacion.NOTA_DEBITO_E
