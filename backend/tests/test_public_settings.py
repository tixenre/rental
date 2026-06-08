"""Regresión del fix de lecturas públicas del catálogo.

Bug: el `auth_middleware` bloqueaba con 401 a visitantes anónimos en endpoints
**públicos por diseño** (`/api/settings/{key}`, `/api/settings`, `/api/marcas`,
`/api/analytics-config`) → el catálogo público no leía las settings que el dueño
administra (logo, taglines, FAQ, contacto, horarios, `usd_rate` del precio) ni
la lista de marcas; todo caía silenciosamente al default bundleado.

Estos tests fijan los dos invariantes del fix:
  1. esos GET quedan exentos del guard de sesión (son públicos);
  2. el subconjunto público de settings NO filtra keys sensibles
     (email_admin_to, comisiones, recordatorios, márgenes internos).
Así una refactorización futura no vuelve a romper el catálogo ni sobre-expone.
"""
import pytest

from middleware import PUBLIC_API_READONLY, PUBLIC_API_ANY
from routes.settings import PUBLIC_SETTINGS_KEYS, ALLOWED_SETTINGS_KEYS

pytestmark = pytest.mark.unit


def _is_public_readonly(path: str) -> bool:
    """Replica la clasificación de `auth_middleware` para GET/HEAD."""
    return any(path.startswith(p) for p in PUBLIC_API_READONLY)


class TestEndpointsPublicosDeLectura:
    @pytest.mark.parametrize("path", [
        "/api/settings",                 # lista (filtrada por sesión en el handler)
        "/api/settings/usd_rate",        # key puntual pública
        "/api/settings/favicon_url",
        "/api/marcas",                   # marcas del catálogo
        "/api/analytics-config",         # GA4 id (no secreto, gateado por entorno)
    ])
    def test_get_es_publico(self, path):
        assert _is_public_readonly(path), f"{path} debería ser GET público (catálogo anónimo)"

    def test_escritura_de_equipos_no_es_publica(self):
        # Sanity: el fix no abre escrituras. /api/equipos sigue siendo readonly-público
        # solo para GET; no está en PUBLIC_API_ANY (que sí acepta POST).
        assert not any("/api/equipos".startswith(p) for p in PUBLIC_API_ANY)


class TestSubconjuntoPublicoDeSettings:
    def test_publicas_son_subconjunto_de_allowed(self):
        assert PUBLIC_SETTINGS_KEYS <= ALLOWED_SETTINGS_KEYS

    @pytest.mark.parametrize("key", [
        "email_from", "email_admin_to",      # direcciones internas
        "comisiones_modelo",                  # reparto de plata
        "recordatorios_enabled", "recordatorios_hora", "recordatorios_dias_antes",
        "roi_pct_default", "shipping_usd",    # márgenes/costos internos
        "ga4_measurement_id",                 # se sirve por /analytics-config, no por key
    ])
    def test_keys_sensibles_no_son_publicas(self, key):
        assert key not in PUBLIC_SETTINGS_KEYS, f"{key} NO debe ser leída sin sesión"

    @pytest.mark.parametrize("key", [
        "usd_rate", "horarios_retiro", "faq_json", "hero_taglines",
        "favicon_url", "wordmark_svg", "business_email", "whatsapp_phone",
    ])
    def test_keys_del_catalogo_son_publicas(self, key):
        assert key in PUBLIC_SETTINGS_KEYS, f"{key} la necesita el catálogo público"
