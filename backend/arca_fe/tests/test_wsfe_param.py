"""Tests del cliente WSFEv1 — sin red.

Prueba el parseo de fechas, la normalización del endpoint, y la lógica de parseo
de respuestas CAE (éxito y rechazo) con objetos mock en vez de llamadas SOAP reales.
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests de _parse_fecha
# ---------------------------------------------------------------------------


def test_parse_fecha_8_digitos():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha("20241201") == date(2024, 12, 1)


def test_parse_fecha_iso():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha("2024-12-01") == date(2024, 12, 1)


def test_parse_fecha_none():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha(None) is None


def test_parse_fecha_vacio():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha("") is None


def test_parse_fecha_malformada_loguea_y_devuelve_none(caplog):
    """Una fecha con formato inesperado (no vacía) → None PERO logueada, no
    tragada en silencio. Cubre también el caso de 8 chars no-dígitos, que
    antes podía explotar con ValueError sin manejar."""
    import logging
    from arca_fe.wsfe import _parse_fecha

    with caplog.at_level(logging.WARNING, logger="arca_fe.wsfe"):
        assert _parse_fecha("2024-6-1x") is None
        assert _parse_fecha("aaaabbcc") is None  # 8 chars, no dígitos
    assert sum("formato inesperado" in r.message for r in caplog.records) == 2


# ---------------------------------------------------------------------------
# Tests de parseo de respuesta FECAESolicitar
# ---------------------------------------------------------------------------


# Nombres de campo verificados contra el WSDL real de WSFEv1
# (https://.../wsfev1/service.asmx?WSDL): el detalle FECAEDetResponse expone
# Resultado/CAE/CAEFchVto/CbteDesde/Observaciones/Errors; la respuesta,
# FeDetResp/Errors. `spec=` acá hace que un typo de campo en wsfe.py (leer un
# atributo que la respuesta real no tiene) reviente el mock — que es cómo se
# coló el bug de `personaReturn` cuando el mock NO tenía spec.
_DET_FIELDS = ["Resultado", "CAE", "CAEFchVto", "CbteDesde", "Observaciones", "Errors"]
_ERRCONT_FIELDS = ["Err"]
_OBSCONT_FIELDS = ["Obs"]
_ITEM_FIELDS = ["Code", "Msg"]


def _make_items(pares):
    items = []
    for code, msg in pares:
        it = MagicMock(spec=_ITEM_FIELDS)
        it.Code = code
        it.Msg = msg
        items.append(it)
    return items


def _make_det(
    resultado: str,
    cae: Optional[str] = None,
    cae_vto: Optional[str] = None,
    cbte_desde: int = 1,
    obs: Optional[list] = None,
    errs: Optional[list] = None,
):
    """Construye un mock del FECAEDetResponse de zeep (campos del WSDL real)."""
    det = MagicMock(spec=_DET_FIELDS)
    det.Resultado = resultado
    det.CAE = cae
    det.CAEFchVto = cae_vto
    det.CbteDesde = cbte_desde

    if obs:
        obs_container = MagicMock(spec=_OBSCONT_FIELDS)
        obs_container.Obs = _make_items(obs)
        det.Observaciones = obs_container
    else:
        det.Observaciones = None

    if errs:
        err_container = MagicMock(spec=_ERRCONT_FIELDS)
        err_container.Err = _make_items(errs)
        det.Errors = err_container
    else:
        det.Errors = None

    return det


def _make_fecae_response(det, cab_errs: Optional[list] = None):
    resp = MagicMock(spec=["FeDetResp", "Errors"])
    resp.FeDetResp = MagicMock(spec=["FECAEDetResponse"])
    resp.FeDetResp.FECAEDetResponse = [det]
    if cab_errs:
        err_container = MagicMock(spec=_ERRCONT_FIELDS)
        err_container.Err = _make_items(cab_errs)
        resp.Errors = err_container
    else:
        resp.Errors = None
    return resp


def test_solicitar_cae_aprobado():
    """Resultado 'A' devuelve CAE + fecha de vencimiento."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    det = _make_det("A", cae="12345678901234", cae_vto="20241215", cbte_desde=5)
    mock_resp = _make_fecae_response(det)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.solicitar_cae({})

    assert result.resultado == "A"
    assert result.cae == "12345678901234"
    assert result.cae_vto == date(2024, 12, 15)
    assert result.numero == 5
    assert result.errores == ()


def test_solicitar_cae_rechazado():
    """Resultado 'R' devuelve errores, sin CAE."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    det = _make_det("R", errs=[(10060, "CUIT del receptor no encontrado")])
    mock_resp = _make_fecae_response(det)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.solicitar_cae({})

    assert result.resultado == "R"
    assert result.cae is None
    assert "10060" in result.errores[0]


def test_solicitar_cae_con_observaciones():
    """Resultado 'A' puede traer Observaciones no fatales."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    det = _make_det(
        "A",
        cae="99887766554433",
        cae_vto="20241231",
        cbte_desde=10,
        obs=[(502, "El campo FchServDesde no es obligatorio para este tipo")],
    )
    mock_resp = _make_fecae_response(det)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.solicitar_cae({})

    assert result.resultado == "A"
    assert result.cae == "99887766554433"
    assert len(result.observaciones) == 1
    assert "502" in result.observaciones[0]


def test_solicitar_cae_sin_fedetresp_pero_con_errors_levanta_business():
    """Si AFIP rechaza el pedido COMPLETO (ej. Auth inválido), FeDetResp puede
    venir ausente. `resp.FeDetResp.FECAEDetResponse[0]` a ciegas explotaba con
    un AttributeError/IndexError críptico; ahora se chequea ANTES y se levanta
    ArcaBusinessError con el motivo real de AFIP. (El mock usa spec sin
    FeDetResp — un MagicMock sin spec autogeneraría el campo y ocultaría el
    bug.)"""
    from arca_fe.wsfe import WsfeClient
    from arca_fe.errores import ArcaBusinessError

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    err = MagicMock(spec=_ITEM_FIELDS)
    err.Code = 600
    err.Msg = "Autenticación fallida"
    err_container = MagicMock(spec=_ERRCONT_FIELDS)
    err_container.Err = [err]
    resp = MagicMock(spec=["Errors"])  # NO tiene FeDetResp
    resp.Errors = err_container

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaBusinessError, match="600") as ei:
            client.solicitar_cae({})

    assert ei.value.codigo == 600


def test_solicitar_cae_sin_fedetresp_ni_errors_levanta_response():
    """Respuesta sin FeDetResp y sin Errors — inentendible; ArcaResponseError
    explícito, no un AttributeError."""
    from arca_fe.wsfe import WsfeClient
    from arca_fe.errores import ArcaResponseError

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    resp = MagicMock(spec=[])  # ni FeDetResp ni Errors

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError, match="respuesta inesperada"):
            client.solicitar_cae({})


def test_ultimo_autorizado_mock():
    """FECompUltimoAutorizado devuelve int."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    mock_resp = MagicMock(spec=["CbteNro", "Errors"])
    mock_resp.CbteNro = 42
    mock_resp.Errors = None

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompUltimoAutorizado.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        nro = client.ultimo_autorizado(1, 1)

    assert nro == 42


def test_consultar_no_existe_devuelve_none():
    """FECompConsultar lanza Fault con código 10016 → devuelve None."""
    import zeep.exceptions
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.side_effect = zeep.exceptions.Fault(
            "El comprobante consultado no existe o no pertenece al contribuyente."
        )
        mock_client_fn.return_value.service = mock_service

        result = client.consultar(1, 1, 9999)

    assert result is None


def test_consultar_no_existe_por_error_602_combinacion_virgen():
    """602 = "no existen datos" para (pto_vta, cbte_tipo) SIN historial (ej. la
    primera Nota de Crédito de un punto de venta) — debe tratarse igual que
    10016, no como error real. Bug de prod: bloqueaba con un 503 espurio."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    err = MagicMock(spec=_ITEM_FIELDS)
    err.Code = 602
    err.Msg = "No existen datos en nuestros registros para los parámetros ingresados."
    err_container = MagicMock(spec=_ERRCONT_FIELDS)
    err_container.Err = [err]
    mock_resp = MagicMock(spec=["Errors", "ResultGet"])
    mock_resp.Errors = err_container

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.consultar(2, 13, 1)

    assert result is None


# ── _get_client: usa el endpoint tal cual, sin URLs propias duplicadas ──────


def test_get_client_usa_el_endpoint_tal_cual_y_lo_cachea(monkeypatch):
    """`endpoint` es la URL completa del WSDL, ya resuelta por el caller según
    ambiente — `_get_client` no debe tener su propia copia de las URLs de
    homologación/producción ni adivinar cuál usar por matching de substring
    (regresión: antes, un endpoint que no contuviera "homo"/"wswhomo" caía
    siempre a la URL de PRODUCCIÓN hardcodeada acá, sin importar qué URL le
    hubiera pasado el caller)."""
    from arca_fe import wsfe

    monkeypatch.setattr(wsfe, "_CLIENT_CACHE", {})
    calls = []

    class _FakeZeepClient:
        def __init__(self, wsdl, transport=None):
            calls.append(wsdl)

    monkeypatch.setattr(wsfe.zeep, "Client", _FakeZeepClient)

    cliente1 = wsfe._get_client("https://ejemplo-cualquiera.test/wsdl")
    cliente2 = wsfe._get_client("https://ejemplo-cualquiera.test/wsdl")

    assert calls == ["https://ejemplo-cualquiera.test/wsdl"]
    assert cliente1 is cliente2


# ── param_*: serialize_object tiene que quedar con target_cls=dict, NUNCA
# list — un dict plano ya cumple el mismo isinstance(obj, (dict, CompoundValue))
# que evalúa zeep.helpers.serialize_object, así que reproduce el bug real sin
# necesitar un CompoundValue de verdad: con target_cls=list, serialize_object
# hace `result = list(); result["Id"] = ...` → TypeError en producción
# ("list indices must be integers or slices, not str"), porque las llamadas
# viejas pasaban `list` en vez de `dict` como segundo argumento — bug real
# encontrado recién en prod al apretar "Actualizar catálogos ARCA".


@pytest.mark.parametrize(
    "metodo,operacion,args",
    [
        ("param_puntos_venta", "FEParamGetPtosVenta", ()),
        ("param_tipos_cbte", "FEParamGetTiposCbte", ()),
        ("param_tipos_doc", "FEParamGetTiposDoc", ()),
        ("param_tipos_concepto", "FEParamGetTiposConcepto", ()),
        ("param_condicion_iva_receptor", "FEParamGetCondicionIvaReceptor", ("A",)),
        ("param_tipos_tributos", "FEParamGetTiposTributos", ()),
        ("param_tipos_opcional", "FEParamGetTiposOpcional", ()),
        ("param_tipos_monedas", "FEParamGetTiposMonedas", ()),
    ],
)
def test_param_devuelve_dicts_con_acceso_por_clave(metodo, operacion, args):
    """Nombres de operación y campo hijo verificados contra el WSDL real de
    WSFEv1 (FETributoResponse.ResultGet=TributoTipo[], OpcionalTipoResponse.
    ResultGet=OpcionalTipo[], MonedaResponse.ResultGet=Moneda[])."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    # Un dict plano cumple isinstance(obj, dict) — el mismo chequeo que hace
    # zeep.helpers.serialize_object para un CompoundValue real, así que
    # ejercita la misma rama de código sin necesitar un mock de zeep interno.
    item = {"Id": 80, "Desc": "CUIT"}
    child_field = {
        "FEParamGetPtosVenta": "PtoVenta",
        "FEParamGetTiposCbte": "CbteTipo",
        "FEParamGetTiposDoc": "DocTipo",
        "FEParamGetTiposConcepto": "ConceptoTipo",
        "FEParamGetCondicionIvaReceptor": "CondicionIvaReceptor",
        "FEParamGetTiposTributos": "TributoTipo",
        "FEParamGetTiposOpcional": "OpcionalTipo",
        "FEParamGetTiposMonedas": "Moneda",
    }[operacion]
    mock_result_get = MagicMock(spec=[child_field])
    setattr(mock_result_get, child_field, [item])
    mock_resp = MagicMock(spec=["ResultGet", "Errors"])
    mock_resp.ResultGet = mock_result_get
    mock_resp.Errors = None

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        getattr(mock_service, operacion).return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        resultado = getattr(client, metodo)(*args)

    assert resultado == [{"Id": 80, "Desc": "CUIT"}]
    assert resultado[0]["Id"] == 80  # regresión: con target_cls=list esto explota


def test_consultar_error_real_no_se_confunde_con_no_existe():
    """Un error de AFIP que NO es 10016/602 tiene que seguir levantando —
    ahora ArcaBusinessError, con el código en `.codigo` y el par en `.errores`
    (dato estructurado, no solo el string)."""
    from arca_fe.wsfe import WsfeClient
    from arca_fe.errores import ArcaBusinessError

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    err = MagicMock(spec=_ITEM_FIELDS)
    err.Code = 500
    err.Msg = "Error interno de AFIP"
    err_container = MagicMock(spec=_ERRCONT_FIELDS)
    err_container.Err = [err]
    mock_resp = MagicMock(spec=["Errors", "ResultGet"])
    mock_resp.Errors = err_container

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaBusinessError, match="500") as ei:
            client.consultar(2, 13, 1)

    assert ei.value.codigo == 500
    assert ei.value.errores == ((500, "Error interno de AFIP"),)


def test_consultar_fault_con_codigo_no_existe_como_substring_no_se_silencia():
    """Word-boundary, no substring crudo: un Fault real cuyo texto contiene
    "602" como PARTE de un número más largo (ej. un nº de comprobante 60210)
    NO tiene que confundirse con el código 602 ("no existe") y silenciarse a
    None. Antes se hacía `str(602) in str(exc)` — "602" matcheaba dentro de
    "60210" y tragaba el error real. Ahora `\\b602\\b` exige límites de
    palabra, así que solo el código 602 exacto cuenta como "no existe". Un
    Fault que no es "no existe" se traduce a ArcaResponseError (no filtra el
    zeep.Fault crudo al consumidor)."""
    import zeep.exceptions
    from arca_fe.wsfe import WsfeClient
    from arca_fe.errores import ArcaResponseError

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.side_effect = zeep.exceptions.Fault(
            "Rechazo real procesando el comprobante 60210"
        )
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError, match="60210"):
            client.consultar(2, 13, 60210)


# ---------------------------------------------------------------------------
# param_cotizacion — forma de respuesta distinta (ResultGet es UN objeto
# Cotizacion, no un array), verificada contra el WSDL real
# ---------------------------------------------------------------------------


def test_param_cotizacion_devuelve_dict_plano(monkeypatch):
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    cotizacion = MagicMock(spec=["MonId", "MonCotiz", "FchCotiz"])
    cotizacion.MonId = "DOL"
    cotizacion.MonCotiz = 1050.5
    cotizacion.FchCotiz = "20260703"
    mock_resp = MagicMock(spec=["ResultGet", "Errors"])
    mock_resp.ResultGet = cotizacion
    mock_resp.Errors = None

    captured = {}
    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()

        def _get_cotizacion(**kwargs):
            captured.update(kwargs)
            return mock_resp

        mock_service.FEParamGetCotizacion.side_effect = _get_cotizacion
        mock_client_fn.return_value.service = mock_service

        result = client.param_cotizacion("DOL", fecha=date(2026, 7, 3))

    assert result == {"mon_id": "DOL", "cotizacion": 1050.5, "fecha": "20260703"}
    assert captured["MonId"] == "DOL"
    assert captured["FchCotiz"] == "20260703"


def test_param_cotizacion_sin_fecha_no_manda_fchcotiz(monkeypatch):
    """`fecha=None` (default) → pide la cotización más reciente, sin filtrar
    por fecha — no se debe mandar el parámetro FchCotiz en absoluto."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    cotizacion = MagicMock(spec=["MonId", "MonCotiz", "FchCotiz"])
    cotizacion.MonId = "PES"
    cotizacion.MonCotiz = 1.0
    cotizacion.FchCotiz = "20260703"
    mock_resp = MagicMock(spec=["ResultGet", "Errors"])
    mock_resp.ResultGet = cotizacion
    mock_resp.Errors = None

    captured = {}
    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()

        def _get_cotizacion(**kwargs):
            captured.update(kwargs)
            return mock_resp

        mock_service.FEParamGetCotizacion.side_effect = _get_cotizacion
        mock_client_fn.return_value.service = mock_service

        client.param_cotizacion("PES")

    assert "FchCotiz" not in captured
