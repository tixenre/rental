"""
admin_guard.py — Guard de admin basado en cookie de sesión local.
"""
from typing import Optional
from fastapi import HTTPException, Request

from routes.auth import get_session, dev_bypass_enabled
from config import settings

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
    # devuelve False en prod (Railway) — ver routes/auth.py.
    if dev_bypass_enabled():
        return {"kind": "bypass", "email": "bypass@local"}

    session = get_session(request)
    if not session:
        raise HTTPException(401, "Autenticación requerida")
    email = (session.get("email") or "").strip().lower()
    if not is_admin_email(email):
        raise HTTPException(403, "Tu cuenta no tiene permisos de administración")
    return {"kind": "session", "email": email, "session": session}
