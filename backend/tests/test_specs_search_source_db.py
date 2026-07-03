"""Búsqueda derivada de specs contra Postgres REAL (#1163 Fase 4).

Verifica, a través del MISMO camino que usa la ruta HTTP real
(busqueda.construir + services.catalogo.proyectar_lista — las dos funciones
que routes/equipos/core.py::list_equipos llama):
1. Buscar por el VALUE de una spec (ej. "FF") encuentra el equipo, aunque
   "FF" no esté en su nombre/ficha — vía spec_value_aliases.
2. Buscar por el LABEL de una spec (ej. "Formato") también lo encuentra.
3. Una búsqueda sin match no trae nada (ni rompe).
4. Un equipo sin specs no rompe la query (NULL-safe).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los otros *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre. Ids altos
(categoría ancla) + limpieza vía CASCADE.
"""
import os
from urllib.parse import urlparse

import pytest

from busqueda import construir
from services.catalogo import proyectar_lista
from services.specs.commands.persist import persistir_specs
from services.specs.commands.seed import _sync_value_aliases, _upsert_spec_definition
from services.specs.registry.models import SpecDef

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

C_ANCLA = 9_400_401
EQ_CON_FF, EQ_SIN_SPECS = 9_400_501, 9_400_502


def _limpiar(conn):
    conn.execute("DELETE FROM equipos WHERE id IN (%s, %s)", (EQ_CON_FF, EQ_SIN_SPECS))
    conn.execute("DELETE FROM categorias WHERE id = %s", (C_ANCLA,))


@pytest.fixture
def dataset():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO categorias (id, nombre) VALUES (%s, %s)", (C_ANCLA, "ZZ-SearchTest-test"))
        # Spec sintético (no depende de que 'Cámaras' exista con ese nombre
        # exacto en esta DB — mismo patrón que test_specs_value_aliases_db.py).
        spec = SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=["Full-frame", "Super 35"],
            aliases=["Sensor Type"],
            value_aliases={"Full-frame": ["FF"]},
        )
        formato_sid = _upsert_spec_definition(conn, spec, C_ANCLA, dry_run=False)
        _sync_value_aliases(conn, formato_sid, spec, dry_run=False)
        sd = conn.execute(
            "SELECT id, label, tipo, enum_options, unidad FROM spec_definitions WHERE id = %s",
            (formato_sid,),
        ).fetchone()

        conn.execute(
            "INSERT INTO equipos (id, nombre, visible_catalogo, cantidad) VALUES (%s, %s, 1, 1), (%s, %s, 1, 1)",
            (EQ_CON_FF, "ZZ-SonyA7-search-test", EQ_SIN_SPECS, "ZZ-SinSpecs-search-test"),
        )
        persistir_specs(conn, EQ_CON_FF, {str(formato_sid): "FF"}, {formato_sid: dict(sd)})
        conn.commit()
    finally:
        conn.close()
    yield
    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


def _buscar(conn, campos_equipo, q):
    pred = construir(campos_equipo, q)
    base_sql = f"FROM equipos e WHERE e.id IN ({EQ_CON_FF}, {EQ_SIN_SPECS})"
    params = []
    if pred.activo:
        base_sql += f" AND ({pred.where})"
        params = pred.where_params
    result = proyectar_lista(conn, filtro_sql=base_sql, filtro_params=params, pred=pred, is_admin=True)
    return [it["nombre"] for it in result["items"]]


class TestBusquedaDerivadaDeSpecs:
    def test_busca_por_alias_de_valor(self, dataset):
        from database import get_db
        from routes.equipos.core import CAMPOS_EQUIPO

        with get_db() as conn:
            nombres = _buscar(conn, CAMPOS_EQUIPO, "FF")
        assert "ZZ-SonyA7-search-test" in nombres
        assert "ZZ-SinSpecs-search-test" not in nombres

    def test_busca_por_label_del_spec(self, dataset):
        from database import get_db
        from routes.equipos.core import CAMPOS_EQUIPO

        with get_db() as conn:
            nombres = _buscar(conn, CAMPOS_EQUIPO, "formato")
        assert "ZZ-SonyA7-search-test" in nombres

    def test_sin_match_no_trae_nada(self, dataset):
        from database import get_db
        from routes.equipos.core import CAMPOS_EQUIPO

        with get_db() as conn:
            nombres = _buscar(conn, CAMPOS_EQUIPO, "zzzterminoinexistente")
        assert nombres == []

    def test_equipo_sin_specs_no_rompe(self, dataset):
        """El equipo sin specs no debe aparecer buscando 'FF', y la query
        entera no debe explotar por su valor NULL de specs_search_expr."""
        from database import get_db
        from routes.equipos.core import CAMPOS_EQUIPO

        with get_db() as conn:
            nombres = _buscar(conn, CAMPOS_EQUIPO, "SinSpecs")
        assert "ZZ-SinSpecs-search-test" in nombres
