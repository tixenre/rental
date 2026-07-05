"""`services.facturacion.repo_exportacion` contra Postgres REAL.

Cubre lo que los tests puros (mockeados) de `test_engine_exportacion.py` no pueden: que la tabla
`facturas_exportacion` existe tal cual la espera el repo tras `init_db()`, que el ciclo
insert→update_cae/update_error→marcar_anulada/revertir_anulacion persiste bien, y que los filtros
de `list_facturas_exportacion` funcionan contra filas reales.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_repo_exportacion_db.py -v -m integration
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
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
        not (_OPT_IN and _looks_like_test_db()),
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
]

_EMISOR = "test_exportacion_repo_db_9300902"


def _limpiar(conn):
    conn.execute("DELETE FROM facturas_exportacion WHERE emisor = %s", (_EMISOR,))


@pytest.fixture
def setup():
    from database import get_db, init_db

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


def _insertar(conn, **overrides) -> int:
    from services.facturacion.repo_exportacion import insert_factura_exportacion

    base = dict(
        conn=conn, emisor=_EMISOR, ambiente="homologacion", cbte_tipo=19, pto_vta=3,
        receptor_razon_social="Acme Corp", receptor_pais_destino=203,
        incoterm="FOB", moneda="USD", cotizacion=Decimal("1000"), imp_total=Decimal("1000.00"),
    )
    base.update(overrides)
    return insert_factura_exportacion(**base)


def test_insert_y_get_by_id_roundtrip(setup):
    from database import get_db

    conn = get_db()
    try:
        factura_id = _insertar(conn)
        conn.commit()

        from services.facturacion.repo_exportacion import get_by_id

        factura = get_by_id(factura_id, conn)
        assert factura is not None
        assert factura.emisor == _EMISOR
        assert factura.cbte_tipo == 19
        assert factura.pto_vta == 3
        assert factura.receptor_razon_social == "Acme Corp"
        assert factura.receptor_pais_destino == 203
        assert factura.incoterm == "FOB"
        assert factura.moneda == "USD"
        assert factura.estado == "pendiente"
        assert factura.cae is None
        assert factura.qr_payload is None
    finally:
        conn.close()


def test_update_cae_exportacion_persiste_cae_y_qr(setup):
    from database import get_db

    conn = get_db()
    try:
        factura_id = _insertar(conn)
        conn.commit()

        from services.facturacion.repo_exportacion import get_by_id, update_cae_exportacion

        update_cae_exportacion(
            factura_id, conn,
            cbte_nro=42, cae="70012345670000", cae_vto=date(2030, 1, 1),
            qr_payload="https://www.afip.gob.ar/fe/qr/?p=xyz",
            raw_response={"resultado": "A"},
        )
        conn.commit()

        factura = get_by_id(factura_id, conn)
        assert factura.estado == "emitida"
        assert factura.cbte_nro == 42
        assert factura.cae == "70012345670000"
        assert factura.cae_vto == date(2030, 1, 1)
        assert factura.qr_payload == "https://www.afip.gob.ar/fe/qr/?p=xyz"
        assert factura.fecha_emision is not None
    finally:
        conn.close()


def test_update_error_exportacion_marca_error_y_no_setea_cae(setup):
    from database import get_db

    conn = get_db()
    try:
        factura_id = _insertar(conn)
        conn.commit()

        from services.facturacion.repo_exportacion import get_by_id, update_error_exportacion

        update_error_exportacion(factura_id, conn, errores=["500: CUIT no habilitado"])
        conn.commit()

        factura = get_by_id(factura_id, conn)
        assert factura.estado == "error"
        assert factura.errores == ["500: CUIT no habilitado"]
        assert factura.cae is None
    finally:
        conn.close()


def test_marcar_anulada_y_revertir_anulacion(setup):
    from database import get_db

    conn = get_db()
    try:
        factura_id = _insertar(conn)
        conn.commit()

        from services.facturacion.repo_exportacion import (
            get_by_id,
            marcar_anulada,
            revertir_anulacion,
            update_cae_exportacion,
        )

        update_cae_exportacion(
            factura_id, conn, cbte_nro=1, cae="70012345670000", cae_vto=date(2030, 1, 1),
            qr_payload="https://www.afip.gob.ar/fe/qr/?p=xyz", raw_response={},
        )
        conn.commit()

        marcar_anulada(factura_id, conn)
        conn.commit()
        assert get_by_id(factura_id, conn).estado == "anulada"

        revertir_anulacion(factura_id, conn)
        conn.commit()
        assert get_by_id(factura_id, conn).estado == "emitida"
    finally:
        conn.close()


def test_list_facturas_exportacion_filtra_por_emisor_y_estado(setup):
    from database import get_db

    conn = get_db()
    try:
        id_pendiente = _insertar(conn)
        id_emitida = _insertar(conn)
        conn.commit()

        from services.facturacion.repo_exportacion import (
            list_facturas_exportacion,
            update_cae_exportacion,
        )

        update_cae_exportacion(
            id_emitida, conn, cbte_nro=1, cae="70012345670000", cae_vto=date(2030, 1, 1),
            qr_payload="https://www.afip.gob.ar/fe/qr/?p=xyz", raw_response={},
        )
        conn.commit()

        todas = list_facturas_exportacion(conn, emisor=_EMISOR)
        assert {f.id for f in todas} == {id_pendiente, id_emitida}

        solo_emitidas = list_facturas_exportacion(conn, emisor=_EMISOR, estado="emitida")
        assert {f.id for f in solo_emitidas} == {id_emitida}

        solo_pendientes = list_facturas_exportacion(conn, emisor=_EMISOR, estado="pendiente")
        assert {f.id for f in solo_pendientes} == {id_pendiente}
    finally:
        conn.close()
