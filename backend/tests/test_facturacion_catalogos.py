"""Tests de services.facturacion.catalogos — catálogos de ARCA (FEParamGet*)
cacheados en `app_settings`. Sin red, sin Postgres real."""
from __future__ import annotations

import json

import pytest

from services.facturacion.catalogos import (
    label_concepto,
    label_condicion_iva_receptor,
    label_doc_tipo,
    refrescar_catalogos,
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
    endpoint_wsfe = "wswhomo.afip.gov.ar"


def _patch_auth(monkeypatch, emisor="pablo"):
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.elegir_autenticador",
        lambda conn: emisor,
    )
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: _FakeCred(),
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio="wsfe": ("tok", "sign"),
    )


def _patch_wsfe(monkeypatch, *, doc_tipo=None, concepto=None, condicion_por_clase=None):
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_tipos_doc",
        lambda self: doc_tipo or [],
    )
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_tipos_concepto",
        lambda self: concepto or [],
    )
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_condicion_iva_receptor",
        lambda self, clase_cmp: (condicion_por_clase or {}).get(clase_cmp, []),
    )


# ── refrescar_catalogos: trae de ARCA y persiste ────────────────────────────


def test_refrescar_catalogos_persiste_los_3_catalogos(monkeypatch):
    conn = _FakeAppSettingsConn()
    _patch_auth(monkeypatch)
    _patch_wsfe(
        monkeypatch,
        doc_tipo=[{"Id": 80, "Desc": "CUIT"}, {"Id": 96, "Desc": "DNI"}],
        concepto=[{"Id": 1, "Desc": "Productos"}, {"Id": 2, "Desc": "Servicios"}],
        condicion_por_clase={
            "A": [{"Id": 1, "Desc": "IVA Responsable Inscripto"}],
            "B": [{"Id": 5, "Desc": "Consumidor Final"}],
            "C": [{"Id": 6, "Desc": "Responsable Monotributo"}],
            "ALEY": [],
            "49": [],
        },
    )

    resultado = refrescar_catalogos(conn)

    assert resultado["doc_tipo"] == [{"id": 80, "desc": "CUIT"}, {"id": 96, "desc": "DNI"}]
    assert resultado["concepto"] == [{"id": 1, "desc": "Productos"}, {"id": 2, "desc": "Servicios"}]
    assert {"id": 1, "desc": "IVA Responsable Inscripto"} in resultado["condicion_iva_receptor"]
    assert {"id": 5, "desc": "Consumidor Final"} in resultado["condicion_iva_receptor"]
    assert {"id": 6, "desc": "Responsable Monotributo"} in resultado["condicion_iva_receptor"]

    # Quedó persistido — una lectura nueva lo ve.
    assert label_doc_tipo(80, conn) == "CUIT"
    assert ultimo_refresco(conn) is not None


def test_refrescar_catalogos_unifica_condicion_iva_de_todas_las_clases(monkeypatch):
    """FEParamGetCondicionIvaReceptor no tiene un valor "todas" — hay que
    pedir A/B/C/ALEY/49 y unificar sin duplicar ids repetidos entre clases."""
    conn = _FakeAppSettingsConn()
    _patch_auth(monkeypatch)
    _patch_wsfe(
        monkeypatch,
        condicion_por_clase={
            "A": [{"Id": 1, "Desc": "IVA Responsable Inscripto"}],
            "B": [{"Id": 1, "Desc": "IVA Responsable Inscripto"}, {"Id": 5, "Desc": "Consumidor Final"}],
            "C": [{"Id": 5, "Desc": "Consumidor Final"}],
            "ALEY": [],
            "49": [],
        },
    )

    resultado = refrescar_catalogos(conn)
    ids = [c["id"] for c in resultado["condicion_iva_receptor"]]
    assert sorted(ids) == [1, 5]


def test_refrescar_catalogos_no_pide_clase_m_invalida(monkeypatch):
    """Regresión: "M" NO es una ClaseCmp válida para
    FEParamGetCondicionIvaReceptor — ARCA devuelve 10244 ("El valor
    ingresado para la clase de comprobante no es valido... solo puede ser
    'A', 'B', 'C', 'ALEY' o '49'"), bug real de prod post-#1180. Si alguna
    clase pedida no es una de esas 5, este test la cacha."""
    from services.facturacion.catalogos import _CLASES_CMP

    assert set(_CLASES_CMP) <= {"A", "B", "C", "ALEY", "49"}


def test_refrescar_catalogos_sin_emisor_con_cert_levanta_value_error(monkeypatch):
    conn = _FakeAppSettingsConn()
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.elegir_autenticador", lambda conn: None
    )

    with pytest.raises(ValueError):
        refrescar_catalogos(conn)


def test_refrescar_catalogos_arca_caida_propaga_arca_error(monkeypatch):
    """`param_tipos_doc()` real levanta `ArcaBusinessError` (taxonomía tipada
    del motor) — `refrescar_catalogos` ya NO la envuelve en `RuntimeError`:
    se deja pasar tal cual para que el route (`routes/facturacion.py`) elija
    el status HTTP por subtipo (422/502/503) en vez de un 503 genérico."""
    from arca_fe.errores import ArcaBusinessError

    conn = _FakeAppSettingsConn()
    _patch_auth(monkeypatch)
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_tipos_doc",
        lambda self: (_ for _ in ()).throw(
            ArcaBusinessError("FEParamGetTiposDoc error — 600: no autorizado")
        ),
    )

    with pytest.raises(ArcaBusinessError, match="600"):
        refrescar_catalogos(conn)


# ── label_*: leen el cache; fallan fuerte si nunca se refrescó ──────────────


def test_label_doc_tipo_lee_del_cache():
    conn = _FakeAppSettingsConn({
        "arca_catalogo_doc_tipo": json.dumps([{"id": 96, "desc": "DNI"}]),
    })
    assert label_doc_tipo(96, conn) == "DNI"


def test_label_concepto_lee_del_cache():
    conn = _FakeAppSettingsConn({
        "arca_catalogo_concepto": json.dumps([{"id": 2, "desc": "Servicios"}]),
    })
    assert label_concepto(2, conn) == "Servicios"


def test_label_condicion_iva_receptor_lee_del_cache():
    conn = _FakeAppSettingsConn({
        "arca_catalogo_condicion_iva_receptor": json.dumps([{"id": 5, "desc": "Consumidor Final"}]),
    })
    assert label_condicion_iva_receptor(5, conn) == "Consumidor Final"


def test_label_con_id_no_catalogado_muestra_el_id_crudo_no_inventa_texto():
    conn = _FakeAppSettingsConn({
        "arca_catalogo_doc_tipo": json.dumps([{"id": 96, "desc": "DNI"}]),
    })
    assert label_doc_tipo(999, conn) == "999"


def test_label_sin_refrescar_nunca_levanta_runtime_error():
    conn = _FakeAppSettingsConn()
    with pytest.raises(RuntimeError, match="todavía no se consultó"):
        label_doc_tipo(96, conn)


def test_ultimo_refresco_none_si_nunca_se_corrio():
    conn = _FakeAppSettingsConn()
    assert ultimo_refresco(conn) is None
