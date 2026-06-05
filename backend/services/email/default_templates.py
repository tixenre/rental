"""Contenido por defecto de las plantillas de email (los 4 mails del sistema).

**Fuente única forward del copy de los templates.** Espeja el end-state de la
cadena de migraciones (`a4e8c2b9d710` siembra → `e7c3a9f5d1b8` → `c1e9f3a7b5d2`
branded → `f2a4c6e8b0d1` botón calendario → restyle Design System). `init_db()`
siembra estas filas de forma idempotente (`ON CONFLICT DO NOTHING`) para que las
plantillas **existan siempre**, aunque las migraciones se traben — la red del
esquema en dos capas (ver `docs/MEMORIA.md` 2026-06-03).

El layout branded (header con logo, colores, footer) lo pone el shell común en
`services/email/service.py` (`_wrap_email_html`); estos bodies guardan **solo el
contenido editable** (el admin los puede editar desde `/admin/email-templates`).

Los tokens visuales (colores, fuentes) y los helpers (`btn`, `H`, `LBL`, …) viven
en `services/email/branding.py` — **fuente única**, no se repiten hex acá.

Si se cambia el copy, se edita ACÁ (+ una migración si hay que repisar prod). No
duplicar el contenido en otro lado.
"""
from __future__ import annotations

from . import branding as b

# key → {subject, body_html, body_text}
DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "pedido_creado_cliente": {
        "subject": "Recibimos tu pedido #{{ numero_pedido }} — Rambla Rental",
        "body_html": f"""<p {b.H}>¡Recibimos tu pedido!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, gracias por tu pedido <strong>#{{{{ numero_pedido }}}}</strong>. Lo estamos revisando y te confirmamos la disponibilidad a la brevedad.</p>
<p {b.LBL}>Tu pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {b.TOTAL}><strong>Total estimado: {{{{ total }}}}</strong></p>
{b.btn("portal_url", "Ver mi pedido")}
<p {b.MUTED_P}>Cuando confirmemos el pedido vas a poder descargar el <strong>remito</strong> y el <strong>contrato</strong> desde tu portal. ¿Tenés alguna duda? Respondé este mail.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>""",
        "body_text": """Hola {{ cliente_nombre }},

Recibimos tu pedido #{{ numero_pedido }}. Lo estamos revisando y te confirmamos la disponibilidad a la brevedad.

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}

{{ items_text }}

Total estimado: {{ total }}

Seguí tu pedido en el portal: {{ portal_url }}
Cuando lo confirmemos vas a poder descargar el remito y el contrato desde ahí.

¿Dudas? Respondé este mail.
— El equipo de Rambla""",
    },
    "pedido_confirmado_cliente": {
        "subject": "Tu pedido #{{ numero_pedido }} está confirmado",
        "body_html": f"""<p {b.H}>¡Tu pedido está confirmado!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, confirmamos tu pedido <strong>#{{{{ numero_pedido }}}}</strong>. Ya está todo listo.</p>
<p {b.LBL}>Tu pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {b.TOTAL}><strong>Total: {{{{ total }}}}</strong></p>
{b.btn("portal_url", "Ver mi pedido")}
{{% if gcal_url %}}{b.btn_secondary("gcal_url", "📅 Agregar al calendario")}{{% endif %}}
<p {b.MUTED_P}>Ya podés descargar el <strong>remito</strong> y el <strong>contrato</strong> desde tu portal. Te esperamos en el galpón el día del retiro.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>""",
        "body_text": """Hola {{ cliente_nombre }},

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

— El equipo de Rambla""",
    },
    "pedido_creado_admin": {
        "subject": "Nuevo pedido #{{ numero_pedido }} — {{ cliente_nombre }}",
        "body_html": f"""<p {b.H}>Entró un pedido nuevo</p>
<p style="margin:0 0 4px;"><strong>#{{{{ numero_pedido }}}}</strong> de <strong>{{{{ cliente_nombre }}}}</strong></p>
<p style="margin:0 0 4px;color:{b.MUTED};font-size:14px;">{{{{ cliente_email }}}}{{% if cliente_telefono %}} · {{{{ cliente_telefono }}}}{{% endif %}}</p>
<p {b.LBL}>Pedido</p>
<p style="margin:0 0 4px;"><strong>Retiro:</strong> {{{{ fecha_desde }}}}<br><strong>Devolución:</strong> {{{{ fecha_hasta }}}}</p>
{{{{ items_html|safe }}}}
<p {b.TOTAL}><strong>Total: {{{{ total }}}}</strong></p>
{{% if notas %}}<p style="margin:8px 0 0;"><strong>Notas:</strong> {{{{ notas }}}}</p>{{% endif %}}
{b.btn("admin_url", "Ver en el back-office")}""",
        "body_text": """Entró un pedido nuevo.

#{{ numero_pedido }} de {{ cliente_nombre }}
Contacto: {{ cliente_email }}{% if cliente_telefono %} · {{ cliente_telefono }}{% endif %}

Retiro: {{ fecha_desde }}
Devolución: {{ fecha_hasta }}

{{ items_text }}

Total: {{ total }}
{% if notas %}Notas: {{ notas }}{% endif %}

Ver en el back-office: {{ admin_url }}""",
    },
    "recordatorio_retiro": {
        "subject": "Mañana retirás tu pedido #{{ numero_pedido }} — Rambla Rental",
        "body_html": f"""<p {b.H}>¡Mañana es el día!</p>
<p style="margin:0 0 8px;">Hola {{{{ cliente_nombre }}}}, te recordamos que <strong>mañana ({{{{ fecha_desde }}}})</strong> retirás tu pedido <strong>#{{{{ numero_pedido }}}}</strong>.</p>
{{{{ items_html|safe }}}}
{b.btn("portal_url", "Ver mi pedido")}
<p {b.MUTED_P}>Te esperamos en el galpón. Si necesitás reagendar, escribinos cuanto antes.</p>
<p style="margin:18px 0 0;">— El equipo de Rambla</p>""",
        "body_text": """Hola {{ cliente_nombre }},

Mañana ({{ fecha_desde }}) retirás tu pedido #{{ numero_pedido }}.

{{ items_text }}

Te esperamos en el galpón. Si necesitás reagendar, escribinos cuanto antes.
Tu portal: {{ portal_url }}

— El equipo de Rambla""",
    },
}
