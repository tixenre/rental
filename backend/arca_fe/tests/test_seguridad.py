"""Tests de arca_fe.seguridad — protección del PDF (permisos + firma PAdES + metadatos + sello de
tiempo). Sin red real (fake de TSA para el fail-open), sin Postgres. Usa un PDF mínimo generado con
PyMuPDF (no hace falta Playwright para estos tests) — portado de
`backend/tests/test_facturacion_pdf_seguridad.py`, usando `generar_cert_autofirmado` directo en
vez de `get_or_create_signing_cert` (esa persistencia es responsabilidad del adapter, no de
`arca_fe`)."""
from __future__ import annotations

import io

import fitz
import pytest

from arca_fe.seguridad import asegurar_pdf, generar_cert_autofirmado

pytestmark = pytest.mark.unit


def _pdf_minimo() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Factura de prueba — total $ 5.700,00")
    return doc.tobytes()


# ── Certificado: PEM válido ──────────────────────────────────────────────────


def test_generar_cert_autofirmado_devuelve_pem_valido():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert key_pem.startswith(b"-----BEGIN PRIVATE KEY-----")


def test_generar_cert_autofirmado_es_distinto_por_llamada():
    cert1, _ = generar_cert_autofirmado("Test CN")
    cert2, _ = generar_cert_autofirmado("Test CN")
    assert cert1 != cert2  # serial number aleatorio por llamada


# ── Permisos: ver/imprimir sí, editar/copiar no, sin contraseña para abrir ──


def test_asegurar_pdf_abre_sin_contrasena():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    assert doc.needs_pass == 0


def test_asegurar_pdf_permite_ver_e_imprimir_pero_no_editar_ni_copiar():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    perms = doc.permissions
    assert perms & fitz.PDF_PERM_PRINT
    assert not (perms & fitz.PDF_PERM_COPY)
    assert not (perms & fitz.PDF_PERM_MODIFY)
    assert not (perms & fitz.PDF_PERM_ANNOTATE)


def test_asegurar_pdf_conserva_el_contenido_original():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    assert "5.700,00" in doc[0].get_text()


# ── Firma de integridad: intacta al generarse, se rompe si se toca el byte ──


def test_asegurar_pdf_queda_firmado_y_la_firma_valida_intacta():
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
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

    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    firmado = bytearray(asegurar_pdf(_pdf_minimo(), cert_pem, key_pem))

    # Tocar el último byte del archivo ya firmado (cubierto por la firma:
    # coverage = ENTIRE_FILE, todo salvo el placeholder de la firma en sí).
    firmado[-1] ^= 0xFF

    reader = PdfFileReader(io.BytesIO(bytes(firmado)))
    reader.decrypt("")
    status = validate_pdf_signature(reader.embedded_signatures[0])
    assert status.intact is False


# ── Metadatos embebidos: el archivo se autoidentifica fuera de contexto ─────


def test_metadata_se_embebe_en_el_info_dict():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(
        _pdf_minimo(), cert_pem, key_pem,
        metadata={"Title": "Factura A 00003-00000042", "Subject": "CAE 71234567890123"},
    )

    doc = fitz.open(stream=protegido, filetype="pdf")
    assert doc.metadata["title"] == "Factura A 00003-00000042"
    assert doc.metadata["subject"] == "CAE 71234567890123"


def test_sin_metadata_no_agrega_nada_comportamiento_identico_a_antes():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem)

    doc = fitz.open(stream=protegido, filetype="pdf")
    assert not doc.metadata.get("title")


# ── Sello de tiempo RFC 3161: fail-open si la TSA no responde ───────────────


def test_tsa_url_none_no_intenta_red_ni_falla():
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(_pdf_minimo(), cert_pem, key_pem, tsa_url=None)
    assert protegido  # firma igual, sin timestamp — comportamiento default sin cambios


def test_tsa_caida_no_bloquea_la_firma_fail_open():
    """Una TSA inalcanzable (dominio inválido, sin red) NUNCA debe impedir entregar el
    comprobante — se loguea el warning y se firma igual sin sello de tiempo."""
    cert_pem, key_pem = generar_cert_autofirmado("Test CN")
    protegido = asegurar_pdf(
        _pdf_minimo(), cert_pem, key_pem,
        tsa_url="http://tsa-que-no-existe.invalid/timestamp",
    )

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    reader = PdfFileReader(io.BytesIO(protegido))
    reader.decrypt("")
    status = validate_pdf_signature(reader.embedded_signatures[0])
    assert status.intact is True  # se firmó igual, aunque la TSA no respondió
