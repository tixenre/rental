"""Regresión del CSP Report-Only (#996).

El CSP arranca en **Report-Only** a propósito: reporta violaciones a /csp-report
sin bloquear, para mapear las fuentes reales de prod antes de pasar a enforcing.
El header solo se agrega al HTML del SPA (que se sirve en prod/staging, no en el
entorno de test sin build) → acá se cubren la constante, el endpoint público y la
selectividad (no va en respuestas JSON). El header-en-HTML se verifica en staging.
"""

import pytest
from fastapi.testclient import TestClient

import main

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False, follow_redirects=False)


class TestCSPReportOnly:
    def test_constante_tiene_directivas_y_fuentes_relevadas(self):
        csp = main.CSP_REPORT_ONLY
        assert "default-src 'self'" in csp
        assert "report-uri /csp-report" in csp
        # fuentes relevadas del código (si alguna se saca, el CSP las bloquearía al enforcing)
        assert "www.googletagmanager.com" in csp  # GA4
        assert "fonts.gstatic.com" in csp  # Google Fonts
        assert "*.r2.dev" in csp  # imágenes R2
        assert "www.youtube.com" in csp  # embeds de video
        assert "maps.google.com" in csp  # embed del mapa
        # sumadas tras la auditoría de seguridad (2026-07-08), confirmadas contra
        # los reportes reales acumulados en prod — sin esto, enforcing rompería
        # analytics, error tracking y el beacon de Cloudflare en silencio
        assert "analytics.google.com" in csp  # GA4 usa este dominio, no solo google-analytics.com
        assert "stats.g.doubleclick.net" in csp  # GA4 (conversiones/audiencias)
        assert "ingest.us.sentry.io" in csp  # Sentry — error tracking del panel admin
        assert "static.cloudflareinsights.com" in csp  # beacon de Cloudflare
        # los style={} de React + el <style> de Google Fonts exigen unsafe-inline
        assert "style-src 'self' 'unsafe-inline'" in csp

    def test_csp_report_endpoint_es_publico_y_204(self):
        # El browser POSTea las violaciones sin sesión → 204, nunca 401
        res = client.post(
            "/csp-report",
            content=b'{"csp-report":{"violated-directive":"img-src"}}',
            headers={"content-type": "application/csp-report"},
        )
        assert res.status_code == 204

    def test_csp_no_va_en_respuestas_json(self):
        # El CSP solo aplica al HTML del SPA, no a /api ni /health (JSON no ejecuta nada)
        res = client.get("/health")
        headers_lower = {k.lower() for k in res.headers.keys()}
        assert "content-security-policy-report-only" not in headers_lower
        # y nunca el enforcing mientras estemos en Report-Only
        assert "content-security-policy" not in headers_lower
