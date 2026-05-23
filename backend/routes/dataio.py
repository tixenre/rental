"""routes/dataio.py — Endpoint admin para descargar JSONs del catálogo.

Expone:
    GET /api/admin/dataio/export?entity=all|<entity_name>
        - entity=all → application/zip con todos los JSONs
        - entity=marcas (o cualquier entidad) → application/json individual

Import por endpoint queda fuera del MVP. Para importar, usar el CLI:
    python -m backend.dataio.cli import
"""

import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from admin_guard import require_admin
from database import get_db
from dataio import orchestrator
from dataio.paths import ENTITY_ORDER

router = APIRouter()


@router.get("/admin/dataio/entities")
def list_entities(_admin: dict = Depends(require_admin)):
    """Lista las entidades disponibles para export."""
    return {"entities": list(ENTITY_ORDER)}


@router.get("/admin/dataio/export")
def export_dataio(
    entity: str = Query("all", description="Entidad a exportar o 'all' para ZIP"),
    _admin: dict = Depends(require_admin),
):
    """Exporta una entidad como JSON, o todas como ZIP.

    `entity=all` devuelve `application/zip` con un archivo por entidad.
    `entity=<nombre>` devuelve `application/json` con los datos de esa entidad.
    """
    conn = get_db()
    try:
        if entity == "all":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for e in ENTITY_ORDER:
                    rows = orchestrator.export_entity(conn, e)
                    zf.writestr(
                        f"{e}.json",
                        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                    )
            buf.seek(0)
            ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            return StreamingResponse(
                buf,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="catalogo-{ts}.zip"'
                },
            )

        if entity not in ENTITY_ORDER:
            raise HTTPException(
                400,
                f"Entidad inválida: {entity!r}. Válidas: {list(ENTITY_ORDER)}",
            )

        rows = orchestrator.export_entity(conn, entity)
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return JSONResponse(
            content=rows,
            headers={
                "Content-Disposition": f'attachment; filename="{entity}-{ts}.json"'
            },
        )
    finally:
        conn.close()
