"""Tests del gating de ambiente ARCA (default-deny).

Verifica el invariante central del sistema de facturación:
- Emite en PRODUCCIÓN solo si is_production=True Y cert ENV presente.
- Ante la duda (staging, local, sin cert) → homologación, nunca producción.
- Emisor desconocido → ValueError (no cae silenciosamente a un default).
- Falta de cert/clave → ValueError descriptivo (no IntegrityError en DB).
- Emisores_para: RI → pablo, cualquier otro → santini.
"""

import os
import pytest

pytestmark = pytest.mark.unit


# ── Fixtures de DB falsa ──────────────────────────────────────────────────────


class _Row:
    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        return self._d[k]


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, cuit="20-30000000-0", ptovta="1"):
        self._rows = [
            _Row({"key": "afip_pablo_cuit", "value": cuit}),
            _Row({"key": "afip_pablo_ptovta", "value": ptovta}),
            _Row({"key": "afip_santini_cuit", "value": "20-40000000-0"}),
            _Row({"key": "afip_santini_ptovta", "value": "2"}),
        ]

    def execute(self, query, params=None):
        key_list = params[0] if params else []
        rows = [r for r in self._rows if r["key"] in key_list]
        return _Cursor(rows)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _set_is_production(monkeypatch, value: bool):
    import config
    monkeypatch.setattr(config.settings, "is_production", value)


def _set_env_certs(monkeypatch, emisor: str, present: bool = True):
    cert_var = f"AFIP_{emisor.upper()}_CERT"
    key_var = f"AFIP_{emisor.upper()}_KEY"
    if present:
        monkeypatch.setenv(cert_var, "-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----")
        monkeypatch.setenv(key_var, "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----")
    else:
        monkeypatch.delenv(cert_var, raising=False)
        monkeypatch.delenv(key_var, raising=False)


# ── Gating default-deny ────────────────────────────────────────────────────────


def test_gating_produccion_cuando_is_production_y_cert(monkeypatch):
    """is_production=True + cert → ambiente='produccion'."""
    from services.facturacion.config import credenciales

    _set_is_production(monkeypatch, True)
    _set_env_certs(monkeypatch, "pablo", present=True)

    cred = credenciales("pablo", _FakeConn())
    assert cred.ambiente == "produccion"
    assert "wsaa.afip.gov.ar" in cred.endpoint_wsaa  # endpoint real, sin "homo"
    assert "homo" not in cred.endpoint_wsaa


def test_gating_homologacion_cuando_no_is_production(monkeypatch):
    """is_production=False → homologación aunque haya cert."""
    from services.facturacion.config import credenciales

    _set_is_production(monkeypatch, False)
    _set_env_certs(monkeypatch, "pablo", present=True)

    cred = credenciales("pablo", _FakeConn())
    assert cred.ambiente == "homologacion"
    assert "homo" in cred.endpoint_wsaa


def test_gating_falta_cert_levanta_valor(monkeypatch):
    """Sin cert → ValueError descriptivo (no 500 críptico)."""
    from services.facturacion.config import credenciales

    _set_is_production(monkeypatch, True)
    _set_env_certs(monkeypatch, "pablo", present=False)

    with pytest.raises(ValueError, match="AFIP_PABLO"):
        credenciales("pablo", _FakeConn())


def test_gating_emisor_desconocido_levanta(monkeypatch):
    """Emisor no reconocido → ValueError (no cae a un default silencioso)."""
    from services.facturacion.config import credenciales

    _set_is_production(monkeypatch, True)
    _set_env_certs(monkeypatch, "pablo", present=True)

    with pytest.raises(ValueError, match="desconocido"):
        credenciales("rambla", _FakeConn())


def test_gating_santini_ok(monkeypatch):
    """Santini también funciona con los mismos invariantes."""
    from services.facturacion.config import credenciales

    _set_is_production(monkeypatch, False)
    _set_env_certs(monkeypatch, "santini", present=True)

    cred = credenciales("santini", _FakeConn())
    assert cred.emisor == "santini"
    assert cred.ambiente == "homologacion"


def test_cert_cargado_true_si_env_presentes(monkeypatch):
    """cert_cargado devuelve True solo si AMBAS vars están seteadas."""
    from services.facturacion.config import cert_cargado

    _set_env_certs(monkeypatch, "pablo", present=True)
    assert cert_cargado("pablo") is True


def test_cert_cargado_false_si_env_ausentes(monkeypatch):
    from services.facturacion.config import cert_cargado

    _set_env_certs(monkeypatch, "pablo", present=False)
    assert cert_cargado("pablo") is False


# ── Routing de emisor ─────────────────────────────────────────────────────────


def test_emisor_para_ri_es_pablo():
    from services.facturacion.emisores import emisor_para

    assert emisor_para("responsable_inscripto") == "pablo"
    assert emisor_para("RESPONSABLE_INSCRIPTO") == "pablo"
    assert emisor_para("  Responsable_Inscripto  ") == "pablo"


def test_emisor_para_monotributo_es_santini():
    from services.facturacion.emisores import emisor_para

    assert emisor_para("monotributo") == "santini"


def test_emisor_para_consumidor_final_es_santini():
    from services.facturacion.emisores import emisor_para

    assert emisor_para("consumidor_final") == "santini"


def test_emisor_para_vacio_es_santini():
    """Default seguro: sin perfil fiscal → santini (no pablo)."""
    from services.facturacion.emisores import emisor_para

    assert emisor_para("") == "santini"
    assert emisor_para(None) == "santini"
