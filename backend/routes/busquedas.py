"""
routes/busquedas.py — Registro y analítica de búsquedas del catálogo público.

El buscador del catálogo filtra en el front (client-side), así que las
búsquedas no quedaban registradas en ningún lado. Para saber QUÉ busca la gente
—y sobre todo qué buscan y NO encontramos (demanda no cubierta)— registramos
cada búsqueda "asentada" (el front debouncea y manda el término una vez que el
usuario deja de tipear), y qué resultado terminan abriendo (click-through).

Diseño raw + normalizado (ver migración i1c2d3e4f5a6):
- `query_text`: el término crudo, tal cual se tipeó. Nada se pierde.
- `query_norm`: minúsculas, sin acentos, espacios colapsados → agrupa variantes
  equivalentes en los reportes. La normalización es la canónica del motor único
  (`backend/busqueda`), la misma que usa el matching — una sola fuente.

Click-through (`search_clicks`, migración s3t4u5v6w7x8): liga una búsqueda con
el equipo que se abrió después. Es la señal para, a futuro, aprender qué
encontró la gente (ranking por comportamiento, sinónimos).

Endpoints:
- POST /search-log       → público (rate-limited). Devuelve el id del registro.
- POST /search-click     → público (rate-limited). Liga la búsqueda con un equipo.
- GET  /admin/busquedas  → admin. Top de búsquedas + búsquedas sin resultados.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from database import get_db, row_to_dict
from admin_guard import require_admin
from rate_limit import limiter
from busqueda import MAX_LEN, normalizar_para_registro

router = APIRouter()


def normalizar_busqueda(texto: str) -> Optional[str]:
    """Normaliza un término para agrupar variantes equivalentes, vía el motor
    único (`backend/busqueda`). Devuelve None si queda demasiado corto."""
    return normalizar_para_registro(texto)


class SearchLogBody(BaseModel):
    query: str = Field(..., max_length=400)
    result_count: int = Field(0, ge=0)


class SearchClickBody(BaseModel):
    query_id: int = Field(..., ge=1)
    equipo_id: Optional[int] = Field(None, ge=1)


@router.post("/search-log")
@limiter.limit("60/minute")
def log_search(body: SearchLogBody, request: Request):
    """Registra una búsqueda del catálogo público. Best-effort: si el término
    queda muy corto al normalizar, se ignora en silencio. Devuelve el `id` del
    registro para que el front pueda ligar el click-through posterior."""
    texto = body.query.strip()[:MAX_LEN]
    norm = normalizar_busqueda(texto)
    if not norm:
        return {"ok": True, "logged": False, "id": None}
    with get_db() as conn:
        row = conn.execute(
            "INSERT INTO search_queries (query_text, query_norm, result_count) "
            "VALUES (%s, %s, %s) RETURNING id",
            (texto, norm, max(0, int(body.result_count))),
        ).fetchone()
        conn.commit()
        return {"ok": True, "logged": True, "id": row[0]}


@router.post("/search-click")
@limiter.limit("120/minute")
def log_click(body: SearchClickBody, request: Request):
    """Registra que, tras la búsqueda `query_id`, el usuario abrió `equipo_id`.
    Best-effort: si la búsqueda no existe (FK), no rompe la UX."""
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO search_clicks (query_id, equipo_id) VALUES (%s, %s)",
                (body.query_id, body.equipo_id),
            )
            conn.commit()
            return {"ok": True, "logged": True}
        except Exception:
            conn.rollback()
            return {"ok": True, "logged": False}


@router.get("/admin/busquedas")
def admin_busquedas(request: Request, dias: Optional[int] = None):
    """Analítica de búsquedas para el back-office (sección Estadísticas).

    Devuelve dos listas agrupadas por término normalizado:
    - `top`:  lo más buscado (veces, ejemplo del texto crudo, última vez,
              máximo de resultados que llegó a dar, y el resultado más abierto
              tras esa búsqueda — click-through).
    - `zero`: términos que NUNCA dieron resultados (demanda no cubierta).

    `dias` opcional acota la ventana (ej. 30 = último mes); sin él, histórico
    completo."""
    require_admin(request)

    where = ""
    params: list = []
    if dias and dias > 0:
        where = "WHERE created_at >= %s"
        params.append(datetime.utcnow() - timedelta(days=dias))

    with get_db() as conn:
        top = conn.execute(
            f"""
            SELECT query_norm,
                   COUNT(*)          AS veces,
                   MAX(query_text)   AS texto,
                   MAX(result_count) AS max_resultados,
                   MAX(created_at)   AS ultima,
                   (SELECT e.nombre
                      FROM search_clicks sc
                      JOIN search_queries sq2 ON sq2.id = sc.query_id
                      JOIN equipos e ON e.id = sc.equipo_id
                     WHERE sq2.query_norm = search_queries.query_norm
                     GROUP BY e.nombre
                     ORDER BY COUNT(*) DESC, e.nombre ASC
                     LIMIT 1) AS click_top
            FROM search_queries
            {where}
            GROUP BY query_norm
            ORDER BY veces DESC, ultima DESC
            LIMIT 100
            """,
            tuple(params),
        ).fetchall()

        zero = conn.execute(
            f"""
            SELECT query_norm,
                   COUNT(*)        AS veces,
                   MAX(query_text) AS texto,
                   MAX(created_at) AS ultima
            FROM search_queries
            {where}
            GROUP BY query_norm
            HAVING MAX(result_count) = 0
            ORDER BY veces DESC, ultima DESC
            LIMIT 100
            """,
            tuple(params),
        ).fetchall()

        return {
            "top": [row_to_dict(r) for r in top],
            "zero": [row_to_dict(r) for r in zero],
        }
