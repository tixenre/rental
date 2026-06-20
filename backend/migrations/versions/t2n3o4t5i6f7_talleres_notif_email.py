"""talleres: columna notif_email + templates de email dinámicos.

Añade notif_email a talleres (destinatario de notificaciones por taller).
Setea jimetroncoso44@gmail.com para el taller de Jime Troncoso.
Actualiza taller_inscripcion_cliente para usar variables de taller en lugar
de fechas/pago hardcodeados — funciona para cualquier taller futuro.

Revision ID: t2n3o4t5i6f7
Revises: t1a2l3l4e5r6
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "t2n3o4t5i6f7"
down_revision: Union[str, Sequence[str], None] = "t1a2l3l4e5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE talleres ADD COLUMN IF NOT EXISTS notif_email TEXT NOT NULL DEFAULT ''"
    )
    op.execute("""
        UPDATE talleres
        SET notif_email = 'jimetroncoso44@gmail.com'
        WHERE slug = 'direccion-de-arte-jime-troncoso'
    """)

    # Template cliente: reemplaza fechas/pago hardcodeados por variables de taller.
    # La inscripción va a pasar las vars: fecha_inicio_str, fecha_fin_str,
    # horario, direccion, precio_sena_str, pago_alias, pago_cbu, pago_banco.
    cliente_html = (
        "<p style=\"margin:0 0 12px;font-size:19px;font-weight:bold;color:#1a1714;\">"
        "{% if en_lista_espera %}Quedaste en lista de espera"
        "{% else %}¡Tu lugar está reservado!{% endif %}</p>"
        "<p style=\"margin:0 0 8px;\">Hola <strong>{{ nombre_pila }}</strong>, "
        "{% if en_lista_espera %}te anotamos en la lista de espera de "
        "<strong>{{ taller_nombre }}</strong>. "
        "Te avisamos si se libera un cupo.{% else %}"
        "recibimos tu inscripción a <strong>{{ taller_nombre }}</strong>. "
        "Tu seña queda confirmada cuando verifiquemos el pago.{% endif %}</p>"
        "{% if not en_lista_espera %}"
        "<p style=\"margin:18px 0 6px;font-size:11px;color:#6b6457;text-transform:uppercase;\">Fechas</p>"
        "<p style=\"margin:0 0 4px;\">"
        "<strong>Clase teórica:</strong> {{ fecha_inicio_str }}, {{ horario }}<br>"
        "<strong>Clase práctica:</strong> {{ fecha_fin_str }}, {{ horario }}<br>"
        "<strong>Lugar:</strong> {{ direccion }}</p>"
        "<p style=\"margin:18px 0 6px;font-size:11px;color:#6b6457;text-transform:uppercase;\">Datos de pago (seña)</p>"
        "<p style=\"margin:0 0 4px;\">"
        "<strong>Alias:</strong> {{ pago_alias }}<br>"
        "<strong>CBU:</strong> {{ pago_cbu }}<br>"
        "<strong>Banco:</strong> {{ pago_banco }}<br>"
        "<strong>Monto:</strong> {{ precio_sena_str }}</p>"
        "{% endif %}"
        "<p style=\"margin:18px 0 0;color:#6b6457;font-size:14px;\">"
        "¿Preguntas? Respondé este mail o escribínos por WhatsApp.</p>"
        "<p style=\"margin:18px 0 0;\">— El equipo de Rambla</p>"
    )
    cliente_text = (
        "{% if en_lista_espera %}"
        "Hola {{ nombre_pila }}, te anotamos en la lista de espera de {{ taller_nombre }}.\n\n"
        "Te avisamos si se libera un cupo.\n"
        "{% else %}"
        "Hola {{ nombre_pila }}, recibimos tu inscripción a {{ taller_nombre }}.\n\n"
        "Clase teórica: {{ fecha_inicio_str }}, {{ horario }}\n"
        "Clase práctica: {{ fecha_fin_str }}, {{ horario }}\n"
        "Lugar: {{ direccion }}\n\n"
        "Datos de pago (seña):\n"
        "  Alias: {{ pago_alias }}\n"
        "  CBU: {{ pago_cbu }}\n"
        "  Banco: {{ pago_banco }}\n"
        "  Monto: {{ precio_sena_str }}\n"
        "{% endif %}"
        "¿Preguntas? Respondé este mail.\n\n— El equipo de Rambla"
    )

    op.execute(f"""
        UPDATE email_templates
        SET body_html    = {_q(cliente_html)},
            body_text    = {_q(cliente_text)},
            updated_by   = 'system:migration'
        WHERE key = 'taller_inscripcion_cliente'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE talleres DROP COLUMN IF EXISTS notif_email")
