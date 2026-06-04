"""email_confirmado_boton_calendario: botón "Agregar al calendario" en el mail
de pedido confirmado.

Suma al cuerpo del template `pedido_confirmado_cliente` un botón secundario que
linkea a Google Calendar (variable `{{ gcal_url }}`, que arma
`routes/alquileres._pedido_email_context`). Complementa al adjunto `.ics` para
clientes de mail que no renderizan la tarjeta del adjunto.

GUARDA (igual que c1e9f3a7b5d2): solo actualiza la fila si
`updated_by = 'system:migration'` — es decir, plantillas que nunca editó un admin
desde la UI. Si el dueño ya customizó el template, no se pisa.

El botón va envuelto en `{% if gcal_url %}` → si la reserva no tiene fecha (no hay
URL), no se muestra.

Revision ID: f2a4c6e8b0d1
Revises: p1q2r3s4t5u6
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f2a4c6e8b0d1"
down_revision: Union[str, Sequence[str], None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _btn(url_var: str, label: str) -> str:
    """Botón CTA primario (amber), table-based + inline (bulletproof en mail)."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0;">'
        '<tr><td style="border-radius:8px;background:#FAB428;">'
        f'<a href="{{{{ {url_var} }}}}" style="display:inline-block;padding:12px 24px;'
        'font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;'
        f'color:#2a251e;text-decoration:none;">{label}</a></td></tr></table>'
    )


def _btn_secondary(url_var: str, label: str) -> str:
    """Botón CTA secundario (contorno) para no competir con el primario."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">'
        '<tr><td style="border-radius:8px;border:1px solid #d9d3c7;">'
        f'<a href="{{{{ {url_var} }}}}" style="display:inline-block;padding:11px 22px;'
        'font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;'
        f'color:#2a251e;text-decoration:none;">{label}</a></td></tr></table>'
    )


_H = 'style="margin:0 0 12px;font-size:19px;font-weight:bold;color:#2a251e;"'
_LBL = 'style="margin:18px 0 4px;color:#8a8378;font-size:12px;text-transform:uppercase;letter-spacing:.05em;"'
_TOTAL = 'style="margin:6px 0 4px;font-size:16px;color:#2a251e;"'
_MUTED = 'style="margin:18px 0 0;color:#6b6457;font-size:14px;"'

_KEY = "pedido_confirmado_cliente"
_SUBJECT = "Tu pedido #{{ numero_pedido }} está confirmado"

_BODY_HTML = (
    f"""<p {_H}>¡Tu pedido está confirmado!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, confirmamos tu pedido <strong>#{{{{ numero_pedido }}}}</strong>. Ya está todo listo.</p>
<p {_LBL}>Tu pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {_TOTAL}><strong>Total: {{{{ total }}}}</strong></p>
{_btn("portal_url", "Ver mi pedido")}
{{% if gcal_url %}}{_btn_secondary("gcal_url", "📅 Agregar al calendario")}{{% endif %}}
<p {_MUTED}>Ya podés descargar el <strong>remito</strong> y el <strong>contrato</strong> desde tu portal. Te esperamos en el galpón el día del retiro.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>"""
)

_BODY_TEXT = """Hola {{ cliente_nombre }},

Tu pedido #{{ numero_pedido }} está confirmado.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}

{{ items_text }}

Total: {{ total }}
{% if gcal_url %}
Agregá la reserva a tu calendario: {{ gcal_url }}
{% endif %}
Ya podés descargar el remito y el contrato desde tu portal: {{ portal_url }}
Te esperamos en el galpón el día del retiro.

— El equipo de Rambla"""


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE email_templates
        SET subject = {_q(_SUBJECT)},
            body_html = {_q(_BODY_HTML)},
            body_text = {_q(_BODY_TEXT)},
            updated_by = 'system:migration'
        WHERE key = {_q(_KEY)} AND updated_by = 'system:migration'
        """
    )


def downgrade() -> None:
    # No-op: el copy anterior queda en el historial de git (c1e9f3a7b5d2).
    pass
