"""#862 — guard anti-#55 contra Postgres real: los _ADMIN_EXIST.

Sin Postgres real, los 53 endpoints de `_ADMIN_EXIST` en
`test_routes_contract_admin.py` devuelven 500 (conexión ausente) que enmascara el
guard: no se puede distinguir "require_admin bloqueó → 403" de "DB explotó → 500".
Con Postgres, la única respuesta aceptable para un logueado no-admin es 4xx:

  - 401/403: guard activo (ideal; 401 = middleware, 403 = require_admin)
  - 422/400: body validation antes del guard (aceptable — no ejecuta lógica admin)
  - 200-204: guard ausente → BUG tipo #55 (p.ej. POST /api/equipos devuelve 201)
  - 404:     guard ausente + recurso no encontrado → BUG
  - 500:     guard ausente + DB falla → BUG (= lo que enmascaraba el unit test)

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
"""
import os
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

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

import main  # noqa: E402 — importado después del gating, igual que en test_routes_contract_admin
from routes.auth import signer

# Sesión válida pero NO-admin: pasa el middleware, la rechaza require_admin.
_COOKIE_NO_ADMIN = (
    f"session={signer.dumps({'email': 'rando@test.com', 'role': 'cliente', 'cliente_id': 1})}"
)

# Los mismos 53 endpoints de _ADMIN_EXIST de test_routes_contract_admin.py.
# Se duplica la lista (no se importa) para que el test sea self-contained y pueda
# ser mantenido independientemente si los endpoints cambian.
_ADMIN_EXIST = [
    # equipos
    ("POST", "/api/admin/equipos/1/upload-html-source"),
    ("POST", "/api/equipos"),
    ("POST", "/api/admin/equipos/bulk"),
    ("POST", "/api/equipos/1/mantenimiento"),
    ("POST", "/api/equipos/1/kit"),
    ("POST", "/api/admin/equipos/1/kit/reorder"),
    ("PUT", "/api/equipos/1/etiquetas"),
    ("PUT", "/api/equipos/1/categorias"),
    ("POST", "/api/admin/etiquetas"),
    ("POST", "/api/admin/etiquetas/reorder"),
    ("POST", "/api/admin/categorias"),
    ("POST", "/api/admin/categorias/reorder"),
    ("POST", "/api/admin/equipos/1/upload-foto-from-url"),
    ("POST", "/api/admin/equipos/1/fotos/from-url"),
    ("PATCH", "/api/admin/equipos/1/fotos/orden"),
    # specs
    ("GET", "/api/admin/spec-definitions"),
    ("GET", "/api/admin/specs/por-categoria"),
    ("GET", "/api/admin/specs/diagnostico"),
    ("GET", "/api/admin/specs/template-debug"),
    ("PUT", "/api/admin/specs/categoria/1/reorder"),
    ("DELETE", "/api/admin/spec-definitions/1"),
    ("GET", "/api/admin/spec-templates/resumen"),
    ("GET", "/api/admin/categorias/1/spec-templates"),
    ("GET", "/api/admin/categorias/1/spec-templates/orphans"),
    ("DELETE", "/api/admin/spec-templates/1"),
    ("POST", "/api/admin/spec-templates/reorder"),
    ("GET", "/api/admin/equipos/1/specs"),
    ("GET", "/api/admin/equipos/1/nombre-publico-preview"),
    ("POST", "/api/admin/equipos/clasificar-bulk"),
    ("GET", "/api/admin/equipos/sin-categoria"),
    ("GET", "/api/admin/equipos/1/compatibilidades"),
    ("DELETE", "/api/admin/compatibilidades/1"),
    ("GET", "/api/admin/equipos/1/compatibles"),
    ("GET", "/api/admin/equipos/nombres-validacion"),
    ("GET", "/api/admin/equipos/pendientes-compat"),
    ("GET", "/api/admin/equipos/1/contexto-compat"),
    ("POST", "/api/admin/spec-definitions"),
    ("PATCH", "/api/admin/spec-definitions/1"),
    ("POST", "/api/admin/categorias/1/spec-templates"),
    ("PATCH", "/api/admin/spec-templates/1"),
    ("PUT", "/api/admin/equipos/1/specs"),
    ("POST", "/api/admin/equipos/regenerar-nombres"),
    ("POST", "/api/admin/equipos/recalcular-ranking"),
    ("POST", "/api/admin/equipos/aplicar-clasificacion"),
    ("POST", "/api/admin/equipos/1/compatibilidades"),
    ("PUT", "/api/admin/equipos/1/nombre-publico"),
    ("POST", "/api/admin/compat/bulk"),
    # contabilidad
    ("POST", "/api/admin/contabilidad/movimientos/1/comprobante"),
    ("POST", "/api/admin/contabilidad/cuentas"),
    ("POST", "/api/admin/contabilidad/categorias"),
    ("POST", "/api/admin/contabilidad/movimientos"),
    ("POST", "/api/admin/contabilidad/movimientos/1/anular"),
    ("POST", "/api/admin/contabilidad/rendicion/2026-06/saldar"),
]


@pytest.fixture(scope="module")
def client_con_db():
    """TestClient con Postgres real. `init_db()` explícito por si el thread de
    arranque de main.py no terminó antes de la primera request del test."""
    from database import init_db

    init_db()
    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c


def _ids(pares):
    return [f"{m}_{p.replace('/', '_').lstrip('_')}" for m, p in pares]


@pytest.mark.parametrize("method,path", _ADMIN_EXIST, ids=_ids(_ADMIN_EXIST))
def test_no_admin_bloqueado_con_postgres(client_con_db, method, path):
    """Con Postgres real, un no-admin recibe 4xx en todo endpoint admin.

    Verifica el guard anti-#55: la sesión no-admin no debe recibir 2xx
    (guard ausente) ni 5xx (DB antes del guard — lo que el unit test no
    podía distinguir de un 403 sin Postgres).
    """
    res = client_con_db.request(
        method, path, json={}, headers={"Cookie": _COOKIE_NO_ADMIN}
    )
    assert res.status_code in (400, 401, 403, 422), (
        f"{method} {path} → {res.status_code} para no-admin\n"
        f"  2xx = guard ausente (bug #55)\n"
        f"  404 = guard ausente + recurso no encontrado (bug)\n"
        f"  5xx = DB antes del guard (bug — esto es lo que enmascaraba el unit test)"
    )
