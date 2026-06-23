"""GET /api/admin/server-errors — historial de errores del servidor."""

import logging

from fastapi import APIRouter, Request, HTTPException

from database import get_db, row_to_dict

router = APIRouter(tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/admin/server-errors")
def listar_server_errors(request: Request, limite: int = 200):
    """Lista los últimos errores no manejados capturados por el handler global."""
    try:
        from admin_guard import require_admin
        require_admin(request)

        limite = max(1, min(limite, 500))

        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, route, error_type, message, traceback, request_id, created_at
                FROM server_errors
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()

        errores = [row_to_dict(r) for r in rows]
        return {"errores": errores, "total": len(errores)}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("listar_server_errors falló")
        raise HTTPException(500, detail=f"{type(exc).__name__}: {exc}")
