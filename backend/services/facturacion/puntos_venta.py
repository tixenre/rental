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


def _tiene_fecha_de_baja(fch_baja) -> bool:
    """`FchBaja` en la respuesta REAL de `FEParamGetPtosVenta` (no la del WSDL/manual) viene como
    la STRING LITERAL `"NULL"` — no `None`, no el elemento ausente — cuando el punto de venta NO
    está dado de baja (quirk conocido del lado de ARCA). Sin este chequeo, `if p.get("FchBaja")`
    trataba ese `"NULL"` como una fecha real → TODO punto de venta salía "dado de baja" sin
    importar su estado verdadero (bug real: un punto de venta activo, usado para emitir una
    factura con éxito, aparecía excluido acá)."""
    return bool(fch_baja) and str(fch_baja).strip().upper() != "NULL"


def _es_cae(emision_tipo) -> bool:
    """`EmisionTipo` en la respuesta REAL de `FEParamGetPtosVenta` NO es el literal `"CAE"` — ARCA
    le agrega el régimen fiscal del emisor como sufijo (confirmado en producción: `"CAE -
    Monotributo"` para un punto de venta habilitado y usado con éxito para facturar). Sin este
    chequeo, `EmisionTipo != "CAE"` marcaba TODO punto de venta electrónico como "no_electronico"
    sin importar su estado real (mismo patrón que el bug de `FchBaja="NULL"`). Se acepta el
    prefijo `"CAE"` seguido de nada o de `" - <lo que sea>"` — pero NO `"CAEA"` (Autorización
    Electrónica Anticipada, un mecanismo distinto: lote pre-autorizado en vez de `FECAESolicitar`
    online, que esta librería no implementa)."""
    valor = str(emision_tipo or "").strip()
    return valor == "CAE" or valor.startswith("CAE -")


def consultar_puntos_venta(nombre_emisor: str, conn) -> dict:
    """Puntos de venta de `nombre_emisor`, separados en habilitados para
    facturación electrónica y excluidos (con motivo).

    Devuelve `{"habilitados": [{"nro": ...}], "excluidos": [{"nro": ...,
    "motivo": "bloqueado" | "dado_de_baja" | "no_electronico", "raw_emision_tipo": ...}]}`.
    Antes esto descartaba los no-habilitados en silencio — si ARCA devolvía puntos pero
    todos bloqueados, se veía el mismo "no hay nada" que si ARCA no tenía
    NINGÚN punto creado; son causas distintas (desbloquear vs. crear uno
    nuevo), así que el motivo de cada exclusión se preserva para que el
    front pueda mostrarlo en vez de un mensaje genérico.

    `raw_emision_tipo` viaja en CUALQUIER exclusión con motivo `no_electronico` — el valor
    EXACTO que ARCA devolvió en `EmisionTipo`, sin normalizar. Mismo criterio que el bug real
    de `FchBaja="NULL"` (ver `_tiene_fecha_de_baja`): la respuesta real de ARCA puede diferir
    de lo documentado, y no hay forma de confirmar un quirk nuevo sin ver el valor crudo — se
    expone acá en vez de asumir qué debería decir.

    Raises:
        ValueError: emisor no encontrado/inactivo/sin cert (mapea a 400).
        arca_fe.ArcaError: ARCA no respondió o rechazó la consulta — se deja
        pasar tal cual para que el route elija el status HTTP por subtipo.
    """
    from arca_fe.wsfe import WsfeClient
    from services.facturacion.config import credenciales
    from services.facturacion.wsaa_cache import get_ta

    cred = credenciales(nombre_emisor, conn)
    token, sign = get_ta(nombre_emisor, conn)
    wsfe = WsfeClient(endpoint=cred.endpoint_wsfe, cuit=cred.cuit, token=token, sign=sign)
    puntos = wsfe.param_puntos_venta()

    habilitados = []
    excluidos = []
    for p in puntos:
        if p.get("Bloqueado") == "S":
            excluidos.append({"nro": p["Nro"], "motivo": "bloqueado"})
        elif _tiene_fecha_de_baja(p.get("FchBaja")):
            excluidos.append({"nro": p["Nro"], "motivo": "dado_de_baja"})
        elif not _es_cae(p.get("EmisionTipo")):
            excluidos.append(
                {
                    "nro": p["Nro"],
                    "motivo": "no_electronico",
                    "raw_emision_tipo": p.get("EmisionTipo"),
                }
            )
        else:
            habilitados.append({"nro": p["Nro"]})

    return {"habilitados": habilitados, "excluidos": excluidos}
