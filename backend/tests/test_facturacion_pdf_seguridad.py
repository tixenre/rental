"""Tests de services.facturacion.pdf_seguridad — persistencia del certificado de firma de PDFs.

La generación del par (certificado, clave) y la protección del PDF en sí (permisos + firma PAdES)
ya están cubiertas en `arca_fe/tests/test_seguridad.py` (puras, sin Postgres) — acá solo se prueba
lo que es responsabilidad de ESTE adapter: persistir el certificado cifrado en `app_settings` y
reusarlo entre llamadas. Sin red, sin Postgres real (fake de `app_settings` en memoria).
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from services.facturacion.pdf_seguridad import get_or_create_signing_cert

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _arca_master_key(monkeypatch):
    monkeypatch.setenv("ARCA_MASTER_KEY", Fernet.generate_key().decode())


class _FakeAppSettingsConn:
    """Fake mínimo de `app_settings` (key/value) — solo lo que `get_or_create_signing_cert`
    necesita: SELECT ... WHERE key = ANY(%s) e INSERT ... ON CONFLICT DO NOTHING."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def execute(self, sql, params=None):
        store = self._store
        if sql.strip().startswith("SELECT"):
            keys = params[0]
            rows = [{"key": k, "value": store[k]} for k in keys if k in store]

            class _R:
                def fetchall(self_inner):
                    return rows

            return _R()
        if sql.strip().startswith("INSERT"):
            key, value = params[0], params[1]
            store.setdefault(key, value)

            class _R:
                def fetchall(self_inner):
                    return []

                def fetchone(self_inner):
                    return None

            return _R()
        raise AssertionError(f"Query inesperada en el fake: {sql}")


def test_get_or_create_signing_cert_devuelve_pem_valido():
    conn = _FakeAppSettingsConn()
    cert_pem, key_pem = get_or_create_signing_cert(conn)
    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert key_pem.startswith(b"-----BEGIN PRIVATE KEY-----")


def test_get_or_create_signing_cert_reusa_el_mismo_par_entre_llamadas():
    conn = _FakeAppSettingsConn()
    cert1, key1 = get_or_create_signing_cert(conn)
    cert2, key2 = get_or_create_signing_cert(conn)
    assert cert1 == cert2
    assert key1 == key2


def test_get_or_create_signing_cert_persiste_cifrado_no_en_texto_plano():
    conn = _FakeAppSettingsConn()
    cert_pem, _ = get_or_create_signing_cert(conn)
    valores_crudos = list(conn._store.values())
    assert not any(b"BEGIN CERTIFICATE" in v.encode() for v in valores_crudos)
