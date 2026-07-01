"""Contrato HTTP de los routes admin: equipos + specs + contabilidad (#862 fase 2).

Continúa la red de `test_routes_contract.py` (alquileres + cliente_portal) hacia
los routers que faltaban antes de la modularización #501 — en particular
`equipos.py`, cuyo split (fase a de #501) cierra #179. **Sin tocar la DB**: las
capas 1-2 (guards) mandan requests con `TestClient`; la capa 3 (existencia) lee
la tabla de rutas (`route_status`) en vez de mandar un request — esos endpoints
tocan la DB antes del guard y colgaban el pool sin Postgres.

Tres capas (las de guard con sesión NO-admin / anónima, para no ejecutar handlers
admin —varios hacen I/O externo: uploads, R2, scraping— y mantener el test
hermético):

  1. **Anónimo** → 401/403 en TODO endpoint admin (lo corta el middleware).
  2. **Guard del handler** (anti-#55) → una sesión logueada no-admin la rechaza el
     `require_admin` (403). Solo aplica a los endpoints cuyo `require_admin` corre
     ANTES de tocar la DB o validar el body; para el resto, sin Postgres no se
     puede distinguir "403 del guard" de "500 por falta de DB" → su guard se
     verifica en la fase de INTEGRACIÓN de #862 (Postgres real). Igual prueba que
     la ruta existe.
  3. **Existencia** → la ruta sigue ruteando (no 404/405), para los endpoints que
     sin DB darían 500 (tocan la DB antes del guard) o 422/400 (validan body antes)
     y para los públicos del catálogo. Se lee la tabla de rutas → instantáneo, sin
     DB, y caza también los GET dropeados (el catch-all del SPA queda excluido).

Las listas se clasificaron data-driven (probe del status real sin DB). Fuente:
`routes/equipos.py`, `routes/specs.py`, `routes/contabilidad.py` (prefix `/api`).
"""
import pytest
from fastapi.testclient import TestClient

import main
from auth.session import signer
from tests.contract_routing import route_status

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False)

# Sesión válida pero NO-admin: pasa el middleware, la rechaza require_admin.
_COOKIE_CLIENTE = f"session={signer.dumps({'email': 'rando@test.com', 'role': 'cliente', 'cliente_id': 1, 'jti': 'contract-cli'})}"


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    """jti obligatorio: `get_session` exige que la sesión esté viva en la allowlist.
    La cookie de contrato lleva jti pero no está en la tabla → stubbeamos `is_active`
    para darla por activa, así pasa el chequeo de revocación y llega al require_admin
    del handler (que es lo que estos tests verifican)."""
    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})


# ── ADMIN con guard ANTES de DB/validación: anon → 401; no-admin → 403 ────────
_ADMIN_GUARD = [
    # equipos.py
    ("GET", "/api/equipos/kpis"),
    ("POST", "/api/equipos/1/duplicate"),
    ("POST", "/api/equipos/1/restore"),
    ("DELETE", "/api/equipos/1"),
    ("DELETE", "/api/equipos/1/mantenimiento/1"),
    ("DELETE", "/api/equipos/1/kit/1"),
    ("GET", "/api/admin/dashboard/uso"),
    ("GET", "/api/admin/equipos/sin-serie"),
    ("GET", "/api/admin/etiquetas"),
    ("DELETE", "/api/admin/etiquetas/1"),
    ("GET", "/api/admin/categorias"),
    ("DELETE", "/api/admin/categorias/1"),
    ("POST", "/api/admin/equipos/1/upload-foto"),
    ("GET", "/api/admin/equipos/1/fotos"),
    ("POST", "/api/admin/equipos/1/fotos"),
    ("DELETE", "/api/admin/equipos/1/fotos/1"),
    ("GET", "/api/admin/storage/diag"),
    ("PATCH", "/api/equipos/1"),
    ("PUT", "/api/equipos/1/ficha"),
    ("PATCH", "/api/equipos/1/mantenimiento/1"),
    ("PATCH", "/api/admin/etiquetas/1"),
    ("PATCH", "/api/admin/categorias/1"),
    ("POST", "/api/admin/equipos/buscar-fotos"),
    # contabilidad.py
    ("GET", "/api/admin/contabilidad/saldos"),
    ("GET", "/api/admin/contabilidad/tablero"),
    ("GET", "/api/admin/contabilidad/cuentas"),
    ("DELETE", "/api/admin/contabilidad/cuentas/1"),
    ("GET", "/api/admin/contabilidad/categorias"),
    ("GET", "/api/admin/contabilidad/beneficiarios"),
    ("GET", "/api/admin/contabilidad/movimientos"),
    ("GET", "/api/admin/contabilidad/gastos"),
    ("GET", "/api/admin/contabilidad/pyl/2026-06"),
    ("GET", "/api/admin/contabilidad/reporte/2026-06"),
    ("GET", "/api/admin/contabilidad/rendicion/2026-06"),
    ("GET", "/api/admin/contabilidad/reconciliacion"),
    ("POST", "/api/admin/contabilidad/cierres/2026-06"),
    ("DELETE", "/api/admin/contabilidad/cierres/2026-06"),
    ("PATCH", "/api/admin/contabilidad/cuentas/1"),
    ("PATCH", "/api/admin/contabilidad/movimientos/1"),
]

# ── ADMIN cuyo guard corre DESPUÉS de tocar DB (500) o validar body (422/400)
#    sin Postgres: solo existencia acá; su guard va a la fase de integración.
_ADMIN_EXIST = [
    # equipos.py
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
    # specs.py
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
    # contabilidad.py
    ("POST", "/api/admin/contabilidad/movimientos/1/comprobante"),
    ("POST", "/api/admin/contabilidad/cuentas"),
    ("POST", "/api/admin/contabilidad/categorias"),
    ("POST", "/api/admin/contabilidad/movimientos"),
    ("POST", "/api/admin/contabilidad/movimientos/1/anular"),
    ("POST", "/api/admin/contabilidad/rendicion/2026-06/saldar"),
]

# ── PÚBLICOS (catálogo): solo existencia ──────────────────────────────────────
_PUBLICOS = [
    ("GET", "/api/equipos/afuera"),
    ("GET", "/api/equipos"),
    ("GET", "/api/equipos/1"),
    ("GET", "/api/equipos/1/ficha"),
    ("GET", "/api/equipos/1/disponibilidad-calendario"),
    ("GET", "/api/equipos/1/historial"),
    ("GET", "/api/equipos/1/mantenimiento"),
    ("GET", "/api/equipos/1/kit"),
    ("GET", "/api/equipos/1/precio-historial"),
    ("GET", "/api/etiquetas"),
    ("GET", "/api/categorias"),
    ("GET", "/api/equipos/1/calendario"),
]

_ADMIN = _ADMIN_GUARD + _ADMIN_EXIST
_EXISTENCIA = _ADMIN_EXIST + _PUBLICOS


def _ids(pares):
    return [f"{m}_{p}" for m, p in pares]


@pytest.mark.parametrize("method,path", _ADMIN, ids=_ids(_ADMIN))
def test_admin_rechaza_anonimo(method, path):
    """Anónimo (sin cookie) → 401/403 en todo endpoint admin (middleware)."""
    res = client.request(method, path, json={})
    assert res.status_code in (401, 403), (
        f"{method} {path} dejó pasar a un anónimo → {res.status_code}"
    )


@pytest.mark.parametrize("method,path", _ADMIN_GUARD, ids=_ids(_ADMIN_GUARD))
def test_admin_guard_rechaza_no_admin(method, path):
    """Sesión logueada pero no-admin → 403 del `require_admin` del handler. Prueba
    el guard (anti-#55) y, de paso, que la ruta existe. (Solo los endpoints cuyo
    guard corre antes de la DB/validación; el resto, en la fase de integración.)"""
    res = client.request(method, path, json={}, headers={"Cookie": _COOKIE_CLIENTE})
    assert res.status_code in (401, 403), (
        f"{method} {path}: un logueado no-admin no fue rechazado → {res.status_code} "
        f"(¿se perdió require_admin?)"
    )


@pytest.mark.parametrize("method,path", _EXISTENCIA, ids=_ids(_EXISTENCIA))
def test_endpoint_existe(method, path):
    """La ruta sigue ruteando (no 404/405). Se chequea leyendo la tabla de rutas
    (`route_status`), no mandando un request: estos endpoints tocan la DB antes
    del guard, así que el request colgaba el timeout del pool sin Postgres (el
    cuello de botella del job). Instantáneo y sin DB. Cómo →
    `tests/contract_routing.py`."""
    estado = route_status(method, path)
    assert estado == "full", (
        f"{method} {path} no rutea "
        f"({'método caído → 405' if estado == 'partial' else 'ruta caída → 404'})"
        f" — ¿la movió/renombró un refactor?"
    )
