"""Listas / kits personales del cliente (#1092 — habilitado por la puerta de
contenido).

El cliente guarda una composición de equipos que alquila seguido y la reserva de
un toque. Acá vive el CRUD; el "reservar de un toque" lo arma el frontend con la
primitiva única `rearmarCarrito` (rearma el carrito y RE-COTIZA contra el catálogo
actual — NO un snapshot de precios; respeta plata/ítems congelados 2026-06-06).

Se guarda SOLO la composición (`equipo_id` + `cantidad`); nombre/foto/precio se
resuelven en vivo desde el catálogo (`useEquipos`), igual que favoritos. Es una
acción logueada deliberada → server-only (sin sync de localStorage).

Registra sus rutas en el router compartido del paquete `routes.cliente_portal`.
`require_cliente` (guard) vive en `core`. Toda operación scopea por
`cliente_id` de la sesión (nunca se confía el dueño desde el cliente).
"""
from fastapi import Request, HTTPException
from pydantic import BaseModel

from database import get_db
from rate_limit import limiter, CLIENTE_WRITE_LIMIT
from routes.cliente_portal.core import router, require_cliente
from services.carrito import normalizar_seleccion, a_tuplas


# ── Caps de seguridad (no son invariantes de negocio, solo cotas sanas) ───────
NOMBRE_MAX = 80
MAX_LISTAS = 50


# ── Modelos de entrada (solo forma del payload; la validación dura está en los
#    helpers para tener una sola fuente) ───────────────────────────────────────
class ListaItemIn(BaseModel):
    equipo_id: int
    cantidad: int = 1


class ListaCreate(BaseModel):
    nombre: str
    items: list[ListaItemIn] = []


class ListaRename(BaseModel):
    nombre: str


class ListaItemsReplace(BaseModel):
    items: list[ListaItemIn] = []


# ── Helpers (fuente única de validación + proyección) ─────────────────────────


def _clean_nombre(nombre: str) -> str:
    """Normaliza el nombre: trim + cota de largo. 400 si queda vacío."""
    n = (nombre or "").strip()[:NOMBRE_MAX].strip()
    if not n:
        raise HTTPException(400, "La lista necesita un nombre.")
    return n


def _fetch_lista(conn, lista_id: int, cliente_id: int) -> dict | None:
    """Proyección canónica de una lista (con sus items). None si no existe o no
    es del cliente."""
    row = conn.execute(
        "SELECT id, nombre, created_at, updated_at FROM cliente_listas"
        " WHERE id = %s AND cliente_id = %s",
        (lista_id, cliente_id),
    ).fetchone()
    if not row:
        return None
    items = conn.execute(
        "SELECT equipo_id, cantidad FROM cliente_listas_items"
        " WHERE lista_id = %s ORDER BY id",
        (lista_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "items": [{"equipo_id": it["equipo_id"], "cantidad": it["cantidad"]} for it in items],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ── Rutas ─────────────────────────────────────────────────────────────────────


@router.get("/api/cliente/listas")
def get_listas(request: Request):
    """Todas las listas del cliente, con sus items, más recientes primero."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        listas = conn.execute(
            "SELECT id, nombre, created_at, updated_at FROM cliente_listas"
            " WHERE cliente_id = %s ORDER BY updated_at DESC NULLS LAST, id DESC",
            (cliente_id,),
        ).fetchall()
        if not listas:
            return []
        # Items en una sola query (sin N+1) y se agrupan por lista en Python.
        ids = [lst["id"] for lst in listas]
        filas = conn.execute(
            "SELECT lista_id, equipo_id, cantidad FROM cliente_listas_items"
            " WHERE lista_id = ANY(%s) ORDER BY id",
            (ids,),
        ).fetchall()
        por_lista: dict[int, list] = {}
        for it in filas:
            por_lista.setdefault(it["lista_id"], []).append(
                {"equipo_id": it["equipo_id"], "cantidad": it["cantidad"]}
            )
        return [
            {
                "id": lst["id"],
                "nombre": lst["nombre"],
                "items": por_lista.get(lst["id"], []),
                "created_at": lst["created_at"],
                "updated_at": lst["updated_at"],
            }
            for lst in listas
        ]


@router.post("/api/cliente/listas", status_code=201)
@limiter.limit(CLIENTE_WRITE_LIMIT)
def create_lista(data: ListaCreate, request: Request):
    """Crea una lista nueva con su composición (ej.: guardar el carrito actual)."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    nombre = _clean_nombre(data.nombre)
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM cliente_listas WHERE cliente_id = %s",
            (cliente_id,),
        ).fetchone()
        if total and total["n"] >= MAX_LISTAS:
            raise HTTPException(
                400, f"Llegaste al máximo de {MAX_LISTAS} listas. Borrá una para crear otra."
            )
        items = a_tuplas(normalizar_seleccion(conn, data.items))
        with conn.transaction():
            lista_id = conn.insert_returning(
                "INSERT INTO cliente_listas (cliente_id, nombre) VALUES (%s, %s)",
                (cliente_id, nombre),
            )
            for eid, cant in items:
                conn.execute(
                    "INSERT INTO cliente_listas_items (lista_id, equipo_id, cantidad)"
                    " VALUES (%s, %s, %s)",
                    (lista_id, eid, cant),
                )
        return _fetch_lista(conn, lista_id, cliente_id)


@router.patch("/api/cliente/listas/{lista_id}")
@limiter.limit(CLIENTE_WRITE_LIMIT)
def rename_lista(lista_id: int, data: ListaRename, request: Request):
    """Renombra una lista del cliente."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    nombre = _clean_nombre(data.nombre)
    with get_db() as conn:
        updated = conn.execute(
            "UPDATE cliente_listas SET nombre = %s, updated_at = CURRENT_TIMESTAMP"
            " WHERE id = %s AND cliente_id = %s RETURNING id",
            (nombre, lista_id, cliente_id),
        ).fetchone()
        if not updated:
            raise HTTPException(404, "Lista no encontrada")
        conn.commit()
        return _fetch_lista(conn, lista_id, cliente_id)


@router.put("/api/cliente/listas/{lista_id}/items")
@limiter.limit(CLIENTE_WRITE_LIMIT)
def replace_items(lista_id: int, data: ListaItemsReplace, request: Request):
    """Reemplaza la composición completa de una lista (ej.: actualizarla con el
    carrito actual)."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        owner = conn.execute(
            "SELECT id FROM cliente_listas WHERE id = %s AND cliente_id = %s",
            (lista_id, cliente_id),
        ).fetchone()
        if not owner:
            raise HTTPException(404, "Lista no encontrada")
        items = a_tuplas(normalizar_seleccion(conn, data.items))
        with conn.transaction():
            conn.execute(
                "DELETE FROM cliente_listas_items WHERE lista_id = %s", (lista_id,)
            )
            for eid, cant in items:
                conn.execute(
                    "INSERT INTO cliente_listas_items (lista_id, equipo_id, cantidad)"
                    " VALUES (%s, %s, %s)",
                    (lista_id, eid, cant),
                )
            conn.execute(
                "UPDATE cliente_listas SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (lista_id,),
            )
        return _fetch_lista(conn, lista_id, cliente_id)


@router.delete("/api/cliente/listas/{lista_id}/items/{equipo_id}")
@limiter.limit(CLIENTE_WRITE_LIMIT)
def remove_item(lista_id: int, equipo_id: int, request: Request):
    """Quita un equipo de una lista (acción rápida desde la card)."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        owner = conn.execute(
            "SELECT id FROM cliente_listas WHERE id = %s AND cliente_id = %s",
            (lista_id, cliente_id),
        ).fetchone()
        if not owner:
            raise HTTPException(404, "Lista no encontrada")
        conn.execute(
            "DELETE FROM cliente_listas_items WHERE lista_id = %s AND equipo_id = %s",
            (lista_id, equipo_id),
        )
        conn.execute(
            "UPDATE cliente_listas SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (lista_id,),
        )
        conn.commit()
        return _fetch_lista(conn, lista_id, cliente_id)


@router.delete("/api/cliente/listas/{lista_id}")
@limiter.limit(CLIENTE_WRITE_LIMIT)
def delete_lista(lista_id: int, request: Request):
    """Borra una lista del cliente (sus items caen por ON DELETE CASCADE)."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM cliente_listas WHERE id = %s AND cliente_id = %s RETURNING id",
            (lista_id, cliente_id),
        ).fetchone()
        if not deleted:
            raise HTTPException(404, "Lista no encontrada")
        conn.commit()
        return {"ok": True}
