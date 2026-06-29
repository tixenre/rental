"""auth/staging.py — login programático de dev/staging (no-prod, fail-closed).

`/auth/dev-login*` (solo con ADMIN_BYPASS_AUTH) y `/auth/staging-login` (doble llave:
no-prod + secreto). Registran sus rutas sobre el `router` compartido de `auth.google`
(patrón `cliente_portal`). Movido verbatim de `routes/auth.py`.
"""
import logging
import os
import secrets

from fastapi import HTTPException, Request
from pydantic import BaseModel

from auth.google import router
from auth.ratelimit import _check_rate, _record_fail
from auth.session import _make_session_response, dev_bypass_enabled
from config import settings
from net_utils import get_client_ip

logger = logging.getLogger(__name__)

# Cuenta de servicio para login programático en STAGING (no en prod). Email
# dedicado y auditable: para que sea admin debe estar en `ADMIN_EMAILS` del
# entorno dev (la admin-ness la sigue resolviendo `is_admin_email`, fuente
# única; este login no la saltea). Override por env si hace falta otro.
STAGING_LOGIN_EMAIL = os.getenv("STAGING_LOGIN_EMAIL", "staging-bot@rambla.local").strip().lower()

# Cliente de servicio para impersonar el PORTAL DEL CLIENTE en staging (target
# "cliente" de `/auth/staging-login`). Se busca por este email salvo que el body
# pase un `cliente_id` puntual. Como staging es copia de prod, también sirve
# impersonar cualquier cliente real existente por id.
STAGING_CLIENTE_EMAIL = os.getenv("STAGING_CLIENTE_EMAIL", "staging-cliente@rambla.local").strip().lower()


def _staging_login_secret() -> str:
    """Secreto compartido para `/auth/staging-login` (env var, solo dev)."""
    return os.getenv("STAGING_LOGIN_SECRET", "").strip()


def staging_login_enabled() -> bool:
    """¿Está disponible el login programático de staging?

    Doble llave, ambas necesarias (defensa en profundidad):
      1. NO es producción — usa `settings.is_production`, que falla hacia "sí es
         prod" ante un nombre de entorno desconocido, así que un ambiente nuevo
         mal nombrado queda con el login APAGADO, no abierto.
      2. Hay un secreto configurado — sin `STAGING_LOGIN_SECRET` el endpoint no
         existe ni siquiera en dev.

    Por qué el secreto es obligatorio: la BD de staging es copia de prod (ver
    MEMORIA / `Settings.is_production`), o sea tiene PII real de clientes. Un
    login abierto en una URL pública de dev sería una fuga. El secreto vive solo
    en el entorno dev de Railway, nunca en el repo, y es rotable.
    """
    if settings.is_production:
        return False
    return bool(_staging_login_secret())


@router.get("/auth/dev-login")
def auth_dev_login():
    """Login directo sin OAuth — solo en dev (ADMIN_BYPASS_AUTH=1, nunca en prod)."""
    if not dev_bypass_enabled():
        raise HTTPException(404, "No encontrado.")
    return _make_session_response(
        email="dev@local",
        name="Dev Admin",
        redirect="/admin",
    )


@router.get("/auth/dev-login-cliente")
def auth_dev_login_cliente():
    """Login de cliente sin OAuth — solo en dev (ADMIN_BYPASS_AUTH=1, nunca en prod).
    Impersona al primer cliente del DB (por STAGING_CLIENTE_EMAIL o el primero que exista)."""
    if not dev_bypass_enabled():
        raise HTTPException(404, "No encontrado.")
    cli = _resolve_staging_cliente(None)
    if cli is None:
        from database import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, email, nombre, apellido FROM clientes ORDER BY id LIMIT 1"
            ).fetchone()
        if row is None:
            raise HTTPException(503, "No hay clientes en la base de datos.")
        cli = {"id": row["id"], "email": row["email"],
               "name": f"{row['nombre']} {row['apellido']}".strip()}
    return _make_session_response(
        email=cli["email"],
        name=cli["name"],
        redirect="/cliente",
        extra={"role": "cliente", "cliente_id": cli["id"]},
    )


def _resolve_staging_cliente(cliente_id: int | None) -> dict | None:
    """Resuelve el cliente a impersonar en staging (target="cliente"). READ-ONLY:
    solo lee `clientes`, nunca muta staging. Por `cliente_id` si se pasa; si no,
    por `STAGING_CLIENTE_EMAIL`. Devuelve `{id, email, name}` o None si no existe."""
    from database import get_db

    with get_db() as conn:
        if cliente_id is not None:
            row = conn.execute(
                "SELECT id, nombre, apellido, email FROM clientes WHERE id = %s",
                (cliente_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, nombre, apellido, email FROM clientes WHERE LOWER(email) = LOWER(%s)",
                (STAGING_CLIENTE_EMAIL,),
            ).fetchone()
    if not row:
        return None
    nombre = f"{row['nombre'] or ''} {row['apellido'] or ''}".strip()
    return {"id": row["id"], "email": row["email"], "name": nombre or row["email"]}


class StagingLoginInput(BaseModel):
    secret: str
    # "admin" (default, sesión de back-office) o "cliente" (sesión del portal del
    # cliente). Backward-compatible: sin `target` se comporta como antes.
    target: str = "admin"
    # Solo para target="cliente": impersonar un cliente puntual por id. Si se
    # omite, se usa el cliente de servicio `STAGING_CLIENTE_EMAIL`.
    cliente_id: int | None = None


@router.post("/auth/staging-login")
def auth_staging_login(body: StagingLoginInput, request: Request):
    """Login programático para STAGING (dev de Railway), sin el flujo OAuth de Google.

    A diferencia de `/auth/dev-login` (que se apaga en CUALQUIER entorno Railway),
    este SÍ corre en el `dev` de Railway — pero solo si `staging_login_enabled()`
    (no-prod + secreto configurado). Mintea la misma cookie de sesión firmada que
    el OAuth real. Devuelve JSON + `Set-Cookie` (sin redirect HTML), para que un
    cliente automatizado capture la cookie y pruebe flujos autenticados en staging.

    Dos targets (la admin-ness y la cliente-ness las siguen resolviendo
    `is_admin_email` / `require_cliente`, fuentes únicas — este login no las saltea):
      - "admin" (default): sesión de back-office para `STAGING_LOGIN_EMAIL`.
      - "cliente": sesión del PORTAL para un cliente real existente (`role` +
        `cliente_id`), resuelto por `_resolve_staging_cliente`. No crea clientes.

    Seguridad: 404 si no está habilitado (que parezca inexistente en prod);
    secreto en body comparado en tiempo constante; rate-limit por IP compartido
    con OAuth; cada intento queda logueado.
    """
    if not staging_login_enabled():
        raise HTTPException(404, "No encontrado.")
    ip = get_client_ip(request)
    _check_rate(ip)
    expected = _staging_login_secret()
    if not (body.secret and secrets.compare_digest(body.secret, expected)):
        _record_fail(ip)
        logger.warning("staging-login: secreto inválido ip=%s", ip)
        raise HTTPException(401, "Secreto inválido.")

    target = (body.target or "admin").strip().lower()
    if target == "cliente":
        cli = _resolve_staging_cliente(body.cliente_id)
        if not cli:
            raise HTTPException(
                404,
                "Cliente de staging no encontrado. Pasá un `cliente_id` existente "
                f"o creá el cliente `{STAGING_CLIENTE_EMAIL}` en staging.",
            )
        logger.info("staging-login OK (cliente) ip=%s cliente_id=%s", ip, cli["id"])
        return _make_session_response(
            email=cli["email"], name=cli["name"],
            extra={"role": "cliente", "cliente_id": cli["id"]},
        )
    if target != "admin":
        raise HTTPException(400, "target inválido (usá 'admin' o 'cliente').")

    logger.info("staging-login OK (admin) ip=%s email=%s", ip, STAGING_LOGIN_EMAIL)
    return _make_session_response(email=STAGING_LOGIN_EMAIL, name="Staging Bot")
