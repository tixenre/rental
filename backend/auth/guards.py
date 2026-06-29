"""auth/guards.py — autorización: guards de admin y de cliente, juntos.

Los guards solo leen la cookie de sesión (`get_session`) — son **agnósticos del
método de login** (da igual si la sesión la minteó Google o una passkey). Por eso
acá conviven los de admin (`require_admin`/`is_admin_email`) y los de cliente
(`require_cliente`/`require_cliente_verificado`).

Movido verbatim de `admin_guard.py` (admin) y `routes/cliente_portal/core.py` (cliente).
"""
from typing import Optional

from fastapi import HTTPException, Request

from auth.session import dev_bypass_enabled, get_session
from config import settings
from database import get_db

# ── Admin ─────────────────────────────────────────────────────────────────────

ADMIN_EMAILS: set[str] = settings.admin_emails


def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in ADMIN_EMAILS


def require_admin(request: Request) -> dict:
    """Exige cookie de sesión válida con email en ADMIN_EMAILS.

    ADMIN_BYPASS_AUTH=1 deja pasar — SOLO en dev (nunca en Railway/prod, ver
    `dev_bypass_enabled`).
    """
    # dev_bypass_enabled() lee ADMIN_BYPASS_AUTH en runtime pero SIEMPRE
    # devuelve False en prod (Railway) — ver auth/session.py.
    if dev_bypass_enabled():
        return {"kind": "bypass", "email": "bypass@local"}

    session = get_session(request)
    if not session:
        raise HTTPException(401, "Autenticación requerida")
    email = (session.get("email") or "").strip().lower()
    if not is_admin_email(email):
        raise HTTPException(403, "Tu cuenta no tiene permisos de administración")
    return {"kind": "session", "email": email, "session": session}


# ── Cliente ───────────────────────────────────────────────────────────────────

def require_cliente(request: Request) -> dict:
    """Devuelve la sesión del cliente (cookie). 401 si no hay sesión válida."""
    session = get_session(request)
    if not session or session.get("role") != "cliente":
        raise HTTPException(401, "Sesión de cliente requerida")
    return session


# Mensaje único del gate de identidad — la UI lo muestra tal cual si llegara a disparar.
IDENTIDAD_NO_VERIFICADA_MSG = (
    "Necesitás verificar tu identidad antes de hacer un pedido. "
    "Verificá tu DNI desde tu portal — tarda menos de 2 minutos."
)


def cliente_verificado(conn, cliente_id: int) -> bool:
    """True si el cliente completó la verificación de identidad (dni_validado_at).
    Fuente única del criterio "está verificado"; usa una conexión ya abierta."""
    row = conn.execute(
        "SELECT dni_validado_at FROM clientes WHERE id = %s", (cliente_id,)
    ).fetchone()
    return bool(row and row["dni_validado_at"])


def require_cliente_verificado(request: Request) -> dict:
    """Como require_cliente pero además exige identidad verificada (el gate del
    flujo de pedidos). 401 sin sesión; 404 si el cliente no existe; 403 si no
    completó la verificación Didit. El criterio "está verificado" lo decide la
    fuente única `cliente_verificado` (no se duplica el chequeo de `dni_validado_at`)."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        if conn.execute("SELECT 1 FROM clientes WHERE id = %s", (cliente_id,)).fetchone() is None:
            raise HTTPException(404, "Cliente no encontrado.")
        if not cliente_verificado(conn, cliente_id):
            raise HTTPException(403, IDENTIDAD_NO_VERIFICADA_MSG)
    return session
