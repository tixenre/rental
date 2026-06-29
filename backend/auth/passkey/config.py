"""Configuración WebAuthn derivada por ambiente — fuente única del `rp_id` / origins.

El **`rp_id`** (Relying Party ID) ata las passkeys a un dominio: si cambia, se
**invalidan todas** las credenciales registradas. Por eso se deriva de forma
estable de `settings.SITE_URL` (prod/staging) o cae a `"localhost"` en dev local.
Se puede forzar con `WEBAUTHN_RP_ID` (útil para fijar el apex antes de promover
a prod).

El set de `expected_origin` reusa `settings.frontend_origins` (el mismo set que
usa CORS) — así no se declara dos veces. En prod el SPA se sirve same-origin que
la API, así que `SITE_URL` también entra.
"""
import os
from urllib.parse import urlparse

from config import settings

RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "Rambla Rental").strip() or "Rambla Rental"


def rp_id() -> str:
    """Dominio del Relying Party. Override por `WEBAUTHN_RP_ID`; si no, derivado:
    apex de `SITE_URL` en Railway, `localhost` en dev local."""
    explicit = os.getenv("WEBAUTHN_RP_ID", "").strip()
    if explicit:
        return explicit
    if not settings.is_railway:
        return "localhost"
    host = urlparse(settings.SITE_URL).hostname or "localhost"
    # Apex cubre apex + www (una passkey de www.x sirve también para x).
    if host.startswith("www."):
        host = host[4:]
    return host


def expected_origins() -> list[str]:
    """Orígenes que el browser puede reportar en la assertion. Reusa
    `FRONTEND_ORIGINS` (mismo set que CORS) + `SITE_URL` (same-origin en prod)."""
    origins = list(settings.frontend_origins)
    site = settings.SITE_URL
    if site and site not in origins:
        origins.append(site)
    return origins
