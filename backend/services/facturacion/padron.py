"""services.facturacion.padron — autocompletar razón social/domicilio/condición
IVA a partir de un CUIT, vía el padrón de ARCA (ws_sr_padron_a13).

Es una comodidad de carga (lo mismo que hace el facturador oficial de ARCA al
tipear un CUIT) — NUNCA crítico: si el padrón no responde, no está configurado,
o el CUIT no tiene datos, el caller degrada a "no se pudo autocompletar" y el
usuario carga los datos a mano como siempre. No participa del flujo de emisión
de comprobantes (no toca `arca_fe.wsfe`/`engine.py`).

Cualquier emisor activo con cert cargado sirve para autenticar la consulta —
el padrón responde por CUALQUIER CUIT consultado, no solo el que autentica.
"""
from __future__ import annotations

from typing import Optional

from arca_fe.padron import PadronClient, PersonaArca, WSAA_SERVICIO

_PADRON_HOMO = "awshomo.afip.gov.ar"
_PADRON_PROD = "aws.afip.gov.ar"


def resolver_persona(cuit_buscado: str, conn) -> Optional[PersonaArca]:
    """Consulta el padrón para `cuit_buscado`. None si no se pudo resolver
    (sin emisor autenticador disponible, AFIP no respondió, o sin datos)."""
    from services.facturacion.config import credenciales
    from services.facturacion.wsaa_cache import get_ta

    emisor_autenticador = _elegir_autenticador(conn)
    if emisor_autenticador is None:
        return None

    try:
        cred = credenciales(emisor_autenticador, conn)
        token, sign = get_ta(emisor_autenticador, conn, servicio=WSAA_SERVICIO)
        endpoint = _PADRON_PROD if cred.ambiente == "produccion" else _PADRON_HOMO
        client = PadronClient(
            endpoint=endpoint, cuit_representada=cred.cuit, token=token, sign=sign
        )
        return client.get_persona(cuit_buscado)
    except Exception:
        # Autocompletado best-effort: cualquier falla (AFIP caído, relación de
        # padrón no delegada, cert vencido) degrada a "no se pudo", no rompe
        # el formulario que está pidiendo el dato.
        return None


def _elegir_autenticador(conn) -> Optional[str]:
    """El primer emisor activo con cert cargado — cualquiera sirve para
    autenticar la consulta de padrón (no tiene que ser el CUIT buscado)."""
    from services.facturacion.emisores_repo import list_emisores

    for emisor in list_emisores(conn):
        if emisor.activo and emisor.cert_cargado:
            return emisor.nombre
    return None
