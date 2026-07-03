"""Tests de firma WSAA — sin red. Solo firma CMS y parseo de TRA.

Genera un certificado auto-firmado on-the-fly para poder probar firmar_tra()
sin necesitar el cert de ARCA (que es secreto y está en ENV).
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import datetime as dt


# ---------------------------------------------------------------------------
# Fixtures: cert auto-firmado de test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_keypair():
    """RSA 2048 key pair + cert auto-firmado válido por 1 día."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "test-rambla-arca")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.timezone.utc))
        .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return cert_pem, key_pem


# ---------------------------------------------------------------------------
# Tests de construir_tra
# ---------------------------------------------------------------------------


def test_tra_es_xml_valido():
    from arca_fe.wsaa import construir_tra

    tra = construir_tra("wsfe")
    root = ET.fromstring(tra)
    assert root.tag == "loginTicketRequest"


def test_tra_contiene_servicio():
    from arca_fe.wsaa import construir_tra

    tra = construir_tra("wsfe")
    root = ET.fromstring(tra)
    service_el = root.find("service")
    assert service_el is not None
    assert service_el.text == "wsfe"


def test_tra_tiempos_razonables():
    from arca_fe.wsaa import construir_tra, _TRA_TTL_SECONDS

    ahora = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    tra = construir_tra("wsfe", ahora=ahora)
    root = ET.fromstring(tra)
    header = root.find("header")
    gen_time = datetime.fromisoformat(header.find("generationTime").text)
    exp_time = datetime.fromisoformat(header.find("expirationTime").text)

    # Hora argentina explícita (AFIP interpreta un timestamp sin tz como local)
    assert gen_time.utcoffset() == timedelta(hours=-3)
    assert exp_time.utcoffset() == timedelta(hours=-3)
    # genTime = 10 min antes de `ahora`; expTime = ahora + TTL configurado
    assert gen_time.astimezone(timezone.utc) == ahora - timedelta(minutes=10)
    assert exp_time.astimezone(timezone.utc) == ahora + timedelta(
        seconds=_TRA_TTL_SECONDS
    )


def test_tra_unique_id_en_rango():
    from arca_fe.wsaa import construir_tra

    tra = construir_tra()
    root = ET.fromstring(tra)
    uid = int(root.find("header/uniqueId").text)
    assert 0 < uid < 2**31


# ---------------------------------------------------------------------------
# Tests de firmar_tra
# ---------------------------------------------------------------------------


def test_firmar_tra_devuelve_bytes(test_keypair):
    from arca_fe.wsaa import construir_tra, firmar_tra

    cert_pem, key_pem = test_keypair
    tra = construir_tra()
    der = firmar_tra(tra, cert_pem, key_pem)
    assert isinstance(der, bytes)
    assert len(der) > 0


def test_firma_es_der_codificado(test_keypair):
    """DER de CMS empieza con 0x30 (SEQUENCE)."""
    from arca_fe.wsaa import construir_tra, firmar_tra

    cert_pem, key_pem = test_keypair
    tra = construir_tra()
    der = firmar_tra(tra, cert_pem, key_pem)
    assert der[0] == 0x30  # DER SEQUENCE


def test_firma_codificable_en_base64(test_keypair):
    from arca_fe.wsaa import construir_tra, firmar_tra

    cert_pem, key_pem = test_keypair
    tra = construir_tra()
    der = firmar_tra(tra, cert_pem, key_pem)
    b64 = base64.b64encode(der).decode("ascii")
    # Debe ser base64 ASCII válido
    assert re.match(r"^[A-Za-z0-9+/]+=*$", b64)


# ---------------------------------------------------------------------------
# Tests de clave privada con passphrase + errores tipados
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_keypair_cifrado():
    """Igual que test_keypair pero con la clave privada cifrada con passphrase
    conocida (b"secreto")."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "test-rambla-arca-cifrado")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.timezone.utc))
        .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.BestAvailableEncryption(b"secreto"),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return cert_pem, key_pem


def test_firmar_tra_con_clave_cifrada_y_password_correcta(test_keypair_cifrado):
    from arca_fe.wsaa import construir_tra, firmar_tra

    cert_pem, key_pem = test_keypair_cifrado
    der = firmar_tra(
        construir_tra(), cert_pem, key_pem, key_password=b"secreto"
    )
    assert der[0] == 0x30  # DER SEQUENCE


def test_firmar_tra_clave_cifrada_sin_password_levanta_auth(test_keypair_cifrado):
    """Clave cifrada + sin passphrase → ArcaAuthError con mensaje accionable,
    no el TypeError críptico de cryptography."""
    from arca_fe.wsaa import construir_tra, firmar_tra
    from arca_fe.errores import ArcaAuthError

    cert_pem, key_pem = test_keypair_cifrado
    with pytest.raises(ArcaAuthError, match="passphrase"):
        firmar_tra(construir_tra(), cert_pem, key_pem)


def test_firmar_tra_clave_cifrada_password_incorrecta_levanta_auth(
    test_keypair_cifrado,
):
    from arca_fe.wsaa import construir_tra, firmar_tra
    from arca_fe.errores import ArcaAuthError

    cert_pem, key_pem = test_keypair_cifrado
    with pytest.raises(ArcaAuthError):
        firmar_tra(construir_tra(), cert_pem, key_pem, key_password=b"mala")


def test_firmar_tra_cert_invalido_levanta_auth(test_keypair):
    from arca_fe.wsaa import construir_tra, firmar_tra
    from arca_fe.errores import ArcaAuthError

    _, key_pem = test_keypair
    with pytest.raises(ArcaAuthError, match="certificado"):
        firmar_tra(construir_tra(), b"-----BEGIN CERTIFICATE-----\nno-es-pem\n", key_pem)


# ---------------------------------------------------------------------------
# Tests de _parece_base64 (estricto) y errores de transporte
# ---------------------------------------------------------------------------


def test_parece_base64_estricto():
    """El heurístico viejo ("¿decodifica como ASCII?") daba un falso positivo
    para bytes ASCII que NO son base64 (ej. con espacio o '!'), y esos se
    usaban crudos en vez de codificarse. Con validate=True eso se rechaza."""
    from arca_fe.wsaa import _parece_base64

    # base64 válido → True
    assert _parece_base64(base64.b64encode(b"hola mundo")) is True
    # ASCII pero NO base64 (espacio y '!') → el viejo daba True (falso
    # positivo); el nuevo da False → se codifica, como corresponde.
    assert _parece_base64(b"hello world!") is False
    # bytes DER crudos (no alfabeto base64) → False → se codificarán
    assert _parece_base64(b"\x30\x82\x01\x00\xff\xfe") is False


def test_login_request_error_es_arca_network_error(monkeypatch):
    """Un timeout/conexión (httpx.RequestError) se traduce a ArcaNetworkError,
    no se filtra el httpx crudo al consumidor."""
    import httpx
    from arca_fe.wsaa import login
    from arca_fe.errores import ArcaNetworkError

    def _boom(*a, **k):
        raise httpx.ConnectTimeout("timeout simulado")

    monkeypatch.setattr(httpx, "post", _boom)
    with pytest.raises(ArcaNetworkError, match="No se pudo contactar"):
        login(b"Zm9v", "https://wsaahomo.afip.gov.ar")


def test_parsear_respuesta_sin_expiration_loguea_fallback(caplog):
    """Sin expirationTime → fallback de 12h PERO logueado (no silencioso)."""
    import logging
    from arca_fe.wsaa import _parsear_login_response

    xml = """<loginTicketResponse version="1.0">
  <credentials><token>T</token><sign>S</sign></credentials>
</loginTicketResponse>"""
    with caplog.at_level(logging.WARNING, logger="arca_fe.wsaa"):
        token, sign, expira_at = _parsear_login_response(xml)
    assert token == "T"
    assert any("expirationTime" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Tests de parseo de respuesta WSAA (sin red)
# ---------------------------------------------------------------------------


_WSAA_RESPONSE_OK = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <loginCmsResponse xmlns="http://wsaa.view.sua.dvadac.desein.afip.gov.ar">
      <loginCmsReturn><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<loginTicketResponse version="1.0">
  <header>
    <source>CN=wsaahomo.afip.gov.ar</source>
    <destination>SERIALNUMBER=CUIT 20123456789</destination>
    <uniqueId>12345678</uniqueId>
    <generationTime>2024-06-15T10:00:00</generationTime>
    <expirationTime>2024-06-15T22:00:00-03:00</expirationTime>
  </header>
  <credentials>
    <token>TOKEN_EJEMPLO_ABC123</token>
    <sign>SIGN_EJEMPLO_XYZ789</sign>
  </credentials>
</loginTicketResponse>]]></loginCmsReturn>
    </loginCmsResponse>
  </soapenv:Body>
</soapenv:Envelope>"""


def test_parsear_respuesta_wsaa_ok():
    from arca_fe.wsaa import _parsear_login_response

    # La respuesta anidada en CDATA
    inner_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<loginTicketResponse version="1.0">
  <header>
    <expirationTime>2024-06-15T22:00:00-03:00</expirationTime>
  </header>
  <credentials>
    <token>TOKEN_EJEMPLO_ABC123</token>
    <sign>SIGN_EJEMPLO_XYZ789</sign>
  </credentials>
</loginTicketResponse>"""

    token, sign, expira_at = _parsear_login_response(inner_xml)
    assert token == "TOKEN_EJEMPLO_ABC123"
    assert sign == "SIGN_EJEMPLO_XYZ789"
    assert expira_at.tzinfo is not None


def test_parsear_respuesta_wsaa_sin_token_lanza():
    from arca_fe.wsaa import _parsear_login_response
    from arca_fe.errores import ArcaResponseError

    bad_xml = """<loginTicketResponse version="1.0">
  <credentials><sign>OK</sign></credentials>
</loginTicketResponse>"""
    with pytest.raises(ArcaResponseError, match="token/sign") as ei:
        _parsear_login_response(bad_xml)
    # el XML crudo queda en .raw para diagnóstico
    assert "loginTicketResponse" in ei.value.raw


def test_wsaa_url_normaliza_endpoint():
    from arca_fe.wsaa import _wsaa_url

    assert _wsaa_url("wsaahomo.afip.gov.ar") == (
        "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
    )
    assert _wsaa_url("https://wsaahomo.afip.gov.ar") == (
        "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
    )
    # Ya con el suffix → no duplica
    full = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
    assert _wsaa_url(full) == full
