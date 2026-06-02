"""
routes/busquedas.py — Registro y analítica de búsquedas del catálogo público.

El buscador del catálogo filtra en el front (client-side), así que las
búsquedas no quedaban registradas en ningún lado. Para saber QUÉ busca la gente
—y sobre todo qué buscan y NO encontramos (demanda no cubierta)— registramos
cada búsqueda "asentada" (el front debouncea y manda el término una vez que el
usuario deja de tipear).

Diseño raw + normalizado (ver migración i1c2d3e4f5a6):
- `query_text`: el término crudo, tal cual se tipeó. Nada se pierde.
- `query_norm`: minúsculas, sin acentos, espacios colapsados → agrupa variantes
  equivalentes en los reportes. El crudo intacto permite re-agrupar más fino en
  el futuro (sinónimos) sobre la misma data histórica.

Endpoints:
- POST /search-log       → público (rate-limited). Lo llama el front.
- GET  /admin/busquedas  → admin. Top de búsquedas + búsquedas sin resultados.
"""

import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from database import get_db, row_to_dict
from admin_guard import require_admin
from rate_limit import limiter

router = APIRouter()

MAX_LEN = 120
MIN_LEN = 2


def normalizar_busqueda(texto: str) -> Optional[str]:
    """Normaliza un término para agrupar variantes equivalentes: minúsculas,
    sin acentos/diacríticos, espacios colapsados. Devuelve None si queda
    demasiado corto (< 2 chars) para ser útil."""
    if not texto:
        return None
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    norm = " ".join(sin_acentos.lower().split())
    if len(norm) < MIN_LEN:
        return None
    return norm[:MAX_LEN]


class SearchLogBody(BaseModel):
    query: str = Field(..., max_length=400)
    result_count: int = Field(0, ge=0)


@router.post("/search-log")
@limiter.limit("60/minute")
def log_search(body: SearchLogBody, request: Request):
    """Registra una búsqueda del catálogo público. Best-effort: si el término
    queda muy corto al normalizar, se ignora en silencio."""
    texto = body.query.strip()[:MAX_LEN]
    norm = normalizar_busqueda(texto)
    if not norm:
        return {"ok": True, "logged": False}
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO search_queries (query_text, query_norm, result_count) "
            "VALUES (?, ?, ?)",
            (texto, norm, max(0, int(body.result_count))),
        )
        conn.commit()
        return {"ok": True, "logged": True}
    finally:
        conn.close()


@router.get("/admin/busquedas")
def admin_busquedas(request: Request, dias: Optional[int] = None):
    """Analítica de búsquedas para el back-office (sección Estadísticas).

    Devuelve dos listas agrupadas por término normalizado:
    - `top`:  lo más buscado (veces, ejemplo del texto crudo, última vez,
              máximo de resultados que llegó a dar).
    - `zero`: términos que NUNCA dieron resultados (demanda no cubierta).

    `dias` opcional acota la ventana (ej. 30 = último mes); sin él, histórico
    completo."""
    require_admin(request)

    where = ""
    params: list = []
    if dias and dias > 0:
        where = "WHERE created_at >= ?"
        params.append(datetime.utcnow() - timedelta(days=dias))

    conn = get_db()
    try:
        top = conn.execute(
            f"""
            SELECT query_norm,
                   COUNT(*)          AS veces,
                   MAX(query_text)   AS texto,
                   MAX(result_count) AS max_resultados,
                   MAX(created_at)   AS ultima
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
    finally:
        conn.close()
