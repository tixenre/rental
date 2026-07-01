"""Routes de facturación electrónica ARCA (#1139).

Fase 1: estado/configuración.
Fase 3: POST /alquileres/{id}/facturar (engine + PDF).
Fases 4-5: listados, PDF download, NC.
Fase 7: CRUD emisores (credenciales dinámicas, cifradas).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from database import get_db
from auth.guards import require_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /admin/facturacion/estado
# ---------------------------------------------------------------------------


@router.get("/admin/facturacion/estado")
def estado_facturacion(request: Request):
    """Estado de configuración: ambiente activo + lista de emisores (sin secretos)."""
    require_admin(request)

    from config import settings as app_settings
    ambiente = "produccion" if app_settings.is_production else "homologacion"

    from services.facturacion.emisores_repo import list_emisores
    with get_db() as conn:
        emisores = list_emisores(conn)

    return {
        "ambiente": ambiente,
        "emisores": [_emisor_to_dict(e) for e in emisores],
    }


# ---------------------------------------------------------------------------
# CRUD emisores (Fase 7)
# ---------------------------------------------------------------------------


@router.get("/admin/emisores-arca")
def listar_emisores(request: Request):
    """Lista todos los emisores configurados (sin cert/clave)."""
    require_admin(request)
    from services.facturacion.emisores_repo import list_emisores
    with get_db() as conn:
        return [_emisor_to_dict(e) for e in list_emisores(conn)]


@router.post("/admin/emisores-arca", status_code=201)
def crear_emisor(request: Request, body: dict):
    """Crea un nuevo emisor. No incluye cert/clave (se suben aparte)."""
    require_admin(request)
    nombre = (body.get("nombre") or "").strip()
    cuit = (body.get("cuit") or "").strip()
    pto_vta = body.get("pto_vta")
    condicion_iva = (body.get("condicion_iva") or "").strip()
    razon_social = (body.get("razon_social") or "").strip() or None
    notas = (body.get("notas") or "").strip() or None

    if not nombre or not cuit or not pto_vta or not condicion_iva:
        raise HTTPException(400, "nombre, cuit, pto_vta y condicion_iva son obligatorios")

    try:
        pto_vta_int = int(pto_vta)
    except (TypeError, ValueError):
        raise HTTPException(400, "pto_vta debe ser un número entero")

    from services.facturacion.emisores_repo import create_emisor
    try:
        with get_db() as conn:
            emisor_id = create_emisor(
                conn,
                nombre=nombre,
                cuit=cuit,
                pto_vta=pto_vta_int,
                condicion_iva=condicion_iva,
                razon_social=razon_social,
                notas=notas,
            )
            from services.facturacion.emisores_repo import get_by_id
            emisor = get_by_id(emisor_id, conn)
            conn.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _emisor_to_dict(emisor)


@router.put("/admin/emisores-arca/{emisor_id}")
def actualizar_emisor(emisor_id: int, request: Request, body: dict):
    """Actualiza datos del emisor (nombre, CUIT, pto_vta, condicion_iva, activo, notas)."""
    require_admin(request)

    from services.facturacion.emisores_repo import update_emisor, get_by_id
    try:
        with get_db() as conn:
            update_emisor(
                emisor_id,
                conn,
                nombre=body.get("nombre"),
                cuit=body.get("cuit"),
                pto_vta=body.get("pto_vta"),
                condicion_iva=body.get("condicion_iva"),
                activo=body.get("activo"),
                razon_social=body.get("razon_social"),
                notas=body.get("notas"),
            )
            emisor = get_by_id(emisor_id, conn)
            conn.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    if emisor is None:
        raise HTTPException(404, "Emisor no encontrado")
    return _emisor_to_dict(emisor)


@router.post("/admin/emisores-arca/{emisor_id}/cert")
def cargar_cert(emisor_id: int, request: Request, body: dict):
    """Sube y cifra el certificado + clave privada PEM del emisor.

    Body: { "cert_pem": "-----BEGIN CERTIFICATE-----\\n...", "key_pem": "-----BEGIN PRIVATE KEY-----\\n..." }
    Nunca devuelve el cert/clave; solo confirma que se guardó.
    """
    require_admin(request)

    cert_pem_str = (body.get("cert_pem") or "").strip()
    key_pem_str = (body.get("key_pem") or "").strip()

    if not cert_pem_str or not key_pem_str:
        raise HTTPException(400, "cert_pem y key_pem son obligatorios")
    if "BEGIN CERTIFICATE" not in cert_pem_str:
        raise HTTPException(400, "cert_pem no parece un certificado PEM válido")
    if "PRIVATE KEY" not in key_pem_str:
        raise HTTPException(400, "key_pem no parece una clave privada PEM válida")

    from services.facturacion.emisores_repo import set_cert, get_by_id
    try:
        with get_db() as conn:
            set_cert(
                emisor_id,
                conn,
                cert_pem=cert_pem_str.encode(),
                key_pem=key_pem_str.encode(),
            )
            emisor = get_by_id(emisor_id, conn)
            conn.commit()
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    if emisor is None:
        raise HTTPException(404, "Emisor no encontrado")
    return {"ok": True, "cert_cargado": emisor.cert_cargado}


@router.delete("/admin/emisores-arca/{emisor_id}", status_code=204)
def desactivar_emisor(emisor_id: int, request: Request):
    """Marca el emisor como inactivo (soft-delete). Las facturas existentes no se tocan."""
    require_admin(request)
    from services.facturacion.emisores_repo import delete_emisor
    with get_db() as conn:
        delete_emisor(emisor_id, conn)
        conn.commit()


# ---------------------------------------------------------------------------
# POST /alquileres/{id}/facturar
# ---------------------------------------------------------------------------


@router.post("/alquileres/{pedido_id}/facturar")
def facturar_pedido(pedido_id: int, request: Request):
    """Emite (o devuelve la vigente) la factura electrónica para el pedido.

    Idempotente: si ya existe una factura 'emitida' o 'pendiente' para el pedido,
    la devuelve sin volver a llamar a ARCA.
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
# POST /facturas/{id}/nota-credito
# ---------------------------------------------------------------------------


@router.post("/facturas/{factura_id}/nota-credito")
def nota_credito(factura_id: int, request: Request):
    """Emite una Nota de Crédito que anula la factura indicada. Idempotente."""
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
# GET /alquileres/{id}/facturas
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
# GET /admin/facturas
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
# GET /facturas/{id}/pdf — siempre on-demand (no se guarda ni se cachea)
# ---------------------------------------------------------------------------

_DOC_NO_CACHE = {"Cache-Control": "no-store, max-age=0"}


def _factura_html_o_404(factura_id: int, conn, layout: str = "clasica"):
    """Carga la factura + renderiza su HTML al vuelo. La factura no cambia una
    vez emitida, así que no hace falta guardar el PDF: regenerar da lo mismo."""
    from services.facturacion.repo import get_by_id
    from services.facturacion.engine import _get_pedido
    from services.facturacion.pdf import factura_html

    factura = get_by_id(factura_id, conn)
    if factura is None:
        raise HTTPException(404, "Factura no encontrada")
    if factura.estado != "emitida":
        raise HTTPException(400, "Solo se pueden ver/descargar/enviar facturas emitidas")

    pedido = _get_pedido(conn, factura.pedido_id)
    return factura, factura_html(factura, pedido, layout=layout)


@router.get("/facturas/{factura_id}/pdf")
async def descargar_pdf_factura(
    factura_id: int, request: Request, format: str = "pdf", layout: str = "clasica"
):
    """PDF de una factura, renderizado on-demand. `format=html` devuelve el preview
    (mismo patrón que Contrato/Presupuesto/Albarán en routes/alquileres/documentos.py).
    `layout`: 'clasica' (default, réplica oficial AFIP/ARCA) · 'celular' (compacta,
    para compartir por WhatsApp) · 'formal' (A4, identidad de la celular)."""
    require_admin(request)

    if layout not in ("clasica", "celular", "formal"):
        layout = "clasica"

    with get_db() as conn:
        factura, html_str = _factura_html_o_404(factura_id, conn, layout=layout)

    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_str, headers=_DOC_NO_CACHE)

    from pdf import _render_pdf
    from services.facturacion.pdf import factura_filename, page_size_for_layout
    try:
        pdf_bytes = await _render_pdf(html_str, page_size=page_size_for_layout(layout))
    except Exception as e:
        raise HTTPException(503, f"No se pudo generar el PDF: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{factura_filename(factura, layout=layout)}"',
            **_DOC_NO_CACHE,
        },
    )


# ---------------------------------------------------------------------------
# POST /facturas/{id}/enviar-mail
# ---------------------------------------------------------------------------


@router.post("/facturas/{factura_id}/enviar-mail")
async def enviar_mail_factura(factura_id: int, request: Request):
    """Envía el PDF de la factura (renderizado on-demand) al email del cliente del pedido."""
    require_admin(request)

    from services.email import send_raw_email, Attachment

    with get_db() as conn:
        factura, html_str = _factura_html_o_404(factura_id, conn)

        # Email del cliente: está en el pedido
        row = conn.execute(
            """
            SELECT c.owner_email, c.nombre, c.apellido
            FROM alquileres a
            JOIN clientes c ON c.id = a.cliente_id
            WHERE a.id = %s
            """,
            (factura.pedido_id,),
        ).fetchone()

    if not row or not row["owner_email"]:
        raise HTTPException(400, "El pedido no tiene cliente con email asociado")

    email_cliente = row["owner_email"]
    nombre_cliente = f"{row['nombre'] or ''} {row['apellido'] or ''}".strip() or email_cliente

    from pdf import _render_pdf
    from services.facturacion.pdf import factura_filename
    try:
        pdf_bytes = await _render_pdf(html_str)
    except Exception as e:
        raise HTTPException(503, f"No se pudo generar el PDF para el mail: {e}")

    cbte_tipo_letra = {1: "A", 3: "A", 6: "B", 8: "B", 11: "C", 13: "C"}.get(
        factura.cbte_tipo, "X"
    )
    filename = factura_filename(factura)

    nro = f"{factura.pto_vta:05d}-{factura.cbte_nro or 0:08d}"
    subject = f"Tu factura {cbte_tipo_letra} Nº {nro} — Rambla Rental"
    body_html = f"""
<p>Hola {nombre_cliente},</p>
<p>Te enviamos la factura electrónica correspondiente a tu alquiler. La encontrás adjunta a este mail.</p>
<p><strong>Factura {cbte_tipo_letra} Nº {nro}</strong><br>
CAE: {factura.cae or "—"}<br>
Total: ${factura.imp_total:,.2f}</p>
<p>Cualquier consulta no dudes en escribirnos.</p>
<p>Saludos,<br>Rambla Rental</p>
"""
    text = f"Hola {nombre_cliente}, adjuntamos tu Factura {cbte_tipo_letra} Nº {nro}. CAE: {factura.cae}. Total: ${factura.imp_total:,.2f}."

    result = send_raw_email(
        to=email_cliente,
        subject=subject,
        body_html=body_html,
        text=text,
        attachments=[Attachment(filename=filename, content=pdf_bytes, content_type="application/pdf")],
        alquiler_id=factura.pedido_id,
        log_key="factura_arca",
    )

    if not result.get("ok"):
        raise HTTPException(503, f"No se pudo enviar el mail: {result.get('error')}")

    return {"ok": True, "to": email_cliente}


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


def _emisor_to_dict(e) -> dict:
    return {
        "id": e.id,
        "nombre": e.nombre,
        "cuit": e.cuit,
        "pto_vta": e.pto_vta,
        "condicion_iva": e.condicion_iva,
        "cert_cargado": e.cert_cargado,
        "activo": e.activo,
        "razon_social": e.razon_social,
        "notas": e.notas,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
