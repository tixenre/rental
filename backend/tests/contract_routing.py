"""Helper de los tests de contrato HTTP (`test_routes_contract*.py`).

`route_status(method, path)` responde si una ruta esperada sigue existiendo en la
app **leyendo la tabla de rutas** (`app.routes`), sin mandar un request real.

Por qué se lee la tabla en vez de mandar un request (como hacía la capa de
"existencia" original):

  · El request llegaba al handler real → `get_db()`, y en el job `python-tests`
    (sin Postgres) colgaba el timeout del pool por CADA endpoint. Era el cuello
    de botella de ~38 min. Leer la tabla es instantáneo y no toca la DB.
  · Es MÁS completo: el enfoque viejo no cazaba un GET borrado (caía al catch-all
    del SPA → 200, no 404). Acá se excluye el catch-all, así un GET caído se caza.

Sobre la fragilidad que el test original evitaba a propósito ("no introspección de
estructura interna, que es frágil entre versiones"): este helper usa SOLO API
pública y estable de routing — el protocolo `route.matches(scope)` de Starlette
(que cada router implementa, incluido el wrapper de `include_router` de FastAPI,
que resuelve su subárbol internamente) y `APIRoute.include_in_schema`. NO toca el
árbol interno de dependencias de FastAPI (eso sí sería frágil) ni nombra clases
privadas. Por eso la introspección acá es robusta, no como la que se descartó.
"""
from fastapi.routing import APIRoute
from starlette.routing import Match

import main


def route_status(method: str, path: str) -> str:
    """'full' si (method, path) rutea a un endpoint real de la API; 'partial' si
    la ruta existe pero no con ese método (== 405); 'none' si no existe (== 404).

    Saltea el catch-all del SPA (`/{full_path:path}`) y las demás rutas que sirven
    HTML —todas `include_in_schema=False`— que si no matchearían cualquier GET y
    taparían un endpoint caído. Los routers de la API (donde viven los endpoints
    del inventario) no son `APIRoute` a nivel raíz, así que el filtro no los toca:
    su `.matches()` resuelve el subárbol y devuelve FULL/PARTIAL directo."""
    scope = {"type": "http", "method": method.upper(), "path": path, "root_path": ""}
    estado = "none"
    for route in main.app.routes:
        if isinstance(route, APIRoute) and not route.include_in_schema:
            continue  # catch-all del SPA + rutas HTML → no son endpoints de API
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return "full"
        if match == Match.PARTIAL:
            estado = "partial"
    return estado
