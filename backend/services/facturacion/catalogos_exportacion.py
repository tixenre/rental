"""services.facturacion.catalogos_exportacion — catálogos de WSFEXv1 (`FEXGetPARAM_*`) cacheados
en `app_settings`.

Paralelo a `catalogos.py` (WSFEv1) — mismo criterio: se refrescan explícitamente (acción del admin),
las funciones de lectura solo leen el cache, fallan fuerte si nunca se refrescó. Necesarios para
poblar los selects del formulario admin de Factura de Exportación (país destino/Incoterm/moneda)
sin hardcodear valores a mano."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

_CATALOGOS = {
    "paises_destino": "arca_exportacion_catalogo_paises_destino",
    "incoterms": "arca_exportacion_catalogo_incoterms",
    "monedas": "arca_exportacion_catalogo_monedas",
}
_SETTING_FETCHED_AT = "arca_exportacion_catalogos_fetched_at"


def refrescar_catalogos_exportacion(conn) -> dict[str, list[dict]]:
    """Consulta a ARCA los catálogos de WSFEXv1 y los persiste en `app_settings`. Requiere un
    emisor ACTIVO, con cert, Y habilitado para exportación (`emisores_arca.habilitado_exportacion`)
    — el catálogo es global, pero autenticar contra WSFEXv1 exige la relación de servicio propia.

    Raises:
        ValueError: no hay ningún emisor activo/con cert/habilitado para exportación.
        arca_fe.ArcaError: ARCA no respondió o rechazó la consulta — se deja pasar tal cual (mismo
        criterio que `catalogos.refrescar_catalogos`)."""
    from arca_fe.wsfex import WsfexClient, WSFEX_WSAA_SERVICIO
    from services.facturacion.config import credenciales
    from services.facturacion.emisores_repo import list_emisores
    from services.facturacion.wsaa_cache import get_ta

    emisor_nombre = next(
        (e.nombre for e in list_emisores(conn) if e.activo and e.cert_cargado and e.habilitado_exportacion),
        None,
    )
    if emisor_nombre is None:
        raise ValueError(
            "No hay ningún emisor activo, con certificado cargado y habilitado para exportación "
            "para autenticar la consulta. Marcá 'habilitado_exportacion' en el back-office → "
            "Facturación ARCA → Emisores."
        )

    cred = credenciales(emisor_nombre, conn)
    token, sign = get_ta(emisor_nombre, conn, servicio=WSFEX_WSAA_SERVICIO)
    wsfex = WsfexClient(endpoint=cred.endpoint_wsfex, cuit=cred.cuit, token=token, sign=sign)

    paises_destino = [
        {"id": p.get("DST_CODIGO") or p.get("Codigo"), "desc": p.get("DST_Ds") or p.get("Ds")}
        for p in wsfex.param_paises_destino()
    ]
    incoterms = [
        {"id": i.get("Id"), "desc": i.get("Ds")} for i in wsfex.param_incoterms()
    ]
    monedas = [
        {"id": m.get("Mon_Id") or m.get("Id"), "desc": m.get("Mon_Ds") or m.get("Ds")}
        for m in wsfex.param_monedas()
    ]

    resultado = {"paises_destino": paises_destino, "incoterms": incoterms, "monedas": monedas}

    for clave, items in resultado.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, 'arca-catalogos-exportacion')
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by,
                                             updated_at = CURRENT_TIMESTAMP
            """,
            (_CATALOGOS[clave], json.dumps(items)),
        )
    ahora = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_by) VALUES (%s, %s, 'arca-catalogos-exportacion')
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
            f"El catálogo '{clave}' de WSFEXv1 todavía no se consultó — corré "
            '"Actualizar catálogos de exportación" desde el back-office.'
        )
    return json.loads(row["value"])


def paises_destino(conn) -> list[dict]:
    return _leer_catalogo("paises_destino", conn)


def incoterms(conn) -> list[dict]:
    return _leer_catalogo("incoterms", conn)


def monedas(conn) -> list[dict]:
    return _leer_catalogo("monedas", conn)
