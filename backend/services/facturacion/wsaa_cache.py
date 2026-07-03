"""services.facturacion.wsaa_cache — cache del Ticket de Acceso en `afip_ta`.

Obtiene (token, sign) frescos: lee `afip_ta`, renueva si falta o está vencido,
persiste el nuevo TA. El refresh es serializado por fila via SELECT FOR UPDATE
para evitar que dos workers pidan el TA simultáneamente.

Nota: no usa threading.Lock porque Railway corre un solo proceso uvicorn; el
FOR UPDATE de Postgres es suficiente para serializar.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Renovar TA si le quedan menos de N minutos de vida
_MARGEN_MINUTOS = 30


def get_ta(emisor: str, conn, servicio: str = "wsfe") -> tuple[str, str]:
    """Devuelve (token, sign) vigentes para el emisor + servicio.

    Un TA autentica una relación (CUIT del cert ↔ SERVICIO) — el de "wsfe" no
    sirve para otro servicio (ej. "ws_sr_constancia_inscripcion"), por eso el
    cache es por (ambiente, emisor, servicio), no solo por emisor.

    Si el TA está vencido (o no existe), llama al WSAA y persiste el nuevo.
    `conn` es una conexión de `database.get_db()` ya en contexto de transacción
    (dentro de `with get_db() as conn:`).
    """
    from services.facturacion.config import credenciales
    from arca_fe.wsaa import login_con_cert

    cred = credenciales(emisor, conn)
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(minutes=_MARGEN_MINUTOS)

    # Intentar usar el TA cacheado (FOR UPDATE para serializar renovación)
    row = conn.execute(
        """
        SELECT token, sign, expira_at
          FROM afip_ta
         WHERE ambiente = %s AND emisor = %s AND servicio = %s
        FOR UPDATE
        """,
        (cred.ambiente, emisor, servicio),
    ).fetchone()

    if row and _vigente(row["expira_at"], limite):
        return row["token"], row["sign"]

    # Necesitamos un TA nuevo
    if not cred.cert_pem or not cred.key_pem:
        raise RuntimeError(
            f"Certificado de '{emisor}' no cargado. "
            "Subí el cert + clave desde el back-office → Facturación ARCA → Emisores."
        )

    try:
        token, sign, expira_at = login_con_cert(
            servicio,
            cred.cert_pem.encode() if isinstance(cred.cert_pem, str) else cred.cert_pem,
            cred.key_pem.encode() if isinstance(cred.key_pem, str) else cred.key_pem,
            cred.endpoint_wsaa,
        )
    except (RuntimeError, ValueError):
        raise
    except Exception as exc:
        # httpx.HTTPStatusError (AFIP 4xx/5xx), httpx.RequestError (timeout/red), etc.
        raise RuntimeError(
            f"Error al contactar WSAA ({cred.endpoint_wsaa}): {type(exc).__name__}: {exc}"
        ) from exc

    conn.execute(
        """
        INSERT INTO afip_ta (ambiente, emisor, servicio, token, sign, expira_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ambiente, emisor, servicio)
        DO UPDATE SET token = EXCLUDED.token,
                      sign  = EXCLUDED.sign,
                      expira_at = EXCLUDED.expira_at
        """,
        (cred.ambiente, emisor, servicio, token, sign, expira_at),
    )

    return token, sign


def _vigente(expira_at: datetime, limite: datetime) -> bool:
    if expira_at is None:
        return False
    if expira_at.tzinfo is None:
        expira_at = expira_at.replace(tzinfo=timezone.utc)
    return expira_at > limite
