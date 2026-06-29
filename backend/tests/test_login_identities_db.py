"""login_identities + el store de identidades de login (Fase 1 identidad), Postgres real.

Ejerce: lookup por (method, identifier); link idempotente con sus 3 estados
(linked / already_yours / taken_by_other); el resolve de Google (por `sub`, con
fallback por mail + backfill del sub); list/count; y el unlink scopeado al dueño
(anti-IDOR). Opt-in (RESERVAS_DB_TEST=1 + DATABASE_URL de test) — toca UNIQUE y FK que
el FakeConn de los unit no captura.
"""
import os
from urllib.parse import urlparse

import pytest

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


def _crear_cliente(conn, email: str) -> int:
    return conn.insert_returning(
        """INSERT INTO clientes (nombre, apellido, email, telefono, direccion, cuit)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        ("Test", "Identidad", email, "11-0000-0000", "-", "-"),
    )


def test_login_identities_store_y_resolve_google():
    from database import init_db, get_db
    from auth import identities_store as store

    init_db()

    email_a = "ident_a@test.local"
    email_b = "ident_b@test.local"
    sub_a = "google-sub-AAA-test"
    created: list[int] = []
    try:
        with get_db() as conn:
            with conn.transaction():
                # Limpieza defensiva por si una corrida anterior abortó sin el finally.
                conn.execute(
                    "DELETE FROM clientes WHERE email IN (%s, %s)", (email_a, email_b)
                )
                cid_a = _crear_cliente(conn, email_a)
                cid_b = _crear_cliente(conn, email_b)
        created = [cid_a, cid_b]

        # link idempotente + los 3 estados
        assert store.link_identity(cliente_id=cid_a, method="email", identifier=email_a) == "linked"
        assert store.link_identity(cliente_id=cid_a, method="email", identifier=email_a) == "already_yours"
        assert store.link_identity(cliente_id=cid_b, method="email", identifier=email_a) == "taken_by_other"

        # lookup directo
        assert store.find_cliente_by_identity("email", email_a) == cid_a
        assert store.find_cliente_by_identity("email", "noexiste@test.local") is None

        # resolve de Google: 1ª vez no hay sub → matchea por mail y backfillea el sub
        assert store.find_cliente_by_identity("google", sub_a) is None
        assert store.find_or_backfill_google(sub_a, email_a) == cid_a
        # ahora el sub quedó vinculado → matchea por sub aunque cambie el mail
        assert store.find_cliente_by_identity("google", sub_a) == cid_a
        assert store.find_or_backfill_google(sub_a, "mail-cambiado@test.local") == cid_a

        # el backfill guardó el mail del Google + el helper "una cuenta = un Google" lo trae
        g = store.google_identity_for_cliente(cid_a)
        assert g is not None and g["identifier"] == sub_a and g["email"] == email_a
        assert store.google_identity_for_cliente(cid_b) is None  # cid_b no tiene Google

        # cuenta inexistente → None (el callback manda a registro)
        assert store.find_or_backfill_google("google-sub-ZZZ", "nadie@test.local") is None

        # list + count: cid_a tiene email + google
        ids = store.list_for_cliente(cid_a)
        assert {r["method"] for r in ids} == {"email", "google"}
        assert store.count_for_cliente(cid_a) == 2

        # unlink scopeado al dueño (anti-IDOR): cid_b NO puede borrar una llave de cid_a
        email_identity = next(r for r in ids if r["method"] == "email")
        assert store.unlink_for_cliente(email_identity["id"], cid_b) is False
        assert store.count_for_cliente(cid_a) == 2  # sigue intacta
        assert store.unlink_for_cliente(email_identity["id"], cid_a) is True
        assert store.count_for_cliente(cid_a) == 1
    finally:
        with get_db() as conn:
            with conn.transaction():
                for cid in created:
                    conn.execute("DELETE FROM clientes WHERE id = %s", (cid,))
