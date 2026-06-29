"""identity/merge + índice único de CUIL contra Postgres REAL (opt-in).

Clava dos garantías de Fase 2 que el FakeConn no puede (necesitan FKs + el índice vivos):

1. `merge_accounts` MUEVE los datos del source al target (pedido, contacto verificado,
   bitácora) y BORRA el source — en una transacción.
2. El índice parcial `uniq_cliente_cuil_verificado` RECHAZA una 2ª cuenta verificada con
   el mismo CUIL, pero NO toca a no-verificados ni a CUIL NULL (extranjeros).

Gating idéntico a `test_contenido_puerta_db` (opt-in + base de prueba). La base tiene que
estar migrada (init_db / alembic upgrade head — ahí vive el índice). Ids altos (>= 9_310_000),
limpia al terminar.

    DATABASE_URL=postgresql://tincho@localhost/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_identity_merge_db.py -v -m integration
"""
import os
from urllib.parse import urlparse

import psycopg
import pytest

from database import get_db, now_ar
from identity import merge

_OPT_IN = os.getenv("RESERVAS_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _OPT_IN, reason="opt-in: RESERVAS_DB_TEST=1 + DATABASE_URL de prueba"),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

A, B = 9_310_001, 9_310_002  # source, target
IDS = (A, B)
_CUIL = "TESTCUIL9310"  # sintético: no choca con CUILs reales de la base


def _limpiar(conn):
    ph = ",".join(["%s"] * len(IDS))
    for tabla in ("alquileres", "verified_contacts", "kyc_events"):
        conn.execute(f"DELETE FROM {tabla} WHERE cliente_id IN ({ph})", IDS)  # noqa: S608
    conn.execute(f"DELETE FROM clientes WHERE id IN ({ph})", IDS)  # noqa: S608
    conn.commit()


def _ins_cliente(conn, cid, *, cuil=None, verificado=False):
    conn.execute(
        "INSERT INTO clientes (id, cuenta_estado, cuil, dni_validado_at) VALUES (%s, %s, %s, %s)",
        (cid, "liviana", cuil, now_ar() if verificado else None),
    )


@pytest.fixture
def conn():
    c = get_db()
    _limpiar(c)
    try:
        yield c
    finally:
        _limpiar(c)
        c.close()


def test_merge_mueve_datos_y_borra_source(conn):
    _ins_cliente(conn, A)  # source con datos
    _ins_cliente(conn, B)  # target
    conn.execute(
        "INSERT INTO alquileres (cliente_id, cliente_nombre) VALUES (%s, %s)", (A, "Pedido de A")
    )
    conn.execute(
        "INSERT INTO verified_contacts (cliente_id, kind, value, source) VALUES (%s,%s,%s,%s)",
        (A, "email", "a@test.com", "didit"),
    )
    conn.execute(
        "INSERT INTO kyc_events (cliente_id, evento) VALUES (%s, %s)", (A, "approved")
    )
    conn.commit()

    merge.merge_accounts(source=A, target=B, conn=conn)

    # El pedido y el contacto ahora cuelgan del target; el source ya no existe.
    assert conn.execute("SELECT cliente_id FROM alquileres WHERE cliente_nombre='Pedido de A'").fetchone()["cliente_id"] == B
    assert conn.execute("SELECT cliente_id FROM verified_contacts WHERE value='a@test.com'").fetchone()["cliente_id"] == B
    assert conn.execute("SELECT 1 FROM clientes WHERE id=%s", (A,)).fetchone() is None
    assert conn.execute("SELECT 1 FROM clientes WHERE id=%s", (B,)).fetchone() is not None
    # Quedó la bitácora del merge en el sobreviviente.
    assert conn.execute(
        "SELECT 1 FROM kyc_events WHERE cliente_id=%s AND evento='merge'", (B,)
    ).fetchone() is not None


def test_indice_cuil_rechaza_segundo_verificado(conn):
    _ins_cliente(conn, A, cuil=_CUIL, verificado=True)
    conn.commit()
    # Una 2ª cuenta VERIFICADA con el mismo CUIL → el índice parcial la rechaza.
    with pytest.raises(psycopg.errors.UniqueViolation):
        _ins_cliente(conn, B, cuil=_CUIL, verificado=True)
        conn.commit()
    conn.rollback()


def test_indice_cuil_no_toca_no_verificados(conn):
    # Mismo CUIL pero SIN verificar (dni_validado_at NULL) → fuera del índice parcial → OK.
    _ins_cliente(conn, A, cuil=_CUIL, verificado=False)
    _ins_cliente(conn, B, cuil=_CUIL, verificado=False)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS n FROM clientes WHERE cuil=%s", (_CUIL,)).fetchone()["n"]
    assert n == 2  # dos no-verificados con el mismo CUIL conviven (el índice no aplica)
