"""email_templates_restyle_ds: repinta los 4 mails al Design System.

Reaplica el CONTENIDO de las 4 plantillas con el restyle al Design System
(labels en mono uppercase, números tabulares, paleta de marca fiel) que vive en
`services/email/default_templates.py`. El layout branded (header/footer/barra de
acento) lo pone el shell común `service._wrap_email_html` (cambio de código, no
de datos → no necesita migración).

**Importa `DEFAULT_TEMPLATES`** (en vez de inlinear el copy como hicieron las
migraciones previas) a propósito: el objetivo de esta iniciativa es la **fuente
única** del estilo de mail. Importando, lo que recibe prod == lo que siembra
`init_db()` para instalaciones nuevas → seed y repaint **no pueden divergir**
(invariante del esquema en dos capas, `docs/MEMORIA.md` 2026-06-03). Cualquier
cambio futuro de copy se edita en `default_templates.py` + su propia migración.

De paso cierra un drift preexistente: `default_templates.py` no reflejaba el
botón "Agregar al calendario" que `f2a4c6e8b0d1` había sumado al confirmado —
ahora sí lo incluye, así que este repaint lo preserva en vez de borrarlo.

GUARDA (igual que c1e9f3a7b5d2 / f2a4c6e8b0d1): solo actualiza filas con
`updated_by = 'system:migration'` — plantillas que nunca editó un admin desde la
UI (el PATCH setea `updated_by` al email del admin). Si el dueño ya customizó un
template, no se pisa.

Revision ID: a7d4f1c9e2b5
Revises: f2a4c6e8b0d1
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op

from services.email.default_templates import DEFAULT_TEMPLATES

revision: str = "a7d4f1c9e2b5"
down_revision: Union[str, Sequence[str], None] = "f2a4c6e8b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    for key, tpl in DEFAULT_TEMPLATES.items():
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
    # No-op: el copy anterior queda en el historial de git (f2a4c6e8b0d1 y
    # anteriores). No revertimos para no pisar el contenido nuevo a ciegas.
    pass
