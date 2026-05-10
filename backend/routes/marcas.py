"""
routes/marcas.py — CRUD de marcas (brands).
"""

from fastapi import APIRouter
from database import get_db, row_to_dict

router = APIRouter()


@router.get("/marcas")
def list_marcas():
    """Lista todas las marcas ordenadas alfabéticamente."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, nombre, logo_url, created_at, updated_at
            FROM marcas
            ORDER BY nombre ASC
        """).fetchall()
        marcas = [row_to_dict(r) for r in rows]
        return {"items": marcas}
    finally:
        conn.close()
