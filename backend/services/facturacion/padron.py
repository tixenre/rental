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
propio portal de AFIP, que igual devolvía "sin datos". Por eso `get_persona`
YA NO devuelve None en silencio: o devuelve la persona, o levanta el motivo
tipado real (ArcaBusinessError con el texto de AFIP, o ArcaResponseError con la
respuesta cruda). `resolver_persona` captura ese motivo por emisor y, si
ninguno resuelve, levanta RuntimeError con el motivo de cada uno + **el
ambiente** en que consultó (producción/homologación — clave: homologación solo
conoce CUIT de prueba). El route (admin-only) lo muestra tal cual. No participa
del flujo de emisión de comprobantes (no toca `arca_fe.wsfe`/`engine.py`).

Puede haber más de un emisor activo con cert cargado y solo alguno de ellos
tener la relación 'Consulta de constancia de inscripción' delegada en ARCA
(cada emisor delega la suya de forma independiente) — por eso NO alcanza con
probar uno solo: `resolver_persona` reintenta con cada emisor activo con cert,
en orden, hasta que uno devuelva persona; recién si TODOS fallan levanta el
RuntimeError nombrando a cada uno con su motivo real y el ambiente.
"""

from __future__ import annotations

from arca_fe.padron import PadronClient, PersonaArca, WSAA_SERVICIO

_PADRON_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"
_PADRON_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"


def resolver_persona(cuit_buscado: str, conn) -> PersonaArca:
    """Consulta el padrón para `cuit_buscado`, probando con cada emisor activo
    con certificado hasta que uno lo resuelva (cada emisor delega su propia
    relación 'Consulta de constancia de inscripción' de forma independiente).

    Devuelve la `PersonaArca` si AFIP la encontró con alguno. Si NINGÚN emisor
    la resuelve, levanta RuntimeError con **el motivo real de AFIP por cada
    emisor probado** y **el ambiente** (producción/homologación) en el que se
    consultó — así el admin ve exactamente qué pasó (CUIT inexistente, bloqueo
    de negocio, relación no delegada, cert vencido, red, o ambiente de prueba)
    en vez de un genérico "sin datos ni motivo". NO se swallowea nada a None.
    El caller (route, admin-only) nunca rompe el formulario, que sigue editable
    a mano."""
    from services.facturacion.config import credenciales
    from services.facturacion.wsaa_cache import get_ta
    from services.facturacion.emisores_repo import list_emisores
    from arca_fe import ArcaError
    from config import settings as app_settings

    candidatos = [e.nombre for e in list_emisores(conn) if e.activo and e.cert_cargado]
    if not candidatos:
        raise RuntimeError(
            "No hay ningún emisor activo con certificado cargado para autenticar "
            "la consulta al padrón."
        )

    ambiente = "producción" if app_settings.is_production else "homologación"

    intentos: list[str] = []
    for emisor_autenticador in candidatos:
        cuit_auth = "?"
        try:
            cred = credenciales(emisor_autenticador, conn)
            cuit_auth = str(cred.cuit)
            token, sign = get_ta(emisor_autenticador, conn, servicio=WSAA_SERVICIO)
            endpoint = _PADRON_PROD if cred.ambiente == "produccion" else _PADRON_HOMO
            client = PadronClient(
                endpoint=endpoint, cuit_representada=cred.cuit, token=token, sign=sign
            )
            # `get_persona` ya NO devuelve None: o devuelve la persona, o levanta
            # ArcaBusinessError/ArcaResponseError con el motivo real de AFIP.
            return client.get_persona(cuit_buscado)
        except (ArcaError, ValueError) as exc:
            # Motivo tipado de AFIP (auth/relación/negocio/respuesta) o de
            # config (ValueError de `credenciales`) — se registra por emisor y
            # se sigue probando el resto.
            intentos.append(f"'{emisor_autenticador}' (CUIT {cuit_auth}): {exc}")
        except Exception as exc:  # último recurso: se surfacea igual, no se traga
            intentos.append(
                f"'{emisor_autenticador}' (CUIT {cuit_auth}): "
                f"{type(exc).__name__}: {exc}"
            )

    if ambiente == "homologación":
        guia = (
            "Estás consultando en HOMOLOGACIÓN: la base de prueba de AFIP solo "
            "conoce unos pocos CUIT de test, así que cualquier CUIT real da 'no "
            "existe' — no es un error de datos, es el ambiente."
        )
    else:
        guia = (
            "Estás consultando en PRODUCCIÓN: si el CUIT buscado tiene Constancia "
            "de Inscripción vigente y AFIP igual no lo devuelve, revisá que el "
            "emisor autenticador tenga la relación 'Consulta de constancia de "
            "inscripción' delegada en el Administrador de Relaciones de Clave Fiscal."
        )

    raise RuntimeError(
        f"No se pudo traer el padrón del CUIT {cuit_buscado} — consultado en "
        f"AMBIENTE {ambiente.upper()}. Motivo de AFIP por cada emisor "
        f"autenticador probado: {' | '.join(intentos)}. {guia}"
    )
