"""arca_fe._ssl_afip — ajuste de TLS compartido para los servidores de ARCA.
PORTABLE (solo stdlib).

Los servidores de AFIP/ARCA (WSAA, WSFEv1, padrón) usan parámetros DH cortos
(DH_KEY_TOO_SMALL) que OpenSSL moderno rechaza por default. `SECLEVEL=1` los
acepta sin bajar la verificación del certificado del servidor (`verify=True`
se mantiene en todos los callers). Fuente única — antes esto vivía duplicado
en `wsfe.py` y `padron.py`, con `wsaa.py` (que usa httpx, no requests) sin el
mismo ajuste; una tercera copia divergente era cuestión de tiempo.
"""
from __future__ import annotations

import ssl


def afip_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    return ctx
