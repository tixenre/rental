"""Admin puede elegir a nombre de quién se factura un pedido (#1251) — el
renter sigue siendo `cliente_id`, esto solo cambia el destino de la factura:
la cuenta default, un perfil fiscal personal del cliente, o una productora
vinculada. Antes solo el checkout del cliente (`cliente_crear_pedido`) podía
setear `perfil_fiscal_id`/`productora_id`; el builder/editor admin no los
usaba (`PedidoDatos` no tenía los campos, `_apply_pedido_datos` no validaba
membership).

Recorre:
  1. Creación (`create_pedido`, es_admin=True): membership + mutua exclusión,
     mismo defense-in-depth que ya tenía el path del cliente.
  2. Edición (`_apply_pedido_datos`): membership + mutua exclusión + limpieza
     automática del otro campo (selección tipo radio) + poder volver a NULL/NULL.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre.
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

CLIENTE_ID = 9_360_001
OTRO_CLIENTE_ID = 9_360_002
EQ_ID = 9_360_201
FD, FH = "2031-07-01T10:00:00", "2031-07-02T10:00:00"


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})


@pytest.fixture
def datos():
    """Dos clientes; un perfil fiscal + una productora, ambos del PRIMERO;
    otra productora vinculada solo al SEGUNDO (para probar 404 de membership)."""
    from database import get_db, init_db

    init_db()
    conn = get_db()
    created_ids = []
    try:
        conn.execute("DELETE FROM equipos WHERE id = %s", (EQ_ID,))
        conn.execute("DELETE FROM clientes WHERE id IN (%s, %s)", (CLIENTE_ID, OTRO_CLIENTE_ID))
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido, email) VALUES "
            "(%s, 'Ana', 'Gómez', 'pedido-facturacion-admin@test.com'), "
            "(%s, 'Otro', 'Cliente', 'otro-pedido-facturacion-admin@test.com')",
            (CLIENTE_ID, OTRO_CLIENTE_ID),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo) "
            "VALUES (%s, 'Cámara pedido-facturacion-admin', 5, 1000, 1)",
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
            "VALUES ('30500009992', 'responsable_inscripto', 'Productora Propia')",
            (),
        )
        conn.execute(
            "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
            (productora_id, CLIENTE_ID),
        )
        productora_ajena_id = conn.insert_returning(
            "INSERT INTO productoras (cuit, perfil_impuestos, razon_social) "
            "VALUES ('30500009993', 'responsable_inscripto', 'Productora Ajena')",
            (),
        )
        conn.execute(
            "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
            (productora_ajena_id, OTRO_CLIENTE_ID),
        )
        conn.commit()
        yield {
            "perfil_id": perfil_id,
            "productora_id": productora_id,
            "productora_ajena_id": productora_ajena_id,
            "created_ids": created_ids,
        }
    finally:
        if created_ids:
            ph = ",".join(str(p) for p in created_ids)
            conn.execute(f"DELETE FROM alquiler_items WHERE pedido_id IN ({ph})")
            conn.execute(f"DELETE FROM alquileres WHERE id IN ({ph})")
        conn.execute("DELETE FROM productora_miembros")
        conn.execute(
            "DELETE FROM productoras WHERE cuit IN ('30500009992', '30500009993')"
        )
        conn.execute(
            "DELETE FROM cliente_perfiles_fiscales WHERE cliente_id IN (%s, %s)",
            (CLIENTE_ID, OTRO_CLIENTE_ID),
        )
        conn.execute("DELETE FROM equipos WHERE id = %s", (EQ_ID,))
        conn.execute("DELETE FROM clientes WHERE id IN (%s, %s)", (CLIENTE_ID, OTRO_CLIENTE_ID))
        conn.commit()
        conn.close()


def _crear_pedido_base(cliente_id=CLIENTE_ID):
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem

    return create_pedido(
        PedidoCreate(
            cliente_id=cliente_id,
            fecha_desde=FD, fecha_hasta=FH,
            estado="presupuesto",
            items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
        ),
        es_admin=True,
    )


# ── Creación ─────────────────────────────────────────────────────────────────

def test_crear_ambos_campos_a_la_vez_400(datos):
    from fastapi import HTTPException
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem

    with pytest.raises(HTTPException) as exc:
        create_pedido(
            PedidoCreate(
                cliente_id=CLIENTE_ID,
                fecha_desde=FD, fecha_hasta=FH,
                estado="presupuesto",
                items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
                perfil_fiscal_id=datos["perfil_id"],
                productora_id=datos["productora_id"],
            ),
            es_admin=True,
        )
    assert exc.value.status_code == 400


def test_crear_productora_de_otro_cliente_404(datos):
    from fastapi import HTTPException
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem

    with pytest.raises(HTTPException) as exc:
        create_pedido(
            PedidoCreate(
                cliente_id=CLIENTE_ID,
                fecha_desde=FD, fecha_hasta=FH,
                estado="presupuesto",
                items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
                productora_id=datos["productora_ajena_id"],
            ),
            es_admin=True,
        )
    assert exc.value.status_code == 404


def test_crear_con_productora_propia_se_persiste(datos):
    from database import get_db
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem

    pedido = create_pedido(
        PedidoCreate(
            cliente_id=CLIENTE_ID,
            fecha_desde=FD, fecha_hasta=FH,
            estado="presupuesto",
            items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
            productora_id=datos["productora_id"],
        ),
        es_admin=True,
    )
    datos["created_ids"].append(pedido["id"])

    with get_db() as conn:
        row = conn.execute(
            "SELECT perfil_fiscal_id, productora_id FROM alquileres WHERE id=%s", (pedido["id"],)
        ).fetchone()
    assert row["productora_id"] == datos["productora_id"]
    assert row["perfil_fiscal_id"] is None


# ── Edición ──────────────────────────────────────────────────────────────────

def test_editar_ambos_campos_a_la_vez_400(datos):
    from routes.alquileres import PedidoDatos

    with pytest.raises(ValueError):
        PedidoDatos(perfil_fiscal_id=datos["perfil_id"], productora_id=datos["productora_id"])


def test_editar_perfil_fiscal_ajeno_404(datos):
    from fastapi import HTTPException
    from database import get_db
    from routes.alquileres import PedidoDatos, _apply_pedido_datos

    pedido = _crear_pedido_base()
    datos["created_ids"].append(pedido["id"])

    with get_db() as conn:
        with pytest.raises(HTTPException) as exc:
            _apply_pedido_datos(conn, pedido["id"], PedidoDatos(perfil_fiscal_id=999999), es_admin=True)
        conn.rollback()
    assert exc.value.status_code == 404


def test_editar_productora_de_otro_cliente_404(datos):
    from fastapi import HTTPException
    from database import get_db
    from routes.alquileres import PedidoDatos, _apply_pedido_datos

    pedido = _crear_pedido_base()
    datos["created_ids"].append(pedido["id"])

    with get_db() as conn:
        with pytest.raises(HTTPException) as exc:
            _apply_pedido_datos(
                conn, pedido["id"], PedidoDatos(productora_id=datos["productora_ajena_id"]), es_admin=True
            )
        conn.rollback()
    assert exc.value.status_code == 404


def test_editar_productora_propia_se_persiste_y_limpia_perfil(datos):
    """Selección tipo radio: elegir una productora limpia el perfil fiscal
    aunque el pedido ya tuviera uno seteado — evita dejar ambos apuntando a algo."""
    from database import get_db
    from routes.alquileres import PedidoDatos, _apply_pedido_datos

    pedido = _crear_pedido_base()
    datos["created_ids"].append(pedido["id"])

    with get_db() as conn:
        _apply_pedido_datos(conn, pedido["id"], PedidoDatos(perfil_fiscal_id=datos["perfil_id"]), es_admin=True)
        conn.commit()
    with get_db() as conn:
        row = conn.execute(
            "SELECT perfil_fiscal_id, productora_id FROM alquileres WHERE id=%s", (pedido["id"],)
        ).fetchone()
    assert row["perfil_fiscal_id"] == datos["perfil_id"]

    with get_db() as conn:
        _apply_pedido_datos(conn, pedido["id"], PedidoDatos(productora_id=datos["productora_id"]), es_admin=True)
        conn.commit()
    with get_db() as conn:
        row = conn.execute(
            "SELECT perfil_fiscal_id, productora_id FROM alquileres WHERE id=%s", (pedido["id"],)
        ).fetchone()
    assert row["productora_id"] == datos["productora_id"]
    assert row["perfil_fiscal_id"] is None


def test_editar_volver_a_default_limpia_ambos(datos):
    from database import get_db
    from routes.alquileres import PedidoDatos, _apply_pedido_datos

    pedido = _crear_pedido_base()
    datos["created_ids"].append(pedido["id"])

    with get_db() as conn:
        _apply_pedido_datos(conn, pedido["id"], PedidoDatos(productora_id=datos["productora_id"]), es_admin=True)
        conn.commit()

    with get_db() as conn:
        _apply_pedido_datos(
            conn, pedido["id"],
            PedidoDatos(perfil_fiscal_id=None, productora_id=None),
            es_admin=True,
        )
        conn.commit()
    with get_db() as conn:
        row = conn.execute(
            "SELECT perfil_fiscal_id, productora_id FROM alquileres WHERE id=%s", (pedido["id"],)
        ).fetchone()
    assert row["perfil_fiscal_id"] is None
    assert row["productora_id"] is None


def test_editar_sin_tocar_fiscal_no_afecta_lo_ya_elegido(datos):
    """Editar otro campo (ej. notas) sin mandar perfil_fiscal_id/productora_id
    no debe tocar lo que ya estaba elegido (exclude_unset)."""
    from database import get_db
    from routes.alquileres import PedidoDatos, _apply_pedido_datos

    pedido = _crear_pedido_base()
    datos["created_ids"].append(pedido["id"])

    with get_db() as conn:
        _apply_pedido_datos(conn, pedido["id"], PedidoDatos(productora_id=datos["productora_id"]), es_admin=True)
        conn.commit()

    with get_db() as conn:
        _apply_pedido_datos(conn, pedido["id"], PedidoDatos(notas="una nota cualquiera"), es_admin=True)
        conn.commit()
    with get_db() as conn:
        row = conn.execute(
            "SELECT productora_id, notas FROM alquileres WHERE id=%s", (pedido["id"],)
        ).fetchone()
    assert row["productora_id"] == datos["productora_id"]
    assert row["notas"] == "una nota cualquiera"
