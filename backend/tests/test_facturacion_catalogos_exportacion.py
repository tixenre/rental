"""Tests de services.facturacion.catalogos_exportacion — catálogos de WSFEXv1 (FEXGetPARAM_*)
cacheados en `app_settings`. Sin red, sin Postgres real."""
from __future__ import annotations

import pytest

from services.facturacion.catalogos_exportacion import (
    incoterms,
    monedas,
    paises_destino,
    refrescar_catalogos_exportacion,
    ultimo_refresco,
)

pytestmark = pytest.mark.unit


class _FakeAppSettingsConn:
    def __init__(self, seed: dict | None = None):
        self._store: dict[str, str] = dict(seed or {})

    def execute(self, sql, params=None):
        store = self._store
        sql_stripped = sql.strip()
        if sql_stripped.startswith("SELECT"):
            key = params[0]
            value = store.get(key)

            class _R:
                def fetchone(self_inner):
                    return {"value": value} if value is not None else None

            return _R()
        if sql_stripped.startswith("INSERT"):
            key, value = params[0], params[1]
            store[key] = value

            class _R:
                pass

            return _R()
        raise AssertionError(f"Query inesperada en el fake: {sql}")


class _FakeCred:
    ambiente = "homologacion"
    cuit = 20300000000
    endpoint_wsfex = "wswhomo.afip.gov.ar/wsfexv1"


def _fake_emisor_habilitado(nombre="santini"):
    from datetime import datetime

    from services.facturacion.emisores_repo import EmisorArca

    return EmisorArca(
        id=1, nombre=nombre, cuit="20300000000", pto_vta=1, condicion_iva="monotributo",
        cert_cargado=True, activo=True, razon_social=None, domicilio=None, iibb=None,
        inicio_actividades=None, notas=None, created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1), habilitado_exportacion=True,
    )


def _patch_auth(monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_fake_emisor_habilitado()],
    )
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: _FakeCred(),
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: ("tok", "sign"),
    )


def _patch_wsfex(monkeypatch, *, paises=None, incoterms_=None, monedas_=None):
    monkeypatch.setattr(
        "arca_fe.wsfex.WsfexClient.param_paises_destino",
        lambda self: paises or [],
    )
    monkeypatch.setattr(
        "arca_fe.wsfex.WsfexClient.param_incoterms",
        lambda self: incoterms_ or [],
    )
    monkeypatch.setattr(
        "arca_fe.wsfex.WsfexClient.param_monedas",
        lambda self: monedas_ or [],
    )


def test_refrescar_sin_emisor_habilitado_falla(monkeypatch):
    monkeypatch.setattr("services.facturacion.emisores_repo.list_emisores", lambda conn: [])
    conn = _FakeAppSettingsConn()
    with pytest.raises(ValueError, match="habilitado para exportación"):
        refrescar_catalogos_exportacion(conn)


def test_refrescar_ignora_emisor_no_habilitado_para_exportacion(monkeypatch):
    from datetime import datetime

    from services.facturacion.emisores_repo import EmisorArca

    no_habilitado = EmisorArca(
        id=2, nombre="pablo", cuit="20300000001", pto_vta=1, condicion_iva="responsable_inscripto",
        cert_cargado=True, activo=True, razon_social=None, domicilio=None, iibb=None,
        inicio_actividades=None, notas=None, created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1), habilitado_exportacion=False,
    )
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores", lambda conn: [no_habilitado]
    )
    conn = _FakeAppSettingsConn()
    with pytest.raises(ValueError, match="habilitado para exportación"):
        refrescar_catalogos_exportacion(conn)


def test_refrescar_y_leer_catalogos(monkeypatch):
    _patch_auth(monkeypatch)
    _patch_wsfex(
        monkeypatch,
        paises=[{"DST_CODIGO": 203, "DST_Ds": "ESTADOS UNIDOS"}],
        incoterms_=[{"Id": "FOB", "Ds": "Free On Board"}],
        monedas_=[{"Mon_Id": "USD", "Mon_Ds": "Dólar Estadounidense"}],
    )
    conn = _FakeAppSettingsConn()

    resultado = refrescar_catalogos_exportacion(conn)
    assert resultado["paises_destino"] == [{"id": 203, "desc": "ESTADOS UNIDOS"}]
    assert resultado["incoterms"] == [{"id": "FOB", "desc": "Free On Board"}]
    assert resultado["monedas"] == [{"id": "USD", "desc": "Dólar Estadounidense"}]

    assert paises_destino(conn) == [{"id": 203, "desc": "ESTADOS UNIDOS"}]
    assert incoterms(conn) == [{"id": "FOB", "desc": "Free On Board"}]
    assert monedas(conn) == [{"id": "USD", "desc": "Dólar Estadounidense"}]
    assert ultimo_refresco(conn) is not None


def test_leer_catalogo_nunca_refrescado_falla_fuerte():
    conn = _FakeAppSettingsConn()
    with pytest.raises(RuntimeError, match="todavía no se consultó"):
        paises_destino(conn)
