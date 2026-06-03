"""Smoke de boot del backend (#632).

Un `NameError` / import faltante en `main.py` llegó a `main` con CI verde y rompió
dos deploys en Railway (#620, #627). Pudo colarse porque NINGÚN test importaba
`main` — los demás usan helpers (`_make_app()`) o llaman funciones sueltas, así que
el módulo de arranque nunca se ejecutaba en CI.

Importar `main` ejecuta TODO el módulo de arranque: construcción de `app`, los
`include_router` de cada router y la definición de todas las rutas. Un fallo de
arranque (import faltante, error a nivel módulo, router roto) rompe estos tests en
rojo en vez de descubrirse recién cuando Railway falla el health-check en prod.

No depende de una DB real: `init_db` corre en un thread daemon aparte (si no hay
DB, loguea y sigue) y `/health` responde sin tocar la base.
"""

from fastapi.testclient import TestClient


def test_import_main_no_crashea():
    """El import en sí es la prueba: corre el módulo de arranque entero."""
    import main

    assert main.app is not None


def test_health_responde_ok():
    """El backend levanta y `/health` responde 200 sin depender de la DB."""
    import main

    with TestClient(main.app) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "migrations" in body
