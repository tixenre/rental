"""services.facturacion.padron — autocompletar razón social/domicilio/condición
IVA a partir de un CUIT, vía el padrón de ARCA (WSDL personaServiceA5, servicio
WSAA "ws_sr_constancia_inscripcion" — antes "ws_sr_padron_a5", deprecado).

Es una comodidad de carga (lo mismo que hace el facturador oficial de ARCA al
tipear un CUIT) — NUNCA bloquea: el formulario sigue siendo editable a mano
pase lo que pase. Pero "ARCA no tiene datos para este CUIT" resultó ser
engañoso en la práctica para CASI todo lo que puede fallar acá: (a) AFIP SÍ
conoce el CUIT pero bloquea la constancia por una regla de negocio propia
(ej. sin adhesión a Domicilio Fiscal Electrónico, RG 3990-E); (b) no pudimos
ni completar la consulta (WSAA no autoriza, relación no delegada, cert
vencido, red, sin emisor con cert configurado); (c) — encontrado en vivo con
un CUIT real, activo, con Constancia de Inscripción vigente confirmada en el
propio portal de AFIP, que igual devolvía "sin datos" — AFIP responde sin
ningún dato NI motivo, casi siempre porque el CUIT del EMISOR AUTENTICADOR
(no el buscado) no tiene la relación de este servicio delegada. Por eso
`resolver_persona` YA NO devuelve None en silencio para (c): levanta
RuntimeError con el nombre y CUIT del emisor autenticador, para que se pueda
verificar la relación del lado correcto. RuntimeError para (a), (b) y (c),
que el route (admin-only) muestra tal cual. No participa del flujo de
emisión de comprobantes (no toca `arca_fe.wsfe`/`engine.py`).

Cualquier emisor activo con cert cargado sirve para autenticar la consulta —
el padrón responde por CUALQUIER CUIT consultado, no solo el que autentica.
"""
from __future__ import annotations

from arca_fe.padron import PadronClient, PersonaArca, WSAA_SERVICIO

_PADRON_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"
_PADRON_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"


def resolver_persona(cuit_buscado: str, conn) -> PersonaArca:
    """Consulta el padrón para `cuit_buscado`. Devuelve la `PersonaArca` si
    AFIP la encontró.

    Levanta RuntimeError con el motivo para CUALQUIER otro caso — sin emisor
    con cert para autenticar, WSAA no autoriza el servicio, relación no
    delegada, cert vencido, red, timeout, bloqueo de negocio de AFIP, o AFIP
    respondiendo sin datos ni motivo (lo más probable ahí: el CUIT del emisor
    AUTENTICADOR, no el buscado, no tiene la relación de este servicio
    delegada en AFIP — el mensaje lo nombra). NO se swallowea nada a None:
    decirle al admin "ARCA no tiene datos" cuando en realidad no pudimos
    completar la consulta es engañoso y no se puede diagnosticar desde
    afuera. El caller (route, admin-only) decide qué mostrar — nunca rompe
    el formulario, que sigue editable a mano."""
    from services.facturacion.config import credenciales
    from services.facturacion.wsaa_cache import get_ta

    from services.facturacion.emisores_repo import elegir_autenticador

    emisor_autenticador = elegir_autenticador(conn)
    if emisor_autenticador is None:
        raise RuntimeError(
            "No hay ningún emisor activo con certificado cargado para autenticar "
            "la consulta al padrón."
        )

    try:
        cred = credenciales(emisor_autenticador, conn)
        token, sign = get_ta(emisor_autenticador, conn, servicio=WSAA_SERVICIO)
        endpoint = _PADRON_PROD if cred.ambiente == "produccion" else _PADRON_HOMO
        client = PadronClient(
            endpoint=endpoint, cuit_representada=cred.cuit, token=token, sign=sign
        )
        persona = client.get_persona(cuit_buscado)
    except RuntimeError:
        # `get_persona` ya arma un RuntimeError con el mensaje de negocio de
        # AFIP en texto plano (ej. "No consta... adhesión al domicilio fiscal
        # electrónico...") — mostrarlo tal cual, sin envolverlo de nuevo.
        raise
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo consultar el padrón con el emisor '{emisor_autenticador}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if persona is None:
        raise RuntimeError(
            f"ARCA no devolvió datos ni motivo para este CUIT, autenticando con "
            f"el emisor '{emisor_autenticador}' (CUIT {cred.cuit}). Si el CUIT "
            f"buscado tiene Constancia de Inscripción vigente (verificable en el "
            f"propio portal de ARCA), revisá que el CUIT {cred.cuit} — el del "
            f"emisor autenticador, no necesariamente el buscado — tenga la "
            f"relación 'Consulta de constancia de inscripción' delegada en el "
            f"Administrador de Relaciones de Clave Fiscal."
        )
    return persona
