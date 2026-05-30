"""Tests del contexto de mails de pedido + la guarda de la migración de copy.

- `_pedido_email_context()` arma URLs **absolutas** (portal_url + admin_url): en un
  cliente de mail un link relativo no resuelve.
- `numero_pedido` cae al `id` cuando falta (filas legacy).
- La migración `e7c3a9f5d1b8` (copy nuevo) sólo pisa el template si sigue idéntico
  al default original sembrado en `a4e8c2b9d710` → sus constantes `_*_OLD_*` deben
  coincidir EXACTAMENTE con ese seed, o la guarda haría un no-op silencioso (y la
  garantía de "no pisar ediciones del admin" sería falsa).
"""
import datetime
import importlib.util
from pathlib import Path

import pytest

from routes.alquileres import _pedido_email_context
from config import SITE_URL

pytestmark = pytest.mark.unit

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"


def _load_migration(filename: str):
    path = VERSIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── formato lindo del contexto ──────────────────────────────────────────────

class TestContextoFormato:
    def test_total_formateado_ars(self):
        ctx = _pedido_email_context({"id": 1, "monto_total": 12500, "items": []})
        assert ctx["total"] == "$ 12.500"

    def test_fecha_amable(self):
        ctx = _pedido_email_context(
            {"id": 1, "fecha_desde": datetime.datetime(2026, 6, 15, 10, 0), "items": []}
        )
        assert ctx["fecha_desde"] == "15 jun · 10:00"

    def test_items_html_es_tabla_con_nombre_escapado(self):
        # Nombre con HTML malicioso → debe quedar escapado (XSS-safe) aunque el
        # blob se inyecte con |safe en la plantilla.
        ctx = _pedido_email_context(
            {
                "id": 1,
                "items": [{"nombre": "<b>Cam</b>", "cantidad": 2, "subtotal": 9000}],
            }
        )
        html = ctx["items_html"]
        assert "<table" in html
        assert "&lt;b&gt;Cam&lt;/b&gt;" in html
        assert "<b>Cam</b>" not in html
        assert "× 2" in html
        assert "$ 9.000" in html

    def test_items_vacio_no_rompe(self):
        ctx = _pedido_email_context({"id": 1, "items": []})
        assert ctx["items_html"] == ""
        assert ctx["items_text"] == ""


# ── _pedido_email_context ───────────────────────────────────────────────────

class TestPedidoEmailContext:
    def test_urls_absolutas(self):
        ctx = _pedido_email_context({"id": 123, "numero_pedido": 1023, "items": []})
        assert ctx["portal_url"] == f"{SITE_URL}/cliente/portal"
        assert ctx["admin_url"] == f"{SITE_URL}/admin/pedidos/123"
        # Ambas tienen que ser absolutas para funcionar dentro de un mail.
        assert ctx["portal_url"].startswith("http")
        assert ctx["admin_url"].startswith("http")

    def test_numero_pedido_usa_el_valor_propio(self):
        ctx = _pedido_email_context({"id": 7, "numero_pedido": 1023, "items": []})
        assert ctx["numero_pedido"] == 1023

    def test_numero_pedido_cae_al_id_si_falta(self):
        ctx = _pedido_email_context({"id": 7, "items": []})
        assert ctx["numero_pedido"] == 7


# ── Guarda de la migración de copy ──────────────────────────────────────────

class TestMigracionCopyGuard:
    def test_old_constants_coinciden_con_el_seed_original(self):
        infra = _load_migration("a4e8c2b9d710_email_infra.py")
        copy = _load_migration("e7c3a9f5d1b8_email_copy_portal_link.py")

        # _DEFAULTS: lista de (key, subject, body_html, body_text)
        seed = {row[0]: (row[1], row[2], row[3]) for row in infra._DEFAULTS}

        creado_subj, creado_html, creado_text = seed["pedido_creado_cliente"]
        assert copy._CREADO_OLD_SUBJECT == creado_subj
        assert copy._CREADO_OLD_HTML == creado_html
        assert copy._CREADO_OLD_TEXT == creado_text

        conf_subj, conf_html, conf_text = seed["pedido_confirmado_cliente"]
        assert copy._CONFIRMADO_SUBJECT == conf_subj
        assert copy._CONFIRMADO_OLD_HTML == conf_html
        assert copy._CONFIRMADO_OLD_TEXT == conf_text

    def test_copy_nuevo_referencia_el_portal(self):
        copy = _load_migration("e7c3a9f5d1b8_email_copy_portal_link.py")
        # El copy nuevo al cliente debe incluir el link al portal.
        assert "{{ portal_url }}" in copy._CREADO_NEW_HTML
        assert "{{ portal_url }}" in copy._CREADO_NEW_TEXT
        assert "{{ portal_url }}" in copy._CONFIRMADO_NEW_HTML
        assert "{{ portal_url }}" in copy._CONFIRMADO_NEW_TEXT
