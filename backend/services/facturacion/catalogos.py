"""services.facturacion.catalogos — catálogos de ARCA (WSFE `FEParamGet*`)
cacheados en `app_settings`, para que las etiquetas que se muestran en el PDF
salgan de ARCA y no de una traducción escrita a mano en el código.

Por qué cachear en vez de consultar en vivo en cada render de PDF: estos
catálogos (tipo de documento, concepto, condición IVA del receptor) son
prácticamente permanentes (documentados por ARCA desde el inicio de WSFEv1),
pero consultarlos requiere un round-trip SOAP autenticado — no tiene sentido
que CADA descarga de un PDF ya emitido dependa de que ARCA esté arriba en ese
instante. Se refrescan explícitamente (acción del admin, `refrescar_catalogos`)
y las funciones de lectura (`label_*`) solo leen el cache — si nunca se
refrescó, fallan fuerte (RuntimeError) en vez de inventar una traducción.

Distinto del padrón (best-effort, silencioso): acá el admin dispara el
refresco a propósito, así que si falla tiene que enterarse por qué.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

# Clave en `app_settings` por catálogo + timestamp del último refresco exitoso.
_CATALOGOS = {
    "doc_tipo": "arca_catalogo_doc_tipo",
    "concepto": "arca_catalogo_concepto",
    "condicion_iva_receptor": "arca_catalogo_condicion_iva_receptor",
}
_SETTING_FETCHED_AT = "arca_catalogos_fetched_at"

# FEParamGetCondicionIvaReceptor no tiene un valor "todas las clases" — hay
# que pedirlas una por una y unificar. "M" NO es una clase válida acá (bug de
# prod: ARCA devuelve 10244 "El valor ingresado para la clase de comprobante
# no es valido... solo puede ser 'A', 'B', 'C', 'ALEY' o '49'") — son las 5
# únicas clases que este webservice puntual acepta.
_CLASES_CMP = ("A", "B", "C", "ALEY", "49")


def refrescar_catalogos(conn) -> dict[str, list[dict]]:
    """Consulta a ARCA los catálogos y los persiste en `app_settings`.
    Cualquier emisor activo con cert sirve para autenticar — el catálogo es
    global, no depende de qué CUIT consulta.

    Raises:
        ValueError: no hay ningún emisor activo con cert cargado.
        arca_fe.ArcaError: ARCA no respondió o rechazó la consulta — se deja
        pasar tal cual (sin envolver en RuntimeError) para que el route
        distinga el subtipo y elija el status HTTP correcto (422/502/503).
    """
    from arca_fe.wsfe import WsfeClient
    from services.facturacion.config import credenciales
    from services.facturacion.emisores_repo import elegir_autenticador
    from services.facturacion.wsaa_cache import get_ta

    emisor = elegir_autenticador(conn)
    if emisor is None:
        raise ValueError(
            "No hay ningún emisor activo con certificado cargado para autenticar la consulta."
        )

    cred = credenciales(emisor, conn)
    token, sign = get_ta(emisor, conn)
    wsfe = WsfeClient(endpoint=cred.endpoint_wsfe, cuit=cred.cuit, token=token, sign=sign)

    doc_tipo = [{"id": d["Id"], "desc": d["Desc"]} for d in wsfe.param_tipos_doc()]
    concepto = [{"id": c["Id"], "desc": c["Desc"]} for c in wsfe.param_tipos_concepto()]

    condicion_iva_receptor: dict[int, str] = {}
    for clase in _CLASES_CMP:
        for c in wsfe.param_condicion_iva_receptor(clase):
            condicion_iva_receptor[c["Id"]] = c["Desc"]
    condicion_iva_receptor_lista = [
        {"id": k, "desc": v} for k, v in sorted(condicion_iva_receptor.items())
    ]

    resultado = {
        "doc_tipo": doc_tipo,
        "concepto": concepto,
        "condicion_iva_receptor": condicion_iva_receptor_lista,
    }

    for clave, items in resultado.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, 'arca-catalogos')
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by,
                                             updated_at = CURRENT_TIMESTAMP
            """,
            (_CATALOGOS[clave], json.dumps(items)),
        )
    ahora = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, 'arca-catalogos')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by,
                                         updated_at = CURRENT_TIMESTAMP
        """,
        (_SETTING_FETCHED_AT, ahora),
    )

    return resultado


def ultimo_refresco(conn) -> Optional[str]:
    """Timestamp ISO del último refresco exitoso, o None si nunca se corrió."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = %s", (_SETTING_FETCHED_AT,)
    ).fetchone()
    return row["value"] if row else None


def _leer_catalogo(clave: str, conn) -> list[dict]:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = %s", (_CATALOGOS[clave],)
    ).fetchone()
    if row is None:
        raise RuntimeError(
            f"El catálogo '{clave}' de ARCA todavía no se consultó — "
            "corré \"Actualizar catálogos ARCA\" desde el back-office."
        )
    return json.loads(row["value"])


def _label(clave: str, id_: int, conn) -> str:
    """Etiqueta del `id_` en el catálogo `clave`. Si el catálogo está
    cacheado pero no incluye ese id (ej. quedó desactualizado), muestra el
    id crudo en vez de inventar un texto — más honesto que adivinar."""
    items = _leer_catalogo(clave, conn)
    for item in items:
        if str(item["id"]) == str(id_):
            return item["desc"]
    return str(id_)


def label_doc_tipo(id_: int, conn) -> str:
    return _label("doc_tipo", id_, conn)


def label_concepto(id_: int, conn) -> str:
    return _label("concepto", id_, conn)


def label_condicion_iva_receptor(id_: int, conn) -> str:
    return _label("condicion_iva_receptor", id_, conn)
