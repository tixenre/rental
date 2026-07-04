"""services.facturacion.signing_cert — persistencia del certificado de firma de PDFs.

La generación del par (certificado, clave) y la protección del PDF en sí (permisos + firma PAdES)
viven en `arca_fe.generar_cert_autofirmado`/`arca_fe.asegurar_pdf` — puras, sin IO. Este módulo
solo aporta lo que esas funciones no pueden resolver solas: DÓNDE persistir el certificado (una
sola vez, cifrado en `app_settings`, mismo patrón que el resto de credenciales ARCA —
`services.facturacion.crypto`, Fernet con `ARCA_MASTER_KEY`). Es un certificado de PLATAFORMA (uno
solo, no por emisor/tenant): prueba integridad del archivo, no identidad fiscal, así que no tiene
sentido gestionar uno por cada emisor/negocio que use este motor.
"""
from __future__ import annotations

import arca_fe

from services.facturacion.crypto import decrypt, encrypt

_CN = "Comprobantes — Motor de Facturación"
_SETTING_CERT = "facturacion_pdf_signing_cert"
_SETTING_KEY = "facturacion_pdf_signing_key"


def get_or_create_signing_cert(conn) -> tuple[bytes, bytes]:
    """(cert_pem, key_pem) del certificado de firma de PDFs. Se genera una única vez (primer uso,
    vía `arca_fe.generar_cert_autofirmado`) y queda persistido cifrado en `app_settings`; llamadas
    siguientes leen el mismo par."""
    rows = conn.execute(
        "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
        ([_SETTING_CERT, _SETTING_KEY],),
    ).fetchall()
    found = {r["key"]: r["value"] for r in rows}
    if _SETTING_CERT not in found or _SETTING_KEY not in found:
        cert_pem, key_pem = arca_fe.generar_cert_autofirmado(_CN)
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
        # Re-leer: si otra request ganó la carrera del INSERT, usamos SU par (nunca dos certs
        # "ganadores" distintos convivendo).
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
            ([_SETTING_CERT, _SETTING_KEY],),
        ).fetchall()
        found = {r["key"]: r["value"] for r in rows}
    return decrypt(found[_SETTING_CERT].encode("ascii")), decrypt(found[_SETTING_KEY].encode("ascii"))
