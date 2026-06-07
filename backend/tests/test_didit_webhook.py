"""Tests de la verificación de firma del webhook de Didit.

Cubre (como piezas puras, sin DB ni red):
  - Firma válida: verify_webhook no lanza.
  - Firma inválida: DiditSignatureError.
  - Timestamp demasiado viejo: DiditSignatureError.
  - Timestamp demasiado del futuro: DiditSignatureError.
  - Prefijo "sha256=" en la firma: se normaliza correctamente.
  - Secret no configurado: DiditSignatureError (fail-closed).
"""

import hashlib
import hmac
import time

import pytest

from services.didit.webhook import DiditSignatureError, MAX_DRIFT_S, verify_webhook

pytestmark = pytest.mark.unit

_SECRET = "test-webhook-secret-didit"
_BODY = b'{"session_id":"abc123","status":"Approved","vendor_data":"42"}'


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _now_ts() -> str:
    return str(int(time.time()))


# ── Fixture: parchea el secret en settings ──────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_secret(monkeypatch):
    import services.didit.webhook as wh_mod
    monkeypatch.setattr(wh_mod.settings, "DIDIT_WEBHOOK_SECRET", _SECRET)


# ── Casos ────────────────────────────────────────────────────────────────────

def test_firma_valida():
    ts = _now_ts()
    sig = _sign(_BODY)
    verify_webhook(body=_BODY, signature=sig, timestamp=ts)


def test_firma_valida_con_prefijo_sha256():
    ts = _now_ts()
    sig = "sha256=" + _sign(_BODY)
    verify_webhook(body=_BODY, signature=sig, timestamp=ts)


def test_firma_invalida():
    with pytest.raises(DiditSignatureError, match="inválida"):
        verify_webhook(
            body=_BODY,
            signature="deadbeef" * 8,
            timestamp=_now_ts(),
        )


def test_body_modificado():
    ts = _now_ts()
    sig = _sign(_BODY)
    body_tampered = _BODY + b" "
    with pytest.raises(DiditSignatureError, match="inválida"):
        verify_webhook(body=body_tampered, signature=sig, timestamp=ts)


def test_timestamp_muy_viejo():
    ts_viejo = str(int(time.time()) - MAX_DRIFT_S - 1)
    sig = _sign(_BODY)
    with pytest.raises(DiditSignatureError, match="freshness"):
        verify_webhook(body=_BODY, signature=sig, timestamp=ts_viejo)


def test_timestamp_muy_del_futuro():
    ts_futuro = str(int(time.time()) + MAX_DRIFT_S + 1)
    sig = _sign(_BODY)
    with pytest.raises(DiditSignatureError, match="freshness"):
        verify_webhook(body=_BODY, signature=sig, timestamp=ts_futuro)


def test_timestamp_invalido():
    with pytest.raises(DiditSignatureError, match="inválido"):
        verify_webhook(body=_BODY, signature=_sign(_BODY), timestamp="no-es-numero")


def test_secret_no_configurado(monkeypatch):
    import services.didit.webhook as wh_mod
    monkeypatch.setattr(wh_mod.settings, "DIDIT_WEBHOOK_SECRET", "")
    with pytest.raises(DiditSignatureError, match="no configurado"):
        verify_webhook(body=_BODY, signature=_sign(_BODY), timestamp=_now_ts())


def test_override_now():
    """El parámetro `now` permite controlar el reloj en tests sin depender de
    time.time() — útil para simular timestamps exactos."""
    base = 1_700_000_000
    ts = str(base)
    sig = _sign(_BODY)
    # Exactamente en el límite: debería pasar.
    verify_webhook(body=_BODY, signature=sig, timestamp=ts, now=float(base + MAX_DRIFT_S))
    # Un segundo más: debe fallar.
    with pytest.raises(DiditSignatureError, match="freshness"):
        verify_webhook(
            body=_BODY,
            signature=sig,
            timestamp=ts,
            now=float(base + MAX_DRIFT_S + 1),
        )
