"""Verificación de webhooks de Didit: HMAC-SHA256 + freshness del timestamp.

Decisiones de seguridad:
- Fail-closed: si DIDIT_WEBHOOK_SECRET está vacía, siempre rechaza.
- Comparación en tiempo constante (hmac.compare_digest) para evitar timing attacks.
- Freshness: rechaza eventos con timestamp a más de MAX_DRIFT_S segundos del reloj
  del servidor (ventana ±300s, igual que el chequeo de JWT estándar). Protege
  contra replay attacks.
- Ley 25.326: este módulo NO loguea el body del webhook (puede contener datos
  personales); el route loguea solo session_id y status.

Didit firma cada webhook con varios headers (mismo secret, distinto algoritmo):
  - `X-Signature`    → HMAC sobre el body CRUDO (los bytes exactos transmitidos).
  - `X-Signature-V2` → HMAC sobre el JSON canonicalizado (keys ordenadas, separadores
                       compactos, ensure_ascii=False, floats recortados).
Verificamos `X-Signature` como variante principal: leemos el body crudo antes de
cualquier middleware, así que el HMAC sobre esos bytes matchea exactamente —sin
depender de reproducir la canonicalización de Didit (incluye "shorten_floats",
frágil de replicar). `X-Signature-V2` se chequea como respaldo best-effort
(resiliente si un proxy re-serializara el body). Alcanza con que UNA matchee
(ambas requieren el secret → un atacante no puede forjar ninguna).

Bug histórico (#didit): se leía el header `X-Signature-V2` pero se hasheaba el
body CRUDO → solo coincidía cuando el body ya era canónico (payloads chicos:
"Not Started"/"In Progress"); el "Approved" (JSON anidado + Unicode de RENAPER)
fallaba la firma y la verificación de identidad nunca se persistía.

Refs: https://docs.didit.me/integration/webhooks
"""

import hashlib
import hmac
import json
import time

from config import settings

MAX_DRIFT_S = 300  # ±5 minutos, igual que los JWT estándar


class DiditSignatureError(Exception):
    """Firma inválida o timestamp fuera del margen de freshness."""


def _canonical_json(body: bytes) -> bytes | None:
    """JSON canónico que firma `X-Signature-V2`: keys ordenadas (recursivo),
    separadores compactos, Unicode preservado. Best-effort: NO replica el
    `shorten_floats` de Didit, así que para payloads con floats el match cae en
    `X-Signature` (body crudo). Devuelve None si el body no es JSON parseable."""
    try:
        obj = json.loads(body)
    except (ValueError, TypeError):
        return None
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hmac_hex(msg: bytes) -> str:
    return hmac.new(
        settings.DIDIT_WEBHOOK_SECRET.encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()


def verify_webhook(
    *,
    body: bytes,
    signature: str = "",
    timestamp: str,
    signature_v2: str = "",
    now: float | None = None,
) -> None:
    """Verifica la firma HMAC-SHA256 y el freshness del timestamp de un webhook.

    Función pura: no toca la BD ni el estado global. Apta para tests unitarios.

    Args:
        body:         Raw bytes del request body (antes de cualquier parsing).
        signature:    Header `X-Signature` — HMAC sobre el body crudo (principal).
        timestamp:    Header `X-Timestamp` (unix seconds, string).
        signature_v2: Header `X-Signature-V2` — HMAC sobre el JSON canónico (respaldo).
        now:          Override del tiempo actual — solo para tests.

    Raises:
        DiditSignatureError: ninguna firma presente verifica, timestamp fuera de
                             rango, o DIDIT_WEBHOOK_SECRET no configurado.
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

    # 2. HMAC-SHA256 en tiempo constante. Cada firma presente se prueba contra su
    #    propio algoritmo; alcanza con que UNA matchee (ambas usan el mismo secret,
    #    así que aceptar cualquiera no debilita la autenticación). Didit puede
    #    enviar el digest con o sin prefijo "sha256="; normalizamos.
    candidatos: list[tuple[str, str]] = []
    if signature:
        candidatos.append((signature.removeprefix("sha256="), _hmac_hex(body)))
    if signature_v2:
        canonical = _canonical_json(body)
        if canonical is not None:
            candidatos.append((signature_v2.removeprefix("sha256="), _hmac_hex(canonical)))

    if not candidatos:
        raise DiditSignatureError("Falta header de firma (X-Signature / X-Signature-V2)")
    if any(hmac.compare_digest(recibida, esperada) for recibida, esperada in candidatos):
        return
    raise DiditSignatureError("Firma HMAC inválida")
