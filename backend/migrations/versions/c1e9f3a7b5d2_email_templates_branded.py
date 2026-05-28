"""email_templates_branded: contenido lindo y completo para los 4 mails

Reescribe el CONTENIDO de las 4 plantillas (saludo cálido, resumen con tabla de
items, botón CTA, próximos pasos). El layout branded (header con logo, colores,
footer) lo pone el shell común en `services/email/service.py` (`_wrap_email_html`),
así que los bodies guardan solo el contenido editable.

GUARDA: solo actualiza filas con `updated_by = 'system:migration'` — es decir,
plantillas que nunca editó un admin desde la UI (el PATCH setea updated_by al
email del admin). Hoy ninguna fue editada (los mails nunca se activaron).

Esta migración es la fuente única del copy actual; para instalaciones nuevas el
end-state es correcto vía el chain (a4e8c2b9d710 siembra → e7c3a9f5d1b8 → ésta).

Revision ID: c1e9f3a7b5d2
Revises: e7c3a9f5d1b8
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c1e9f3a7b5d2"
down_revision: Union[str, Sequence[str], None] = "e7c3a9f5d1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _btn(url_var: str, label: str) -> str:
    """Botón CTA bulletproof (table-based, inline) para clientes de mail."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0;">'
        '<tr><td style="border-radius:8px;background:#FAB428;">'
        f'<a href="{{{{ {url_var} }}}}" style="display:inline-block;padding:12px 24px;'
        'font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;'
        f'color:#2a251e;text-decoration:none;">{label}</a></td></tr></table>'
    )


_H = 'style="margin:0 0 12px;font-size:19px;font-weight:bold;color:#2a251e;"'
_LBL = 'style="margin:18px 0 4px;color:#8a8378;font-size:12px;text-transform:uppercase;letter-spacing:.05em;"'
_TOTAL = 'style="margin:6px 0 4px;font-size:16px;color:#2a251e;"'
_MUTED = 'style="margin:18px 0 0;color:#6b6457;font-size:14px;"'

# key → (subject, body_html, body_text)
_TEMPLATES = {
    "pedido_creado_cliente": (
        "Recibimos tu pedido #{{ numero_pedido }} — Rambla Rental",
        f"""<p {_H}>¡Recibimos tu pedido!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, gracias por tu pedido <strong>#{{{{ numero_pedido }}}}</strong>. Lo estamos revisando y te confirmamos la disponibilidad a la brevedad.</p>
<p {_LBL}>Tu pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {_TOTAL}><strong>Total estimado: {{{{ total }}}}</strong></p>
{_btn("portal_url", "Ver mi pedido")}
<p {_MUTED}>Cuando confirmemos el pedido vas a poder descargar el <strong>remito</strong> y el <strong>contrato</strong> desde tu portal. ¿Tenés alguna duda? Respondé este mail.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>""",
        """Hola {{ cliente_nombre }},

Recibimos tu pedido #{{ numero_pedido }}. Lo estamos revisando y te confirmamos la disponibilidad a la brevedad.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}

{{ items_text }}

Total estimado: {{ total }}

Seguí tu pedido en el portal: {{ portal_url }}
Cuando lo confirmemos vas a poder descargar el remito y el contrato desde ahí.

¿Dudas? Respondé este mail.
— El equipo de Rambla""",
    ),
    "pedido_confirmado_cliente": (
        "Tu pedido #{{ numero_pedido }} está confirmado",
        f"""<p {_H}>¡Tu pedido está confirmado!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, confirmamos tu pedido <strong>#{{{{ numero_pedido }}}}</strong>. Ya está todo listo.</p>
<p {_LBL}>Tu pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {_TOTAL}><strong>Total: {{{{ total }}}}</strong></p>
{_btn("portal_url", "Ver mi pedido")}
<p {_MUTED}>Ya podés descargar el <strong>remito</strong> y el <strong>contrato</strong> desde tu portal. Te esperamos en el galpón el día del retiro.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>""",
        """Hola {{ cliente_nombre }},

Tu pedido #{{ numero_pedido }} está confirmado.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}

{{ items_text }}

Total: {{ total }}

Ya podés descargar el remito y el contrato desde tu portal: {{ portal_url }}
Te esperamos en el galpón el día del retiro.

— El equipo de Rambla""",
    ),
    "pedido_creado_admin": (
        "Nuevo pedido #{{ numero_pedido }} — {{ cliente_nombre }}",
        f"""<p {_H}>Entró un pedido nuevo</p>
<p style="margin:0 0 4px;"><strong>#{{{{ numero_pedido }}}}</strong> de <strong>{{{{ cliente_nombre }}}}</strong></p>
<p style="margin:0 0 4px;color:#6b6457;font-size:14px;">{{{{ cliente_email }}}}{{% if cliente_telefono %}} · {{{{ cliente_telefono }}}}{{% endif %}}</p>
<p {_LBL}>Pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {_TOTAL}><strong>Total: {{{{ total }}}}</strong></p>
{{% if notas %}}<p style="margin:8px 0 0;"><strong>Notas:</strong> {{{{ notas }}}}</p>{{% endif %}}
{_btn("admin_url", "Ver en el back-office")}""",
        """Entró un pedido nuevo.

#{{ numero_pedido }} de {{ cliente_nombre }}
Contacto: {{ cliente_email }}{% if cliente_telefono %} · {{ cliente_telefono }}{% endif %}

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}

{{ items_text }}

Total: {{ total }}
{% if notas %}Notas: {{ notas }}{% endif %}

Ver en el back-office: {{ admin_url }}""",
    ),
    "recordatorio_retiro": (
        "Mañana retirás tu pedido #{{ numero_pedido }} — Rambla Rental",
        f"""<p {_H}>¡Mañana es el día!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, te recordamos que <strong>mañana ({{{{ fecha_desde }}}})</strong> retirás tu pedido <strong>#{{{{ numero_pedido }}}}</strong>.</p>
{{{{ items_html|safe }}}}
{_btn("portal_url", "Ver mi pedido")}
<p {_MUTED}>Te esperamos en el galpón. Si necesitás reagendar, escribinos cuanto antes.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>""",
        """Hola {{ cliente_nombre }},

Mañana ({{ fecha_desde }}) retirás tu pedido #{{ numero_pedido }}.

{{ items_text }}

Te esperamos en el galpón. Si necesitás reagendar, escribinos cuanto antes.
Tu portal: {{ portal_url }}

— El equipo de Rambla""",
    ),
}


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    for key, (subject, body_html, body_text) in _TEMPLATES.items():
        op.execute(
            f"""
            UPDATE email_templates
            SET subject = {_q(subject)},
                body_html = {_q(body_html)},
                body_text = {_q(body_text)},
                updated_by = 'system:migration'
            WHERE key = {_q(key)} AND updated_by = 'system:migration'
            """
        )


def downgrade() -> None:
    # No-op: el copy viejo queda en el historial de git (migraciones previas).
    # No revertimos para no pisar el contenido nuevo con el viejo a ciegas.
    pass
