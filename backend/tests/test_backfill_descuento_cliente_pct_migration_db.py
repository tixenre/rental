"""Regresión del hallazgo del supervisor en PR #1220 (Fase C, #1219): sin
backfill, un pedido preexistente con `descuento_pct` histórico ≠0 quedaría
mostrando el % MANUAL en vez del % que realmente ganó en su momento
(cliente/jornadas vía `max()`, el sistema pre-C-1) — divergiendo de
`monto_total` ya persistido/congelado.

Simula el camino real de prod: `init_db()` (esquema al día) + un pedido
"legacy" insertado con el shape PRE-C-1 (`descuento_pct` no-cero,
`descuento_cliente_pct` en 0 = default, sin backfillear) + `alembic upgrade
head` (aplica la migración de backfill `v9w0x1y2z3a4`). Verifica que el
backfill preserva EXACTAMENTE el % que hubiera ganado bajo el `max()` viejo.

OPT-IN y SEGURO POR DEFECTO (mismo gating que test_alembic_upgrade_db.py):
se saltea salvo ALEMBIC_DB_TEST=1 + DATABASE_URL a una base de prueba.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

_OPT_IN = os.getenv("ALEMBIC_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _OPT_IN,
        reason="opt-in: setear ALEMBIC_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return cfg


def _reset_schema():
    from database import get_db

    conn = get_db()
    try:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def clean_db():
    _reset_schema()
    yield
    _reset_schema()


PEDIDO_JORNADAS_GANO = 9_360_001  # descuento_pct(5) < descuento_jornadas_pct(10)
PEDIDO_CLIENTE_GANO = 9_360_002   # descuento_pct(15) > descuento_jornadas_pct(10)
PEDIDO_SIN_DESCUENTO = 9_360_003  # descuento_pct(0) — nada que backfillear


def test_backfill_preserva_el_pct_ganador_historico(clean_db):
    from alembic import command
    from database import init_db, get_db
    import migration_state

    init_db()

    conn = get_db()
    try:
        # Pedidos "legacy": insertados como si vinieran de ANTES de C-1 — sin
        # `descuento_cliente_pct` (default 0, nunca backfillear a mano).
        conn.execute(
            "INSERT INTO alquileres (id, cliente_nombre, estado, monto_total, descuento_pct, descuento_jornadas_pct) "
            "VALUES (%s,'legacy','confirmado',100,5,10)",
            (PEDIDO_JORNADAS_GANO,),
        )
        conn.execute(
            "INSERT INTO alquileres (id, cliente_nombre, estado, monto_total, descuento_pct, descuento_jornadas_pct) "
            "VALUES (%s,'legacy','confirmado',100,15,10)",
            (PEDIDO_CLIENTE_GANO,),
        )
        conn.execute(
            "INSERT INTO alquileres (id, cliente_nombre, estado, monto_total, descuento_pct, descuento_jornadas_pct) "
            "VALUES (%s,'legacy','confirmado',100,0,0)",
            (PEDIDO_SIN_DESCUENTO,),
        )
        conn.commit()
    finally:
        conn.close()

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    head = migration_state._head_revision(cfg)
    current = migration_state._current_revision()
    assert current == head, f"La cadena quedó en {current!r}, head es {head!r}"

    conn = get_db()
    try:
        rows = {
            r["id"]: r
            for r in conn.execute(
                "SELECT id, descuento_pct, descuento_cliente_pct, descuento_jornadas_pct "
                "FROM alquileres WHERE id IN (%s,%s,%s)",
                (PEDIDO_JORNADAS_GANO, PEDIDO_CLIENTE_GANO, PEDIDO_SIN_DESCUENTO),
            ).fetchall()
        }
    finally:
        conn.execute("DELETE FROM alquileres WHERE id IN (%s,%s,%s)" % (
            PEDIDO_JORNADAS_GANO, PEDIDO_CLIENTE_GANO, PEDIDO_SIN_DESCUENTO
        ))
        conn.commit()
        conn.close()

    # Caso 1: jornadas (10) había ganado sobre el 5 histórico → el backfill
    # mueve el 5 a `descuento_cliente_pct`, resetea el manual a 0 → bajo la
    # jerarquía nueva cae al fallback max(5, 10) = 10, IGUAL que antes.
    r1 = rows[PEDIDO_JORNADAS_GANO]
    assert float(r1["descuento_pct"] or 0) == 0
    assert float(r1["descuento_cliente_pct"] or 0) == 5
    from descuentos.queries.decision import resolver_descuento_pedido
    assert resolver_descuento_pedido(
        r1["descuento_pct"], r1["descuento_cliente_pct"], r1["descuento_jornadas_pct"]
    ) == 10.0  # el % que YA estaba reflejado en monto_total

    # Caso 2: el 15 histórico había ganado sobre jornadas (10) → mismo
    # backfill, mismo resultado numérico bajo el fallback: max(15, 10) = 15.
    r2 = rows[PEDIDO_CLIENTE_GANO]
    assert float(r2["descuento_pct"] or 0) == 0
    assert float(r2["descuento_cliente_pct"] or 0) == 15
    assert resolver_descuento_pedido(
        r2["descuento_pct"], r2["descuento_cliente_pct"], r2["descuento_jornadas_pct"]
    ) == 15.0

    # Caso 3: sin descuento histórico — nada que tocar, el backfill es no-op.
    r3 = rows[PEDIDO_SIN_DESCUENTO]
    assert float(r3["descuento_pct"] or 0) == 0
    assert float(r3["descuento_cliente_pct"] or 0) == 0
