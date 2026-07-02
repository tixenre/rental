"""services.facturacion.padron — autocompletar razón social/domicilio/condición
IVA a partir de un CUIT, vía el padrón de ARCA (WSDL personaServiceA5, servicio
WSAA "ws_sr_constancia_inscripcion" — antes "ws_sr_padron_a5", deprecado).

Es una comodidad de carga (lo mismo que hace el facturador oficial de ARCA al
tipear un CUIT) — NUNCA bloquea: el formulario sigue siendo editable a mano
pase lo que pase. Pero "ARCA no tiene datos para este CUIT" y "no pudimos ni
preguntarle a ARCA" son cosas MUY distintas para diagnosticar (la primera es
un hecho de AFIP; la segunda es nuestro/su lado — WSAA no autoriza, relación
no delegada, cert vencido, red) — `resolver_persona` las distingue: None solo
para la primera (o sin emisor autenticador), RuntimeError con el motivo real
para la segunda, que el route (admin-only) muestra tal cual. No participa del
flujo de emisión de comprobantes (no toca `arca_fe.wsfe`/`engine.py`).

Cualquier emisor activo con cert cargado sirve para autenticar la consulta —
el padrón responde por CUALQUIER CUIT consultado, no solo el que autentica.
"""
from __future__ import annotations

from typing import Optional

from arca_fe.padron import PadronClient, PersonaArca, WSAA_SERVICIO

_PADRON_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"
_PADRON_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"


def resolver_persona(cuit_buscado: str, conn) -> Optional[PersonaArca]:
    """Consulta el padrón para `cuit_buscado`.

    None: no hay ningún emisor con cert para autenticar, o AFIP respondió que
    no tiene datos para ese CUIT (`arca_fe.padron.PadronClient.get_persona` ya
    distingue esto de un fault real — ver sus tests).

    Levanta RuntimeError con el motivo real para cualquier OTRA falla (WSAA no
    autoriza el servicio, relación no delegada, cert vencido, red, timeout) —
    NO se swallowea: decirle al admin "ARCA no tiene datos" cuando en realidad
    no pudimos ni completar la consulta es engañoso y no se puede diagnosticar
    desde afuera. El caller (route, admin-only) decide qué mostrar."""
    from services.facturacion.config import credenciales
    from services.facturacion.wsaa_cache import get_ta

    from services.facturacion.emisores_repo import elegir_autenticador

    emisor_autenticador = elegir_autenticador(conn)
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
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo consultar el padrón con el emisor '{emisor_autenticador}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc
