"""Candado de concurrencia para `verificar_y_crear_perfil_fiscal` (#1240,
hallazgo de segunda revisión). El `es_default` del PRIMER perfil de un cliente
se decidía con "¿el cliente ya tiene ALGÚN perfil?" — dos requests concurrentes
dando de alta el primer perfil con CUITs DISTINTOS para el MISMO cliente veían
ambas "todavía no tiene ninguno" y calculaban `es_default=True` los dos; el
segundo INSERT violaba `uq_cliente_perfiles_fiscales_default` (partial unique
index) sin capturar en ningún caller → 500 crudo. Fix: `pg_advisory_xact_lock`
por `cliente_id` (namespace propio `_ADVISORY_NS_PERFIL_FISCAL`) serializa el
alta del primer perfil.

Verificado contra Postgres real con dos hilos + threading.Event (mismo patrón
que `test_reportes_cierres_db.py::test_lock_serializa_cerrar_mes_concurrente`):
uno toma el lock y lo retiene, el otro debe quedar bloqueado hasta que el
primero libere — nunca los dos calculan `es_default=True` a la vez.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre.
"""
import os
import threading
import time
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
        not _OPT_IN, reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba"
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

CLIENTE_ID = 9_350_001
CUIT_A = "30500002227"
CUIT_B = "30500002235"


@pytest.fixture
def cliente_sin_perfiles():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM cliente_perfiles_fiscales WHERE cliente_id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido, email) VALUES (%s, %s, %s, %s)",
            (CLIENTE_ID, "Perfiles", "Concurrencia", "perfiles-concurrencia-db@test.com"),
        )
        conn.commit()
        yield
    finally:
        conn.execute("DELETE FROM cliente_perfiles_fiscales WHERE cliente_id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.commit()
        conn.close()


def _persona(cuit: str):
    from arca_fe.padron import PersonaArca

    return PersonaArca(
        cuit=cuit,
        razon_social=f"Persona {cuit}",
        nombre="",
        apellido="",
        domicilio="Calle Falsa 123",
        condicion_iva="responsable_inscripto",
        estado_clave="ACTIVO",
    )


def test_lock_serializa_alta_del_primer_perfil_concurrente(cliente_sin_perfiles, monkeypatch):
    from database import get_db
    from services.facturacion import padron

    monkeypatch.setattr(padron, "resolver_persona", lambda cuit, conn: _persona(cuit))

    orden: list[str] = []
    lock_tomado = threading.Event()
    liberar_lock = threading.Event()
    errores: dict[str, Exception] = {}

    def _tomar_lock_y_esperar():
        conn = get_db()
        try:
            conn.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (padron._ADVISORY_NS_PERFIL_FISCAL, CLIENTE_ID),
            )
            orden.append("A_tomo_lock")
            lock_tomado.set()
            liberar_lock.wait(timeout=5)
            conn.commit()  # libera el advisory lock xact-scoped
            orden.append("A_libero_lock")
        except Exception as e:  # noqa: BLE001 — se re-lanza al hilo principal
            errores["A"] = e
        finally:
            conn.close()

    def _verificar_bloqueado():
        lock_tomado.wait(timeout=5)
        conn = get_db()
        try:
            padron.verificar_y_crear_perfil_fiscal(CUIT_B, CLIENTE_ID, conn)
            conn.commit()
            orden.append("B_creo_perfil")
        except Exception as e:  # noqa: BLE001
            errores["B"] = e
        finally:
            conn.close()

    ta = threading.Thread(target=_tomar_lock_y_esperar)
    tb = threading.Thread(target=_verificar_bloqueado)
    ta.start()
    lock_tomado.wait(timeout=5)
    tb.start()
    time.sleep(0.3)  # B debería seguir esperando el lock en este punto.
    assert "B_creo_perfil" not in orden, "B no debería poder crear el perfil mientras A retiene el lock"
    liberar_lock.set()
    ta.join(timeout=5)
    tb.join(timeout=5)

    assert not ta.is_alive() and not tb.is_alive(), "deadlock: algún hilo no terminó"
    assert not errores, f"errores en los hilos: {errores}"
    assert orden == ["A_tomo_lock", "A_libero_lock", "B_creo_perfil"], orden


def test_dos_altas_concurrentes_del_primer_perfil_solo_una_gana_el_default(
    cliente_sin_perfiles, monkeypatch
):
    """Reproduce el bug real: dos hilos dan de alta el PRIMER perfil del mismo
    cliente con CUITs DISTINTOS al mismo tiempo. Sin el lock, ambos calculan
    `es_default=True` y el segundo INSERT viola el índice único parcial sin
    capturar → 500 crudo. Con el lock, se serializan: exactamente UN perfil
    queda `es_default=True`, el otro no truena."""
    from database import get_db
    from services.facturacion import padron

    monkeypatch.setattr(padron, "resolver_persona", lambda cuit, conn: _persona(cuit))

    errores: dict[str, Exception] = {}

    def _crear(cuit):
        conn = get_db()
        try:
            padron.verificar_y_crear_perfil_fiscal(cuit, CLIENTE_ID, conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001
            errores[cuit] = e
        finally:
            conn.close()

    ta = threading.Thread(target=_crear, args=(CUIT_A,))
    tb = threading.Thread(target=_crear, args=(CUIT_B,))
    ta.start()
    tb.start()
    ta.join(timeout=10)
    tb.join(timeout=10)

    assert not ta.is_alive() and not tb.is_alive(), "deadlock: algún hilo no terminó"
    assert not errores, f"errores en los hilos (no debería violar el índice único): {errores}"

    conn = get_db()
    try:
        filas = conn.execute(
            "SELECT cuit, es_default FROM cliente_perfiles_fiscales WHERE cliente_id = %s ORDER BY cuit",
            (CLIENTE_ID,),
        ).fetchall()
    finally:
        conn.close()

    assert len(filas) == 2
    defaults = [f["es_default"] for f in filas]
    assert defaults.count(True) == 1, f"exactamente uno debe ser default, no {defaults}"
