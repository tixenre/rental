"""`services.facturacion.emisores_repo` contra Postgres REAL.

CRUD completo (create/get/list/update/set_cert/delete) no tenía ningún test dedicado pese a
usarse en producción (hallazgo de la auditoría cruzada de la librería `arca_fe`, 2026-07-04) —
cubre lo que los tests puros no pueden: que la tabla `emisores_arca` existe tal cual la espera
el repo tras `init_db()`, que el cifrado/descifrado de cert+clave hace roundtrip real, y que
`delete_emisor` es soft-delete (no borra la fila).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_facturacion_emisores_repo_db.py -v -m integration
"""
import os
from urllib.parse import urlparse

import pytest
from cryptography.fernet import Fernet

_OPT_IN = os.getenv("RESERVAS_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (_OPT_IN and _looks_like_test_db()),
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
]

_NOMBRE = "test_emisor_repo_db_9300901"


def _limpiar(conn):
    conn.execute("DELETE FROM emisores_arca WHERE nombre = %s", (_NOMBRE,))


@pytest.fixture
def setup(monkeypatch):
    from database import get_db, init_db

    monkeypatch.setenv("ARCA_MASTER_KEY", Fernet.generate_key().decode())
    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
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


def test_create_get_list_roundtrip(setup):
    from database import get_db
    from services.facturacion.emisores_repo import create_emisor, get_by_id, get_by_nombre, list_emisores

    conn = get_db()
    try:
        emisor_id = create_emisor(
            conn,
            nombre=_NOMBRE,
            cuit="20123456786",
            pto_vta=3,
            condicion_iva="responsable_inscripto",
            razon_social="Test SA",
            domicilio="Av. Siempre Viva 742",
        )
        conn.commit()

        emisor = get_by_id(emisor_id, conn)
        assert emisor is not None
        assert emisor.nombre == _NOMBRE
        assert emisor.cuit == "20123456786"
        assert emisor.pto_vta == 3
        assert emisor.condicion_iva == "responsable_inscripto"
        assert emisor.activo is True
        assert emisor.cert_cargado is False
        assert emisor.razon_social == "Test SA"

        por_nombre = get_by_nombre(_NOMBRE, conn)
        assert por_nombre is not None
        assert por_nombre.id == emisor_id

        todos = list_emisores(conn)
        assert any(e.id == emisor_id for e in todos)
    finally:
        conn.close()


def test_create_condicion_iva_invalida_no_inserta(setup):
    from database import get_db
    from services.facturacion.emisores_repo import create_emisor

    conn = get_db()
    try:
        with pytest.raises(ValueError):
            create_emisor(
                conn,
                nombre=_NOMBRE,
                cuit="20123456786",
                pto_vta=3,
                condicion_iva="no-es-una-condicion-valida",
            )
    finally:
        conn.close()


def test_update_emisor_campos_parciales(setup):
    from database import get_db
    from services.facturacion.emisores_repo import create_emisor, get_by_id, update_emisor

    conn = get_db()
    try:
        emisor_id = create_emisor(
            conn,
            nombre=_NOMBRE,
            cuit="20123456786",
            pto_vta=3,
            condicion_iva="monotributo",
        )
        conn.commit()

        # Solo se actualiza domicilio: el resto de los campos no debería tocarse.
        update_emisor(emisor_id, conn, domicilio="Nueva dirección 123")
        conn.commit()

        emisor = get_by_id(emisor_id, conn)
        assert emisor.domicilio == "Nueva dirección 123"
        assert emisor.cuit == "20123456786"
        assert emisor.condicion_iva == "monotributo"

        with pytest.raises(ValueError):
            update_emisor(emisor_id, conn, condicion_iva="otra-cosa")
    finally:
        conn.close()


def test_set_cert_y_get_cert_pem_roundtrip(setup):
    """El cert/clave se cifran al persistir y se descifran EXACTOS al leer — nunca en texto plano
    en la tabla (`cert_enc`/`key_enc` son BYTEA cifrado, no el PEM)."""
    from database import get_db
    from services.facturacion.emisores_repo import (
        create_emisor,
        get_by_id,
        get_cert_pem,
        set_cert,
    )

    conn = get_db()
    try:
        emisor_id = create_emisor(
            conn,
            nombre=_NOMBRE,
            cuit="20123456786",
            pto_vta=3,
            condicion_iva="responsable_inscripto",
        )
        conn.commit()

        cert_pem = b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n"
        key_pem = b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"
        set_cert(emisor_id, conn, cert_pem=cert_pem, key_pem=key_pem)
        conn.commit()

        emisor = get_by_id(emisor_id, conn)
        assert emisor.cert_cargado is True

        cert_leido, key_leido = get_cert_pem(emisor_id, conn)
        assert cert_leido == cert_pem
        assert key_leido == key_pem

        # A nivel fila cruda, el ciphertext no debe contener el plaintext del cert.
        row = conn.execute(
            "SELECT cert_enc FROM emisores_arca WHERE id = %s", (emisor_id,)
        ).fetchone()
        assert cert_pem not in bytes(row["cert_enc"])
    finally:
        conn.close()


def test_get_cert_pem_sin_cert_cargado_lanza_value_error(setup):
    from database import get_db
    from services.facturacion.emisores_repo import create_emisor, get_cert_pem

    conn = get_db()
    try:
        emisor_id = create_emisor(
            conn,
            nombre=_NOMBRE,
            cuit="20123456786",
            pto_vta=3,
            condicion_iva="responsable_inscripto",
        )
        conn.commit()

        with pytest.raises(ValueError):
            get_cert_pem(emisor_id, conn)
    finally:
        conn.close()


def test_delete_emisor_es_soft_delete(setup):
    """`delete_emisor` marca `activo=false`, no borra la fila (la factura ya emitida sigue
    referenciando el nombre del emisor)."""
    from database import get_db
    from services.facturacion.emisores_repo import create_emisor, delete_emisor, get_by_id

    conn = get_db()
    try:
        emisor_id = create_emisor(
            conn,
            nombre=_NOMBRE,
            cuit="20123456786",
            pto_vta=3,
            condicion_iva="responsable_inscripto",
        )
        conn.commit()

        delete_emisor(emisor_id, conn)
        conn.commit()

        emisor = get_by_id(emisor_id, conn)
        assert emisor is not None
        assert emisor.activo is False
    finally:
        conn.close()


def test_get_activo_para_condicion_y_elegir_autenticador(setup):
    from database import get_db
    from services.facturacion.emisores_repo import (
        create_emisor,
        elegir_autenticador,
        get_activo_para_condicion,
        set_cert,
    )

    conn = get_db()
    try:
        emisor_id = create_emisor(
            conn,
            nombre=_NOMBRE,
            cuit="20123456786",
            pto_vta=3,
            condicion_iva="responsable_inscripto",
        )
        conn.commit()

        encontrado = get_activo_para_condicion("responsable_inscripto", conn)
        assert encontrado is not None
        assert encontrado.id == emisor_id

        assert get_activo_para_condicion("monotributo", conn) is None

        # Sin cert cargado, no es candidato a autenticador (aunque esté activo).
        assert elegir_autenticador(conn) != _NOMBRE

        set_cert(emisor_id, conn, cert_pem=b"cert", key_pem=b"key")
        conn.commit()
        assert elegir_autenticador(conn) == _NOMBRE
    finally:
        conn.close()
