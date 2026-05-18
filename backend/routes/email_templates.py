"""CRUD admin de plantillas de email + endpoints de preview/test.

Endpoints (todos bajo /api/admin):
- GET  /email-templates                  → lista
- GET  /email-templates/{key}            → detalle
- PATCH /email-templates/{key}           → editar
- POST /email-templates/{key}/preview    → renderiza con context (no envía)
- POST /email-templates/{key}/test       → envía mail real al `to` que pasa el admin
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db, row_to_dict
from services.email import render_template, send_email

logger = logging.getLogger(__name__)
router = APIRouter()


# Sample context para previews — refleja los placeholders comunes que
# pueden aparecer en cualquier template. Pisable por el caller.
_PREVIEW_CONTEXT: dict[str, Any] = {
    "cliente_nombre": "Pérez, Juan",
    "cliente_email": "juan@ejemplo.com",
    "cliente_telefono": "+598 99 123 456",
    "numero_pedido": "1234",
    "fecha_desde": "lun 20 may",
    "fecha_hasta": "vie 24 may",
    "total": "$ 12.500",
    "items_html": "<ul><li>Sony FX3 × 1</li><li>RØDE NTG × 2</li></ul>",
    "items_text": "- Sony FX3 × 1\n- RØDE NTG × 2",
    "admin_url": "https://rambla.com.uy/admin/pedidos/1234",
}


class TemplateUpdate(BaseModel):
    subject: str
    body_html: str
    body_text: str


class TemplatePreview(BaseModel):
    context: Optional[dict[str, Any]] = None


class TemplateTest(BaseModel):
    to: str
    context: Optional[dict[str, Any]] = None


@router.get("/admin/email-templates")
def list_templates(request: Request):
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT key, subject, updated_at, updated_by FROM email_templates ORDER BY key"
        ).fetchall()
        return {"items": [row_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/admin/email-templates/{key}")
def get_template(key: str, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT key, subject, body_html, body_text, updated_at, updated_by
            FROM email_templates WHERE key = ?
            """,
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Template '{key}' no encontrado")
        return row_to_dict(row)
    finally:
        conn.close()


@router.patch("/admin/email-templates/{key}")
def update_template(key: str, data: TemplateUpdate, request: Request):
    session = require_admin(request)
    if not data.subject.strip():
        raise HTTPException(400, "subject no puede estar vacío")
    if not data.body_html.strip() and not data.body_text.strip():
        raise HTTPException(400, "body_html y body_text no pueden estar ambos vacíos")
    conn = get_db()
    try:
        cur = conn.execute(
            """
            UPDATE email_templates
            SET subject = ?, body_html = ?, body_text = ?,
                updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE key = ?
            RETURNING key, subject, body_html, body_text, updated_at, updated_by
            """,
            (data.subject, data.body_html, data.body_text,
             session.get("email", "unknown"), key),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"Template '{key}' no encontrado")
        conn.commit()
        return row_to_dict(row)
    finally:
        conn.close()


@router.post("/admin/email-templates/{key}/preview")
def preview_template(key: str, data: TemplatePreview = Body(default=TemplatePreview()),
                     request: Request = None):
    require_admin(request)
    ctx = {**_PREVIEW_CONTEXT, **(data.context or {})}
    try:
        return render_template(key, ctx)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        # Errores de Jinja (sintaxis, variable indefinida con strict) caen acá.
        logger.warning("preview falló para %s: %s", key, e)
        raise HTTPException(400, f"Error renderizando template: {e}")


@router.post("/admin/email-templates/{key}/test")
def test_template(key: str, data: TemplateTest, request: Request):
    require_admin(request)
    if not data.to or "@" not in data.to:
        raise HTTPException(400, "Dirección 'to' inválida")
    ctx = {**_PREVIEW_CONTEXT, **(data.context or {})}
    result = send_email(template_key=key, to=data.to, context=ctx, alquiler_id=None)
    return result
