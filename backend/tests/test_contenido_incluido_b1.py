"""B1 #635: contenido_incluido_json en equipo_fichas.

Verifica:
- FichaUpdate acepta el campo y lo serializa bien.
- FichaUpdate valida nombre no vacío, cantidad en rango y máx ítems.
- attach_ficha incluye contenido_incluido_json en el resultado.
"""
import json
import pytest

pytestmark = pytest.mark.unit


# ── FichaUpdate ──────────────────────────────────────────────────────────────

def test_ficha_update_acepta_contenido_incluido():
    from routes.equipos import FichaUpdate

    items = [
        {"nombre": "Cuerpo", "cantidad": 1, "foto_url": None},
        {"nombre": "Cargador", "cantidad": 2, "foto_url": "https://r2.example.com/foto.webp"},
    ]
    data = FichaUpdate(contenido_incluido_json=json.dumps(items))
    patch = data.model_dump(exclude_unset=True)
    assert "contenido_incluido_json" in patch
    parsed = json.loads(patch["contenido_incluido_json"])
    assert len(parsed) == 2
    assert parsed[0]["nombre"] == "Cuerpo"
    assert parsed[1]["cantidad"] == 2


def test_ficha_update_exclude_unset_no_incluye_cuando_no_se_manda():
    from routes.equipos import FichaUpdate

    data = FichaUpdate(descripcion="Solo esto")
    patch = data.model_dump(exclude_unset=True)
    assert "contenido_incluido_json" not in patch
    assert patch == {"descripcion": "Solo esto"}


def test_ficha_update_permite_lista_vacia():
    from routes.equipos import FichaUpdate

    data = FichaUpdate(contenido_incluido_json=json.dumps([]))
    patch = data.model_dump(exclude_unset=True)
    assert patch["contenido_incluido_json"] == "[]"


# ── Validación server-side ───────────────────────────────────────────────────

def test_ficha_update_rechaza_nombre_vacio():
    from pydantic import ValidationError
    from routes.equipos import FichaUpdate

    with pytest.raises(ValidationError, match="nombre"):
        FichaUpdate(contenido_incluido_json=json.dumps([{"nombre": "", "cantidad": 1}]))


def test_ficha_update_rechaza_nombre_solo_espacios():
    from pydantic import ValidationError
    from routes.equipos import FichaUpdate

    with pytest.raises(ValidationError, match="nombre"):
        FichaUpdate(contenido_incluido_json=json.dumps([{"nombre": "   ", "cantidad": 1}]))


def test_ficha_update_rechaza_cantidad_cero():
    from pydantic import ValidationError
    from routes.equipos import FichaUpdate

    with pytest.raises(ValidationError, match="cantidad"):
        FichaUpdate(contenido_incluido_json=json.dumps([{"nombre": "Cable", "cantidad": 0}]))


def test_ficha_update_rechaza_cantidad_fuera_de_rango():
    from pydantic import ValidationError
    from routes.equipos import FichaUpdate

    with pytest.raises(ValidationError, match="cantidad"):
        FichaUpdate(contenido_incluido_json=json.dumps([{"nombre": "Cable", "cantidad": 1000}]))


def test_ficha_update_rechaza_json_invalido():
    from pydantic import ValidationError
    from routes.equipos import FichaUpdate

    with pytest.raises(ValidationError):
        FichaUpdate(contenido_incluido_json="no es json")


def test_ficha_update_rechaza_mas_de_100_items():
    from pydantic import ValidationError
    from routes.equipos import FichaUpdate

    items = [{"nombre": f"Item {i}", "cantidad": 1} for i in range(101)]
    with pytest.raises(ValidationError, match="100"):
        FichaUpdate(contenido_incluido_json=json.dumps(items))


def test_ficha_update_acepta_exactamente_100_items():
    from routes.equipos import FichaUpdate

    items = [{"nombre": f"Item {i}", "cantidad": 1} for i in range(100)]
    data = FichaUpdate(contenido_incluido_json=json.dumps(items))
    assert data.contenido_incluido_json is not None


# ── attach_ficha ─────────────────────────────────────────────────────────────

class _FakeRow(dict):
    """dict que se comporta como psycopg2 RealDictRow."""
    def __getitem__(self, key):
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params):
        pass

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


def _make_ficha_row(equipo_id: int, contenido_incluido_json=None):
    return _FakeRow({
        "equipo_id": equipo_id,
        "descripcion": None,
        "notas": None,
        "keywords_json": None,
        "nombre_publico_template": None,
        "incluye_json": None,
        "conectividad_json": None,
        "compatible_con_json": None,
        "video_url": None,
        "precio_bh_usd": None,
        "fuente_url": None,
        "fuente_titulo": None,
        "enriquecido_at": None,
        "enriquecido_fuente": None,
        "contenido_incluido_json": contenido_incluido_json,
    })


def test_attach_ficha_incluye_contenido_incluido():
    from database import attach_ficha

    items = [{"nombre": "Reflector", "cantidad": 1, "foto_url": None}]
    row = _make_ficha_row(1, json.dumps(items))
    conn = _FakeConn([row])
    equipos = [{"id": 1}]
    result = attach_ficha(conn, equipos)
    ficha = result[0]["ficha"]
    assert "contenido_incluido_json" in ficha
    assert json.loads(ficha["contenido_incluido_json"]) == items


def test_attach_ficha_contenido_incluido_null_cuando_no_hay_ficha():
    from database import attach_ficha

    conn = _FakeConn([])  # sin ficha en BD
    equipos = [{"id": 99}]
    result = attach_ficha(conn, equipos)
    ficha = result[0]["ficha"]
    assert ficha["contenido_incluido_json"] is None


def test_attach_ficha_multiples_equipos():
    from database import attach_ficha

    items_a = [{"nombre": "Cable HDMI", "cantidad": 2, "foto_url": None}]
    items_b = []
    rows = [
        _make_ficha_row(1, json.dumps(items_a)),
        _make_ficha_row(2, json.dumps(items_b)),
    ]
    conn = _FakeConn(rows)
    equipos = [{"id": 1}, {"id": 2}]
    result = attach_ficha(conn, equipos)
    assert json.loads(result[0]["ficha"]["contenido_incluido_json"]) == items_a
    assert json.loads(result[1]["ficha"]["contenido_incluido_json"]) == items_b
