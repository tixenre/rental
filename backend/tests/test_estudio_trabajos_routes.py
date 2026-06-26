"""Regresión de routing de los trabajos del estudio.

La ruta literal `PATCH /admin/estudio/trabajos/orden` (reordenar) debe rutear
ANTES que la dinámica `PATCH /admin/estudio/trabajos/{trabajo_id}` (editar). Si
no, FastAPI matchea "orden" como `trabajo_id` (int) y devuelve 422 — el reorder
del drag-drop nunca llega a su handler ("Error reordenando [object Object]").

No toca la DB: con sesión admin el request pasa el guard y llega al routing; sin
Postgres el handler puede 500ear, pero NUNCA debe ser 422 (que probaría que la
ruta dinámica se comió la literal).
"""
import pytest
from fastapi.testclient import TestClient

import main
from routes.auth import signer

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False)
_COOKIE_ADMIN = f"session={signer.dumps({'email': 'admin@test.com', 'name': 'Admin'})}"


def test_reorder_trabajos_no_lo_captura_la_ruta_dinamica():
    resp = client.patch(
        "/api/admin/estudio/trabajos/orden",
        headers={"Cookie": _COOKIE_ADMIN},
        json={"trabajos": [{"id": 1, "orden": 0}]},
    )
    assert resp.status_code != 422, (
        f"PATCH /trabajos/orden fue capturado por /{{trabajo_id}} "
        f"(static-before-dynamic roto) → {resp.status_code}: {resp.text[:200]}"
    )


def test_editar_trabajo_por_id_sigue_ruteando():
    # La ruta dinámica sigue viva para ids reales (no se rompió al reordenar).
    resp = client.patch(
        "/api/admin/estudio/trabajos/123",
        headers={"Cookie": _COOKIE_ADMIN},
        json={"titulo": "x"},
    )
    # 404 (no existe) o 500 (sin DB) están OK; 405 significaría ruta perdida.
    assert resp.status_code != 405
