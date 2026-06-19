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
import json
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


def test_signature_v2_canonical_valida():
    """`X-Signature-V2` firma el JSON canónico (keys ordenadas, compacto,
    ensure_ascii=False). Pasado como signature_v2, verifica."""
    canonical = json.dumps(
        json.loads(_BODY), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    sig_v2 = hmac.new(_SECRET.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    verify_webhook(body=_BODY, signature_v2=sig_v2, timestamp=_now_ts())


def test_regresion_approved_no_canonico():
    """Regresión del bug real: el header `X-Signature-V2` firma el JSON CANÓNICO,
    NO el body crudo. Un payload no-canónico (keys desordenadas + Unicode), como el
    'Approved' con datos de RENAPER:
      - su firma X-Signature (sobre el crudo) verifica por la rama `signature`;
      - su firma X-Signature-V2 (sobre el canónico) verifica por `signature_v2`;
      - el bug viejo —leer V2 pero hashear el crudo— rechazaba esto (la firma V2
        no coincide con el HMAC del body crudo).
    """
    raw = (
        '{"status":"Approved","kyc":{"last_name":"García","first_name":"José"},'
        '"session_id":"s1","vendor_data":"42"}'
    ).encode("utf-8")
    canonical = json.dumps(
        json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert canonical != raw, "el caso de test exige un body NO canónico"

    ts = _now_ts()
    sig_raw = hmac.new(_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    sig_v2 = hmac.new(_SECRET.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

    # Ambas variantes verifican el mismo body.
    verify_webhook(body=raw, signature=sig_raw, timestamp=ts)
    verify_webhook(body=raw, signature_v2=sig_v2, timestamp=ts)

    # El bug viejo: la firma V2 tratada como si fuera sobre el crudo → rechazada.
    with pytest.raises(DiditSignatureError, match="inválida"):
        verify_webhook(body=raw, signature=sig_v2, timestamp=ts)


def test_sin_ningun_header_de_firma():
    """Sin X-Signature ni X-Signature-V2 → rechaza (no se cuela un webhook sin firma)."""
    with pytest.raises(DiditSignatureError, match="Falta header"):
        verify_webhook(body=_BODY, timestamp=_now_ts())


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
