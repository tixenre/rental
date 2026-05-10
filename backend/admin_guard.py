"""
admin_guard.py — Guard de admin basado en cookie de sesión local.
"""
import os
from typing import Optional
from fastapi import HTTPException, Request

from routes.auth import get_session

_ADMIN_EMAILS_ENV = os.getenv("ADMIN_EMAILS", "tinchosantini@gmail.com")
ADMIN_EMAILS: set[str] = {
    e.strip().lower() for e in _ADMIN_EMAILS_ENV.split(",") if e.strip()
}


def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in ADMIN_EMAILS


def require_admin(request: Request) -> dict:
    """Exige cookie de sesión válida con email en ADMIN_EMAILS.

    ADMIN_BYPASS_AUTH=1 deja pasar (solo dev).
    """
    if os.getenv("ADMIN_BYPASS_AUTH", "").strip() in ("1", "true", "yes"):
        return {"kind": "bypass", "email": "bypass@local"}

    session = get_session(request)
    if not session:
        raise HTTPException(401, "Autenticación requerida")
    email = (session.get("email") or "").strip().lower()
    if not is_admin_email(email):
        raise HTTPException(403, "Tu cuenta no tiene permisos de administración")
    return {"kind": "session", "email": email, "session": session}
