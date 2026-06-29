"""auth/passkey/routes.py — endpoints de login con passkey (WebAuthn/FIDO2).

**Transporte** del motor `auth/passkey/`: registro (usuario YA logueado por
Google registra una passkey), login discoverable (entrar con la passkey), y
gestión (listar/borrar/renombrar). Aditivo a Google OAuth — la sesión que se
mintea al loguear es la MISMA cookie firmada (`auth.session._make_session_response`),
no una sesión paralela.

Recuperación de cuenta: trivial — Google es el anchor (registrar passkey exige
estar logueado por Google), así que perder el dispositivo = entrar por Google y
re-registrar. No hay flujo de recovery extra.
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg.errors

from auth.guards import is_admin_email, require_admin
from database import get_db
from auth.session import COOKIE_SECURE, _make_session_response
from auth.guards import require_cliente
from auth.passkey import ceremonies, store

logger = logging.getLogger(__name__)
router = APIRouter()

_REG_COOKIE = "wa_chal_reg"
_AUTH_COOKIE = "wa_chal_auth"


class RegisterCompleteIn(BaseModel):
    credential: dict
    device_name: str | None = None


class LoginCompleteIn(BaseModel):
    credential: dict


class RenameIn(BaseModel):
    device_name: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _admin_identity(admin: dict) -> tuple[str, str]:
    """(email, display_name) del admin a partir del dict de `require_admin`."""
    email = admin["email"]
    name = (admin.get("session") or {}).get("name") or email
    return email, name


def _set_challenge(res, cookie: str, token: str) -> None:
    res.set_cookie(
        cookie, token, httponly=True, samesite="lax",
        secure=COOKIE_SECURE, max_age=ceremonies.CHALLENGE_MAX_AGE,
    )


def _extract_transports(credential: dict) -> str | None:
    t = (credential.get("response") or {}).get("transports")
    if isinstance(t, list) and t:
        return ",".join(str(x) for x in t)
    return None


# ── Registro (begin/complete) — admin y cliente ──────────────────────────────

def _register_begin(*, owner_type: str, owner_email: str, cliente_id, display_name: str):
    owner_key = owner_email.lower() if owner_type == "admin" else str(cliente_id)
    uh = ceremonies.user_handle_for(owner_type, owner_key)
    exclude = store.credential_ids_for_owner(
        owner_type, owner_email=owner_email, cliente_id=cliente_id
    )
    options, challenge_b64 = ceremonies.build_registration_options(
        user_name=owner_email, user_display_name=display_name,
        user_handle_b64=uh, exclude_ids=exclude,
    )
    res = JSONResponse(options)
    _set_challenge(res, _REG_COOKIE,
                   ceremonies.sign_challenge(challenge_b64, ot=owner_type, ok=owner_key, uh=uh))
    return res


def _register_complete(request: Request, body: RegisterCompleteIn, *, owner_type, owner_email,
                       cliente_id, owner_key):
    data = ceremonies.read_challenge(request.cookies.get(_REG_COOKIE) or "")
    if not data or data.get("ot") != owner_type or data.get("ok") != owner_key:
        raise HTTPException(400, "Challenge inválido o expirado. Reintentá.")
    try:
        reg = ceremonies.verify_registration(credential=body.credential, challenge_b64=data["challenge"])
    except Exception as e:  # noqa: BLE001 — la lib lanza varios tipos; todos = registro inválido
        logger.warning("passkey register verify falló: %s", e)
        raise HTTPException(400, "No se pudo verificar la passkey.")
    device_name = (body.device_name or "").strip() or "Passkey"
    try:
        new_id = store.insert_credential(
            owner_type=owner_type, owner_email=owner_email, cliente_id=cliente_id,
            credential_id=reg["credential_id"], public_key=reg["public_key"],
            sign_count=reg["sign_count"], transports=_extract_transports(body.credential),
            aaguid=reg["aaguid"], device_name=device_name, user_handle=data["uh"],
        )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Esa passkey ya está registrada.")
    res = JSONResponse({"ok": True, "id": new_id, "device_name": device_name})
    res.delete_cookie(_REG_COOKIE)
    return res


@router.post("/auth/passkey/register/begin")
def admin_register_begin(request: Request):
    email, name = _admin_identity(require_admin(request))
    return _register_begin(owner_type="admin", owner_email=email, cliente_id=None, display_name=name)


@router.post("/auth/passkey/register/complete")
def admin_register_complete(body: RegisterCompleteIn, request: Request):
    email, _ = _admin_identity(require_admin(request))
    return _register_complete(request, body, owner_type="admin", owner_email=email,
                              cliente_id=None, owner_key=email.lower())


@router.post("/cliente/auth/passkey/register/begin")
def cliente_register_begin(request: Request):
    sess = require_cliente(request)
    return _register_begin(owner_type="cliente", owner_email=sess["email"],
                           cliente_id=sess["cliente_id"],
                           display_name=sess.get("name") or sess["email"])


@router.post("/cliente/auth/passkey/register/complete")
def cliente_register_complete(body: RegisterCompleteIn, request: Request):
    sess = require_cliente(request)
    return _register_complete(request, body, owner_type="cliente", owner_email=sess["email"],
                              cliente_id=sess["cliente_id"], owner_key=str(sess["cliente_id"]))


# ── Login (begin/complete) — discoverable, un solo flujo para admin y cliente ─

@router.post("/auth/passkey/login/begin")
def login_begin():
    options, challenge_b64 = ceremonies.build_authentication_options()
    res = JSONResponse(options)
    _set_challenge(res, _AUTH_COOKIE, ceremonies.sign_challenge(challenge_b64))
    return res


@router.post("/auth/passkey/login/complete")
def login_complete(body: LoginCompleteIn, request: Request):
    data = ceremonies.read_challenge(request.cookies.get(_AUTH_COOKIE) or "")
    if not data:
        raise HTTPException(400, "Challenge inválido o expirado. Reintentá.")
    cred_id = body.credential.get("id") or body.credential.get("rawId")
    if not cred_id:
        raise HTTPException(400, "Credencial inválida.")
    row = store.get_by_credential_id(cred_id)
    if not row:
        raise HTTPException(401, "Passkey no reconocida.")
    try:
        new_count = ceremonies.verify_authentication(
            credential=body.credential, challenge_b64=data["challenge"],
            public_key_b64=row["public_key"], current_sign_count=row["sign_count"],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("passkey auth verify falló: %s", e)
        raise HTTPException(401, "No se pudo verificar la passkey.")
    if ceremonies.es_replay(row["sign_count"], new_count):
        logger.warning("passkey replay/clonación id=%s stored=%s new=%s",
                       row["id"], row["sign_count"], new_count)
        raise HTTPException(401, "Passkey rechazada (contador inválido).")
    store.update_sign_count(row["id"], new_count)
    res = _mint_session_for_owner(row, request)
    res.delete_cookie(_AUTH_COOKIE)
    return res


def _mint_session_for_owner(row: dict, request: Request):
    """Mintea la MISMA cookie de sesión que el OAuth, resolviendo el rol como
    siempre (admin por `is_admin_email`; cliente con role+cliente_id). Los datos
    vivos (email/nombre del cliente) salen por `cliente_id` (clave estable).
    `request` aporta el user_agent para etiquetar el dispositivo en la sesión."""
    if row["owner_type"] == "admin":
        email = row["owner_email"]
        if not is_admin_email(email):
            raise HTTPException(403, "Tu cuenta ya no tiene permisos de administración.")
        return _make_session_response(email=email, name=email, request=request)
    with get_db() as conn:
        c = conn.execute(
            "SELECT id, email, nombre, apellido FROM clientes WHERE id = %s",
            (row["cliente_id"],),
        ).fetchone()
    if not c:
        raise HTTPException(401, "Cliente no encontrado.")
    name = f"{c['nombre'] or ''} {c['apellido'] or ''}".strip() or c["email"]
    return _make_session_response(
        email=c["email"], name=name, extra={"role": "cliente", "cliente_id": c["id"]},
        request=request,
    )


# ── Gestión (listar/borrar/renombrar) — scopeado al dueño ────────────────────

@router.get("/auth/passkey/credentials")
def admin_list(request: Request):
    email, _ = _admin_identity(require_admin(request))
    return {"credentials": store.list_for_owner("admin", owner_email=email)}


@router.delete("/auth/passkey/credentials/{cred_id}")
def admin_delete(cred_id: int, request: Request):
    email, _ = _admin_identity(require_admin(request))
    if not store.delete_for_owner(cred_id, "admin", owner_email=email):
        raise HTTPException(404, "Passkey no encontrada.")
    return {"ok": True}


@router.patch("/auth/passkey/credentials/{cred_id}")
def admin_rename(cred_id: int, body: RenameIn, request: Request):
    email, _ = _admin_identity(require_admin(request))
    name = body.device_name.strip()
    if not name:
        raise HTTPException(400, "Nombre vacío.")
    if not store.rename_for_owner(cred_id, name, "admin", owner_email=email):
        raise HTTPException(404, "Passkey no encontrada.")
    return {"ok": True}


@router.get("/cliente/auth/passkey/credentials")
def cliente_list(request: Request):
    sess = require_cliente(request)
    return {"credentials": store.list_for_owner("cliente", cliente_id=sess["cliente_id"])}


@router.delete("/cliente/auth/passkey/credentials/{cred_id}")
def cliente_delete(cred_id: int, request: Request):
    sess = require_cliente(request)
    if not store.delete_for_owner(cred_id, "cliente", cliente_id=sess["cliente_id"]):
        raise HTTPException(404, "Passkey no encontrada.")
    return {"ok": True}


@router.patch("/cliente/auth/passkey/credentials/{cred_id}")
def cliente_rename(cred_id: int, body: RenameIn, request: Request):
    sess = require_cliente(request)
    name = body.device_name.strip()
    if not name:
        raise HTTPException(400, "Nombre vacío.")
    if not store.rename_for_owner(cred_id, name, "cliente", cliente_id=sess["cliente_id"]):
        raise HTTPException(404, "Passkey no encontrada.")
    return {"ok": True}
