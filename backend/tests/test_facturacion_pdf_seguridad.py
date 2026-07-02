"""Tests de services.facturacion.pdf_seguridad — protección del PDF ya
generado: permisos (ver/imprimir sí, editar/copiar no) + firma de
integridad de archivo (PAdES, certificado propio autofirmado).

Sin red, sin Postgres real (fake de `app_settings` en memoria). Usa un PDF
mínimo generado con PyMuPDF (no hace falta Playwright para estos tests).
"""
from __future__ import annotations

import io

import fitz
import pytest
from cryptography.fernet import Fernet

from services.facturacion.pdf_seguridad import (
    asegurar_pdf,
    get_or_create_signing_cert,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _arca_master_key(monkeypatch):
    monkeypatch.setenv("ARCA_MASTER_KEY", Fernet.generate_key().decode())


class _FakeAppSettingsConn:
    """Fake mínimo de `app_settings` (key/value) — solo lo que
    `get_or_create_signing_cert` necesita: SELECT ... WHERE key = ANY(%s) e
    INSERT ... ON CONFLICT DO NOTHING."""

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


def _pdf_minimo() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Factura de prueba — total $ 5.700,00")
    return doc.tobytes()


# ── Certificado: se genera una vez, se persiste, se reusa ───────────────────


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


# ── Permisos: ver/imprimir sí, editar/copiar no, sin contraseña para abrir ──


def test_asegurar_pdf_abre_sin_contrasena():
    conn = _FakeAppSettingsConn()
    cert_pem, key_pem = get_or_create_signing_cert(conn)
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    assert doc.needs_pass == 0


def test_asegurar_pdf_permite_ver_e_imprimir_pero_no_editar_ni_copiar():
    conn = _FakeAppSettingsConn()
    cert_pem, key_pem = get_or_create_signing_cert(conn)
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    perms = doc.permissions
    assert perms & fitz.PDF_PERM_PRINT
    assert not (perms & fitz.PDF_PERM_COPY)
    assert not (perms & fitz.PDF_PERM_MODIFY)
    assert not (perms & fitz.PDF_PERM_ANNOTATE)


def test_asegurar_pdf_conserva_el_contenido_original():
    conn = _FakeAppSettingsConn()
    cert_pem, key_pem = get_or_create_signing_cert(conn)
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    assert "5.700,00" in doc[0].get_text()


# ── Firma de integridad: intacta al generarse, se rompe si se toca el byte ──


def test_asegurar_pdf_queda_firmado_y_la_firma_valida_intacta():
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    conn = _FakeAppSettingsConn()
    cert_pem, key_pem = get_or_create_signing_cert(conn)
    firmado = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    reader = PdfFileReader(io.BytesIO(firmado))
    reader.decrypt("")
    sigs = reader.embedded_signatures
    assert len(sigs) == 1
    status = validate_pdf_signature(sigs[0])
    assert status.intact is True
    assert status.valid is True


def test_asegurar_pdf_detecta_manipulacion_posterior():
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    conn = _FakeAppSettingsConn()
    cert_pem, key_pem = get_or_create_signing_cert(conn)
    firmado = bytearray(asegurar_pdf(_pdf_minimo(), cert_pem, key_pem))

    # Tocar el último byte del archivo ya firmado (cubierto por la firma:
    # coverage = ENTIRE_FILE, todo salvo el placeholder de la firma en sí).
    firmado[-1] ^= 0xFF

    reader = PdfFileReader(io.BytesIO(bytes(firmado)))
    reader.decrypt("")
    status = validate_pdf_signature(reader.embedded_signatures[0])
    assert status.intact is False
