"""Routes de facturación electrónica ARCA (#1139).

Fase 1: solo estado/configuración (sin emitir).
Fases siguientes: emisión, PDF, NC.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from database import get_db
from routes.auth import require_admin
from services.facturacion.config import cert_cargado

router = APIRouter()

_EMISORES = ("pablo", "santini")


@router.get("/admin/facturacion/estado")
def estado_facturacion(request: Request):
    """Estado de configuración de los dos emisores ARCA.

    Devuelve CUIT, PtoVta y si el certificado está cargado en ENV (sí/no).
    Nunca expone el secreto.
    Requiere sesión de admin.
    """
    require_admin(request)

    with get_db() as conn:
        keys = [f"afip_{e}_{campo}" for e in _EMISORES for campo in ("cuit", "ptovta")]
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
            (keys,),
        ).fetchall()
    kv = {r["key"]: r["value"] for r in rows}

    from config import settings as app_settings
    ambiente = "produccion" if app_settings.is_production else "homologacion"

    return {
        "ambiente": ambiente,
        "emisores": {
            emisor: {
                "cuit": kv.get(f"afip_{emisor}_cuit", "") or "",
                "ptovta": kv.get(f"afip_{emisor}_ptovta", "") or "",
                "cert_cargado": cert_cargado(emisor),
            }
            for emisor in _EMISORES
        },
    }
