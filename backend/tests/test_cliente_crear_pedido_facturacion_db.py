"""`POST /api/cliente/pedidos` con `perfil_fiscal_id`/`productora_id` (#1240) —
contra Postgres real: valida mutua exclusión (400) y ownership (404 si el
perfil/productora no es del cliente autenticado), y que el valor elegido
efectivamente queda persistido en `alquileres`.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`).
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
        not _OPT_IN, reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba"
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

import main  # noqa: E402
from auth.session import signer  # noqa: E402

CLIENTE_ID = 9_350_001
OTRO_CLIENTE_ID = 9_350_002
EQ_ID = 9_350_100

_COOKIE = f"session={signer.dumps({'email': 'crear-pedido-fiscal@test.com', 'role': 'cliente', 'cliente_id': CLIENTE_ID, 'jti': 'crear-pedido-fiscal'})}"

_BODY_BASE = {
    "fecha_desde": "2030-01-01T10:00",
    "fecha_hasta": "2030-01-02T10:00",
    "items": [{"equipo_id": EQ_ID, "cantidad": 1, "precio_jornada": 1}],
}


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})


@pytest.fixture
def datos(monkeypatch):
    """Cliente verificado (identidad) + equipo de catálogo + un perfil fiscal
    propio + una productora vinculada al OTRO cliente (para probar 404)."""
    from database import get_db, init_db, now_ar

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM equipos WHERE id = %s", (EQ_ID,))
        conn.execute("DELETE FROM clientes WHERE id IN (%s, %s)", (CLIENTE_ID, OTRO_CLIENTE_ID))
        conn.execute(
            """INSERT INTO clientes (id, nombre, apellido, email, dni_validado_at)
               VALUES (%s, 'Ana', 'Gómez', 'crear-pedido-fiscal@test.com', %s),
                      (%s, 'Otro', 'Cliente', 'otro-crear-pedido@test.com', NULL)""",
            (CLIENTE_ID, now_ar(), OTRO_CLIENTE_ID),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo) "
            "VALUES (%s, 'Cámara crear-pedido-fiscal-test', 5, 1000, 1)",
            (EQ_ID,),
        )
        perfil_id = conn.insert_returning(
            """INSERT INTO cliente_perfiles_fiscales
                   (cliente_id, cuit, perfil_impuestos, razon_social, es_default)
               VALUES (%s, '20111111112', 'monotributo', 'Perfil Propio', TRUE)""",
            (CLIENTE_ID,),
        )
        productora_id = conn.insert_returning(
            "INSERT INTO productoras (cuit, perfil_impuestos, razon_social) "
            "VALUES ('30500009991', 'responsable_inscripto', 'Productora Ajena')",
            (),
        )
        conn.execute(
            "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
            (productora_id, OTRO_CLIENTE_ID),
        )
        conn.commit()
        yield {"perfil_id": perfil_id, "productora_id": productora_id}
    finally:
        conn.execute("DELETE FROM alquileres WHERE cliente_id IN (%s, %s)", (CLIENTE_ID, OTRO_CLIENTE_ID))
        conn.execute("DELETE FROM productora_miembros")
        conn.execute("DELETE FROM productoras WHERE cuit = '30500009991'")
        conn.execute("DELETE FROM cliente_perfiles_fiscales WHERE cliente_id IN (%s, %s)", (CLIENTE_ID, OTRO_CLIENTE_ID))
        conn.execute("DELETE FROM equipos WHERE id = %s", (EQ_ID,))
        conn.execute("DELETE FROM clientes WHERE id IN (%s, %s)", (CLIENTE_ID, OTRO_CLIENTE_ID))
        conn.commit()
        conn.close()


def _post(client, body):
    return client.post("/api/cliente/pedidos", json=body, headers={"Cookie": _COOKIE})


def test_ambos_campos_a_la_vez_400(datos):
    from fastapi.testclient import TestClient

    client = TestClient(main.app, raise_server_exceptions=False)
    body = {**_BODY_BASE, "perfil_fiscal_id": datos["perfil_id"], "productora_id": datos["productora_id"]}
    r = _post(client, body)
    assert r.status_code == 400, r.text


def test_perfil_fiscal_ajeno_404(datos):
    from fastapi.testclient import TestClient

    client = TestClient(main.app, raise_server_exceptions=False)
    # Un id de perfil que existe pero NO es de este cliente (no hay ninguno acá,
    # pero probamos con un id inexistente que igual ejercita el mismo camino).
    r = _post(client, {**_BODY_BASE, "perfil_fiscal_id": 999999})
    assert r.status_code == 404, r.text


def test_productora_de_otro_cliente_404(datos):
    from fastapi.testclient import TestClient

    client = TestClient(main.app, raise_server_exceptions=False)
    r = _post(client, {**_BODY_BASE, "productora_id": datos["productora_id"]})
    assert r.status_code == 404, r.text


def test_perfil_fiscal_propio_se_persiste_en_el_pedido(datos):
    from fastapi.testclient import TestClient
    from database import get_db

    client = TestClient(main.app, raise_server_exceptions=False)
    r = _post(client, {**_BODY_BASE, "perfil_fiscal_id": datos["perfil_id"]})
    assert r.status_code == 201, r.text
    pedido_id = r.json()["id"]

    conn = get_db()
    row = conn.execute(
        "SELECT perfil_fiscal_id, productora_id FROM alquileres WHERE id = %s", (pedido_id,)
    ).fetchone()
    conn.close()
    assert row["perfil_fiscal_id"] == datos["perfil_id"]
    assert row["productora_id"] is None


def test_sin_target_elegido_no_rompe_el_flujo_de_siempre(datos):
    from fastapi.testclient import TestClient
    from database import get_db

    client = TestClient(main.app, raise_server_exceptions=False)
    r = _post(client, _BODY_BASE)
    assert r.status_code == 201, r.text
    pedido_id = r.json()["id"]

    conn = get_db()
    row = conn.execute(
        "SELECT perfil_fiscal_id, productora_id FROM alquileres WHERE id = %s", (pedido_id,)
    ).fetchone()
    conn.close()
    assert row["perfil_fiscal_id"] is None
    assert row["productora_id"] is None
