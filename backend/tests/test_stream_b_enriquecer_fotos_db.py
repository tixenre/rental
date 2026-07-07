"""Stream B de la iniciativa de completitud de catálogo (#1051) contra Postgres
real: `POST /admin/equipos/{id}/enriquecer-from-html` (hermano JSON de
upload-html-source, sin R2) + `POST /admin/equipos/{id}/fotos/from-urls`
(batch de la versión singular).

`enriquecer-from-html` reusa el mismo `extract_from_html`/Canal C que
upload-html-source — lo único que cambia es que NO persiste en R2 ni toca
`html_source_url`. Ese es exactamente el contrato que este archivo verifica
contra una fila real de `equipos` (un FakeConn no distingue "no llamé a R2"
de "llamé a R2 y no hizo nada").

`fotos/from-urls` se prueba con `_agregar_foto_desde_url` monkeypatcheado
(no hace falta red/R2 real para probar que el batch es best-effort — eso es
lógica pura de la ruta, no de la descarga).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre.
"""
import os
from pathlib import Path
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

EQ_ID = 9_600_701
_FIXTURES = Path(__file__).parent / "fixtures" / "html"


@pytest.fixture
def admin_cookie(monkeypatch):
    """Sesión admin válida sin tocar `auth_sessions` (jti obligatorio, mismo
    truco que test_routes_admin_guard_db.py)."""
    from auth.session import signer

    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})
    payload = {"email": "admin@test.com", "role": "admin", "jti": "stream-b-db"}
    return {"session": signer.dumps(payload)}


def _client() -> TestClient:
    import main

    return TestClient(main.app, raise_server_exceptions=False)


def _limpiar(conn):
    conn.execute("DELETE FROM spec_propuestas_pendientes WHERE equipo_id = %s", (EQ_ID,))
    conn.execute("DELETE FROM equipo_fotos WHERE equipo_id = %s", (EQ_ID,))
    conn.execute("DELETE FROM equipos WHERE id = %s", (EQ_ID,))


@pytest.fixture
def equipo(monkeypatch):
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo) VALUES (%s,%s,%s,1)",
            (EQ_ID, "ZZ-TEST-stream-b", 1),
        )
        conn.commit()
    finally:
        conn.close()
    yield EQ_ID
    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


# ── enriquecer-from-html ──────────────────────────────────────────────────


def test_enriquecer_from_html_no_toca_r2_ni_html_source_url(equipo, admin_cookie):
    """Contrato central: mismo extractor que upload-html-source, pero NO
    persiste nada — ni el blob en R2 ni `equipos.html_source_url`."""
    from database import get_db

    html = (_FIXTURES / "camara_minimal.html").read_text(encoding="utf-8")
    c = _client()
    r = c.post(
        f"/api/admin/equipos/{equipo}/enriquecer-from-html",
        json={"html": html},
        cookies=admin_cookie,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "html_source_url" not in body
    assert body["categoria_sugerida"] == "Cámaras"
    assert len(body["specs"]) > 0

    with get_db() as conn:
        row = conn.execute(
            "SELECT html_source_url FROM equipos WHERE id = %s", (equipo,)
        ).fetchone()
        assert row["html_source_url"] is None, (
            "enriquecer-from-html NO debe tocar html_source_url — para eso está upload-html-source"
        )


def test_enriquecer_from_html_encola_no_reconocidos(equipo, admin_cookie):
    """Mismo Canal C (#1203) que upload-html-source: un label sin match
    termina en la cola de aprendizaje, atribuido a este equipo."""
    from services.specs import listar_no_reconocidos_agrupados
    from database import get_db

    html = (_FIXTURES / "camara_minimal.html").read_text(encoding="utf-8")
    c = _client()
    r = c.post(
        f"/api/admin/equipos/{equipo}/enriquecer-from-html",
        json={"html": html},
        cookies=admin_cookie,
    )
    assert r.status_code == 200, r.text
    unmatched_labels = {p["label"] for p in r.json().get("unmatched", [])}
    assert unmatched_labels, "este fixture siempre tuvo un label sin match (ver diagnose)"

    with get_db() as conn:
        grupos = listar_no_reconocidos_agrupados(conn)
    grupos_de_este_equipo = [g for g in grupos if equipo in (g.get("equipo_ids") or [])]
    assert grupos_de_este_equipo, "el unmatched de enriquecer-from-html debería encolarse igual que upload-html-source"


def test_enriquecer_from_html_404_si_equipo_no_existe(admin_cookie):
    c = _client()
    r = c.post(
        "/api/admin/equipos/999999999/enriquecer-from-html",
        json={"html": "<html></html>"},
        cookies=admin_cookie,
    )
    assert r.status_code == 404


def test_enriquecer_from_html_400_si_html_vacio(equipo, admin_cookie):
    c = _client()
    r = c.post(
        f"/api/admin/equipos/{equipo}/enriquecer-from-html",
        json={"html": "   "},
        cookies=admin_cookie,
    )
    assert r.status_code == 400


# ── fotos/from-urls (batch) ───────────────────────────────────────────────


def test_fotos_from_urls_es_best_effort(equipo, admin_cookie, monkeypatch):
    """Una URL que falla no aborta el batch — se reporta en `fallidas`
    (mismo criterio que /admin/equipos/buscar-fotos). Monkeypatcheamos el
    paso de red/R2 (`_agregar_foto_desde_url`): lo que este test prueba es
    la resiliencia del LOOP del batch, no la descarga en sí."""
    import routes.equipos.fotos as fotos_mod
    from fastapi import HTTPException

    llamadas: list[str] = []

    def _fake(conn, equipo_id, url, cfg_pub):
        llamadas.append(url)
        if "malo" in url:
            raise HTTPException(400, "no es una imagen")
        return {"id": len(llamadas), "url": url, "path": None, "media_id": None,
                 "orden": 0, "es_principal": False, "created_at": None}

    monkeypatch.setattr(fotos_mod, "_agregar_foto_desde_url", _fake)

    c = _client()
    r = c.post(
        f"/api/admin/equipos/{equipo}/fotos/from-urls",
        json={"urls": ["https://x.test/a.jpg", "https://x.test/malo.jpg", "https://x.test/b.jpg"]},
        cookies=admin_cookie,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["agregadas"]) == 2
    assert len(body["fallidas"]) == 1
    assert body["fallidas"][0]["url"] == "https://x.test/malo.jpg"
    assert llamadas == [
        "https://x.test/a.jpg", "https://x.test/malo.jpg", "https://x.test/b.jpg"
    ], "las 3 URLs se intentan — una que falla no corta el batch"


def test_fotos_from_urls_maximo_20(equipo, admin_cookie):
    c = _client()
    r = c.post(
        f"/api/admin/equipos/{equipo}/fotos/from-urls",
        json={"urls": [f"https://x.test/{i}.jpg" for i in range(21)]},
        cookies=admin_cookie,
    )
    assert r.status_code == 400


def test_fotos_from_urls_404_si_equipo_no_existe(admin_cookie):
    c = _client()
    r = c.post(
        "/api/admin/equipos/999999999/fotos/from-urls",
        json={"urls": ["https://x.test/a.jpg"]},
        cookies=admin_cookie,
    )
    assert r.status_code == 404
