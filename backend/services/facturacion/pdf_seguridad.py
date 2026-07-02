"""services.facturacion.pdf_seguridad — protección del PDF ya renderizado.

Dos mecanismos, DISTINTOS del CAE/QR de ARCA (que valida el comprobante
fiscal contra los servidores de ARCA — eso no se toca acá):

  - **Permisos**: se puede abrir/ver/imprimir libremente (sin contraseña),
    pero no editar ni copiar texto/imágenes — evita que alguien "levante" un
    CUIT o un monto con un copy-paste, o edite el PDF y lo reenvíe como si
    fuera el original.
  - **Firma de integridad de archivo (PAdES)**: certificado PROPIO
    autofirmado (no el de ARCA) que prueba que el PDF no fue alterado desde
    que este motor lo generó — cualquier lector de PDF (Adobe, etc.) lo
    muestra como "documento no modificado desde la firma". No reemplaza al
    CAE/QR (eso certifica el comprobante fiscal en sí); esto certifica el
    ARCHIVO.

El certificado de firma se genera UNA sola vez (autofirmado, RSA 2048,
válido 10 años) y se persiste cifrado en `app_settings` — mismo patrón que
el resto de credenciales ARCA (`services.facturacion.crypto`, Fernet con
`ARCA_MASTER_KEY`). Es un certificado de PLATAFORMA (uno solo, no por
emisor/tenant): prueba integridad del archivo, no identidad fiscal, así que
no tiene sentido gestionar uno por cada emisor/negocio que use este motor.

Ambos pasos se aplican en un ÚNICO writer de pyhanko (encriptar primero,
firmar después, sobre el mismo objeto) — PyMuPDF y pyhanko no son
intercambiables acá: MuPDF guarda el diccionario `/Encrypt` como objeto
directo y pyhanko exige que sea una referencia indirecta, así que un PDF
"protegido" con PyMuPDF y después firmado con pyhanko no se puede leer. La
encriptación tiene que salir del mismo writer que después firma.
"""
from __future__ import annotations

import io
import secrets
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from services.facturacion.crypto import decrypt, encrypt

_CN = "Comprobantes — Motor de Facturación"
_SETTING_CERT = "facturacion_pdf_signing_cert"
_SETTING_KEY = "facturacion_pdf_signing_key"

_RAZON_FIRMA = "Certifica que el archivo no fue modificado desde su generación."


# ---------------------------------------------------------------------------
# Certificado de firma — autofirmado, generado una vez, cifrado en app_settings
# ---------------------------------------------------------------------------


def _generar_cert_autofirmado(cn: str) -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def get_or_create_signing_cert(conn) -> tuple[bytes, bytes]:
    """(cert_pem, key_pem) del certificado de firma de PDFs. Se genera una
    única vez (primer uso) y queda persistido cifrado en `app_settings`;
    llamadas siguientes leen el mismo par."""
    rows = conn.execute(
        "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
        ([_SETTING_CERT, _SETTING_KEY],),
    ).fetchall()
    found = {r["key"]: r["value"] for r in rows}
    if _SETTING_CERT not in found or _SETTING_KEY not in found:
        cert_pem, key_pem = _generar_cert_autofirmado(_CN)
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, 'system-seed') "
            "ON CONFLICT (key) DO NOTHING",
            (_SETTING_CERT, encrypt(cert_pem).decode("ascii")),
        )
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, 'system-seed') "
            "ON CONFLICT (key) DO NOTHING",
            (_SETTING_KEY, encrypt(key_pem).decode("ascii")),
        )
        # Re-leer: si otra request ganó la carrera del INSERT, usamos SU par
        # (nunca dos certs "ganadores" distintos convivendo).
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
            ([_SETTING_CERT, _SETTING_KEY],),
        ).fetchall()
        found = {r["key"]: r["value"] for r in rows}
    return decrypt(found[_SETTING_CERT].encode("ascii")), decrypt(found[_SETTING_KEY].encode("ascii"))


# ---------------------------------------------------------------------------
# Protección del PDF: permisos + firma, en un único writer de pyhanko
# ---------------------------------------------------------------------------


def _signer_desde_pem(cert_pem: bytes, key_pem: bytes):
    from asn1crypto import keys as asn1_keys
    from asn1crypto import x509 as asn1_x509
    from pyhanko.sign import signers
    from pyhanko_certvalidator.registry import SimpleCertificateStore

    cert_der = x509.load_pem_x509_certificate(cert_pem).public_bytes(serialization.Encoding.DER)
    cert = asn1_x509.Certificate.load(cert_der)
    key_obj = serialization.load_pem_private_key(key_pem, password=None)
    key_der = key_obj.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    key = asn1_keys.PrivateKeyInfo.load(key_der)
    registry = SimpleCertificateStore()
    registry.register(cert)
    return signers.SimpleSigner(signing_cert=cert, signing_key=key, cert_registry=registry)


def asegurar_pdf(pdf_bytes: bytes, cert_pem: bytes, key_pem: bytes) -> bytes:
    """Restringe permisos (ver/imprimir sí, editar/copiar no) y firma el
    archivo (integridad) — devuelve los bytes finales del PDF a entregar.

    La contraseña de propietario es aleatoria por documento: nadie necesita
    conocerla, solo existe para que el lector de PDF haga cumplir los
    permisos (el usuario abre el archivo sin contraseña)."""
    from pyhanko.pdf_utils.crypt.permissions import StandardPermissions
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.pdf_utils.writer import copy_into_new_writer
    from pyhanko.sign import PdfSignatureMetadata, signers

    reader = PdfFileReader(io.BytesIO(pdf_bytes))
    writer = copy_into_new_writer(reader)

    owner_pw = secrets.token_urlsafe(24)
    permisos = (
        StandardPermissions.ALLOW_PRINTING
        | StandardPermissions.ALLOW_HIGH_QUALITY_PRINTING
        | StandardPermissions.ALLOW_ASSISTIVE_TECHNOLOGY
    )
    writer.encrypt(owner_pass=owner_pw, user_pass="", perms=permisos)

    signer = _signer_desde_pem(cert_pem, key_pem)
    meta = PdfSignatureMetadata(field_name="IntegridadDocumento", reason=_RAZON_FIRMA)
    out = signers.sign_pdf(writer, meta, signer=signer)
    return out.getvalue()
