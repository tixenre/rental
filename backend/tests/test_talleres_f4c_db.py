"""Escuela v2 F4c — candados contra Postgres REAL: cierre de inscripciones
por fecha, trabajos pasados (YouTube), FAQ del concepto.

OPT-IN y seguro por defecto (RESERVAS_DB_TEST=1 + DATABASE_URL a una base de
prueba). Ids altos + limpieza antes/después.
"""

import os
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
        not _OPT_IN,
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

TALLER_ID = 9_860_001
SLUG = "test-f4c-cierre-trabajos-faq-zzq"


def _limpiar(conn):
    conn.execute(
        "DELETE FROM taller_inscripciones WHERE taller_id = %s", (TALLER_ID,)
    )
    conn.execute("DELETE FROM taller_trabajos WHERE taller_id = %s", (TALLER_ID,))
    conn.execute("DELETE FROM ediciones_taller WHERE taller_id = %s", (TALLER_ID,))
    conn.execute("DELETE FROM talleres WHERE id = %s", (TALLER_ID,))
    conn.execute("DELETE FROM media_assets WHERE original_key = 'test-f4c-fake-poster'")


@pytest.fixture
def taller_base(monkeypatch):
    import routes.talleres as t
    from database import get_db, init_db

    monkeypatch.setattr(t, "require_admin", lambda r: None)
    monkeypatch.setattr(t, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(t, "get_admin_to", lambda: "admin@example.com")

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO talleres (id, slug, slug_base, nombre, instructor_nombre, "
            "fecha_inicio, fecha_fin) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (TALLER_ID, SLUG, SLUG, "Taller F4c", "Instructor F4c", "2099-01-01", "2099-01-02"),
        )
        conn.commit()
    finally:
        conn.close()

    yield t

    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


def _crear_edicion_activa(t, cupos_total=5):
    from database import get_db

    body = t.EdicionCreateBody(
        clases=[t.ClaseBody(fecha="2099-03-06", hora_inicio_min=510, hora_fin_min=750)],
        numero_edicion=1,
        activo=False,
    )
    d = t.admin_create_edicion(TALLER_ID, body, None)
    ed = d["ediciones"][0] if "ediciones" in d else d
    with get_db() as conn:
        conn.execute(
            "UPDATE ediciones_taller SET activo = TRUE, cupos_total = %s WHERE id = %s",
            (cupos_total, ed["id"]),
        )
        conn.commit()
    return ed


class _FakeVariant:
    def __init__(self, url):
        self.url = url


class _FakeAsset:
    def __init__(self, asset_id, url):
        self.id = asset_id
        self.variants = [_FakeVariant(url)]

    def variant(self, name):
        return self.variants[0] if name == "display" else None


def _fake_poster(t, monkeypatch):
    from database import get_db

    with get_db() as conn:
        row = conn.execute(
            "INSERT INTO media_assets (kind, original_key) VALUES ('taller', 'test-f4c-fake-poster') "
            "RETURNING id"
        ).fetchone()
        conn.commit()
    fake_id = row["id"]
    monkeypatch.setattr(
        t, "store_youtube_poster",
        lambda vid, *, kind, conn: _FakeAsset(fake_id, "https://cdn.example.com/trabajo-poster.webp"),
    )


def test_fecha_cierre_inscripcion_bloquea_pasada(taller_base):
    from fastapi.testclient import TestClient
    from database import get_db
    import main
    t = taller_base

    ed = _crear_edicion_activa(t)
    with get_db() as conn:
        conn.execute(
            "UPDATE ediciones_taller SET fecha_cierre_inscripcion = '2020-01-01' WHERE id = %s",
            (ed["id"],),
        )
        conn.commit()

    client = TestClient(main.app)
    r = client.post(f"/api/talleres/{ed['slug']}/inscripcion", json={
        "nombre": "Tarde", "email": "tarde@example.com", "telefono": "2235550000",
    })
    assert r.status_code == 400, r.text


def test_fecha_cierre_inscripcion_permite_antes_de_cerrar(taller_base):
    from fastapi.testclient import TestClient
    from database import get_db
    import main
    t = taller_base

    ed = _crear_edicion_activa(t)
    with get_db() as conn:
        conn.execute(
            "UPDATE ediciones_taller SET fecha_cierre_inscripcion = '2099-12-31' WHERE id = %s",
            (ed["id"],),
        )
        conn.commit()

    client = TestClient(main.app)
    r = client.post(f"/api/talleres/{ed['slug']}/inscripcion", json={
        "nombre": "A tiempo", "email": "atiempo@example.com", "telefono": "2235550001",
    })
    assert r.status_code == 200, r.text


def test_fecha_cierre_null_nunca_bloquea(taller_base):
    from fastapi.testclient import TestClient
    import main
    t = taller_base

    ed = _crear_edicion_activa(t)  # sin fecha_cierre_inscripcion (default NULL)
    client = TestClient(main.app)
    r = client.post(f"/api/talleres/{ed['slug']}/inscripcion", json={
        "nombre": "Sin cierre", "email": "sincierre@example.com", "telefono": "2235550002",
    })
    assert r.status_code == 200, r.text


def test_admin_update_edicion_fecha_cierre_invalida_400(taller_base):
    t = taller_base
    ed = _crear_edicion_activa(t)
    with pytest.raises(t.HTTPException) as exc:
        t.admin_update_edicion(
            ed["id"], t.EdicionUpdateBody(fecha_cierre_inscripcion="no-es-una-fecha"), None
        )
    assert exc.value.status_code == 400


def test_admin_update_edicion_fecha_cierre_setea_y_borra(taller_base):
    from database import get_db
    t = taller_base
    ed = _crear_edicion_activa(t)

    d1 = t.admin_update_edicion(
        ed["id"], t.EdicionUpdateBody(fecha_cierre_inscripcion="2099-06-01"), None
    )
    assert d1["fecha_cierre_inscripcion"] == "2099-06-01"

    d2 = t.admin_update_edicion(
        ed["id"], t.EdicionUpdateBody(fecha_cierre_inscripcion=""), None
    )
    assert d2["fecha_cierre_inscripcion"] is None

    with get_db() as conn:
        row = conn.execute(
            "SELECT fecha_cierre_inscripcion FROM ediciones_taller WHERE id = %s", (ed["id"],)
        ).fetchone()
    assert row["fecha_cierre_inscripcion"] is None


def test_trabajo_crear_editar_eliminar(taller_base, monkeypatch):
    t = taller_base
    _fake_poster(t, monkeypatch)

    creado = t.admin_crear_trabajo(
        TALLER_ID, t.TrabajoBody(titulo="Videoclip", youtube_url="https://youtu.be/dQw4w9WgXcQ"), None
    )
    assert creado["titulo"] == "Videoclip"
    assert creado["poster_url"] == "https://cdn.example.com/trabajo-poster.webp"
    trabajo_id = creado["id"]

    editado = t.admin_editar_trabajo(trabajo_id, t.TrabajoUpdateBody(titulo="Videoclip (editado)"), None)
    assert editado["titulo"] == "Videoclip (editado)"
    assert editado["youtube_url"] == "https://youtu.be/dQw4w9WgXcQ", "no cambió, no debe tocarse"

    editado2 = t.admin_editar_trabajo(
        trabajo_id, t.TrabajoUpdateBody(youtube_url="https://youtu.be/9bZkp7q19f0"), None
    )
    assert editado2["youtube_url"] == "https://youtu.be/9bZkp7q19f0"

    t.admin_eliminar_trabajo(trabajo_id, None)
    with pytest.raises(t.HTTPException) as exc:
        t.admin_editar_trabajo(trabajo_id, t.TrabajoUpdateBody(titulo="x"), None)
    assert exc.value.status_code == 404


def test_trabajo_youtube_url_invalida_400(taller_base):
    t = taller_base
    with pytest.raises(t.HTTPException) as exc:
        t.admin_crear_trabajo(TALLER_ID, t.TrabajoBody(youtube_url="no-es-youtube"), None)
    assert exc.value.status_code == 400


def test_faqs_guarda_y_filtra_pregunta_vacia(taller_base):
    t = taller_base
    d = t.admin_update_concepto(
        TALLER_ID,
        t.TallerConceptoUpdateBody(faqs=[
            t.FaqItemBody(pregunta="¿Necesito experiencia previa?", respuesta="No, para nada."),
            t.FaqItemBody(pregunta="   ", respuesta="esto se descarta"),
        ]),
        None,
    )
    assert len(d["faqs"]) == 1
    assert d["faqs"][0]["pregunta"] == "¿Necesito experiencia previa?"
