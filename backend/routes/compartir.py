"""Compartir una composición de equipos por link (#1092 feature #4).

Un cliente (logueado o anónimo) arma un carrito / una lista / mira un pedido y
comparte esa composición por un link público corto (`/c/<token>`) — el caso
gaffer → productor: "che, reservá esto". El destinatario abre el link, ve el
"qué incluye" y la rearma en SU carrito con la primitiva única `rearmarCarrito`
(re-cotiza contra el catálogo ACTUAL — NO un snapshot de precios; respeta
plata/ítems congelados 2026-06-06, igual que listas / repetir-pedido).

Endpoints PÚBLICOS (sin login — el destinatario puede no tener cuenta):
  POST /api/public/compartir          → crea el link (anónimo o logueado)
  GET  /api/public/compartir/{token}  → trae la composición para rearmar

Se guarda SOLO la composición (`equipo_id` + `cantidad`) + un título opcional;
nombre/foto/precio/disponibilidad se resuelven en vivo desde el catálogo, igual
que listas. El prefijo `/api/public/` ya está en `middleware.PUBLIC_API_ANY`
(no requiere sesión). Rate-limit por IP para acotar el abuso del POST anónimo.
"""
import json
import secrets

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from config import SITE_URL
from database import get_db
from rate_limit import limiter
from auth.session import get_session

router = APIRouter(tags=["compartir"])

# ── Caps de seguridad (cotas sanas, no invariantes de negocio) ────────────────
TITULO_MAX = 80
CANTIDAD_MAX = 99
MAX_ITEMS = 200
TOKEN_BYTES = 12  # ~16 chars urlsafe — corto para un link, sobra de entropía


class CompartirItemIn(BaseModel):
    equipo_id: int
    cantidad: int = 1


class CompartirCreate(BaseModel):
    titulo: str | None = None
    items: list[CompartirItemIn] = []


def _clean_titulo(titulo: str | None) -> str | None:
    """Trim + cota. El título es OPCIONAL → None si queda vacío (no es error)."""
    if not titulo:
        return None
    t = titulo.strip()[:TITULO_MAX].strip()
    return t or None


def _normalizar_items(conn, items: list[CompartirItemIn]) -> list[dict]:
    """Dedup por equipo_id (última cantidad gana), clamp de cantidad y filtro a
    equipos existentes. Cap a MAX_ITEMS. Preserva el orden de inserción.

    Espeja `cliente_portal/listas._normalizar_items` (misma forma de validación);
    devuelve dicts {equipo_id, cantidad} listos para serializar a items_json.
    """
    dedup: dict[int, int] = {}
    for it in items:
        dedup[it.equipo_id] = max(1, min(int(it.cantidad), CANTIDAD_MAX))
    if not dedup:
        return []
    existentes = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM equipos WHERE id = ANY(%s)", (list(dedup.keys()),)
        ).fetchall()
    }
    out = [
        {"equipo_id": eid, "cantidad": cant}
        for eid, cant in dedup.items()
        if eid in existentes
    ]
    return out[:MAX_ITEMS]


@router.post("/public/compartir", status_code=201)
@limiter.limit("20/minute")
def crear_compartido(data: CompartirCreate, request: Request):
    """Crea un link compartible para una composición de equipos.

    Anónimo o logueado: si hay sesión cliente, se guarda el `cliente_id` como
    atribución (nada más se confía del cliente). 400 si la composición queda
    vacía (todos los equipos eran inexistentes).
    """
    titulo = _clean_titulo(data.titulo)

    session = get_session(request)
    cliente_id = session["cliente_id"] if session and "cliente_id" in session else None

    with get_db() as conn:
        items = _normalizar_items(conn, data.items)
        if not items:
            raise HTTPException(400, "Agregá al menos un equipo para compartir.")
        # token_urlsafe es colisión-improbable (96 bits); el UNIQUE de la columna
        # es la red final. Pre-chequeamos para evitar el choque rarísimo.
        token = ""
        for _ in range(5):
            token = secrets.token_urlsafe(TOKEN_BYTES)
            if not conn.execute(
                "SELECT 1 FROM carritos_compartidos WHERE token = %s", (token,)
            ).fetchone():
                break
        else:
            raise HTTPException(503, "No se pudo generar el link, probá de nuevo.")
        conn.execute(
            "INSERT INTO carritos_compartidos (token, titulo, items_json, cliente_id)"
            " VALUES (%s, %s, %s::jsonb, %s)",
            (token, titulo, json.dumps(items), cliente_id),
        )
        conn.commit()

    return {"token": token, "url": f"{SITE_URL}/c/{token}"}


@router.get("/public/compartir/{token}")
def get_compartido(token: str, request: Request):
    """Trae la composición de un link compartido (para rearmar el carrito).

    Token inválido → 404 (no revelamos si existe). Suma una vista (métrica
    simple, best-effort).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, token, titulo, items_json, created_at"
            " FROM carritos_compartidos WHERE token = %s",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Link no encontrado")
        conn.execute(
            "UPDATE carritos_compartidos SET vistas = vistas + 1 WHERE id = %s",
            (row["id"],),
        )
        conn.commit()

    raw = row["items_json"]
    items = raw if isinstance(raw, list) else json.loads(raw or "[]")
    return {
        "token": row["token"],
        "titulo": row["titulo"],
        "items": items,
        "created_at": row["created_at"],
    }
