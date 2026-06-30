"""Routes de facturación electrónica ARCA (#1139).

Fase 1: estado/configuración (sin emitir).
Fase 3: POST /alquileres/{id}/facturar (engine + PDF).
Fases 4-5: listados, PDF download, mail, NC.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from database import get_db
from routes.auth import require_admin
from services.facturacion.config import cert_cargado

router = APIRouter()

_EMISORES = ("pablo", "santini")


# ---------------------------------------------------------------------------
# GET /admin/facturacion/estado (Fase 1)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# POST /alquileres/{id}/facturar (Fase 3)
# ---------------------------------------------------------------------------


@router.post("/alquileres/{pedido_id}/facturar")
def facturar_pedido(pedido_id: int, request: Request):
    """Emite (o devuelve la vigente) la factura electrónica para el pedido.

    Idempotente: si ya existe una factura 'emitida' o 'pendiente' para el pedido,
    la devuelve sin volver a llamar a ARCA.

    Requiere sesión de admin. El estado del pedido debe ser ≥ 'confirmado'.
    """
    require_admin(request)

    try:
        from services.facturacion.engine import emitir_factura
        session = getattr(request.state, "session", None)
        emitido_por = (session or {}).get("email") if session else None
        factura = emitir_factura(pedido_id, emitido_por=emitido_por)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return _factura_to_dict(factura)


# ---------------------------------------------------------------------------
# POST /facturas/{id}/nota-credito (Fase 5 — adelantamos el handler)
# ---------------------------------------------------------------------------


@router.post("/facturas/{factura_id}/nota-credito")
def nota_credito(factura_id: int, request: Request):
    """Emite una Nota de Crédito que anula la factura indicada.

    Idempotente: si ya existe una NC vigente para esta factura, la devuelve.
    Requiere sesión de admin.
    """
    require_admin(request)

    try:
        from services.facturacion.engine import emitir_nota_credito
        session = getattr(request.state, "session", None)
        emitido_por = (session or {}).get("email") if session else None
        nc = emitir_nota_credito(factura_id, emitido_por=emitido_por)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return _factura_to_dict(nc)


# ---------------------------------------------------------------------------
# GET /alquileres/{id}/facturas (Fase 4)
# ---------------------------------------------------------------------------


@router.get("/alquileres/{pedido_id}/facturas")
def facturas_del_pedido(pedido_id: int, request: Request):
    """Lista las facturas de un pedido (incluye NC)."""
    require_admin(request)

    from services.facturacion.repo import list_facturas
    with get_db() as conn:
        facturas = list_facturas(conn, pedido_id=pedido_id)
    return [_factura_to_dict(f) for f in facturas]


# ---------------------------------------------------------------------------
# GET /admin/facturas — listado global con filtros (Fase 4)
# ---------------------------------------------------------------------------


@router.get("/admin/facturas")
def listar_facturas(
    request: Request,
    emisor: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Listado global de facturas con filtros. Requiere sesión de admin."""
    require_admin(request)

    from services.facturacion.repo import list_facturas
    with get_db() as conn:
        facturas = list_facturas(
            conn,
            emisor=emisor or None,
            estado=estado or None,
            desde=desde or None,
            hasta=hasta or None,
            limit=limit,
            offset=offset,
        )

    dicts = [_factura_to_dict(f) for f in facturas]
    total_imp_total = sum(d["imp_total"] for d in dicts if d.get("estado") == "emitida")
    return {
        "facturas": dicts,
        "total_imp_total": total_imp_total,
        "count": len(dicts),
    }


# ---------------------------------------------------------------------------
# GET /facturas/{id}/pdf — descarga del PDF de la factura (Fase 4)
# ---------------------------------------------------------------------------


@router.get("/facturas/{factura_id}/pdf")
def descargar_pdf_factura(factura_id: int, request: Request):
    """Descarga el PDF de una factura desde R2. Requiere sesión de admin."""
    require_admin(request)

    from services.facturacion.repo import get_by_id
    with get_db() as conn:
        factura = get_by_id(factura_id, conn)

    if factura is None:
        raise HTTPException(404, "Factura no encontrada")
    if not factura.pdf_key:
        raise HTTPException(404, "PDF no disponible aún")

    try:
        from services.media.storage import get as storage_get
        pdf_bytes = storage_get(factura.pdf_key)
    except Exception as e:
        raise HTTPException(503, f"No se pudo obtener el PDF: {e}")

    cbte_tipo_letra = {1: "A", 3: "A", 6: "B", 8: "B", 11: "C", 13: "C"}.get(
        factura.cbte_tipo, "X"
    )
    es_nc = factura.cbte_tipo in (3, 8, 13)
    prefijo = "NC" if es_nc else "Factura"
    filename = f"{prefijo}-{cbte_tipo_letra}-{factura.pto_vta:05d}-{factura.cbte_nro or 0:08d}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------


def _factura_to_dict(f) -> dict:
    if f is None:
        return {}
    return {
        "id": f.id,
        "pedido_id": f.pedido_id,
        "emisor": f.emisor,
        "ambiente": f.ambiente,
        "cbte_tipo": f.cbte_tipo,
        "pto_vta": f.pto_vta,
        "cbte_nro": f.cbte_nro,
        "cae": f.cae,
        "cae_vto": str(f.cae_vto) if f.cae_vto else None,
        "doc_tipo": f.doc_tipo,
        "doc_nro": f.doc_nro,
        "condicion_iva_receptor": f.condicion_iva_receptor,
        "imp_neto": f.imp_neto,
        "imp_iva": f.imp_iva,
        "imp_total": f.imp_total,
        "moneda": f.moneda,
        "cliente_cuit": f.cliente_cuit,
        "razon_social": f.razon_social,
        "qr_payload": f.qr_payload,
        "pdf_key": f.pdf_key,
        "estado": f.estado,
        "nota_credito_de": f.nota_credito_de,
        "errores": f.errores,
        "fecha_emision": f.fecha_emision.isoformat() if f.fecha_emision else None,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "created_by": f.created_by,
    }
