"""Alta passwordless → cuenta liviana, Postgres real (Fase 4 identidad).

Ejerce el flujo `POST /auth/passkey/signup/{begin,complete}` contra Postgres: una
cuenta-cliente nace SOLO con `id` + passkey, sin nombre/mail/datos. Lo que el
FakeConn de los unit no captura y por eso va contra DB real:

  - los `NOT NULL` relajados de `clientes` (nombre/apellido/telefono/email/
    direccion/cuit) → el INSERT liviano entra;
  - el `UNIQUE(email)` sigue permitiendo **múltiples NULL** → dos cuentas livianas
    coexisten (Postgres no colisiona NULLs);
  - `passkey_credentials.owner_email = ''` (la cuenta no tiene mail) satisface el
    `NOT NULL` y el CHECK de `owner_type='cliente'`;
  - la cuenta queda **inerte**: `cliente_verificado` = False (gate de pedidos) hasta
    que Didit la complete.

Solo se mockea la verificación WebAuthn (la lib `webauthn`); el resto es real
(transacción, esquema, minteo de sesión server-side). Opt-in: RESERVAS_DB_TEST=1.
"""
import os
from urllib.parse import urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_OPT_IN = os.getenv("RESERVAS_DB_TEST") == "1"
_DB_NAME = urlparse(os.getenv("DATABASE_URL", "")).path.lstrip("/")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _OPT_IN, reason="opt-in: RESERVAS_DB_TEST=1 + DATABASE_URL de test"),
    pytest.mark.skipif(
        _OPT_IN and "test" not in _DB_NAME.lower(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]


def _client() -> TestClient:
    from auth import auth_passkey_router as router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _signup(c: TestClient, monkeypatch, *, credential_id: str) -> int:
    """Corre begin→complete con la verificación WebAuthn mockeada. Devuelve el
    cliente_id de la cuenta liviana recién creada (leído de la sesión minteada)."""
    from auth.passkey import ceremonies
    from auth.session import signer

    # begin: opciones + cookie de challenge firmada REAL (signup=True) — la lleva el client.
    assert c.post("/auth/passkey/signup/begin").status_code == 200
    # complete: mockeamos SOLO la verificación de la lib; el INSERT es real.
    monkeypatch.setattr(
        ceremonies, "verify_registration",
        lambda **kw: {"credential_id": credential_id, "public_key": "pk-" + credential_id,
                      "sign_count": 0, "aaguid": "aa"},
    )
    r = c.post("/auth/passkey/signup/complete",
               json={"credential": {"id": credential_id, "response": {"transports": ["internal"]}},
                     "device_name": "iPhone"})
    assert r.status_code == 200, r.text
    sess = signer.loads(r.cookies["session"])
    assert sess["role"] == "cliente" and sess["email"] == ""
    return sess["cliente_id"]


def test_alta_passwordless_crea_cuenta_liviana_inerte():
    from database import init_db, get_db
    from auth.guards import cliente_verificado
    from auth.ratelimit import _failures as _rl_failures

    init_db()
    _rl_failures.clear()

    created: list[int] = []
    cred_a, cred_b = "cred-liviana-AAA", "cred-liviana-BBB"
    try:
        with get_db() as conn:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM passkey_credentials WHERE credential_id IN (%s, %s)",
                    (cred_a, cred_b),
                )

        from _pytest.monkeypatch import MonkeyPatch
        mp = MonkeyPatch()
        try:
            c = _client()
            cid_a = _signup(c, mp, credential_id=cred_a)
            # Segunda alta: otra cuenta liviana (otra passkey). Prueba que DOS cuentas
            # con email NULL coexisten (UNIQUE(email) no colisiona NULLs).
            c2 = _client()
            cid_b = _signup(c2, mp, credential_id=cred_b)
        finally:
            mp.undo()
        created = [cid_a, cid_b]
        assert cid_a != cid_b

        with get_db() as conn:
            # La cuenta nació liviana, sin datos.
            row = conn.execute(
                "SELECT cuenta_estado, nombre, apellido, email, telefono, direccion, cuit "
                "FROM clientes WHERE id = %s", (cid_a,),
            ).fetchone()
            assert row["cuenta_estado"] == "liviana"
            assert row["nombre"] is None and row["apellido"] is None
            assert row["email"] is None and row["telefono"] is None
            assert row["direccion"] is None and row["cuit"] is None

            # La passkey quedó atada a la cuenta con owner_email='' (sin mail).
            pk = conn.execute(
                "SELECT owner_type, owner_email, cliente_id FROM passkey_credentials "
                "WHERE credential_id = %s", (cred_a,),
            ).fetchone()
            assert pk["owner_type"] == "cliente"
            assert pk["owner_email"] == ""
            assert pk["cliente_id"] == cid_a

            # Inerte hasta Didit: el gate de pedidos la bloquea.
            assert cliente_verificado(conn, cid_a) is False
    finally:
        with get_db() as conn:
            with conn.transaction():
                for cid in created:
                    conn.execute("DELETE FROM clientes WHERE id = %s", (cid,))
