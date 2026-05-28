"""email_copy: link al portal + nota de documentos en los mails al cliente

Mejora el contenido de dos plantillas de email al cliente:
- pedido_creado_cliente: número de pedido en el asunto + bloque "seguí el
  estado en tu portal" + aclaración de que el remito y el contrato se podrán
  descargar desde ahí cuando confirmemos.
- pedido_confirmado_cliente: línea "ya podés descargar el remito y el contrato
  desde tu portal".

GUARDA: cada UPDATE sólo se aplica si la fila sigue **idéntica** al default
original sembrado en `a4e8c2b9d710_email_infra.py`. Si el admin editó la
plantilla desde `/admin/email-templates`, no se toca. Hoy no hay ediciones (los
mails nunca se activaron), pero la guarda lo deja a prueba de balas.

Para instalaciones nuevas el end-state es correcto sin tocar la migración
histórica: `a4e8c2b9d710` siembra el default viejo y luego ésta lo actualiza
(el WHERE matchea exactamente lo recién sembrado). Esta migración es la fuente
única del copy nuevo.

Revision ID: e7c3a9f5d1b8
Revises: d2e4f6a8c1b3
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e7c3a9f5d1b8"
down_revision: Union[str, Sequence[str], None] = "d2e4f6a8c1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── pedido_creado_cliente ───────────────────────────────────────────────────
_CREADO_OLD_SUBJECT = "Recibimos tu pedido — Rambla Rental"
_CREADO_OLD_HTML = """<p>Hola {{ cliente_nombre }},</p>
<p>Gracias por tu pedido en <strong>Rambla Rental</strong>. Te lo confirmamos pronto.</p>
<p><strong>Fechas:</strong> {{ fecha_desde }} → {{ fecha_hasta }}<br>
<strong>Total:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p>Cualquier consulta respondé este mail.</p>
<p>— El equipo de Rambla</p>"""
_CREADO_OLD_TEXT = """Hola {{ cliente_nombre }},

Gracias por tu pedido en Rambla Rental. Te lo confirmamos pronto.

Fechas: {{ fecha_desde }} → {{ fecha_hasta }}
Total: {{ total }}

{{ items_text }}

Cualquier consulta respondé este mail.

— El equipo de Rambla"""

_CREADO_NEW_SUBJECT = "Recibimos tu pedido #{{ numero_pedido }} — Rambla Rental"
_CREADO_NEW_HTML = """<p>Hola {{ cliente_nombre }},</p>
<p>Recibimos tu pedido <strong>#{{ numero_pedido }}</strong> en <strong>Rambla Rental</strong>. Lo estamos revisando y te confirmamos la disponibilidad a la brevedad.</p>
<p><strong>Fechas:</strong> {{ fecha_desde }} → {{ fecha_hasta }}<br>
<strong>Total estimado:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p>Seguí el estado de tu pedido en tu portal: <a href="{{ portal_url }}">{{ portal_url }}</a>. Cuando lo confirmemos vas a poder descargar el <strong>remito</strong> y el <strong>contrato</strong> desde ahí.</p>
<p>Cualquier consulta respondé este mail.</p>
<p>— El equipo de Rambla</p>"""
_CREADO_NEW_TEXT = """Hola {{ cliente_nombre }},

Recibimos tu pedido #{{ numero_pedido }} en Rambla Rental. Lo estamos revisando y te confirmamos la disponibilidad a la brevedad.

Fechas: {{ fecha_desde }} → {{ fecha_hasta }}
Total estimado: {{ total }}

{{ items_text }}

Seguí el estado de tu pedido en tu portal: {{ portal_url }}
Cuando lo confirmemos vas a poder descargar el remito y el contrato desde ahí.

Cualquier consulta respondé este mail.

— El equipo de Rambla"""


# ── pedido_confirmado_cliente ───────────────────────────────────────────────
_CONFIRMADO_SUBJECT = "Tu pedido #{{ numero_pedido }} está confirmado"
_CONFIRMADO_OLD_HTML = """<p>Hola {{ cliente_nombre }},</p>
<p>Tu pedido <strong>#{{ numero_pedido }}</strong> está <strong>confirmado</strong>.</p>
<p><strong>Retiro:</strong> {{ fecha_desde }}<br>
<strong>Devolución:</strong> {{ fecha_hasta }}<br>
<strong>Total:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p>Te esperamos en el galpón el día del retiro. Cualquier cambio avisanos cuanto antes.</p>
<p>— El equipo de Rambla</p>"""
_CONFIRMADO_OLD_TEXT = """Hola {{ cliente_nombre }},

Tu pedido #{{ numero_pedido }} está confirmado.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}
Total: {{ total }}

{{ items_text }}

Te esperamos en el galpón el día del retiro. Cualquier cambio avisanos cuanto antes.

— El equipo de Rambla"""

_CONFIRMADO_NEW_HTML = """<p>Hola {{ cliente_nombre }},</p>
<p>Tu pedido <strong>#{{ numero_pedido }}</strong> está <strong>confirmado</strong>.</p>
<p><strong>Retiro:</strong> {{ fecha_desde }}<br>
<strong>Devolución:</strong> {{ fecha_hasta }}<br>
<strong>Total:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p>Ya podés descargar el <strong>remito</strong> y el <strong>contrato</strong> desde tu portal: <a href="{{ portal_url }}">{{ portal_url }}</a></p>
<p>Te esperamos en el galpón el día del retiro. Cualquier cambio avisanos cuanto antes.</p>
<p>— El equipo de Rambla</p>"""
_CONFIRMADO_NEW_TEXT = """Hola {{ cliente_nombre }},

Tu pedido #{{ numero_pedido }} está confirmado.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}
Total: {{ total }}

{{ items_text }}

Ya podés descargar el remito y el contrato desde tu portal: {{ portal_url }}

Te esperamos en el galpón el día del retiro. Cualquier cambio avisanos cuanto antes.

— El equipo de Rambla"""


def _q(s: str) -> str:
    """Escape simple para strings literales en SQL — duplica comillas simples."""
    return "'" + s.replace("'", "''") + "'"


def _guarded_update(
    key: str,
    new_subject: str, new_html: str, new_text: str,
    old_subject: str, old_html: str, old_text: str,
) -> None:
    """Actualiza el template SÓLO si sigue idéntico a `old_*` (default original).
    No pisa ediciones del admin."""
    op.execute(
        f"""
        UPDATE email_templates
        SET subject = {_q(new_subject)},
            body_html = {_q(new_html)},
            body_text = {_q(new_text)},
            updated_by = 'system:migration'
        WHERE key = {_q(key)}
          AND subject = {_q(old_subject)}
          AND body_html = {_q(old_html)}
          AND body_text = {_q(old_text)}
        """
    )


def upgrade() -> None:
    _guarded_update(
        "pedido_creado_cliente",
        _CREADO_NEW_SUBJECT, _CREADO_NEW_HTML, _CREADO_NEW_TEXT,
        _CREADO_OLD_SUBJECT, _CREADO_OLD_HTML, _CREADO_OLD_TEXT,
    )
    _guarded_update(
        "pedido_confirmado_cliente",
        _CONFIRMADO_SUBJECT, _CONFIRMADO_NEW_HTML, _CONFIRMADO_NEW_TEXT,
        _CONFIRMADO_SUBJECT, _CONFIRMADO_OLD_HTML, _CONFIRMADO_OLD_TEXT,
    )


def downgrade() -> None:
    # Simétrico: revierte sólo si la fila sigue idéntica al copy nuevo.
    _guarded_update(
        "pedido_creado_cliente",
        _CREADO_OLD_SUBJECT, _CREADO_OLD_HTML, _CREADO_OLD_TEXT,
        _CREADO_NEW_SUBJECT, _CREADO_NEW_HTML, _CREADO_NEW_TEXT,
    )
    _guarded_update(
        "pedido_confirmado_cliente",
        _CONFIRMADO_SUBJECT, _CONFIRMADO_OLD_HTML, _CONFIRMADO_OLD_TEXT,
        _CONFIRMADO_SUBJECT, _CONFIRMADO_NEW_HTML, _CONFIRMADO_NEW_TEXT,
    )
