"""email_infra: tablas email_templates + emails_log

Crea la infraestructura para envío de emails transaccionales:
- email_templates: subject + body_html + body_text, editables desde admin UI.
- emails_log: registro de cada envío con status, provider_id y error.
- UNIQUE INDEX parcial para idempotencia del recordatorio D-1 (evita duplicado
  si el scheduler corre dos veces).

Seed inicial con 4 plantillas default:
- pedido_creado_cliente
- pedido_creado_admin
- pedido_confirmado_cliente
- recordatorio_retiro

Revision ID: a4e8c2b9d710
Revises: d2a4f6b8e1c3
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a4e8c2b9d710"
down_revision: Union[str, Sequence[str], None] = "d2a4f6b8e1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEFAULTS = [
    (
        "pedido_creado_cliente",
        "Recibimos tu pedido — Rambla Rental",
        """<p>Hola {{ cliente_nombre }},</p>
<p>Gracias por tu pedido en <strong>Rambla Rental</strong>. Te lo confirmamos pronto.</p>
<p><strong>Fechas:</strong> {{ fecha_desde }} → {{ fecha_hasta }}<br>
<strong>Total:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p>Cualquier consulta respondé este mail.</p>
<p>— El equipo de Rambla</p>""",
        """Hola {{ cliente_nombre }},

Gracias por tu pedido en Rambla Rental. Te lo confirmamos pronto.

Fechas: {{ fecha_desde }} → {{ fecha_hasta }}
Total: {{ total }}

{{ items_text }}

Cualquier consulta respondé este mail.

— El equipo de Rambla""",
    ),
    (
        "pedido_creado_admin",
        "Nuevo pedido #{{ numero_pedido }} — {{ cliente_nombre }}",
        """<p>Entró un pedido nuevo.</p>
<p><strong>Cliente:</strong> {{ cliente_nombre }} ({{ cliente_email }})<br>
<strong>Fechas:</strong> {{ fecha_desde }} → {{ fecha_hasta }}<br>
<strong>Total:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p><a href="{{ admin_url }}">Ver en back-office</a></p>""",
        """Entró un pedido nuevo.

Cliente: {{ cliente_nombre }} ({{ cliente_email }})
Fechas: {{ fecha_desde }} → {{ fecha_hasta }}
Total: {{ total }}

{{ items_text }}

Ver en back-office: {{ admin_url }}""",
    ),
    (
        "pedido_confirmado_cliente",
        "Tu pedido #{{ numero_pedido }} está confirmado",
        """<p>Hola {{ cliente_nombre }},</p>
<p>Tu pedido <strong>#{{ numero_pedido }}</strong> está <strong>confirmado</strong>.</p>
<p><strong>Retiro:</strong> {{ fecha_desde }}<br>
<strong>Devolución:</strong> {{ fecha_hasta }}<br>
<strong>Total:</strong> {{ total }}</p>
<p>{{ items_html }}</p>
<p>Te esperamos en el galpón el día del retiro. Cualquier cambio avisanos cuanto antes.</p>
<p>— El equipo de Rambla</p>""",
        """Hola {{ cliente_nombre }},

Tu pedido #{{ numero_pedido }} está confirmado.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}
Total: {{ total }}

{{ items_text }}

Te esperamos en el galpón el día del retiro. Cualquier cambio avisanos cuanto antes.

— El equipo de Rambla""",
    ),
    (
        "recordatorio_retiro",
        "Recordatorio — retiro mañana de tu pedido #{{ numero_pedido }}",
        """<p>Hola {{ cliente_nombre }},</p>
<p>Mañana ({{ fecha_desde }}) tenés el retiro de tu pedido <strong>#{{ numero_pedido }}</strong>.</p>
<p>{{ items_html }}</p>
<p>Te esperamos en el galpón. Si necesitás reagendar, escribinos cuanto antes.</p>
<p>— El equipo de Rambla</p>""",
        """Hola {{ cliente_nombre }},

Mañana ({{ fecha_desde }}) tenés el retiro de tu pedido #{{ numero_pedido }}.

{{ items_text }}

Te esperamos en el galpón. Si necesitás reagendar, escribinos cuanto antes.

— El equipo de Rambla""",
    ),
]


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            key         TEXT PRIMARY KEY,
            subject     TEXT NOT NULL,
            body_html   TEXT NOT NULL,
            body_text   TEXT NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by  TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS emails_log (
            id           BIGSERIAL PRIMARY KEY,
            to_addr      TEXT NOT NULL,
            subject      TEXT NOT NULL,
            template_key TEXT NOT NULL,
            alquiler_id  INTEGER REFERENCES alquileres(id) ON DELETE SET NULL,
            status       TEXT NOT NULL,
            provider     TEXT NOT NULL,
            provider_id  TEXT,
            error        TEXT,
            sent_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_emails_log_alquiler ON emails_log(alquiler_id)")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_log_recordatorio
        ON emails_log(alquiler_id, template_key)
        WHERE template_key = 'recordatorio_retiro' AND status = 'sent'
    """)

    # Seed plantillas default (idempotente, ON CONFLICT DO NOTHING).
    for key, subject, body_html, body_text in _DEFAULTS:
        op.execute(
            f"""
            INSERT INTO email_templates (key, subject, body_html, body_text, updated_by)
            VALUES (
                {_q(key)}, {_q(subject)}, {_q(body_html)}, {_q(body_text)},
                'system:migration'
            )
            ON CONFLICT (key) DO NOTHING
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_emails_log_recordatorio")
    op.execute("DROP INDEX IF EXISTS idx_emails_log_alquiler")
    op.execute("DROP TABLE IF EXISTS emails_log")
    op.execute("DROP TABLE IF EXISTS email_templates")


def _q(s: str) -> str:
    """Escape simple para strings literales en SQL — duplica comillas simples."""
    return "'" + s.replace("'", "''") + "'"
