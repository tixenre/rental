"""Candado de `POST /api/checkout/contrato-preview` — preview del CONTRATO del
pedido EN CURSO, antes de crearlo (#1209, feature "leer el contrato antes de
firmar", sienta base para la firma digital de #1098 Fase 5).

Arma un `pedido` equivalente en memoria desde `carritos_activos` + `equipos` +
`clientes` y llama al mismo `_contrato_html` que genera el contrato real de un
pedido ya creado — no persiste nada. El HTML vuelve marcado como SIMULACIÓN
(banner + marca de agua) para que no se confunda con el documento válido, que
recién existe en el portal / se manda por mail al confirmar el pedido.

Contra Postgres real (mismo gating opt-in y seguro por defecto que los demás
`*_db.py`): se saltea salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test'.
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
from fastapi.testclient import TestClient  # noqa: E402

CLIENTE_ID = 9_340_001
EQ_ID = 9_340_101
EQ_ID_BORRADO = 9_340_102
SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SESSION_ID_VACIO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeef"
SESSION_ID_CON_BORRADO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeef1"

_COOKIE = f"session={signer.dumps({'email': 'contrato-preview-db@test.com', 'role': 'cliente', 'cliente_id': CLIENTE_ID, 'jti': 'contrato-preview-cli'})}"

client = TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})


@pytest.fixture
def carrito_con_equipo():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    _sesiones = (SESSION_ID, SESSION_ID_VACIO, SESSION_ID_CON_BORRADO)
    try:
        conn.execute("DELETE FROM carritos_activos WHERE session_id = ANY(%s)", (list(_sesiones),))
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM equipos WHERE id IN (%s, %s)", (EQ_ID, EQ_ID_BORRADO))
        conn.execute(
            """INSERT INTO clientes (id, nombre, apellido, email)
               VALUES (%s, %s, %s, %s)""",
            (CLIENTE_ID, "Ana", "Gómez", "contrato-preview-db@test.com"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo) "
            "VALUES (%s, 'Cámara contrato-preview-test', 5, 1000, 1)",
            (EQ_ID,),
        )
        # Equipo soft-deleted (eliminado_at seteado) — no debería colarse en el
        # preview aunque siga referenciado en un carrito viejo (#carrito viejo
        # que nunca se refrescó tras borrar el equipo del catálogo).
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, eliminado_at) "
            "VALUES (%s, 'Cámara borrada contrato-preview-test', 5, 1000, 1, now())",
            (EQ_ID_BORRADO,),
        )
        conn.execute(
            """INSERT INTO carritos_activos (session_id, cliente_id, items_json, fecha_desde, fecha_hasta)
               VALUES (%s, %s, %s, CURRENT_DATE + 1, CURRENT_DATE + 3)""",
            (SESSION_ID, CLIENTE_ID, f'[{{"equipo_id": {EQ_ID}, "cantidad": 1}}]'),
        )
        conn.execute(
            """INSERT INTO carritos_activos (session_id, cliente_id, items_json, fecha_desde, fecha_hasta)
               VALUES (%s, %s, '[]', CURRENT_DATE + 1, CURRENT_DATE + 3)""",
            (SESSION_ID_VACIO, CLIENTE_ID),
        )
        # Carrito con un ítem borrado + uno vigente — el preview debe mostrar
        # solo el vigente, sin romper.
        conn.execute(
            """INSERT INTO carritos_activos (session_id, cliente_id, items_json, fecha_desde, fecha_hasta)
               VALUES (%s, %s, %s, CURRENT_DATE + 1, CURRENT_DATE + 3)""",
            (
                SESSION_ID_CON_BORRADO, CLIENTE_ID,
                f'[{{"equipo_id": {EQ_ID}, "cantidad": 1}}, {{"equipo_id": {EQ_ID_BORRADO}, "cantidad": 1}}]',
            ),
        )
        conn.commit()
        yield
    finally:
        conn.execute("DELETE FROM carritos_activos WHERE session_id = ANY(%s)", (list(_sesiones),))
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM equipos WHERE id IN (%s, %s)", (EQ_ID, EQ_ID_BORRADO))
        conn.commit()
        conn.close()


def test_contrato_preview_devuelve_html_marcado_como_simulacion(carrito_con_equipo):
    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": SESSION_ID},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    html = res.text
    assert "SIMULACIÓN" in html
    assert "Vista previa" in html
    assert "Cámara contrato-preview-test" in html
    # No persiste nada: no crea un pedido real.
    assert "preview" not in html.split("<body>", 1)[0]  # sanity: no filtra el id interno al <head>


def test_contrato_preview_no_expone_pii_real_del_cliente(carrito_con_equipo):
    """El preview es una SIMULACIÓN que queda en el DOM del browser — ni el
    nombre/email real del cliente logueado (Locatario) NI los datos
    institucionales reales de Rambla (Locador) deben aparecer; ambas partes
    llevan datos de muestra (`_CLIENTE_DE_MUESTRA` / `_LOCADOR_DE_MUESTRA`)."""
    from pdf_templates import OWNER_CUIL, OWNER_NOMBRE
    from routes.checkout import _LOCADOR_DE_MUESTRA

    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": SESSION_ID},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 200
    html = res.text
    assert "Ana Gómez" not in html
    assert "contrato-preview-db@test.com" not in html
    assert "Juan Pérez" in html  # placeholder de _CLIENTE_DE_MUESTRA
    assert OWNER_NOMBRE not in html
    assert OWNER_CUIL not in html
    assert _LOCADOR_DE_MUESTRA["nombre"] in html  # placeholder de _LOCADOR_DE_MUESTRA


def test_contrato_preview_serie_y_valor_de_equipos_son_ficticios(carrito_con_equipo):
    """Los números de serie y valores de reposición reales del inventario
    tampoco se muestran — se reemplazan por placeholders (`EJEMPLO-####`)."""
    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": SESSION_ID},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 200
    assert "EJEMPLO-0001" in res.text


def test_contrato_preview_carrito_vacio_400(carrito_con_equipo):
    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": SESSION_ID_VACIO},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 400
    assert "vacío" in res.json()["detail"]


def test_contrato_preview_sin_carrito_404(carrito_con_equipo):
    otra = "11111111-2222-3333-4444-555555555555"
    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": otra},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 404


def test_contrato_preview_session_id_invalido_400(carrito_con_equipo):
    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": "no-es-un-uuid"},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 400


def test_contrato_preview_excluye_equipo_soft_deleted(carrito_con_equipo):
    """Un equipo con `eliminado_at` seteado (borrado del catálogo) no debe
    aparecer en el preview aunque siga referenciado en un carrito viejo que
    nunca se refrescó — el resto del carrito se muestra igual."""
    res = client.post(
        "/api/checkout/contrato-preview",
        json={"session_id": SESSION_ID_CON_BORRADO},
        headers={"Cookie": _COOKIE},
    )
    assert res.status_code == 200
    assert "Cámara contrato-preview-test" in res.text
    assert "Cámara borrada contrato-preview-test" not in res.text
