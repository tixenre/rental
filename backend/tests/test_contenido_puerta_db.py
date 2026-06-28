"""Puerta única de contenido (`services.contenido`) contra Postgres REAL.

Clava las dos garantías del módulo:

1. **Misma fuente que el gate.** El conjunto de componentes DIRECTOS que devuelve
   la puerta (`contenido_de`) == el de `reservas.semantics.componentes_de`
   (la adyacencia que usa el gate), restringido a equipos NO soft-deleted. Así, lo
   que se MUESTRA no puede divergir de la receta que se RESERVA — son la misma tabla.

2. **Granularidad de display = 1 nivel.** La puerta muestra los componentes
   directos ("este combo trae este kit"), NO la expansión recursiva hasta las hojas
   (eso es del gate, para el stock). Un combo→kit→hoja: la puerta del combo devuelve
   el kit, no la hoja.

Además: un componente soft-deleted (`eliminado_at`) NO aparece en el display
(criterio canónico unificado — antes `attach_kit` lo filtraba y `get_kit` no).

OPT-IN y SEGURO POR DEFECTO (mismo gating que `test_reservas_nested_db.py`):
se saltea salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el
nombre. Trabaja sobre ids altos (>= 9_300_000) y limpia al terminar.

    DATABASE_URL=postgresql://tincho@localhost/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_contenido_puerta_db.py -v -m integration
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

# Grafo:  Combo X → Kit Y → Hoja Z   ;   Y también trae W (soft-deleted)
Z, Y, X, W = 9_300_001, 9_300_002, 9_300_003, 9_300_004
ALL_EQ = (Z, Y, X, W)


def _limpiar(conn):
    ph = ",".join(["%s"] * len(ALL_EQ))
    conn.execute(f"DELETE FROM kit_componentes WHERE equipo_id IN ({ph})", ALL_EQ)
    conn.execute(f"DELETE FROM kit_componentes WHERE componente_id IN ({ph})", ALL_EQ)
    conn.execute(f"DELETE FROM equipos WHERE id IN ({ph})", ALL_EQ)


@pytest.fixture
def setup_grafo():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (Z, "Hoja Z", 1))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (Y, "Kit Y", 9999))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (X, "Combo X", 9999))
        # W: componente soft-deleted → no debe aparecer en el display.
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, eliminado_at) VALUES (%s,%s,%s, NOW())",
            (W, "Extra W eliminado", 5),
        )
        # Recetas (1 nivel cada arista).
        conn.execute("INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (%s,%s,%s)", (Y, Z, 2))
        conn.execute("INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (%s,%s,%s)", (Y, W, 1))
        conn.execute("INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (%s,%s,%s)", (X, Y, 1))
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


def test_display_es_directo_un_nivel(setup_grafo):
    """La puerta del combo X devuelve el kit Y (directo), NO la hoja Z (recursivo)."""
    from database import get_db
    from services.contenido import contenido_de

    conn = get_db()
    try:
        comps_x = contenido_de(conn, X)
        ids_x = {c["componente_id"] for c in comps_x}
        assert ids_x == {Y}, "el display del combo es 1 nivel: trae el kit, no la hoja"
    finally:
        conn.close()


def test_soft_deleted_no_aparece(setup_grafo):
    """W (soft-deleted) NO aparece en el display de Y; Z sí, con su cantidad."""
    from database import get_db
    from services.contenido import contenido_de

    conn = get_db()
    try:
        comps_y = contenido_de(conn, Y)
        by_id = {c["componente_id"]: c for c in comps_y}
        assert set(by_id) == {Z}, "el componente soft-deleted no se muestra"
        assert by_id[Z]["cantidad"] == 2
        assert by_id[Z]["nombre"] == "Hoja Z"
    finally:
        conn.close()


def test_puerta_misma_fuente_que_el_gate(setup_grafo):
    """El conjunto de aristas directas de la puerta == el de `componentes_de`
    (la adyacencia del gate), restringido a equipos NO soft-deleted. Garantía de
    'misma fuente': mostrado y reservado leen la misma tabla `kit_componentes`."""
    from database import get_db
    from reservas.semantics import componentes_de
    from services.contenido import contenido_de_batch

    conn = get_db()
    try:
        gate = componentes_de(conn, [X, Y])  # {eid: [(comp_id, cant, esencial), ...]}
        puerta = contenido_de_batch(conn, [X, Y])

        # El gate incluye W (no filtra soft-delete); el display lo excluye. La
        # garantía es sobre los componentes NO eliminados.
        for eid in (X, Y):
            gate_set = {(cid, cant) for (cid, cant, _ess) in gate.get(eid, []) if cid != W}
            puerta_set = {(c["componente_id"], c["cantidad"]) for c in puerta.get(eid, [])}
            assert puerta_set == gate_set, f"puerta y gate divergen en equipo {eid}"
    finally:
        conn.close()


def test_hoja_sin_componentes(setup_grafo):
    """Una hoja (simple) no tiene componentes → lista vacía."""
    from database import get_db
    from services.contenido import contenido_de

    conn = get_db()
    try:
        assert contenido_de(conn, Z) == []
    finally:
        conn.close()
