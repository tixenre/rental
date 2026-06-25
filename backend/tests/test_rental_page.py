"""Tests para el handler GET /rental y los helpers de inyección de datos.

Cubre:
  - `_inject_initial_data` inyecta <script id="__INITIAL__"> antes de </body>
  - `_get_initial_catalog` retorna el shape esperado (equipos + categorias)
  - El handler /rental no rompe cuando no hay frontend construido
"""

import json
import pytest
from fastapi.testclient import TestClient

import main
from main import _inject_initial_data, _get_initial_catalog

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False, follow_redirects=False)


class TestInjectInitialData:
    def test_inyecta_script_antes_de_body(self):
        html = "<html><head></head><body><p>hi</p></body></html>"
        data = {"equipos": {"total": 1, "items": [{"id": 1}]}, "categorias": []}
        result = _inject_initial_data(html, data)

        assert '<script id="__INITIAL__" type="application/json">' in result
        # El script debe ir antes de </body>
        script_pos = result.index('id="__INITIAL__"')
        body_close_pos = result.index("</body>")
        assert script_pos < body_close_pos

    def test_payload_es_json_valido(self):
        html = "<html><body></body></html>"
        data = {"equipos": {"total": 2, "items": [{"id": 1, "nombre": "Cámara"}]}, "categorias": [{"id": 1, "nombre": "Cámaras"}]}
        result = _inject_initial_data(html, data)

        start = result.index('type="application/json">') + len('type="application/json">')
        end = result.index("</script>")
        payload = json.loads(result[start:end])
        assert payload["equipos"]["total"] == 2
        assert payload["categorias"][0]["nombre"] == "Cámaras"

    def test_escapa_cierre_script_en_payload(self):
        # Un valor que contenga </script> no debe romper el parser HTML.
        html = "<html><body></body></html>"
        data = {"x": "</script><script>alert(1)</script>"}
        result = _inject_initial_data(html, data)
        # No debe haber un </script> crudo antes del tag de cierre del __INITIAL__
        assert "</script><script>" not in result


class TestGetInitialCatalog:
    def test_retorna_shape_esperado(self, tmp_path):
        """Verifica el shape sin BD real — usa sqlite en memoria con tablas mínimas."""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        # Tabla mínima: equipos
        conn.execute("""
            CREATE TABLE equipos (
                id INTEGER PRIMARY KEY,
                nombre TEXT,
                nombre_publico TEXT,
                modelo TEXT,
                foto_url TEXT,
                foto_url_sm TEXT,
                foto_url_thumb TEXT,
                foto_url_avif TEXT,
                foto_url_sm_avif TEXT,
                foto_url_thumb_avif TEXT,
                foto_lqip TEXT,
                precio_jornada REAL,
                precio_usd REAL,
                cantidad INTEGER DEFAULT 1,
                estado TEXT DEFAULT 'disponible',
                visible_catalogo INTEGER DEFAULT 1,
                relevancia_manual INTEGER DEFAULT 100,
                popularidad_score REAL DEFAULT 0,
                destacado INTEGER DEFAULT 0,
                tipo TEXT DEFAULT 'simple',
                eliminado_at TEXT,
                es_recurso_interno INTEGER DEFAULT 0,
                brand_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE marcas (id INTEGER PRIMARY KEY, nombre TEXT)
        """)
        conn.execute("""
            CREATE TABLE categorias (
                id INTEGER PRIMARY KEY, nombre TEXT,
                total INTEGER DEFAULT 0, prioridad INTEGER, parent_id INTEGER
            )
        """)
        conn.execute(
            "INSERT INTO equipos (id, nombre, visible_catalogo, estado, precio_jornada) VALUES (1, 'Canon R5', 1, 'disponible', 5000)"
        )
        conn.execute(
            "INSERT INTO categorias (id, nombre, total, prioridad) VALUES (1, 'Cámaras', 1, 1)"
        )
        conn.commit()

        result = _get_initial_catalog(conn)
        conn.close()

        assert "equipos" in result
        assert "categorias" in result
        assert result["equipos"]["total"] == 1
        assert result["equipos"]["items"][0]["nombre"] == "Canon R5"
        assert result["equipos"]["items"][0]["etiquetas"] == []
        assert result["equipos"]["items"][0]["kit"] == []
        assert result["categorias"][0]["nombre"] == "Cámaras"


class TestRentalRoute:
    def test_rental_sin_frontend_no_falla(self):
        # Sin frontend construido, el handler debe caer al spa_fallback o al index plano.
        # Nunca debe lanzar 500.
        res = client.get("/rental")
        assert res.status_code in (200, 503), f"/rental devolvió {res.status_code}"

    def test_rental_no_redirige_a_login(self):
        # Regresión: la ruta pública no debe requerir sesión.
        res = client.get("/rental")
        cayo_a_login = res.status_code in (302, 307) and res.headers.get("location") == "/login"
        assert not cayo_a_login
