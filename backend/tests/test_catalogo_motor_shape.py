"""Motor de catálogo — test de caracterización (Fase 0).

Captura el ESTADO ACTUAL de los endpoints /api/equipos y /api/equipos/{id}
antes de mover el código al motor (`services/catalogo/`). Las Fases 1 y 2
deben dejar esta caracterización INALTERADA: mismo shape, mismo orden de
claves en los ítems de kit, mismo número de queries o menos.

Punto más fino: la lista y el detalle usan el MISMO conjunto de 7 claves
para los ítems de kit pero en DISTINTO orden. Si el motor los iguala
(issue de calidad, deseado), los tests de orden se actualizan explícitamente
— no debe pasar silenciosamente.

Opt-in (igual que los demás *_db.py):
    RESERVAS_DB_TEST=1 DATABASE_URL=postgresql://...test python -m pytest \\
        tests/test_catalogo_motor_shape.py -v -m integration
"""
import os
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

# ── Gating (idéntico al patrón *_db.py) ──────────────────────────────────────

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

import main  # noqa: E402 — importado después del gating

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app, raise_server_exceptions=True) as c:
        yield c


@contextmanager
def _count_queries(monkeypatch):
    """Cuenta todas las queries SQL (PGConnection.execute + PGCursor.execute)."""
    from database.core import PGConnection, PGCursor

    counter = [0]
    orig_conn = PGConnection.execute
    orig_cur = PGCursor.execute

    def _conn(self, sql, params=()):
        counter[0] += 1
        return orig_conn(self, sql, params)

    def _cur(self, sql, params=()):
        counter[0] += 1
        return orig_cur(self, sql, params)

    monkeypatch.setattr(PGConnection, "execute", _conn)
    monkeypatch.setattr(PGCursor, "execute", _cur)
    try:
        yield counter
    finally:
        monkeypatch.setattr(PGConnection, "execute", orig_conn)
        monkeypatch.setattr(PGCursor, "execute", orig_cur)


# ── Orden de claves de kit (documentado — lista ≠ detalle) ───────────────────
#
# Lista  (attach_kit → contenido_de_batch, db/equipos.py):
#   ["componente_id", "nombre", "marca", "foto_url", "cantidad", "descuento_pct", "esencial"]
#
# Detalle (contenido_de directo, routes/equipos/core.py::get_equipo):
#   ["componente_id", "cantidad", "descuento_pct", "esencial", "nombre", "marca", "foto_url"]
#
# Son las mismas 7 claves en distinto orden — diferencia CONOCIDA en Fase 0.
# El motor (Fase 1) las mueve verbatim; si las iguala (mejora), estos
# comentarios se actualizan en el mismo commit que unifica el orden.

_KIT_KEYS_LISTA = [
    "componente_id", "nombre", "marca", "foto_url",
    "cantidad", "descuento_pct", "esencial",
]
_KIT_KEYS_DETALLE = [
    "componente_id", "cantidad", "descuento_pct", "esencial",
    "nombre", "marca", "foto_url",
]

# Claves raíz de la respuesta de lista
_LISTA_ROOT_KEYS = ["total", "page", "per_page", "items"]

# Claves mínimas de un equipo en la lista
_EQUIPO_LISTA_KEYS = {
    "id", "nombre", "tipo", "precio_jornada",
    "kit", "categorias", "specs", "specs_destacados",
}

# Claves mínimas de un equipo en el detalle (superset de la lista + fotos)
_EQUIPO_DETALLE_EXTRA = {"fotos"}


# ── Tests de shape de la lista ────────────────────────────────────────────────


class TestListaShape:
    def test_estructura_raiz(self, client):
        r = client.get("/api/equipos")
        assert r.status_code == 200
        assert list(r.json().keys()) == _LISTA_ROOT_KEYS

    def test_hay_items(self, client):
        r = client.get("/api/equipos")
        assert r.json()["total"] > 0
        assert len(r.json()["items"]) > 0

    def test_equipo_claves_minimas(self, client):
        r = client.get("/api/equipos")
        equipo = r.json()["items"][0]
        for k in _EQUIPO_LISTA_KEYS:
            assert k in equipo, f"falta clave '{k}' en equipo de lista"

    def test_kit_keys_orden_en_lista(self, client):
        """Orden exacto de claves de los ítems de kit en la lista.

        DOCUMENTADO: la lista y el detalle usan el mismo set de 7 claves
        en DISTINTO orden. El motor (Fase 1) mueve esto verbatim.
        """
        kits = [e for e in client.get("/api/equipos").json()["items"] if e.get("kit")]
        if not kits:
            pytest.skip("no hay equipos con componentes en el catálogo visible")
        actual_keys = list(kits[0]["kit"][0].keys())
        assert actual_keys == _KIT_KEYS_LISTA, (
            f"orden de claves del kit en LISTA cambió.\n"
            f"  actual:   {actual_keys}\n"
            f"  esperado: {_KIT_KEYS_LISTA}\n"
            "Actualizá _KIT_KEYS_LISTA si fue intencional."
        )

    def test_lista_con_cookie_invalida_devuelve_catalogo_publico(self, client):
        """Una cookie firmada con jti inexistente en auth_sessions → get_session
        retorna None → is_admin=False → se sirve el catálogo público (200 con items).

        NOTA: este test NO verifica el path admin (que requiere un jti vivo en la
        tabla). El path admin se cubre en tests de integración con staging-login.
        """
        from auth.session import signer
        cookie = signer.dumps({"email": "admin@test.com", "role": "admin", "jti": "jti-inexistente"})
        r = client.get("/api/equipos", cookies={"session": cookie})
        assert r.status_code == 200
        assert "items" in r.json()


# ── Tests de shape del detalle ────────────────────────────────────────────────


class TestDetalleShape:
    @pytest.fixture(scope="class")
    def primer_equipo(self, client):
        items = client.get("/api/equipos").json()["items"]
        assert items, "lista vacía — no hay qué detallar"
        return items[0]["id"]

    @pytest.fixture(scope="class")
    def primer_kit_id(self, client):
        for e in client.get("/api/equipos").json()["items"]:
            if e.get("kit"):
                return e["id"]
        return None

    def test_detalle_status_200(self, client, primer_equipo):
        assert client.get(f"/api/equipos/{primer_equipo}").status_code == 200

    def test_detalle_claves_minimas(self, client, primer_equipo):
        e = client.get(f"/api/equipos/{primer_equipo}").json()
        for k in _EQUIPO_LISTA_KEYS | _EQUIPO_DETALLE_EXTRA:
            assert k in e, f"falta clave '{k}' en equipo de detalle"

    def test_kit_keys_orden_en_detalle(self, client, primer_kit_id):
        """Orden exacto de claves de los ítems de kit en el detalle.

        DOCUMENTADO: distinto al de la lista (mismas 7 claves, orden diferente).
        """
        if primer_kit_id is None:
            pytest.skip("no hay equipos con componentes en el catálogo visible")
        kit = client.get(f"/api/equipos/{primer_kit_id}").json().get("kit", [])
        if not kit:
            pytest.skip(f"equipo {primer_kit_id} no tiene componentes en el detalle")
        actual_keys = list(kit[0].keys())
        assert actual_keys == _KIT_KEYS_DETALLE, (
            f"orden de claves del kit en DETALLE cambió.\n"
            f"  actual:   {actual_keys}\n"
            f"  esperado: {_KIT_KEYS_DETALLE}\n"
            "Actualizá _KIT_KEYS_DETALLE si fue intencional."
        )

    def test_kit_lista_vs_detalle_difieren(self, client, primer_kit_id):
        """Documenta que la lista y el detalle tienen el mismo SET de claves
        de kit pero en ORDEN DISTINTO. Si el motor los iguala (mejora), este
        test se actualiza explícitamente."""
        if primer_kit_id is None:
            pytest.skip("no hay kit visible")
        lista_kit = next(
            (e["kit"] for e in client.get("/api/equipos").json()["items"]
             if e["id"] == primer_kit_id),
            None,
        )
        detalle_kit = client.get(f"/api/equipos/{primer_kit_id}").json().get("kit", [])
        if not lista_kit or not detalle_kit:
            pytest.skip("kit vacío en algún endpoint")

        lista_keys = list(lista_kit[0].keys())
        detalle_keys = list(detalle_kit[0].keys())

        # Mismo conjunto, distinto orden — esta es la inconsistencia conocida.
        assert set(lista_keys) == set(detalle_keys), (
            f"conjunto de claves de kit difiere entre lista y detalle:\n"
            f"  lista:   {lista_keys}\n"
            f"  detalle: {detalle_keys}"
        )
        assert lista_keys != detalle_keys, (
            "lista y detalle ahora devuelven kit con el MISMO orden de claves. "
            "Actualizá test_kit_lista_vs_detalle_difieren y _KIT_KEYS_* para "
            "reflejar el nuevo estado unificado."
        )

    def test_fotos_shape(self, client, primer_equipo):
        fotos = client.get(f"/api/equipos/{primer_equipo}").json()["fotos"]
        assert isinstance(fotos, list)
        for f in fotos[:3]:  # chequear las primeras
            assert "url" in f and "es_principal" in f


# ── Tests de conteo de queries (baseline) ────────────────────────────────────
#
# Capturan el número ACTUAL de queries para que Fases 1+2 no lo aumenten.
# Bounds generosos: detectan N+1 (que agregaría cientos de queries con 168
# equipos) sin clavarlo al número exacto (que varía según los datos del catálogo).
#
# Distribución esperada para la lista pública (sin desde/hasta):
#   COUNT · main SELECT · marcas batch · attach_kit/contenido ·
#   attach_categorias · attach_ficha · attach_specs_estructuradas ·
#   attach_specs_destacados · precios_combo_batch (si hay combos) ·
#   _stock_sin_reservas × 2 (equipos + componentes_de)
#   ≈ 10-12 queries
#
# Para el detalle:
#   main SELECT · attach_ficha · attach_categorias ·
#   attach_specs_estructuradas · contenido_de · fotos · precio_combo (si combo)
#   ≈ 6-8 queries


class TestQueryCount:
    def test_lista_publica_query_count(self, client, monkeypatch):
        """La lista pública no supera el baseline ni introduce N+1."""
        with _count_queries(monkeypatch) as counter:
            from auth.queries.sessions import is_active as orig_is_active
            monkeypatch.setattr("auth.queries.sessions.is_active", orig_is_active)
            r = client.get("/api/equipos")
        assert r.status_code == 200
        n = counter[0]
        assert n >= 4, f"muy pocas queries ({n}) — algo está roto"
        assert n <= 25, (
            f"demasiadas queries ({n}) en la lista pública — probable N+1. "
            f"Baseline Fase 0: ~11-13. Si Fase 1 lo aumenta, investigar."
        )

    def test_detalle_query_count(self, client, monkeypatch):
        """El detalle no supera el baseline."""
        items = client.get("/api/equipos").json()["items"]
        assert items
        eid = items[0]["id"]

        with _count_queries(monkeypatch) as counter:
            r = client.get(f"/api/equipos/{eid}")
        assert r.status_code == 200
        n = counter[0]
        assert n >= 2, f"muy pocas queries ({n}) — algo está roto"
        assert n <= 15, (
            f"demasiadas queries ({n}) en el detalle — probable N+1. "
            f"Baseline Fase 0: ~7-9. Si Fase 1 lo aumenta, investigar."
        )
