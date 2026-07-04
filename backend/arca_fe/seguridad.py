"""arca_fe.seguridad — protección del PDF ya renderizado. PORTABLE.

Tres capas, DISTINTAS del CAE/QR de ARCA (que valida el comprobante fiscal contra los servidores
de ARCA — eso no se toca acá, vive en `arca_fe.qr`/`arca_fe.wsfe`):

  - **Permisos**: se puede abrir/ver/imprimir libremente (sin contraseña), pero no editar ni
    copiar texto/imágenes — evita que alguien "levante" un CUIT o un monto con un copy-paste, o
    edite el PDF y lo reenvíe como si fuera el original.
  - **Firma de integridad de archivo (PAdES)**: certificado PROPIO autofirmado (no el de ARCA) que
    prueba que el PDF no fue alterado desde que este motor lo generó — cualquier lector de PDF
    (Adobe, etc.) lo muestra como "documento no modificado desde la firma". No reemplaza al
    CAE/QR (eso certifica el comprobante fiscal en sí); esto certifica el ARCHIVO.
  - **Metadatos embebidos** (opcional) + **sello de tiempo RFC 3161** (opcional, vía una TSA
    externa): ver `asegurar_pdf`.

El certificado de firma NO lo genera este módulo por sí solo en cada llamada — `generar_cert_autofirmado`
es la pieza portable (RSA 2048, autofirmado); persistirlo (una vez, cifrado) es responsabilidad
del caller, que sabe DÓNDE guardarlo (cada app tiene su propio almacén de config/secrets).

Ambos pasos base (permisos + firma) se aplican en un ÚNICO writer de pyhanko (encriptar primero,
firmar después, sobre el mismo objeto) — PyMuPDF y pyhanko no son intercambiables acá: MuPDF
guarda el diccionario `/Encrypt` como objeto directo y pyhanko exige que sea una referencia
indirecta, así que un PDF "protegido" con PyMuPDF y después firmado con pyhanko no se puede leer.
La encriptación tiene que salir del mismo writer que después firma.
"""
from __future__ import annotations

import io
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

_logger = logging.getLogger(__name__)

_RAZON_FIRMA = "Certifica que el archivo no fue modificado desde su generación."


# ---------------------------------------------------------------------------
# Certificado de firma — autofirmado, puro (sin IO: el caller decide dónde/cómo persistirlo)
# ---------------------------------------------------------------------------


def generar_cert_autofirmado(cn: str) -> tuple[bytes, bytes]:
    """Genera un par (certificado, clave privada) autofirmado — RSA 2048, válido 10 años, PEM.

    `cn`: el `CommonName` del certificado (identifica QUÉ firma, ej. "Comprobantes — Motor de
    Facturación de Rambla") — es un certificado de PLATAFORMA (prueba integridad de archivo, no
    identidad fiscal), no hace falta uno por emisor/tenant.

    Puro: no persiste nada — el caller decide dónde guardar el par (típicamente cifrado, una sola
    vez, reusado en llamadas siguientes; ver el patrón `get_or_create_signing_cert` de un adapter
    típico: buscar en el almacén propio, generar con esta función solo si no existe, guardar).

    Devuelve `(cert_pem, key_pem)`, ambos en formato PEM (bytes)."""
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


# ---------------------------------------------------------------------------
# Protección del PDF: permisos + metadatos + firma (+ sello de tiempo opcional)
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


def _build_encrypted_writer(pdf_bytes: bytes, metadata: Optional[dict[str, str]]):
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.crypt.permissions import StandardPermissions
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.pdf_utils.writer import copy_into_new_writer

    reader = PdfFileReader(io.BytesIO(pdf_bytes))
    writer = copy_into_new_writer(reader)

    if metadata:
        writer.set_info(generic.DictionaryObject({
            generic.NameObject(f"/{k}"): generic.TextStringObject(v)
            for k, v in metadata.items()
        }))

    owner_pw = secrets.token_urlsafe(24)
    permisos = (
        StandardPermissions.ALLOW_PRINTING
        | StandardPermissions.ALLOW_HIGH_QUALITY_PRINTING
        | StandardPermissions.ALLOW_ASSISTIVE_TECHNOLOGY
    )
    writer.encrypt(owner_pass=owner_pw, user_pass="", perms=permisos)
    return writer


def asegurar_pdf(
    pdf_bytes: bytes,
    cert_pem: bytes,
    key_pem: bytes,
    *,
    metadata: Optional[dict[str, str]] = None,
    tsa_url: Optional[str] = None,
) -> bytes:
    """Restringe permisos (ver/imprimir sí, editar/copiar no), embebe metadatos opcionales y firma
    el archivo (integridad PAdES) — devuelve los bytes finales del PDF a entregar.

    `cert_pem`/`key_pem`: el par de `generar_cert_autofirmado` (o cualquier cert/key PEM válido).
    `metadata`: dict opcional de metadatos del `Info` dict del PDF (ej. `{"Title": "Factura A
    00003-00000042", "Subject": "CAE 71234567890123"}`) — así el archivo se autoidentifica aunque
    se lo extraiga de su contexto (ej. reenviado suelto por mail). `None` (default) no agrega
    ningún metadato — comportamiento idéntico a antes de este parámetro.
    `tsa_url`: URL de una Time Stamping Authority (RFC 3161) para sellar CUÁNDO se firmó, además de
    QUE no se modificó — opcional, `None` (default) no pide timestamp. **Fail-open**: si la TSA no
    responde (red caída, timeout — 5s por intento, sin reintento), se firma IGUAL sin timestamp —
    un tercero externo caído nunca debe bloquear la entrega de un comprobante. La URL de la TSA es
    decisión del caller; esta función no hardcodea ningún proveedor.

    La contraseña de propietario del PDF es aleatoria por documento: nadie necesita conocerla,
    solo existe para que el lector de PDF haga cumplir los permisos (el usuario abre el archivo
    sin contraseña)."""
    from pyhanko.sign import PdfSignatureMetadata, signers

    signer = _signer_desde_pem(cert_pem, key_pem)
    meta = PdfSignatureMetadata(field_name="IntegridadDocumento", reason=_RAZON_FIRMA)

    if tsa_url:
        from pyhanko.sign.timestamps import HTTPTimeStamper

        try:
            writer = _build_encrypted_writer(pdf_bytes, metadata)
            out = signers.sign_pdf(
                writer, meta, signer=signer, timestamper=HTTPTimeStamper(tsa_url)
            )
            return out.getvalue()
        except Exception:
            _logger.warning(
                "asegurar_pdf: la TSA %s no respondió — firmando sin sello de tiempo.",
                tsa_url,
                exc_info=True,
            )

    writer = _build_encrypted_writer(pdf_bytes, metadata)
    out = signers.sign_pdf(writer, meta, signer=signer)
    return out.getvalue()
