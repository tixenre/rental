"""Canal C (spec_propuestas_pendientes) + el embudo que aprende, contra Postgres REAL (#1176 F7).

`spec_propuestas_pendientes` no tiene FKs (columnas: id/tipo/payload/origen/
confianza/created_at/aplicado_at/descartado_at) — no hace falta ancla de
categoría, alcanza con limpiar por `origen`.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los otros *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre.
"""
import os
from urllib.parse import urlparse

import pytest

from services.specs import (
    aplicar_propuesta,
    descartar_propuesta,
    encolar_propuesta,
    listar_propuestas_pendientes,
)
from services.specs_ingesta.commands.proponer import proponer_desde_unmatched

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

_ORIGEN_TEST = "test_specs_ingesta_proponer_db"


def _limpiar(conn):
    conn.execute("DELETE FROM spec_propuestas_pendientes WHERE origen = %s", (_ORIGEN_TEST,))


@pytest.fixture(autouse=True)
def _cleanup():
    from database import get_db

    with get_db() as conn:
        _limpiar(conn)
        conn.commit()
    yield
    with get_db() as conn:
        _limpiar(conn)
        conn.commit()


class TestCanalC:
    def test_encolar_y_listar(self):
        from database import get_db

        with get_db() as conn:
            pid = encolar_propuesta(
                conn, tipo="spec_nueva", payload={"label": "Test"}, origen=_ORIGEN_TEST, confianza=0.7
            )
            conn.commit()
            pendientes = listar_propuestas_pendientes(conn)
        propuesta = next(p for p in pendientes if p["id"] == pid)
        assert propuesta["tipo"] == "spec_nueva"
        assert propuesta["payload"] == {"label": "Test"}, "payload debe auto-decodificar de JSONB a dict"
        assert propuesta["confianza"] == pytest.approx(0.7)

    def test_aplicar_saca_de_pendientes(self):
        from database import get_db

        with get_db() as conn:
            pid = encolar_propuesta(conn, tipo="spec_nueva", payload={}, origen=_ORIGEN_TEST)
            conn.commit()
            aplicar_propuesta(conn, pid)
            conn.commit()
            pendientes = listar_propuestas_pendientes(conn)
        assert pid not in {p["id"] for p in pendientes}

    def test_descartar_saca_de_pendientes(self):
        from database import get_db

        with get_db() as conn:
            pid = encolar_propuesta(conn, tipo="spec_nueva", payload={}, origen=_ORIGEN_TEST)
            conn.commit()
            descartar_propuesta(conn, pid)
            conn.commit()
            pendientes = listar_propuestas_pendientes(conn)
        assert pid not in {p["id"] for p in pendientes}

    def test_tipo_invalido_rechazado_por_check_constraint(self):
        from database import get_db

        with get_db() as conn:
            with pytest.raises(Exception):
                encolar_propuesta(conn, tipo="tipo_que_no_existe", payload={}, origen=_ORIGEN_TEST)
            conn.rollback()


class TestProponerDesdeUnmatched:
    def _unmatched_realista(self):
        """Espeja el caso real medido contra el dataset de Modificadores_Luz:
        'interior color' aparece en 3 HTMLs distintos (cruza el umbral default
        de 3), 'material of construction' en solo 2 (no lo cruza)."""
        return [
            [{"label": "Interior Color", "value": "White"}],
            [{"label": "Interior Color", "value": "Silver"}],
            [{"label": "Interior Color", "value": "White"},
             {"label": "Material of Construction", "value": "Nylon"}],
            [{"label": "Material of Construction", "value": "Nylon"}],
        ]

    def test_propone_solo_lo_que_cruza_el_umbral(self):
        from database import get_db

        with get_db() as conn:
            ids = proponer_desde_unmatched(
                conn, "Modificadores", self._unmatched_realista(), origen=_ORIGEN_TEST
            )
            conn.commit()
            pendientes = [p for p in listar_propuestas_pendientes(conn) if p["origen"] == _ORIGEN_TEST]

        assert len(ids) == 1
        payloads = {p["payload"]["label_normalizado"]: p["payload"] for p in pendientes}
        assert "interior color" in payloads
        assert payloads["interior color"]["count"] == 3
        assert "material of construction" not in payloads, "2 HTMLs, bajo el umbral de 3 — no debe proponerse"

    def test_mismo_label_repetido_en_un_html_cuenta_una_vez(self):
        """Una tabla con el label duplicado en el MISMO HTML no infla el count."""
        from database import get_db

        unmatched_por_html = [
            [{"label": "Interior Color", "value": "White"}, {"label": "Interior Color", "value": "White (dup)"}],
            [{"label": "Interior Color", "value": "Silver"}],
            [{"label": "Interior Color", "value": "Black"}],
        ]
        with get_db() as conn:
            ids = proponer_desde_unmatched(conn, "Modificadores", unmatched_por_html, origen=_ORIGEN_TEST)
            conn.commit()
            pendientes = [p for p in listar_propuestas_pendientes(conn) if p["origen"] == _ORIGEN_TEST]

        assert len(ids) == 1
        assert pendientes[0]["payload"]["count"] == 3, "3 HTMLs distintos, no 4 pares"

    def test_no_duplica_en_una_segunda_corrida(self):
        from database import get_db

        with get_db() as conn:
            ids1 = proponer_desde_unmatched(
                conn, "Modificadores", self._unmatched_realista(), origen=_ORIGEN_TEST
            )
            conn.commit()
            ids2 = proponer_desde_unmatched(
                conn, "Modificadores", self._unmatched_realista(), origen=_ORIGEN_TEST
            )
            conn.commit()

        assert len(ids1) == 1
        assert ids2 == [], "correr 2 veces sobre el mismo dataset no debe re-proponer lo ya pendiente"
