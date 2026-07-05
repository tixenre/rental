"""Tests del cliente WSFEXv1 — sin red.

Mismo criterio que `test_wsfe_param.py`: mockea zeep con `spec=` para que un typo de campo en
`wsfex.py` (leer un atributo que la respuesta real no tendría) reviente el mock, no pase en
silencio."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _fake_comprobante():
    from arca_fe.modelos import CondicionIva, Concepto, Emisor
    from arca_fe.modelos_exportacion import ComprobanteExportacionRequest, DatosExportacion, ReceptorExterior

    emisor = Emisor(cuit=20301234563, punto_venta=3, condicion_iva=CondicionIva.RESPONSABLE_INSCRIPTO)
    receptor = ReceptorExterior(razon_social="Acme Corp", pais_destino_id=203)
    exportacion = DatosExportacion(incoterm="FOB", permiso_embarque="X")
    return ComprobanteExportacionRequest(
        emisor=emisor, receptor=receptor, exportacion=exportacion, concepto=Concepto.PRODUCTOS,
        importe_neto=Decimal("1000.00"), fecha=date(2026, 7, 1), moneda="USD",
        cotizacion=Decimal("1000"),
    )


def test_client_cache_separado_del_de_wsfe():
    """El cache de `wsfex.py` es un dict propio, distinto del de `wsfe.py` — no comparten
    namespace ni se pisan entre sí."""
    from arca_fe import wsfe, wsfex

    assert wsfex._CLIENT_CACHE is not wsfe._CLIENT_CACHE


def test_wsfex_wsaa_servicio_constante():
    from arca_fe.wsfex import WSFEX_WSAA_SERVICIO

    assert WSFEX_WSAA_SERVICIO == "wsfex"


class TestUltimoAutorizado:
    def test_devuelve_el_numero(self):
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")
        resp = MagicMock(spec=["Cbte_nro", "FEXErr"])
        resp.Cbte_nro = 42
        resp.FEXErr = None

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXGetLast_CMP.return_value = resp
            assert client.ultimo_autorizado(pto_vta=1, cbte_tipo=19) == 42

    def test_nunca_emitido_devuelve_cero(self):
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")
        resp = MagicMock(spec=["Cbte_nro", "FEXErr"])
        resp.Cbte_nro = 0
        resp.FEXErr = None

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXGetLast_CMP.return_value = resp
            assert client.ultimo_autorizado(pto_vta=1, cbte_tipo=19) == 0


class TestAutorizar:
    def _make_resp(
        self,
        resultado: str,
        cae: Optional[str] = None,
        cae_vto: Optional[str] = None,
        cbte_nro: int = 1,
        err: Optional[tuple[int, str]] = None,
    ):
        auth_fields = ["Resultado", "Cae", "Fch_venc_Cae", "Cbte_nro"]
        fex_auth = MagicMock(spec=auth_fields)
        fex_auth.Resultado = resultado
        fex_auth.Cae = cae
        fex_auth.Fch_venc_Cae = cae_vto
        fex_auth.Cbte_nro = cbte_nro

        resp = MagicMock(spec=["FEXResultAuth", "FEXErr", "FEXEvents"])
        resp.FEXResultAuth = fex_auth
        resp.FEXEvents = None
        if err:
            fex_err = MagicMock(spec=["ErrCode", "ErrMsg"])
            fex_err.ErrCode, fex_err.ErrMsg = err
            resp.FEXErr = fex_err
        else:
            resp.FEXErr = None
        return resp

    def test_aprobado_devuelve_cae(self):
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")
        resp = self._make_resp("A", cae="12345678901234", cae_vto="20260801", cbte_nro=1)

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXAuthorize.return_value = resp
            resultado = client.autorizar(_fake_comprobante(), numero=1)

        assert resultado.resultado == "A"
        assert resultado.cae == "12345678901234"
        assert resultado.cae_vto == date(2026, 8, 1)
        assert resultado.numero == 1

    def test_rechazado_expone_errores(self):
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")
        resp = self._make_resp("R", err=(500, "CUIT no autorizado a operar en exportación"))

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXAuthorize.return_value = resp
            resultado = client.autorizar(_fake_comprobante(), numero=1)

        assert resultado.resultado == "R"
        assert resultado.cae is None
        assert any("500" in e for e in resultado.errores)

    def test_sin_fexresultauth_levanta_error_tipado(self):
        from arca_fe.errores import ArcaResponseError
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")
        resp = MagicMock(spec=["FEXResultAuth", "FEXErr"])
        resp.FEXResultAuth = None
        resp.FEXErr = None

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXAuthorize.return_value = resp
            with pytest.raises(ArcaResponseError, match="FEXResultAuth"):
                client.autorizar(_fake_comprobante(), numero=1)


class TestParamCatalogos:
    def test_param_paises_destino(self):
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")
        pais = MagicMock(spec=["DST_CODIGO", "DST_Ds"])
        pais.DST_CODIGO = 203
        pais.DST_Ds = "ESTADOS UNIDOS"
        result_get = MagicMock(spec=["Dst_pais"])
        result_get.Dst_pais = [pais]
        resp = MagicMock(spec=["FEXResultGet", "FEXErr"])
        resp.FEXResultGet = result_get
        resp.FEXErr = None

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXGetPARAM_DST_pais.return_value = resp
            paises = client.param_paises_destino()

        assert len(paises) == 1

    def test_error_de_negocio_levanta_arcabusinesserror(self):
        from arca_fe.errores import ArcaBusinessError
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")
        fex_err = MagicMock(spec=["ErrCode", "ErrMsg"])
        fex_err.ErrCode = 601
        fex_err.ErrMsg = "CUIT no encontrado"
        resp = MagicMock(spec=["FEXResultGet", "FEXErr"])
        resp.FEXErr = fex_err

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXGetPARAM_Incoterms.return_value = resp
            with pytest.raises(ArcaBusinessError, match="601"):
                client.param_incoterms()


class TestSoapFaultTraducido:
    def test_fault_de_zeep_se_traduce_a_arcaresponseerror(self):
        import zeep.exceptions

        from arca_fe.errores import ArcaResponseError
        from arca_fe.wsfex import WsfexClient

        client = WsfexClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")

        with patch.object(client, "_client") as mock_client_fn:
            mock_client_fn.return_value.service.FEXAuthorize.side_effect = zeep.exceptions.Fault(
                "boom"
            )
            with pytest.raises(ArcaResponseError, match="SOAP Fault"):
                client.autorizar(_fake_comprobante(), numero=1)
