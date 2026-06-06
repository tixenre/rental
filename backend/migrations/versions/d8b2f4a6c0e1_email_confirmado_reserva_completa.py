"""email_confirmado_reserva_completa: enriquece los mails al cliente.

Repinta los templates al cliente (`pedido_creado_cliente` +
`pedido_confirmado_cliente`) con el cuerpo "estilo pasaje de avión": secciones de
Reserva (fechas + jornadas), Equipos, Pago (total + estado de pago) y Documentos,
más una nota opcional del admin (`mensaje_admin`) y la lista de PDFs adjuntos
(`docs_adjuntos`) cuando el mail se manda desde el modal de envío del back-office.

Los bloques nuevos son **condicionales** (`{% if ... %}`): el mismo template sirve
para el disparo automático (sin adjuntos ni nota) y para el envío manual con los
PDFs adjuntos — no divergen.

**Importa `DEFAULT_TEMPLATES`** (no inlinea el copy) a propósito: lo que recibe
prod == lo que siembra `init_db()` para instalaciones nuevas → seed y repaint no
pueden divergir (invariante del esquema en dos capas, `docs/MEMORIA.md`
2026-06-03). El copy se edita en `services/email/default_templates.py`.

GUARDA (igual que a7d4f1c9e2b5 / c1e9f3a7b5d2): solo actualiza filas con
`updated_by = 'system:migration'` — plantillas que nunca editó un admin desde la
UI. Si el dueño ya customizó un template, no se pisa.

Revision ID: d8b2f4a6c0e1
Revises: c5e9a3f7d1b4
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op

from services.email.default_templates import DEFAULT_TEMPLATES

revision: str = "d8b2f4a6c0e1"
down_revision: Union[str, Sequence[str], None] = "c5e9a3f7d1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Solo los mails al cliente que cambian en esta iniciativa. Repintar de más sería
# inocuo (mismo contenido que el seed) pero acotamos al cambio real.
_KEYS = ("pedido_creado_cliente", "pedido_confirmado_cliente")


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    for key in _KEYS:
        tpl = DEFAULT_TEMPLATES[key]
        op.execute(
            f"""
            UPDATE email_templates
            SET subject = {_q(tpl["subject"])},
                body_html = {_q(tpl["body_html"])},
                body_text = {_q(tpl["body_text"])},
                updated_by = 'system:migration'
            WHERE key = {_q(key)} AND updated_by = 'system:migration'
            """
        )


def downgrade() -> None:
    # No-op: el copy anterior queda en el historial de git (a7d4f1c9e2b5 y
    # anteriores). No revertimos para no pisar el contenido nuevo a ciegas.
    pass
