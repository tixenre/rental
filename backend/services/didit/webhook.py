"""Verificación de webhooks de Didit: HMAC-SHA256 + freshness del timestamp.

Decisiones de seguridad:
- Fail-closed: si DIDIT_WEBHOOK_SECRET está vacía, siempre rechaza.
- Comparación en tiempo constante (hmac.compare_digest) para evitar
  timing attacks.
- Freshness: rechaza eventos con timestamp a más de MAX_DRIFT_S segundos
  del reloj del servidor (ventana ±300s, igual que el chequeo de JWT
  estándar). Protege contra replay attacks.
- Ley 25.326: este módulo NO loguea el body del webhook (puede contener
  datos personales); el route loguea solo session_id y status.

Refs: https://docs.didit.me/reference/webhooks
"""

import hashlib
import hmac
import time

from config import settings

MAX_DRIFT_S = 300  # ±5 minutos, igual que los JWT estándar


class DiditSignatureError(Exception):
    """Firma inválida o timestamp fuera del margen de freshness."""


def verify_webhook(
    *,
    body: bytes,
    signature: str,
    timestamp: str,
    now: float | None = None,
) -> None:
    """Verifica la firma HMAC-SHA256 y el freshness del timestamp de un webhook.

    Función pura: no toca la BD ni el estado global. Apta para tests unitarios.

    Args:
        body:      Raw bytes del request body (antes de cualquier parsing).
        signature: Valor del header X-Signature-V2.
        timestamp: Valor del header X-Timestamp (unix seconds, string).
        now:       Override del tiempo actual — solo para tests.

    Raises:
        DiditSignatureError: Firma inválida, timestamp fuera de rango, o
                             DIDIT_WEBHOOK_SECRET no configurado.
    """
    if not settings.DIDIT_WEBHOOK_SECRET:
        raise DiditSignatureError("DIDIT_WEBHOOK_SECRET no configurado (feature apagada)")

    # 1. Freshness: el evento no puede tener más de MAX_DRIFT_S segundos de antigüedad.
    _now = now if now is not None else time.time()
    try:
        event_ts = int(timestamp)
    except (ValueError, TypeError):
        raise DiditSignatureError("X-Timestamp inválido")
    if abs(_now - event_ts) > MAX_DRIFT_S:
        raise DiditSignatureError(
            f"X-Timestamp fuera del margen de freshness ({MAX_DRIFT_S}s)"
        )

    # 2. HMAC-SHA256 en tiempo constante (evita timing attacks).
    expected = hmac.new(
        settings.DIDIT_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    # Didit puede enviar el digest con o sin prefijo "sha256="; normalizamos.
    received = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, received):
        raise DiditSignatureError("Firma HMAC inválida")
