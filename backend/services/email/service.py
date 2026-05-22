"""Entry point del servicio de email.

`send_email()` es la única función pública para mandar mails desde el
resto del backend. Internamente:
1. Lee `app_settings` para resolver `email_from` (con fallback a env var).
2. Lee el template de `email_templates`.
3. Renderiza subject + html + text con Jinja2 (autoescape para html).
4. Llama al backend (resend/smtp/test).
5. Loggea TODO en `emails_log` — éxito o fallo.

NUNCA propaga excepciones del provider — los triggers (crear pedido,
confirmar pedido) no deben fallar si el mail no se envía.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import jinja2

from database import get_db

logger = logging.getLogger(__name__)

_jinja_html = jinja2.Environment(autoescape=True, undefined=jinja2.Undefined)
_jinja_text = jinja2.Environment(autoescape=False, undefined=jinja2.Undefined)

# Templates que solo deben enviarse UNA vez por pedido (idempotency).
# El recordatorio_retiro tiene su propio UNIQUE INDEX en DB; estos los
# chequeamos via SELECT antes de enviar para evitar dobles envíos por
# doble-click, retries, o reentradas al endpoint de confirmación.
_IDEMPOTENT_PER_PEDIDO = {
    "pedido_creado_cliente",
    "pedido_confirmado_cliente",
}


def _resolve_from(conn) -> str:
    """from address: env EMAIL_FROM > app_settings.email_from > fallback."""
    env_val = os.environ.get("EMAIL_FROM", "").strip()
    if env_val:
        return env_val
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("email_from",),
    ).fetchone()
    if row and row["value"]:
        return row["value"]
    return "Rambla Rental <noreply@rambla.com.uy>"


def get_admin_to() -> Optional[str]:
    """`to` para notif al admin: env EMAIL_ADMIN_TO > app_settings.email_admin_to."""
    env_val = os.environ.get("EMAIL_ADMIN_TO", "").strip()
    if env_val:
        return env_val
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("email_admin_to",),
        ).fetchone()
        return row["value"] if row and row["value"] else None
    finally:
        conn.close()


def render_template(
    template_key: str,
    context: dict[str, Any],
) -> dict[str, str]:
    """Renderiza una plantilla del catálogo con el contexto dado.
    Devuelve {subject, html, text}. Útil para preview sin enviar."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT subject, body_html, body_text FROM email_templates WHERE key = ?",
            (template_key,),
        ).fetchone()
        if not row:
            raise ValueError(f"Template '{template_key}' no existe")
        # subject + text: sin autoescape (texto plano).
        subject = _jinja_text.from_string(row["subject"]).render(**context)
        text = _jinja_text.from_string(row["body_text"]).render(**context)
        # html: con autoescape — variables de usuario quedan escapadas, pero
        # las que vienen con .html() o {{ x|safe }} pasan literales.
        html = _jinja_html.from_string(row["body_html"]).render(**context)
        return {"subject": subject, "html": html, "text": text}
    finally:
        conn.close()


def send_email(
    template_key: str,
    to: str,
    context: dict[str, Any],
    alquiler_id: Optional[int] = None,
) -> dict[str, Any]:
    """Envía un mail renderizando una plantilla. Loggea SIEMPRE en
    `emails_log`. NUNCA propaga excepciones del provider.

    Devuelve un dict {ok, provider, provider_id?, error?, log_id} útil para
    el endpoint de test del admin.
    """
    from . import get_backend
    from .base import EmailBackendError

    if not to or "@" not in to:
        logger.warning("send_email: 'to' inválido (%r), abortando", to)
        return {"ok": False, "error": "destinatario inválido"}

    conn = get_db()
    try:
        # Idempotency: si este template ya se envió OK para este pedido,
        # no lo mandamos de nuevo (doble-click en confirmar, retries, etc).
        if template_key in _IDEMPOTENT_PER_PEDIDO and alquiler_id:
            existing = conn.execute(
                """
                SELECT id FROM emails_log
                 WHERE template_key = ? AND alquiler_id = ? AND status = 'sent'
                 LIMIT 1
                """,
                (template_key, alquiler_id),
            ).fetchone()
            if existing:
                logger.info(
                    "send_email: skip duplicado tpl=%s alquiler=%s log_id=%s",
                    template_key, alquiler_id, existing["id"],
                )
                return {"ok": True, "skipped": True, "log_id": existing["id"]}

        try:
            rendered = render_template(template_key, context)
        except Exception as e:
            logger.error("Render falló para %s: %s", template_key, e, exc_info=True)
            log_id = _insert_log(
                conn, to=to, subject=f"[render error] {template_key}",
                template_key=template_key, alquiler_id=alquiler_id,
                status="failed", provider="(none)", provider_id=None,
                error=f"render error: {e}",
            )
            conn.commit()
            return {"ok": False, "error": str(e), "log_id": log_id}

        from_addr = _resolve_from(conn)
        backend = get_backend()

        try:
            result = backend.send(
                to=to,
                subject=rendered["subject"],
                html=rendered["html"],
                text=rendered["text"],
                from_addr=from_addr,
            )
        except EmailBackendError as e:
            logger.error("Envío falló (%s → %s): %s", template_key, to, e)
            log_id = _insert_log(
                conn, to=to, subject=rendered["subject"],
                template_key=template_key, alquiler_id=alquiler_id,
                status="failed", provider=backend.name, provider_id=None,
                error=str(e),
            )
            conn.commit()
            return {"ok": False, "error": str(e), "provider": backend.name, "log_id": log_id}

        log_id = _insert_log(
            conn, to=to, subject=rendered["subject"],
            template_key=template_key, alquiler_id=alquiler_id,
            status="sent", provider=result.provider, provider_id=result.provider_id,
            error=None,
        )
        conn.commit()
        logger.info(
            "send_email ok: tpl=%s to=%s provider=%s id=%s",
            template_key, to, result.provider, result.provider_id,
        )
        return {
            "ok": True,
            "provider": result.provider,
            "provider_id": result.provider_id,
            "log_id": log_id,
        }
    except Exception as e:
        # Captura amplia para garantizar el contrato "nunca propaga".
        logger.exception("send_email: error inesperado: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "error": f"error interno: {e}"}
    finally:
        conn.close()


def _insert_log(
    conn,
    *,
    to: str,
    subject: str,
    template_key: str,
    alquiler_id: Optional[int],
    status: str,
    provider: str,
    provider_id: Optional[str],
    error: Optional[str],
) -> Optional[int]:
    """INSERT en emails_log; devuelve el id generado. Devuelve None si el
    INSERT falla por race condition con el UNIQUE INDEX (recordatorio_retiro
    duplicado) — en ese caso es OK que se ignore, ya hay otro envío exitoso.
    """
    try:
        cur = conn.execute(
            """
            INSERT INTO emails_log
                (to_addr, subject, template_key, alquiler_id,
                 status, provider, provider_id, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (to, subject, template_key, alquiler_id,
             status, provider, provider_id, error),
        )
        row = cur.fetchone()
        return row["id"] if row else None
    except Exception as e:
        # El UNIQUE INDEX parcial del recordatorio puede tirar IntegrityError
        # si el job corre 2 veces — es comportamiento deseado (idempotencia).
        logger.warning("emails_log INSERT falló (idempotencia?): %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
