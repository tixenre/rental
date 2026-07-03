"""#1209 — round-trip de dataio para `alquiler_pagos.anulado` (backup/restore).

Bug real (auditoría #1184/#1209): `export_alquileres` no incluía
`anulado`/`anulado_por`/`anulado_at`/`anulado_motivo` de `alquiler_pagos` — un
pago ANULADO (soft-delete, ver auditoría de `backend/contabilidad/`) volvía a
la vida como ACTIVO tras un ciclo `dataio export` → `dataio import` (backup o
clonado de ambiente), porque el import lo reinsertaba con el default de la
columna (`anulado=FALSE`). Eso hacía subir `monto_pagado`/cajas/liquidación
sin que nadie lo pidiera — la anulación desaparecía sin dejar rastro.

Este test (mismo patrón que `test_dataio_roundtrip_db.py`) verifica contra
Postgres real:
  1. `export_alquileres` incluye `anulado` + columnas de auditoría del pago.
  2. Round-trip completo: export → se borra el pago (simula un ambiente
     fresco, ej. clon a otro ambiente) → import → el pago vuelve ANULADO,
     no activo.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el
nombre. Trabaja sobre ids de prueba (>= 9_700_000) y limpia al terminar.
"""
import os
from urllib.parse import urlparse

import pytest

_OPT_IN = os.getenv("RESERVAS_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _OPT_IN,
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

ALQ_ID = 9_700_001
NUMERO_PEDIDO = 9_700_001
ANULADO_POR = "admin@test.com"
ANULADO_MOTIVO = "cargado por error (test #1209)"


def _limpiar(conn):
    # CASCADE en alquiler_pagos/alquiler_items limpia lo embebido.
    conn.execute("DELETE FROM alquileres WHERE id = %s", (ALQ_ID,))


@pytest.fixture
def alquiler_con_pago_anulado():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            """
            INSERT INTO alquileres
                (id, numero_pedido, cliente_nombre, estado,
                 fecha_desde, fecha_hasta, monto_total, monto_pagado)
            VALUES (%s, %s, %s, 'confirmado',
                    '2026-07-01', '2026-07-05', 100000, 0)
            """,
            (ALQ_ID, NUMERO_PEDIDO, "Cliente Roundtrip Anulado Test"),
        )
        conn.execute(
            """
            INSERT INTO alquiler_pagos
                (pedido_id, monto, concepto, fecha,
                 anulado, anulado_por, anulado_at, anulado_motivo)
            VALUES (%s, 100000, 'Seña', '2026-07-01 10:00:00',
                    TRUE, %s, '2026-07-01 11:00:00', %s)
            """,
            (ALQ_ID, ANULADO_POR, ANULADO_MOTIVO),
        )
        conn.commit()
    finally:
        conn.close()

    yield

    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


def test_export_alquileres_incluye_anulado_del_pago(alquiler_con_pago_anulado):
    """El export debe incluir anulado + auditoría — antes se perdían."""
    from database import get_db
    from dataio.exporters import export_alquileres

    conn = get_db()
    try:
        rows = export_alquileres(conn)
        alq = next(r for r in rows if r["numero_pedido"] == NUMERO_PEDIDO)
        assert len(alq["pagos"]) == 1
        pago = alq["pagos"][0]
        assert pago["anulado"] is True, "el export debe conservar anulado=True"
        assert pago["anulado_por"] == ANULADO_POR
        assert pago["anulado_motivo"] == ANULADO_MOTIVO
        assert pago["anulado_at"] is not None
    finally:
        conn.close()


def test_import_no_revive_pago_anulado(alquiler_con_pago_anulado):
    """Round-trip completo: export → (simula ambiente fresco) → import → el
    pago vuelve ANULADO, no activo (regresión #1209)."""
    from database import get_db
    from dataio.exporters import export_alquileres
    from dataio.importers import import_alquileres
    from dataio.natural_keys import KeyResolver

    conn = get_db()
    try:
        rows = export_alquileres(conn)

        # Simula el escenario de falla real: el pago no existe todavía en el
        # destino (backup restaurado en un ambiente fresco / clonado).
        conn.execute("DELETE FROM alquiler_pagos WHERE pedido_id = %s", (ALQ_ID,))
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM alquiler_pagos WHERE pedido_id = %s",
            (ALQ_ID,),
        ).fetchone()["n"] == 0

        resolver = KeyResolver(conn)
        import_alquileres(conn, rows, resolver)
        conn.commit()
    finally:
        conn.close()

    conn = get_db()
    try:
        pago = conn.execute(
            """
            SELECT monto, anulado, anulado_por, anulado_motivo
            FROM alquiler_pagos WHERE pedido_id = %s
            """,
            (ALQ_ID,),
        ).fetchone()
        assert pago is not None, "el import debe restaurar el pago"
        assert bool(pago["anulado"]) is True, (
            "BUG #1209: el pago anulado revivió ACTIVO tras el roundtrip "
            "export→import (el import lo reinsertó con el default de la "
            "columna anulado=FALSE)"
        )
        assert pago["anulado_por"] == ANULADO_POR
        assert pago["anulado_motivo"] == ANULADO_MOTIVO
    finally:
        conn.close()
