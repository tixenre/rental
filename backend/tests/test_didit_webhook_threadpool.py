"""Regresión: el webhook async NO debe correr el httpx SÍNCRONO de
`retrieve_decision` en el event loop.

`webhook_didit` es `async def` (necesita `await request.body()` para el HMAC).
Sin el fix llamaba `retrieve_decision(session_id)` directo — un GET httpx
síncrono de hasta 30s — dentro del handler async → un webhook 'liviano' (sin la
`decision` embebida) **congelaba el event loop** hasta el timeout. El fix lo
envuelve en `run_in_threadpool` para que corra en un worker thread.
"""
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import main

pytestmark = pytest.mark.unit

_SECRET = "test-webhook-secret-didit"


def _sign(body: bytes) -> str:
    return hmac.new(_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_retrieve_decision_se_offloadea_a_threadpool(monkeypatch):
    import routes.didit as didit_mod
    import services.didit.webhook as wh_mod

    monkeypatch.setattr(wh_mod.settings, "DIDIT_WEBHOOK_SECRET", _SECRET)

    # Spy sobre run_in_threadpool: registra qué función se offloadea y la ejecuta.
    offloaded = []

    async def fake_run_in_threadpool(func, *args, **kwargs):
        offloaded.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(didit_mod, "run_in_threadpool", fake_run_in_threadpool)
    # retrieve_decision mockeado (no toca red); _guardar_verificacion no-op (no DB).
    monkeypatch.setattr(didit_mod, "retrieve_decision", lambda sid: {"id_verifications": []})
    monkeypatch.setattr(didit_mod, "_guardar_verificacion", lambda **kw: None)

    # Payload 'liviano' Approved (sin `decision`) → fuerza el fallback retrieve_decision.
    body = json.dumps(
        {"session_id": "abc123", "status": "Approved", "vendor_data": "42"}
    ).encode("utf-8")
    headers = {
        "X-Signature": _sign(body),
        "X-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
    }

    client = TestClient(main.app, raise_server_exceptions=False)
    res = client.post("/api/webhooks/didit", content=body, headers=headers)

    assert res.status_code == 200
    assert didit_mod.retrieve_decision in offloaded, (
        "retrieve_decision (httpx síncrono) no se offloadeó a run_in_threadpool "
        "→ bloquearía el event loop del servidor"
    )
