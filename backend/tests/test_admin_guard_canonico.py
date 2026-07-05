"""Regresión del crítico de escalada de privilegios cliente→admin.

Un `require_admin` / `_require_admin` **local** en specs / settings / unidades /
calendar que solo chequeaba `if not session` (NO `is_admin_email`) dejaba pasar a
CUALQUIER sesión logueada — incluida la de un CLIENTE del portal, que mintea la
misma cookie `session`. Resultado: un cliente podía editar settings, specs,
unidades y el feed del calendario → escalada de privilegios.

El fix reemplaza esos guards por el canónico `admin_guard.require_admin` (valida
email ∈ ADMIN_EMAILS → 403). Dos capas de regresión:

  1. **Invariante de wiring** (`test_guards_son_el_canonico`): los 4 módulos
     reexportan EXACTAMENTE el guard canónico, no una copia. Si alguien reintroduce
     un guard local a futuro (la misma clase de bug, recurrente), este test lo caza.
  2. **Contrato HTTP** (`test_cliente_no_escala_a_admin`): una cookie de cliente
     válida → 403 en endpoints admin cuyo guard corre ANTES de tocar la DB. Es
     hermético (no necesita Postgres): sin el fix el cliente pasaba el guard y caía
     a la DB (500) o ejecutaba la acción — nunca 403. El `test_routes_contract_admin`
     no lo cazaba porque clasificaba estos endpoints como "solo existencia" (500 sin
     DB ≡ "no hay Postgres"), que es justo por donde se coló el agujero.
"""
import pytest
from fastapi.testclient import TestClient

import main
from auth.session import signer

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False)

# Cookie de un cliente del portal: sesión válida, role=cliente, email NO-admin.
_COOKIE_CLIENTE = (
    "session="
    + signer.dumps(
        {"email": "rando@test.com", "name": "Rando", "role": "cliente", "cliente_id": 1, "jti": "canonico-cli"}
    )
)


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    """jti obligatorio: la cookie de test lleva jti pero no está en la allowlist →
    stubbeamos is_active para darla por activa y que el request llegue al
    require_admin canónico (que es lo que este test verifica: cliente → 403)."""
    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})

# Endpoints admin cuyo guard (canónico) corre ANTES de tocar la DB → 403 hermético.
# Al menos uno por cada módulo que tenía el guard local débil.
_GUARD_FIRST = [
    # specs (paquete routes.specs → `_require_admin` compartido en core.py)
    ("GET", "/api/admin/spec-definitions"),
    ("GET", "/api/admin/specs/por-categoria"),
    ("GET", "/api/admin/specs/diagnostico"),
    ("GET", "/api/admin/equipos/1/specs"),
    # settings.py
    ("PUT", "/api/admin/settings/business_email"),
    ("GET", "/api/admin/equipos/precios-manuales"),
    ("POST", "/api/admin/backup-manual"),
    # unidades.py
    ("GET", "/api/admin/unidades"),
    # calendar.py (importaba el guard de settings)
    ("GET", "/api/admin/calendar/feed"),
    ("POST", "/api/admin/calendar/feed/regenerate"),
]


def _ids(pares):
    return [f"{m}_{p}" for m, p in pares]


def test_guards_son_el_canonico():
    """Los 4 módulos reexportan el guard canónico, no una copia local débil."""
    import auth.guards as admin_guard
    import routes.specs.core as specs_core
    import routes.settings as settings_mod
    import routes.unidades as unidades_mod
    import routes.calendar as calendar_mod

    canonico = admin_guard.require_admin
    assert specs_core._require_admin is canonico, "specs reintrodujo un guard local"
    assert settings_mod.require_admin is canonico, "settings reintrodujo un guard local"
    assert unidades_mod._require_admin is canonico, "unidades reintrodujo un guard local"
    assert calendar_mod.require_admin is canonico, "calendar reintrodujo un guard local"


@pytest.mark.parametrize("method,path", _GUARD_FIRST, ids=_ids(_GUARD_FIRST))
def test_cliente_no_escala_a_admin(method, path):
    """Sesión de CLIENTE (no-admin) → 403. Sin el fix el cliente pasaba el guard
    local débil (DB 500 / acción ejecutada), nunca 403."""
    res = client.request(method, path, json={}, headers={"Cookie": _COOKIE_CLIENTE})
    assert res.status_code == 403, (
        f"{method} {path}: un CLIENTE no fue rechazado con 403 → {res.status_code} "
        f"(¿el guard volvió a ser local/débil?)"
    )


@pytest.mark.parametrize("method,path", _GUARD_FIRST, ids=_ids(_GUARD_FIRST))
def test_anonimo_rechazado(method, path):
    """Sin cookie → 401/403 (lo corta el middleware antes del handler)."""
    res = client.request(method, path, json={})
    assert res.status_code in (401, 403), (
        f"{method} {path} dejó pasar a un anónimo → {res.status_code}"
    )
