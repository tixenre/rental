"""Candado con Postgres REAL del escenario del bug de stock con kits (2026-07-05).

Escenario del dueño: Maffer (hoja, stock 5); Brazo Mágico (kit, receta 2× Maffer);
pedido confirmado con 3× Maffer + 1× Brazo. El editor mostraba "2 libres" para el
Maffer cuando quedan 0 (5 − 3 − 2). Verifica:

  1. `calcular_disponibilidad_draft` con el draft del pedido → Maffer 0 (el fix).
  2. Con Maffer subido a 4 → −1 (faltante con signo) Y el gate hipotético rechaza
     — PARIDAD: el badge y el gate no pueden divergir (misma expansión).
  3. El pedido tal cual (5 de 5) pasa el gate — el escenario NO está sobrevendido.

OPT-IN y SEGURO POR DEFECTO (mismo gating que `test_reservas_nested_db.py`):

    DATABASE_URL=postgresql://tincho@localhost/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_disponibilidad_draft_db.py -v -m integration
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

MAFFER, BRAZO = 9_300_001, 9_300_002
PEDIDO = 9_300_101
FD, FH = "2026-08-10T09:00:00", "2026-08-12T18:00:00"


class _Item:
    def __init__(self, equipo_id, cantidad):
        self.equipo_id, self.cantidad = equipo_id, cantidad


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id = %s", (PEDIDO,))
    conn.execute("DELETE FROM alquileres WHERE id = %s", (PEDIDO,))
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id IN (%s,%s)", (MAFFER, BRAZO))
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s)", (MAFFER, BRAZO))


@pytest.fixture
def escenario_kit():
    """Maffer stock 5; Brazo = kit con 2× Maffer (stock propio 1); pedido
    confirmado con 3× Maffer + 1× Brazo (consume 5 de 5 Maffer)."""
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)",
            (MAFFER, "Maffer (test draft)", 5),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, tipo) VALUES (%s,%s,%s,'kit')",
            (BRAZO, "Brazo Mágico (test draft)", 1),
        )
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (%s,%s,2)",
            (BRAZO, MAFFER),
        )
        conn.execute(
            "INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta) "
            "VALUES (%s,%s,'confirmado',%s,%s)",
            (PEDIDO, "Cliente test (draft kit)", FD, FH),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) VALUES "
            "(%s,%s,3), (%s,%s,1)",
            (PEDIDO, MAFFER, PEDIDO, BRAZO),
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


def test_draft_con_kit_no_miente_y_es_par_con_el_gate(escenario_kit):
    from database import get_db
    from reservas import (
        calcular_disponibilidad,
        calcular_disponibilidad_draft,
        validar_stock,
        validar_stock_hipotetico,
    )

    conn = get_db()
    try:
        # El cálculo clásico excluyendo el pedido (lo que el editor usaba):
        # Maffer 5 → la resta naive del front daba 5 − 3 = "2 libres". Mentira.
        clasico = calcular_disponibilidad(conn, FD, FH, exclude_pedido_id=PEDIDO)
        assert clasico[str(MAFFER)] == 5

        # EL FIX: el draft completo (3 Maffer + 1 Brazo) expandido → 0 libres.
        draft = {MAFFER: 3, BRAZO: 1}
        out = calcular_disponibilidad_draft(conn, FD, FH, draft, exclude_pedido_id=PEDIDO)
        assert out[str(MAFFER)] == 0
        assert out[str(BRAZO)] == 0

        # El pedido tal cual NO está sobrevendido (5 de 5) — el gate lo acepta.
        assert validar_stock(conn, PEDIDO, FD, FH) == []
        conn.rollback()  # suelta los FOR UPDATE del gate

        # PARIDAD badge↔gate: Maffer→4 (6 de 5) da −1 en el mapa Y el gate
        # hipotético lo rechaza. El badge predice exactamente al gate.
        over = {MAFFER: 4, BRAZO: 1}
        out_over = calcular_disponibilidad_draft(conn, FD, FH, over, exclude_pedido_id=PEDIDO)
        assert out_over[str(MAFFER)] == -1
        assert out_over[str(BRAZO)] == -1  # hereda el faltante de su hoja
        problemas = validar_stock_hipotetico(
            conn, PEDIDO, FD, FH, [_Item(MAFFER, 4), _Item(BRAZO, 1)]
        )
        assert len(problemas) == 1 and "Maffer (test draft)" in problemas[0]
        conn.rollback()
    finally:
        conn.close()
