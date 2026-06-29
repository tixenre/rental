"""auth/linking.py — gestión unificada de las llaves de acceso del cliente.

"Métodos de acceso" del portal: une las **passkeys** (`passkey_credentials`) y las
**identidades de login** (`login_identities`: Google / mail) en UNA vista de lectura,
y permite **quitar** una llave con el guardrail **"no podés quitar tu última llave"**
(si no, la cuenta queda sin forma de entrar). Agregar una passkey vive en
`passkey/routes`; vincular Google, en `google.py` (link-mode). Es la cara de
account-linking de la iniciativa de identidad (#1098, Fase 1B): "varias llaves
intercambiables" sobre una cuenta estable.

Todo scopeado al dueño (`cliente_id` de la sesión) — anti-IDOR, igual que `passkey/store`.
"""
import logging

from fastapi import APIRouter, HTTPException, Request

from auth.guards import require_cliente
from auth.passkey import store as passkey_store
from auth import identities_store

logger = logging.getLogger(__name__)
router = APIRouter()


def _total_keys(cliente_id: int) -> int:
    """Total de llaves de la cuenta (passkeys + identidades). Fuente única del
    guardrail de "última llave" — cuenta las DOS tablas (no alcanza con una sola)."""
    passkeys = len(passkey_store.list_for_owner("cliente", cliente_id=cliente_id))
    return passkeys + identities_store.count_for_cliente(cliente_id)


@router.get("/cliente/auth/keys")
def cliente_list_keys(request: Request):
    """Lista unificada de las llaves de acceso del cliente (para "Métodos de acceso").
    Une passkeys + identidades en lectura, sin doble-escritura (cada una en su tabla)."""
    sess = require_cliente(request)
    cid = sess["cliente_id"]
    keys: list[dict] = []
    for pk in passkey_store.list_for_owner("cliente", cliente_id=cid):
        keys.append({
            "kind": "passkey",
            "id": pk["id"],
            "label": pk["device_name"] or "Passkey",
            "detail": pk["transports"],
            "created_at": pk["created_at"],
            "last_used_at": pk["last_used_at"],
        })
    for idy in identities_store.list_for_cliente(cid):
        method = idy["method"]
        # Google: mostrar el mail con que se vinculó (el `identifier` es el `sub` opaco);
        # si no lo tenemos (vínculos viejos), cae al genérico "Google". 'email' → el mail.
        if method == "google":
            label = idy["email"] or "Google"
        else:
            label = idy["identifier"]
        keys.append({
            "kind": method,
            "id": idy["id"],
            "label": label,
            "detail": "Google" if method == "google" else None,
            "created_at": idy["created_at"],
            "last_used_at": None,
        })
    return {"keys": keys, "total": len(keys)}


@router.delete("/cliente/auth/keys/{kind}/{key_id}")
def cliente_remove_key(kind: str, key_id: int, request: Request):
    """Quita una llave (`passkey` o `identity`), scopeada al dueño. Guardrail: no podés
    quitar la última (te dejaría sin acceso). El chequeo es best-effort (cuenta antes de
    borrar) — alcanza para el caso real (no auto-lockearse); no es un candado concurrente."""
    sess = require_cliente(request)
    cid = sess["cliente_id"]
    if kind not in ("passkey", "identity"):
        raise HTTPException(404, "Tipo de llave inválido.")
    if _total_keys(cid) <= 1:
        raise HTTPException(409, "No podés quitar tu única llave de acceso. Agregá otra primero.")
    if kind == "passkey":
        ok = passkey_store.delete_for_owner(key_id, "cliente", cliente_id=cid)
    else:
        ok = identities_store.unlink_for_cliente(key_id, cid)
    if not ok:
        raise HTTPException(404, "Llave no encontrada.")
    return {"ok": True}
