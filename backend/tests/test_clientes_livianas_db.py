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


def _mk_liviana(conn, *, estado="liviana", dias_old, email=None) -> int:
    return conn.insert_returning(
        """INSERT INTO clientes (cuenta_estado, email, created_at)
           VALUES (%s, %s, NOW() - make_interval(days => %s))""",
        (estado, email, dias_old),
    )


def test_cleanup_borra_solo_las_livianas_abandonadas():
    """El barrido borra SOLO la liviana inequívocamente abandonada (vieja, sin
    verificar, sin contacto, sin pedidos) y respeta todo lo demás."""
    from database import init_db, get_db
    from jobs.cleanup_livianas import purgar_cuentas_livianas_stale

    init_db()
    mails = ("cl_link@test.local", "cl_completa@test.local")
    created: list[int] = []
    try:
        with get_db() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM clientes WHERE email IN (%s, %s)", mails)
                # (1) abandonada → DEBE borrarse
                ab = _mk_liviana(conn, dias_old=40)
                # (2) liviana reciente → sobrevive (no pasó el plazo)
                reciente = _mk_liviana(conn, dias_old=2)
                # (3) liviana vieja pero VERIFICADA → sobrevive
                verif = _mk_liviana(conn, dias_old=40)
                conn.execute("UPDATE clientes SET dni_validado_at = NOW() WHERE id = %s", (verif,))
                # (4) liviana vieja pero con CONTACTO (email linkeado) → sobrevive
                linked = _mk_liviana(conn, dias_old=40, email=mails[0])
                # (5) liviana vieja pero con un PEDIDO → sobrevive (y no se orfana el pedido)
                con_pedido = _mk_liviana(conn, dias_old=40)
                conn.execute(
                    "INSERT INTO alquileres (cliente_id, cliente_nombre) VALUES (%s, %s)",
                    (con_pedido, "Test Pedido"),
                )
                # (6) cuenta COMPLETA vieja → sobrevive (no nació por el alta passwordless)
                completa = _mk_liviana(conn, estado="completa", dias_old=40, email=mails[1])
        created = [ab, reciente, verif, linked, con_pedido, completa]

        borradas = purgar_cuentas_livianas_stale()
        assert borradas >= 1  # al menos la nuestra (puede haber otras en una DB compartida)

        with get_db() as conn:
            def existe(cid: int) -> bool:
                return conn.execute("SELECT 1 FROM clientes WHERE id = %s", (cid,)).fetchone() is not None

            assert existe(ab) is False          # la abandonada se fue
            assert existe(reciente) is True     # el resto sobrevive
            assert existe(verif) is True
            assert existe(linked) is True
            assert existe(con_pedido) is True
            assert existe(completa) is True
            # el pedido de (5) sigue apuntando a su cliente (no se orfanó)
            ped = conn.execute(
                "SELECT cliente_id FROM alquileres WHERE cliente_id = %s", (con_pedido,)
            ).fetchone()
            assert ped is not None
    finally:
        with get_db() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM alquileres WHERE cliente_nombre = %s", ("Test Pedido",))
                for cid in created:
                    conn.execute("DELETE FROM clientes WHERE id = %s", (cid,))


def test_merge_absorbe_la_cuenta_liviana_y_mueve_sus_llaves():
    """El merge-on-link une dos cuentas de la misma persona: mueve las llaves de la
    cuenta liviana a la cuenta real y la borra. `account_is_absorbable` solo deja
    absorber lo vacío (liviana, sin verificar, sin pedidos)."""
    from database import init_db, get_db
    from auth.account_merge import account_is_absorbable, merge_accounts

    init_db()
    cred = "cred-merge-src"
    mail = "merge_real@test.local"
    created: list[int] = []
    try:
        with get_db() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM passkey_credentials WHERE credential_id = %s", (cred,))
                conn.execute("DELETE FROM clientes WHERE email = %s", (mail,))
                # source: cuenta liviana con una passkey
                src = conn.insert_returning(
                    "INSERT INTO clientes (cuenta_estado) VALUES (%s)", ("liviana",))
                conn.execute(
                    """INSERT INTO passkey_credentials
                           (owner_type, owner_email, cliente_id, credential_id, public_key,
                            sign_count, user_handle)
                       VALUES ('cliente', '', %s, %s, 'pk', 0, 'uh')""",
                    (src, cred))
                # una lista guardada en la cuenta liviana → tiene que MUDARSE (no perderse)
                lista_id = conn.insert_returning(
                    "INSERT INTO cliente_listas (cliente_id, nombre) VALUES (%s, %s)",
                    (src, "Lista de prueba merge"))
                # target: cuenta real (completa) con identidad Google
                tgt = conn.insert_returning(
                    """INSERT INTO clientes (cuenta_estado, nombre, apellido, email, telefono,
                                             direccion, cuit)
                       VALUES ('completa', %s, %s, %s, %s, %s, %s)""",
                    ("Real", "Cuenta", mail, "-", "-", "-"))
                conn.execute(
                    "INSERT INTO login_identities (cliente_id, method, identifier) VALUES (%s,'google',%s)",
                    (tgt, "sub-merge-real"))
                # control: una liviana CON pedido y una liviana VERIFICADA → NO absorbibles
                liv_ped = conn.insert_returning(
                    "INSERT INTO clientes (cuenta_estado) VALUES ('liviana')")
                conn.execute(
                    "INSERT INTO alquileres (cliente_id, cliente_nombre) VALUES (%s, %s)",
                    (liv_ped, "MergeCtl"))
                liv_ver = conn.insert_returning(
                    "INSERT INTO clientes (cuenta_estado) VALUES ('liviana')")
                conn.execute(
                    "UPDATE clientes SET dni_validado_at = NOW() WHERE id = %s", (liv_ver,))
        created = [src, tgt, liv_ped, liv_ver]

        assert account_is_absorbable(src) is True       # liviana, sin verificar, sin pedidos
        assert account_is_absorbable(tgt) is False       # completa
        assert account_is_absorbable(liv_ped) is False   # liviana pero con pedido
        assert account_is_absorbable(liv_ver) is False   # liviana pero verificada

        merge_accounts(source=src, target=tgt)
        created = [tgt, liv_ped, liv_ver]  # src se borró

        with get_db() as conn:
            assert conn.execute("SELECT 1 FROM clientes WHERE id = %s", (src,)).fetchone() is None
            pk = conn.execute(
                "SELECT cliente_id FROM passkey_credentials WHERE credential_id = %s", (cred,)
            ).fetchone()
            assert pk is not None and pk["cliente_id"] == tgt  # la passkey se movió a la real
            assert conn.execute(
                "SELECT 1 FROM login_identities WHERE cliente_id = %s AND method = 'google'", (tgt,)
            ).fetchone() is not None  # la real conserva su Google
            lista = conn.execute(
                "SELECT cliente_id FROM cliente_listas WHERE id = %s", (lista_id,)
            ).fetchone()
            assert lista is not None and lista["cliente_id"] == tgt  # la lista se mudó, no se perdió
    finally:
        with get_db() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM passkey_credentials WHERE credential_id = %s", (cred,))
                conn.execute("DELETE FROM alquileres WHERE cliente_nombre = %s", ("MergeCtl",))
                for cid in created:
                    conn.execute("DELETE FROM clientes WHERE id = %s", (cid,))
