"""Favoritos del cliente (#501 — extraído del god-module `routes/cliente_portal.py`).

CRUD de los equipos favoritos del cliente logueado (listar / sync / agregar /
quitar). Registra sus rutas en el router compartido del paquete
`routes.cliente_portal`. `require_cliente` (guard) vive en `core`.
"""
from fastapi import Request, HTTPException
from pydantic import BaseModel

from database import get_db
from routes.cliente_portal.core import router, require_cliente


# ── Favoritos del cliente ──────────────────────────────────────────────────────


@router.get("/api/cliente/favoritos")
def get_favoritos(request: Request):
    """Lista de equipo_ids marcados como favoritos por el cliente."""
    session = require_cliente(request)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT equipo_id FROM cliente_favoritos WHERE cliente_id = %s",
            (session["cliente_id"],),
        ).fetchall()
        return [str(r["equipo_id"]) for r in rows]


class FavSync(BaseModel):
    ids: list[int]


@router.post("/api/cliente/favoritos/sync")
def sync_favoritos(data: FavSync, request: Request):
    """Merge de favoritos de localStorage al servidor al hacer login. No borra nada."""
    session = require_cliente(request)
    if not data.ids:
        return {"synced": 0}
    with get_db() as conn:
        count = 0
        for eid in data.ids[:200]:  # cap de seguridad
            eq = conn.execute(
                "SELECT id FROM equipos WHERE id = %s", (eid,)
            ).fetchone()
            if not eq:
                continue
            conn.execute(
                "INSERT INTO cliente_favoritos (cliente_id, equipo_id) VALUES (%s, %s)"
                " ON CONFLICT (cliente_id, equipo_id) DO NOTHING",
                (session["cliente_id"], eid),
            )
            count += 1
        conn.commit()
        return {"synced": count}


@router.post("/api/cliente/favoritos/{equipo_id}", status_code=201)
def add_favorito(equipo_id: int, request: Request):
    """Agrega un equipo a los favoritos del cliente."""
    session = require_cliente(request)
    with get_db() as conn:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = %s", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute(
            "INSERT INTO cliente_favoritos (cliente_id, equipo_id) VALUES (%s, %s)"
            " ON CONFLICT (cliente_id, equipo_id) DO NOTHING",
            (session["cliente_id"], equipo_id),
        )
        conn.commit()
        return {"ok": True}


@router.delete("/api/cliente/favoritos/{equipo_id}")
def remove_favorito(equipo_id: int, request: Request):
    """Quita un equipo de los favoritos del cliente."""
    session = require_cliente(request)
    with get_db() as conn:
        conn.execute(
            "DELETE FROM cliente_favoritos WHERE cliente_id = %s AND equipo_id = %s",
            (session["cliente_id"], equipo_id),
        )
        conn.commit()
        return {"ok": True}
