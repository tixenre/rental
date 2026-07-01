"""Documentos PDF del cliente (#501 — extraído del god-module `routes/cliente_portal.py`).

Remito / contrato / albarán del pedido del cliente (preview HTML embebible + PDF).
Registra sus rutas en el router compartido del paquete `routes.cliente_portal`.
Los helpers/constantes compartidos (`require_cliente`, `_proyectar`,
`_documentos_disponibles`, `_ITEM_CAMPOS_DOC`, `_COMP_CAMPOS_DOC`) viven en `core`.
"""
from fastapi import Request, HTTPException
from fastapi.responses import Response

from database import get_db, row_to_dict
from identity import direccion_validada, nombre_validado
from pdf import _pedido_html, _albaran_html, _contrato_html, _render_pdf, _pedido_filename
from routes.cliente_portal.core import (
    router, require_cliente, _proyectar, _documentos_disponibles,
    _ITEM_CAMPOS_DOC, _COMP_CAMPOS_DOC,
)


# ── Documentos PDF (cliente) ──────────────────────────────────────────────────

def _load_pedido_para_pdf(conn, pedido_id: int, cliente_id: int) -> dict:
    """Carga el pedido validando ownership y rellena items + componentes."""
    row = conn.execute(
        "SELECT * FROM alquileres WHERE id = %s AND cliente_id = %s",
        (pedido_id, cliente_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Pedido no encontrado")
    pedido = row_to_dict(row)

    from routes.alquileres import _get_alquiler_items
    pedido["items"] = [
        {
            **_proyectar(it, _ITEM_CAMPOS_DOC),
            "componentes": [_proyectar(c, _COMP_CAMPOS_DOC) for c in it["componentes"]],
        }
        for it in _get_alquiler_items(conn, pedido_id)
    ]

    # Datos del cliente para el contrato + Factura A si aplica.
    # Nombre y dirección: preferir datos RENAPER si la identidad fue verificada.
    cli = conn.execute(
        """SELECT nombre, apellido, email, telefono, direccion, cuit,
                  perfil_impuestos, razon_social, domicilio_fiscal,
                  email_facturacion,
                  dni, nombre_renaper, apellido_renaper, direccion_renaper
           FROM clientes WHERE id = %s""",
        (cliente_id,),
    ).fetchone()
    if cli:
        c = row_to_dict(cli)
        # Nombre/dirección: preferí RENAPER si está verificado (fuente única en identity).
        pedido["cliente_nombre"] = nombre_validado(c) or f"{c.get('nombre', '')} {c.get('apellido', '')}".strip()
        pedido["cliente_email"] = c.get("email")
        pedido["cliente_telefono"] = c.get("telefono")
        pedido["cliente_direccion"] = direccion_validada(c) or c.get("direccion")
        pedido["cliente_cuit"] = c.get("cuit")
        pedido["cliente_dni"] = c.get("dni")
        pedido["cliente_perfil_impuestos"] = c.get("perfil_impuestos")
        pedido["cliente_razon_social"] = c.get("razon_social")
        pedido["cliente_domicilio_fiscal"] = c.get("domicilio_fiscal")
        pedido["cliente_email_facturacion"] = c.get("email_facturacion")

    # Desglose canónico (bruto/descuento/neto/IVA) — misma fuente de verdad
    # que el admin: el PDF sólo pinta lo que devuelve `calcular_total`.
    from routes.alquileres import _enriquecer_pedido_con_total
    _enriquecer_pedido_con_total(conn, pedido)

    return pedido


# Los documentos se generan al vuelo y deben reflejar siempre el estado actual
# del pedido. Sin esto el navegador cachea la URL estática y sirve un PDF viejo
# tras editar el pedido (mismo criterio que `_DOC_NO_CACHE` en alquileres.py).
_DOC_NO_CACHE = {"Cache-Control": "no-store, max-age=0"}

# El preview HTML se muestra dentro de un <iframe> del portal (mismo origen). El
# middleware global pone X-Frame-Options: DENY, que bloquea TODO embedding —
# incluido el propio — y deja el preview en blanco. SAMEORIGIN permite que el
# portal embeba su propio documento sin abrir framing a terceros.
_DOC_PREVIEW_HEADERS = {**_DOC_NO_CACHE, "X-Frame-Options": "SAMEORIGIN"}


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', **_DOC_NO_CACHE},
    )


def _doc_response(
    html_str: str,
    pdf_filename: str,
    format: str,
):
    """Devuelve HTML inline (preview) o PDF (download) según `format`.

    Issue #106: el cliente puede previsualizar el documento antes de
    descargar el PDF. HTML es más liviano y mejor UX mobile.
    """
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_str, headers=_DOC_PREVIEW_HEADERS)
    return None  # caller sigue con PDF


async def _doc_response_or_pdf(html_str: str, pdf_filename: str, format: str, page_size=None):
    preview = _doc_response(html_str, pdf_filename, format)
    if preview is not None:
        return preview
    pdf_bytes = await _render_pdf(html_str, page_size=page_size)
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{pdf_filename}"', **_DOC_NO_CACHE},
    )


@router.get("/api/cliente/pedidos/{id}/remito.pdf")
@router.get("/api/cliente/pedidos/{id}/remito")
async def cliente_pedido_remito(id: int, request: Request, format: str = "pdf"):
    """Remito del pedido. format=pdf (default, download) o html (preview)."""
    session = require_cliente(request)
    with get_db() as conn:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    if not _documentos_disponibles(pedido.get("estado", ""))["remito"]:
        raise HTTPException(403, "El remito estará disponible cuando confirmemos el pedido.")
    return await _doc_response_or_pdf(
        _pedido_html(pedido), _pedido_filename(pedido), format
    )


@router.get("/api/cliente/pedidos/{id}/contrato.pdf")
@router.get("/api/cliente/pedidos/{id}/contrato")
async def cliente_pedido_contrato(id: int, request: Request, format: str = "pdf"):
    """Contrato del pedido. format=pdf (default) o html (preview)."""
    session = require_cliente(request)
    with get_db() as conn:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    if not _documentos_disponibles(pedido.get("estado", ""))["contrato"]:
        raise HTTPException(403, "El contrato estará disponible cuando confirmemos el pedido.")
    return await _doc_response_or_pdf(
        _contrato_html(pedido), _pedido_filename(pedido, doc="contrato"), format
    )


@router.get("/api/cliente/pedidos/{id}/albaran.pdf")
@router.get("/api/cliente/pedidos/{id}/albaran")
async def cliente_pedido_albaran(id: int, request: Request, format: str = "pdf"):
    """Albarán del pedido. format=pdf (default) o html (preview)."""
    session = require_cliente(request)
    with get_db() as conn:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    if not _documentos_disponibles(pedido.get("estado", ""))["albaran"]:
        raise HTTPException(403, "El albarán estará disponible al momento de la entrega.")
    return await _doc_response_or_pdf(
        _albaran_html(pedido), _pedido_filename(pedido, doc="albaran"), format
    )


@router.get("/api/cliente/pedidos/{id}/factura.pdf")
@router.get("/api/cliente/pedidos/{id}/factura")
async def cliente_pedido_factura(
    id: int, request: Request, format: str = "pdf", layout: str = "clasica"
):
    """Factura ARCA del pedido. A diferencia de remito/contrato/albarán, no
    depende del estado del pedido sino de si la factura ya fue emitida —
    aparece como documento recién ahí, no antes (y desaparece si se anula).
    `layout`: 'clasica' (default) · 'celular' (para compartir por WhatsApp) · 'formal'."""
    session = require_cliente(request)
    if layout not in ("clasica", "celular", "formal"):
        layout = "clasica"
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM alquileres WHERE id = %s AND cliente_id = %s",
            (id, session["cliente_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Pedido no encontrado")

        from services.facturacion.repo import get_factura_principal_emitida
        factura = get_factura_principal_emitida(id, conn)
        if factura is None:
            raise HTTPException(404, "Todavía no hay factura para este pedido.")

        from services.facturacion.engine import _get_pedido
        from services.facturacion.pdf import factura_html, factura_filename, page_size_for_layout
        pedido_data = _get_pedido(conn, id)
        html_str = factura_html(factura, pedido_data, layout=layout)

    return await _doc_response_or_pdf(
        html_str, factura_filename(factura, layout=layout), format,
        page_size=page_size_for_layout(layout),
    )

