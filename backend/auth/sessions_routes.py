"""auth/sessions_routes.py — gestión de sesiones activas (revocación).

Transporte sobre el store `auth.sessions_store`: listar las sesiones vivas del
dueño, cerrar "las otras" (revoke-all salvo la actual) y cerrar una puntual.
Todo **scopeado al dueño** (anti-IDOR: resuelve owner_email/cliente_id de la
sesión, nunca del body), espejando la gestión de passkeys. Router propio
(`auth_sessions_router`): admin bajo `/auth/sessions*`, cliente bajo
`/cliente/auth/sessions*` (este último exento del middleware → el guard va
in-handler, igual que las passkeys de cliente).
"""
import logging

from fastapi import APIRouter, HTTPException, Request

from auth import sessions_store
from auth.guards import require_admin, require_cliente

logger = logging.getLogger(__name__)
router = APIRouter()


def _payload(rows: list[dict], current_jti: str | None) -> dict:
    """Marca la sesión actual ('este dispositivo') para que la UI la distinga y
    no se ofrezca cerrarla a sí misma por error."""
    return {
        "sessions": [{**r, "current": r["jti"] == current_jti} for r in rows],
        "current_jti": current_jti,
    }


# ── Admin ────────────────────────────────────────────────────────────────────

@router.get("/auth/sessions")
def admin_list(request: Request):
    admin = require_admin(request)
    current_jti = (admin.get("session") or {}).get("jti")
    rows = sessions_store.list_for_owner("admin", owner_email=admin["email"])
    return _payload(rows, current_jti)


@router.post("/auth/sessions/revoke-all")
def admin_revoke_all(request: Request):
    """Cierra todas las otras sesiones del admin (mantiene la actual, `except_jti`)."""
    admin = require_admin(request)
    current_jti = (admin.get("session") or {}).get("jti")
    n = sessions_store.revoke_all_for_owner(
        "admin", owner_email=admin["email"], except_jti=current_jti
    )
    return {"ok": True, "revoked": n}


@router.delete("/auth/sessions/{jti}")
def admin_revoke_one(jti: str, request: Request):
    admin = require_admin(request)
    if not sessions_store.revoke_one_for_owner(jti, "admin", owner_email=admin["email"]):
        raise HTTPException(404, "Sesión no encontrada.")
    return {"ok": True}


# ── Cliente ──────────────────────────────────────────────────────────────────

@router.get("/cliente/auth/sessions")
def cliente_list(request: Request):
    sess = require_cliente(request)
    rows = sessions_store.list_for_owner("cliente", cliente_id=sess["cliente_id"])
    return _payload(rows, sess.get("jti"))


@router.post("/cliente/auth/sessions/revoke-all")
def cliente_revoke_all(request: Request):
    """Cierra todas las otras sesiones del cliente (mantiene la actual)."""
    sess = require_cliente(request)
    n = sessions_store.revoke_all_for_owner(
        "cliente", cliente_id=sess["cliente_id"], except_jti=sess.get("jti")
    )
    return {"ok": True, "revoked": n}


@router.delete("/cliente/auth/sessions/{jti}")
def cliente_revoke_one(jti: str, request: Request):
    sess = require_cliente(request)
    if not sessions_store.revoke_one_for_owner(jti, "cliente", cliente_id=sess["cliente_id"]):
        raise HTTPException(404, "Sesión no encontrada.")
    return {"ok": True}
