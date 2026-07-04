"""Routes de facturación electrónica ARCA (#1139).

Fase 1: estado/configuración.
Fase 3: POST /alquileres/{id}/facturar (engine + PDF).
Fases 4-5: listados, PDF download, NC.
Fase 7: CRUD emisores (credenciales dinámicas, cifradas).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from database import get_db
from auth.guards import require_admin
from arca_fe import ArcaBusinessError, ArcaError, ArcaResponseError
from rate_limit import limiter, ADMIN_WRITE_LIMIT
# Reusado tal cual de routes/contabilidad.py (misma auditoría 2026-07-02, #1184/#1209):
# traduce UniqueViolation/NumericValueOutOfRange a 400 limpio en vez de que el
# handler global exponga el mensaje interno de Postgres.
from routes.contabilidad import map_pg_errors

router = APIRouter()


def _status_for_arca_error(exc: ArcaError) -> int:
    """Mapea cada subtipo de `ArcaError` a un status HTTP que refleje qué
    pasó realmente, en vez de un 503 genérico para todo (antes cada adapter
    de `services/facturacion/` aplanaba todo a RuntimeError→503 — atrapaba
    los 4 tipos por igual, pero el front nunca distinguía "AFIP caída,
    reintentá" de "AFIP rechazó esto por una regla de negocio, corregí algo").

    - ArcaBusinessError → 422: AFIP contestó y rechazó por una regla de
      negocio real (CAE 'R', bloqueo tipo RG 3990-E) — no es transitorio,
      reintentar no cambia nada.
    - ArcaResponseError → 502: AFIP contestó pero en forma inesperada/
      imparseable — problema de integración (la categoría donde hubiera
      caído, ruidosamente, el bug de `personaReturn`), no del cliente.
    - ArcaAuthError/ArcaNetworkError/ArcaError (base) → 503: falla de auth,
      relación no delegada, o red — transitorio o de configuración, tiene
      sentido reintentar. Mismo status que ya usaban RuntimeError acá."""
    if isinstance(exc, ArcaBusinessError):
        return 422
    if isinstance(exc, ArcaResponseError):
        return 502
    return 503  # ArcaAuthError, ArcaNetworkError, o ArcaError base


# ---------------------------------------------------------------------------
# GET /admin/facturacion/estado
# ---------------------------------------------------------------------------


@router.get("/admin/facturacion/estado")
def estado_facturacion(request: Request):
    """Estado de configuración: ambiente activo + lista de emisores (sin
    secretos) + cuándo se actualizaron por última vez los catálogos de ARCA
    (doc_tipo/concepto/condición IVA receptor — ver services.facturacion.catalogos)."""
    require_admin(request)

    from config import settings as app_settings
    ambiente = "produccion" if app_settings.is_production else "homologacion"

    from services.facturacion.catalogos import ultimo_refresco
    from services.facturacion.emisores_repo import list_emisores
    with get_db() as conn:
        emisores = list_emisores(conn)
        catalogos_actualizados_at = ultimo_refresco(conn)

    return {
        "ambiente": ambiente,
        "emisores": [_emisor_to_dict(e) for e in emisores],
        "catalogos_actualizados_at": catalogos_actualizados_at,
    }


@router.post("/admin/arca/catalogos/refrescar")
def refrescar_catalogos_arca(request: Request):
    """Actualiza los catálogos de ARCA (doc_tipo/concepto/condición IVA
    receptor) que se muestran en el PDF de la factura — las etiquetas salen
    de acá, nunca de una traducción escrita a mano en el código."""
    require_admin(request)

    from services.facturacion.catalogos import refrescar_catalogos

    with get_db() as conn:
        try:
            resultado = refrescar_catalogos(conn)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except ArcaError as e:
            raise HTTPException(_status_for_arca_error(e), str(e))
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        conn.commit()

    return {
        "ok": True,
        "doc_tipo": len(resultado["doc_tipo"]),
        "concepto": len(resultado["concepto"]),
        "condicion_iva_receptor": len(resultado["condicion_iva_receptor"]),
    }


# ---------------------------------------------------------------------------
# GET /admin/arca/padron/{cuit} — autocompletar razón social/domicilio/IVA
# ---------------------------------------------------------------------------


@router.get("/admin/arca/padron/{cuit}")
def consultar_padron(cuit: str, request: Request):
    """Autocompleta razón social/domicilio/condición IVA desde el padrón de
    ARCA (ws_sr_constancia_inscripcion) — mismo autocompletado que hace el
    facturador oficial al tipear un CUIT. Best-effort: nunca un error HTTP —
    el formulario sigue siendo editable a mano. `resolver_persona` levanta
    RuntimeError para cualquier cosa que no sea un CUIT encontrado (ya no
    hay un "sin datos" silencioso) — se muestra tal cual, es más útil para
    diagnosticar que un genérico "sin datos"."""
    require_admin(request)

    from services.facturacion.padron import resolver_persona
    with get_db() as conn:
        try:
            persona = resolver_persona(cuit, conn)
        except RuntimeError as e:
            return {"encontrado": False, "motivo": str(e)}

    return {
        "encontrado": True,
        "razon_social": persona.razon_social,
        "nombre": persona.nombre,
        "apellido": persona.apellido,
        "domicilio": persona.domicilio,
        "condicion_iva": persona.condicion_iva,
        "estado_clave": persona.estado_clave,
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
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
def crear_emisor(request: Request, body: dict):
    """Crea un nuevo emisor. No incluye cert/clave (se suben aparte)."""
    require_admin(request)
    nombre = (body.get("nombre") or "").strip()
    cuit = (body.get("cuit") or "").strip()
    pto_vta = body.get("pto_vta")
    condicion_iva = (body.get("condicion_iva") or "").strip()
    razon_social = (body.get("razon_social") or "").strip() or None
    domicilio = (body.get("domicilio") or "").strip() or None
    iibb = (body.get("iibb") or "").strip() or None
    inicio_actividades = (body.get("inicio_actividades") or "").strip() or None
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
                domicilio=domicilio,
                iibb=iibb,
                inicio_actividades=inicio_actividades,
                notas=notas,
            )
            from services.facturacion.emisores_repo import get_by_id
            emisor = get_by_id(emisor_id, conn)
            conn.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _emisor_to_dict(emisor)


@router.put("/admin/emisores-arca/{emisor_id}")
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
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
                domicilio=body.get("domicilio"),
                iibb=body.get("iibb"),
                inicio_actividades=body.get("inicio_actividades"),
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
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
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


@router.get("/admin/emisores-arca/{emisor_id}/cert-info")
def info_cert_emisor(emisor_id: int, request: Request):
    """Metadata del certificado cargado (Subject, Nº de serie, vigencia) —
    NUNCA el PEM/clave privada. Sirve para comparar 1 a 1 contra el
    "Computador Fiscal" que figura delegado en el Administrador de
    Relaciones de Clave Fiscal de ARCA: si el número de serie no coincide,
    la relación fue delegada a un certificado DISTINTO del que este emisor
    usa hoy para autenticar — causa real de prod: ARCA respondía sin datos
    ni motivo aunque la relación estuviera bien delegada, porque estaba
    delegada al certificado viejo."""
    require_admin(request)

    from cryptography import x509

    from services.facturacion.emisores_repo import get_cert_pem

    try:
        with get_db() as conn:
            cert_pem, _ = get_cert_pem(emisor_id, conn)
    except ValueError as e:
        raise HTTPException(400, str(e))

    cert = x509.load_pem_x509_certificate(cert_pem)
    return {
        "subject": cert.subject.rfc4514_string(),
        "numero_serie": format(cert.serial_number, "X"),
        "vigente_desde": cert.not_valid_before_utc.date().isoformat(),
        "vigente_hasta": cert.not_valid_after_utc.date().isoformat(),
    }


@router.get("/admin/emisores-arca/{emisor_id}/puntos-venta")
def consultar_puntos_venta_emisor(emisor_id: int, request: Request):
    """Consulta a ARCA (WSFE `FEParamGetPtosVenta`) los puntos de venta
    habilitados de este emisor — para validar/elegir el número en vez de
    cargarlo a mano y descubrir recién al pedir el primer CAE que estaba mal.
    Requiere que el emisor ya tenga cert cargado."""
    require_admin(request)

    from services.facturacion.emisores_repo import get_by_id
    from services.facturacion.puntos_venta import consultar_puntos_venta

    with get_db() as conn:
        emisor = get_by_id(emisor_id, conn)
        if emisor is None:
            raise HTTPException(404, "Emisor no encontrado")
        try:
            resultado = consultar_puntos_venta(emisor.nombre, conn)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except ArcaError as e:
            raise HTTPException(_status_for_arca_error(e), str(e))
        except RuntimeError as e:
            raise HTTPException(503, str(e))

    return {"puntos_venta": resultado["habilitados"], "excluidos": resultado["excluidos"]}


@router.delete("/admin/emisores-arca/{emisor_id}", status_code=204)
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
def desactivar_emisor(emisor_id: int, request: Request):
    """Marca el emisor como inactivo (soft-delete). Las facturas existentes no se tocan."""
    require_admin(request)
    from services.facturacion.emisores_repo import delete_emisor
    with get_db() as conn:
        delete_emisor(emisor_id, conn)
        conn.commit()


# ---------------------------------------------------------------------------
# GET /alquileres/{id}/facturar/preview
# ---------------------------------------------------------------------------


@router.get("/alquileres/{pedido_id}/facturar/preview")
def preview_factura(pedido_id: int, request: Request):
    """Arma el comprobante y calcula sus importes SIN emitir — para que el
    admin confirme los datos antes de pedir un CAE real (irreversible)."""
    require_admin(request)

    try:
        from services.facturacion.engine import previsualizar_factura
        with get_db() as conn:
            return previsualizar_factura(pedido_id, conn)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except ArcaError as e:
        raise HTTPException(_status_for_arca_error(e), str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


# ---------------------------------------------------------------------------
# POST /alquileres/{id}/facturar
# ---------------------------------------------------------------------------


@router.post("/alquileres/{pedido_id}/facturar")
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
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
    except ArcaError as e:
        raise HTTPException(_status_for_arca_error(e), str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return _factura_to_dict(factura)


# ---------------------------------------------------------------------------
# POST /facturas/{id}/nota-credito
# ---------------------------------------------------------------------------


@router.post("/facturas/{factura_id}/nota-credito")
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
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
    except ArcaError as e:
        raise HTTPException(_status_for_arca_error(e), str(e))
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


def _factura_html_o_404(factura_id: int, conn, layout: str = "celular"):
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
    try:
        html_str = factura_html(factura, pedido, layout=layout)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return factura, html_str


@router.get("/facturas/{factura_id}/pdf")
async def descargar_pdf_factura(
    factura_id: int, request: Request, format: str = "pdf", layout: str = "celular"
):
    """PDF de una factura, renderizado on-demand. `format=html` devuelve el preview
    (mismo patrón que Contrato/Presupuesto/Albarán en routes/alquileres/documentos.py).
    `layout`: 'celular' (default de Rambla — compacta 4:5) · 'clasica' (réplica
    oficial AFIP/ARCA, A4) · 'formal' (A4, identidad de la celular)."""
    require_admin(request)

    if layout not in ("clasica", "celular", "formal"):
        layout = "celular"

    with get_db() as conn:
        factura, html_str = _factura_html_o_404(factura_id, conn, layout=layout)
        if format == "html":
            cert_pem = key_pem = None
        else:
            from services.facturacion.pdf_seguridad import get_or_create_signing_cert
            cert_pem, key_pem = get_or_create_signing_cert(conn)

    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_str, headers=_DOC_NO_CACHE)

    from pdf import _render_pdf
    from services.facturacion.pdf import factura_filename, page_size_for_layout
    from services.facturacion.pdf_seguridad import asegurar_pdf
    try:
        pdf_bytes = await _render_pdf(html_str, page_size=page_size_for_layout(layout))
        # asegurar_pdf firma con pyhanko, cuyo sign_pdf sync internamente hace
        # asyncio.run() — explota si se llama directo desde acá (ya estamos
        # dentro del loop de FastAPI). to_thread lo corre en un thread aparte,
        # sin loop activo, donde ese asyncio.run() interno sí puede crear el suyo.
        pdf_bytes = await asyncio.to_thread(asegurar_pdf, pdf_bytes, cert_pem, key_pem)
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
@limiter.limit(ADMIN_WRITE_LIMIT)
# Sin @map_pg_errors: es async y el decorator no le hace `await` a la corrutina
# (mismo motivo por el que `subir_comprobante`, también async, en contabilidad.py
# no lo lleva) — no hay escritura propensa a UniqueViolation acá de todos modos.
async def enviar_mail_factura(factura_id: int, request: Request):
    """Envía el PDF de la factura (renderizado on-demand) al email del cliente del pedido."""
    require_admin(request)

    from services.email import send_raw_email, Attachment
    from services.facturacion.pdf_seguridad import get_or_create_signing_cert

    with get_db() as conn:
        factura, html_str = _factura_html_o_404(factura_id, conn)
        cert_pem, key_pem = get_or_create_signing_cert(conn)

        # Email del cliente: está en el pedido
        row = conn.execute(
            """
            SELECT c.email, c.nombre, c.apellido
            FROM alquileres a
            JOIN clientes c ON c.id = a.cliente_id
            WHERE a.id = %s
            """,
            (factura.pedido_id,),
        ).fetchone()

    if not row or not row["email"]:
        raise HTTPException(400, "El pedido no tiene cliente con email asociado")

    email_cliente = row["email"]
    nombre_cliente = f"{row['nombre'] or ''} {row['apellido'] or ''}".strip() or email_cliente

    from pdf import _render_pdf
    from services.facturacion.pdf import factura_filename
    from services.facturacion.pdf_seguridad import asegurar_pdf
    try:
        pdf_bytes = await _render_pdf(html_str)
        pdf_bytes = await asyncio.to_thread(asegurar_pdf, pdf_bytes, cert_pem, key_pem)
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
        attachments=[Attachment(filename=filename, content=pdf_bytes, mimetype="application/pdf")],
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
        "domicilio": e.domicilio,
        "iibb": e.iibb,
        "inicio_actividades": e.inicio_actividades,
        "notas": e.notas,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
