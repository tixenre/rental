"""services.facturacion.puntos_venta — puntos de venta habilitados de un
emisor, consultados en vivo a ARCA (WSFE `FEParamGetPtosVenta`).

A diferencia del padrón (que responde por CUALQUIER CUIT autenticando con
el cert de cualquier emisor), acá el emisor tiene que autenticarse con SU
PROPIO cert — WSFE devuelve los puntos de venta DEL CUIT AUTENTICADO, no de
un CUIT arbitrario. Por eso esto es una acción explícita del admin sobre UN
emisor concreto (no un autocompletado en segundo plano como el padrón): si
falla, importa por qué (cert vencido, relación no delegada, ARCA caída), así
que propaga el error en vez de degradar a `[]`.

Sirve para validar/elegir el punto de venta en vez de cargarlo a mano y
descubrir recién al pedir el primer CAE que estaba mal.
"""
from __future__ import annotations


def consultar_puntos_venta(nombre_emisor: str, conn) -> list[dict]:
    """Puntos de venta de `nombre_emisor` habilitados para facturación
    electrónica: excluye los bloqueados, dados de baja, o que no emiten por
    CAE (los puntos de venta "manuales"/imprenta no sirven acá).

    Raises:
        ValueError: emisor no encontrado/inactivo/sin cert (mapea a 400).
        RuntimeError: ARCA no respondió o rechazó la consulta (mapea a 503).
    """
    from arca_fe import ArcaError
    from arca_fe.wsfe import WsfeClient
    from services.facturacion.config import credenciales
    from services.facturacion.wsaa_cache import get_ta

    cred = credenciales(nombre_emisor, conn)
    token, sign = get_ta(nombre_emisor, conn)
    wsfe = WsfeClient(endpoint=cred.endpoint_wsfe, cuit=cred.cuit, token=token, sign=sign)
    try:
        puntos = wsfe.param_puntos_venta()
    except ArcaError as exc:
        raise RuntimeError(str(exc)) from exc

    return [
        {"nro": p["Nro"]}
        for p in puntos
        if p.get("EmisionTipo") == "CAE" and p.get("Bloqueado") != "S" and not p.get("FchBaja")
    ]
