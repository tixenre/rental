"""Contrato HTTP de los routes de pedidos — red previa a #501 (#862).

Cuando la modularización del backend (#501) mueva los handlers de
`routes/alquileres.py` y `routes/cliente_portal.py` a paquetes/routers nuevos,
lo que NO debe cambiar es el **contrato HTTP externo**. Estos tests lo fijan de
punta a punta (app real + middleware + routing), en cuatro capas, todas vía
requests con `TestClient` (no introspección de estructura interna, que es frágil
entre versiones) y **sin tocar la DB** (el rechazo/los 404 ocurren antes de
cualquier query; la lógica de negocio puede 500ear sin DB y no afecta el assert):

  1. **Existencia** — cada ruta esperada sigue ruteando (no 404/405). Se manda
     con una sesión admin que pasa el middleware en todas las rutas, así el
     request llega al routing. Caza drops de MÉTODO (405) y de rutas no-GET
     (404), incluidas las POST públicas (`cotizar`/`registro`). Límite conocido:
     un GET dropeado cae al catch-all del SPA (200, no 404) → ese caso lo cubren
     las capas 3-4 para los GET con guard. (`test_endpoint_existe`)
  2. **Middleware** — un anónimo no entra a ningún endpoint protegido (401/403).
     (`test_endpoint_protegido_rechaza_anonimo`)
  3. **Guard admin** — una sesión logueada pero NO admin la rechaza el
     `require_admin` del handler (403). (`test_endpoint_admin_rechaza_sesion_no_admin`)
  4. **Guard cliente** — una sesión sin rol cliente la rechaza el
     `require_cliente` (401). (`test_endpoint_cliente_rechaza_sesion_no_cliente`)

Las capas 3-4 son la protección anti-#55 (handler que pierde su guard), que un
refactor de módulos rompe en silencio. El happy-path con datos (Postgres
sembrado) va como fase de integración de #862. Fuente del inventario:
`routes/alquileres.py` + `routes/cliente_portal.py`.
"""
import pytest
from fastapi.testclient import TestClient

import main
from routes.auth import signer

pytestmark = pytest.mark.unit

# TestClient sin entrar al context manager → NO dispara los eventos de startup
# (scheduler/DB); solo ejercita routing + middleware + guards.
# `raise_server_exceptions=False`: si un handler llega a la DB y esta no está
# (CI corre sin Postgres), queremos un 500 como respuesta —no que TestClient
# re-lance la excepción— para que el chequeo de existencia distinga "ruta existe
# pero la lógica 500ea sin DB" (ok) de "ruta perdida" (404/405).
client = TestClient(main.app, raise_server_exceptions=False)

# Cookies de sesión firmadas con el MISMO signer de la app (mismo SECRET_KEY de
# tests) — no tocan la DB, los guards deciden por rol/email.
#   · admin:   sesión válida con email en ADMIN_EMAILS (pasa middleware + require_admin).
#   · cliente: sesión válida de cliente (email fuera de ADMIN_EMAILS).
_COOKIE_ADMIN = f"session={signer.dumps({'email': 'admin@test.com', 'name': 'Admin'})}"
_COOKIE_CLIENTE = f"session={signer.dumps({'email': 'rando@test.com', 'role': 'cliente', 'cliente_id': 1})}"


# ── Inventario ───────────────────────────────────────────────────────────────
# Endpoints ADMIN: anónimo → 401 (middleware); sesión no-admin → 403 (guard).
_ADMIN = [
    ("POST", "/api/alquileres"),
    ("GET", "/api/alquileres"),
    ("GET", "/api/alquileres/1"),
    ("PATCH", "/api/alquileres/1"),
    ("DELETE", "/api/alquileres/1"),
    ("GET", "/api/alquileres/1/pagos"),
    ("POST", "/api/alquileres/1/pagos"),
    ("DELETE", "/api/alquileres/1/pagos/1"),
    ("GET", "/api/admin/pagos"),
    ("POST", "/api/admin/descuentos-jornada"),
    ("DELETE", "/api/admin/descuentos-jornada/1"),
    ("PATCH", "/api/alquileres/1/datos"),
    ("PUT", "/api/alquileres/1/items"),
    ("GET", "/api/alquileres/1/pdf"),
    ("GET", "/api/alquileres/1/albaran"),
    ("GET", "/api/alquileres/1/packing-list"),
    ("GET", "/api/alquileres/1/contrato"),
    ("POST", "/api/alquileres/1/enviar-documentos"),
    ("POST", "/api/alquileres/1/mail-preview"),
    ("POST", "/api/admin/recordatorios/retiro/run"),
    # cliente_portal.py — solicitudes de modificación (las gestiona el admin)
    ("GET", "/api/admin/solicitudes"),
    ("PATCH", "/api/admin/solicitudes/1"),
]

# Endpoints CLIENTE: anónimo → 401 (middleware); sesión no-cliente → 401 (guard).
_CLIENTE = [
    ("GET", "/api/cliente/me"),
    ("PATCH", "/api/cliente/me"),
    ("POST", "/api/cliente/pedidos"),
    ("GET", "/api/cliente/pedidos"),
    ("GET", "/api/cliente/pedidos/1"),
    ("PATCH", "/api/cliente/pedidos/1/cancelar"),
    ("POST", "/api/cliente/pedidos/1/modificacion"),
    ("DELETE", "/api/cliente/pedidos/1/modificacion/1"),
    ("GET", "/api/cliente/pedidos/1/disponibilidad"),
    ("GET", "/api/cliente/modificacion-config"),
    ("GET", "/api/cliente/pedidos/1/remito"),
    ("GET", "/api/cliente/pedidos/1/remito.pdf"),
    ("GET", "/api/cliente/pedidos/1/contrato"),
    ("GET", "/api/cliente/pedidos/1/contrato.pdf"),
    ("GET", "/api/cliente/pedidos/1/albaran"),
    ("GET", "/api/cliente/pedidos/1/albaran.pdf"),
    ("GET", "/api/cliente/favoritos"),
    ("POST", "/api/cliente/favoritos/sync"),
    ("POST", "/api/cliente/favoritos/1"),
    ("DELETE", "/api/cliente/favoritos/1"),
]

# Endpoints PÚBLICOS (anónimo permitido). Solo entran a la capa de existencia.
_PUBLICOS = [
    ("POST", "/api/cotizar"),
    ("GET", "/api/disponibilidad"),
    ("GET", "/api/disponibilidad-dias"),
    ("GET", "/api/descuentos-jornada"),
    ("GET", "/api/cliente/registro-info"),
    ("POST", "/api/cliente/registro"),
]

_PROTEGIDOS = _ADMIN + _CLIENTE
_TODOS = _PROTEGIDOS + _PUBLICOS

# FastAPI valida el body/query (Pydantic) ANTES de ejecutar el cuerpo del
# handler, que es donde vive `require_admin`/`require_cliente`. Para estos
# endpoints, un request con body vacío devuelve 422 antes de llegar al guard →
# no se pueden ejercer en las capas 3-4 sin armar un body válido por-schema
# (frágil, acopla el test al schema → queda como fase de integración de #862).
# Igual están cubiertos por la capa 1 (existencia) y la 2 (anónimo).
_VALIDA_ANTES_DEL_GUARD = {
    ("PATCH", "/api/alquileres/1"),
    ("POST", "/api/alquileres/1/pagos"),
    ("POST", "/api/admin/descuentos-jornada"),
    ("PUT", "/api/alquileres/1/items"),
    ("POST", "/api/alquileres/1/enviar-documentos"),
    ("PATCH", "/api/admin/solicitudes/1"),
    ("POST", "/api/cliente/pedidos/1/modificacion"),
    ("GET", "/api/cliente/pedidos/1/disponibilidad"),
    ("POST", "/api/cliente/favoritos/sync"),
}
_ADMIN_GUARD = [e for e in _ADMIN if e not in _VALIDA_ANTES_DEL_GUARD]
_CLIENTE_GUARD = [e for e in _CLIENTE if e not in _VALIDA_ANTES_DEL_GUARD]


def _id(pares):
    return [f"{m}_{p}" for m, p in pares]


@pytest.mark.parametrize("method,path", _TODOS, ids=_id(_TODOS))
def test_endpoint_existe(method, path):
    """Cada ruta esperada sigue ruteando. Se manda con una sesión admin (pasa el
    middleware en todas las rutas) para LLEGAR al routing: un 404 = path perdido,
    un 405 = método perdido. La lógica puede 500ear sin DB o devolver 401/403/422
    (existe igual) — solo 404/405 significan que #501 movió/renombró la ruta.

    Límite: un GET dropeado cae al catch-all del SPA (200, no 404) → no se caza
    acá; los GET con guard quedan cubiertos por las capas 3-4. Los métodos de
    escritura y las POST públicas sí se cazan (el SPA solo sirve GET)."""
    res = client.request(method, path, json={}, headers={"Cookie": _COOKIE_ADMIN})
    assert res.status_code not in (404, 405), (
        f"{method} {path} no existe (status {res.status_code}) — ¿la movió/renombró #501?"
    )


@pytest.mark.parametrize("method,path", _PROTEGIDOS, ids=_id(_PROTEGIDOS))
def test_endpoint_protegido_rechaza_anonimo(method, path):
    """Anónimo (sin cookie) → 401/403 en todo endpoint protegido (lo corta el
    middleware antes de la DB)."""
    res = client.request(method, path, json={})
    assert res.status_code in (401, 403), (
        f"{method} {path} dejó pasar a un anónimo → {res.status_code}"
    )


@pytest.mark.parametrize("method,path", _ADMIN_GUARD, ids=_id(_ADMIN_GUARD))
def test_endpoint_admin_rechaza_sesion_no_admin(method, path):
    """Sesión LOGUEADA pero no-admin → rechazada por el `require_admin` del
    handler (403). Si #501 mueve el handler y se pierde el guard, un no-admin
    pasaría el middleware y llegaría a la lógica → este test lo caza."""
    res = client.request(method, path, json={}, headers={"Cookie": _COOKIE_CLIENTE})
    assert res.status_code in (401, 403), (
        f"{method} {path}: un logueado no-admin no fue rechazado → {res.status_code} "
        f"(¿se perdió require_admin?)"
    )


@pytest.mark.parametrize("method,path", _CLIENTE_GUARD, ids=_id(_CLIENTE_GUARD))
def test_endpoint_cliente_rechaza_sesion_no_cliente(method, path):
    """Sesión LOGUEADA pero sin rol cliente → rechazada por el `require_cliente`
    del handler (401). Protege el guard a nivel handler ante el refactor."""
    res = client.request(method, path, json={}, headers={"Cookie": _COOKIE_ADMIN})
    assert res.status_code in (401, 403), (
        f"{method} {path}: una sesión no-cliente no fue rechazada → {res.status_code} "
        f"(¿se perdió require_cliente?)"
    )
