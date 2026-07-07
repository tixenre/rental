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
    from auth.queries import identities as queries
    from auth.commands import identities as commands

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
        assert commands.link_identity(cliente_id=cid_a, method="email", identifier=email_a) == "linked"
        assert commands.link_identity(cliente_id=cid_a, method="email", identifier=email_a) == "already_yours"
        assert commands.link_identity(cliente_id=cid_b, method="email", identifier=email_a) == "taken_by_other"

        # lookup directo
        assert queries.find_cliente_by_identity("email", email_a) == cid_a
        assert queries.find_cliente_by_identity("email", "noexiste@test.local") is None

        # resolve de Google: 1ª vez no hay sub → matchea por mail y backfillea el sub
        assert queries.find_cliente_by_identity("google", sub_a) is None
        assert commands.find_or_backfill_google(sub_a, email_a) == cid_a
        # ahora el sub quedó vinculado → matchea por sub aunque cambie el mail
        assert queries.find_cliente_by_identity("google", sub_a) == cid_a
        assert commands.find_or_backfill_google(sub_a, "mail-cambiado@test.local") == cid_a

        # el backfill guardó el mail del Google + el helper "una cuenta = un Google" lo trae
        g = queries.google_identity_for_cliente(cid_a)
        assert g is not None and g["identifier"] == sub_a and g["email"] == email_a
        assert queries.google_identity_for_cliente(cid_b) is None  # cid_b no tiene Google

        # cuenta inexistente → None (el callback manda a registro)
        assert commands.find_or_backfill_google("google-sub-ZZZ", "nadie@test.local") is None

        # list + count: cid_a tiene email + google
        ids = queries.list_for_cliente(cid_a)
        assert {r["method"] for r in ids} == {"email", "google"}
        assert queries.count_for_cliente(cid_a) == 2

        # unlink scopeado al dueño (anti-IDOR): cid_b NO puede borrar una llave de cid_a
        email_identity = next(r for r in ids if r["method"] == "email")
        assert commands.unlink_for_cliente(email_identity["id"], cid_b) is False
        assert queries.count_for_cliente(cid_a) == 2  # sigue intacta
        assert commands.unlink_for_cliente(email_identity["id"], cid_a) is True
        assert queries.count_for_cliente(cid_a) == 1
    finally:
        with get_db() as conn:
            with conn.transaction():
                for cid in created:
                    conn.execute("DELETE FROM clientes WHERE id = %s", (cid,))


def test_link_identity_carrera_unique_no_revienta():
    """Dos requests concurrentes vinculando la MISMA (method, identifier) —doble-click,
    reintento de red— compiten en el INSERT bajo el UNIQUE. Confirma contra Postgres
    real (no un mock) que `link_identity` atrapa el `UniqueViolation` de esa carrera y
    resuelve el status correcto, en vez de propagar la excepción cruda."""
    import threading

    from database import init_db, get_db
    from auth.commands import identities as commands

    init_db()
    identifier = "race-google-sub-real"
    email_a, email_b = "race_a@test.local", "race_b@test.local"
    created: list[int] = []
    ganador_listo = threading.Event()
    liberar_ganador = threading.Event()
    resultado: dict = {}

    def _ganador(cid_a):
        """Simula la request que gana la carrera: inserta y NO commitea hasta que
        se le avisa — deja a la otra conexión bloqueada en su propio INSERT
        (comportamiento real de Postgres ante un conflicto de índice único
        todavía no resuelto), no en el SELECT."""
        conn = get_db()
        try:
            with conn.transaction():
                conn.execute(
                    """INSERT INTO login_identities (cliente_id, method, identifier, verified_at)
                       VALUES (%s, 'google', %s, NOW())""",
                    (cid_a, identifier),
                )
                ganador_listo.set()
                liberar_ganador.wait(timeout=5)
        finally:
            conn.close()

    def _perdedor(cid_b):
        resultado["status"] = commands.link_identity(
            cliente_id=cid_b, method="google", identifier=identifier
        )

    try:
        with get_db() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM login_identities WHERE identifier = %s", (identifier,))
                conn.execute("DELETE FROM clientes WHERE email IN (%s, %s)", (email_a, email_b))
                cid_a = _crear_cliente(conn, email_a)
                cid_b = _crear_cliente(conn, email_b)
        created = [cid_a, cid_b]

        t_ganador = threading.Thread(target=_ganador, args=(cid_a,))
        t_ganador.start()
        assert ganador_listo.wait(timeout=5), "el hilo ganador no llegó a insertar"

        t_perdedor = threading.Thread(target=_perdedor, args=(cid_b,))
        t_perdedor.start()
        # `_perdedor` queda bloqueado en su propio INSERT (el índice único todavía
        # no puede resolver el conflicto mientras el ganador no commitea/rollbackea).
        t_perdedor.join(timeout=0.3)
        assert t_perdedor.is_alive(), "el perdedor debería seguir bloqueado en el INSERT"

        liberar_ganador.set()
        t_ganador.join(timeout=5)
        t_perdedor.join(timeout=5)
        assert not t_ganador.is_alive() and not t_perdedor.is_alive(), "deadlock: algún hilo no terminó"

        # Nunca propagó la excepción — resolvió el status correcto re-consultando al ganador.
        assert resultado.get("status") == "taken_by_other"
        with get_db() as conn:
            fila = conn.execute(
                "SELECT cliente_id FROM login_identities WHERE identifier = %s", (identifier,)
            ).fetchone()
        assert fila["cliente_id"] == cid_a  # el ganador real quedó persistido, sin duplicar
    finally:
        with get_db() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM login_identities WHERE identifier = %s", (identifier,))
                for cid in created:
                    conn.execute("DELETE FROM clientes WHERE id = %s", (cid,))
