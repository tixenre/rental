"""Backfill: taller_inscripciones.telefono histórico → E.164 (+54...).

Los teléfonos de inscripciones viejas se guardaron crudos y con formatos
inconsistentes (`1131661693`, `2236898641`, `+542235766569`, con/sin +54, con
espacios). Desde ahora `crear_inscripcion` los normaliza vía la puerta única
`services.telefono` (E.164, listo para WhatsApp); este backfill lleva los que
ya estaban a la misma forma, para que el listado del admin y la futura
integración de WhatsApp los vean consistentes.

Solo se toca una fila si el número PARSEA y es VÁLIDO (AR) y el E.164 difiere
de lo guardado — un número que no valida se deja tal cual (no se pierde el dato
que cargó la persona). Data-only, corre UNA VEZ (no va en init_db()).

Se **inlinea** `phonenumbers` a propósito en vez de importar `services.telefono`:
una migración tiene que quedar congelada en el tiempo, no depender de app code
que puede cambiar y romper el replay sobre una base nueva. La lógica es la
misma que `services.telefono.normalizar`.

Revision ID: t3l3f0n0bkfl
Revises: f604c6bd934c
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "t3l3f0n0bkfl"
down_revision: Union[str, Sequence[str], None] = "f604c6bd934c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import phonenumbers

    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT id, telefono FROM taller_inscripciones "
            "WHERE telefono IS NOT NULL AND telefono <> ''"
        )
    ).fetchall()

    for rid, tel in rows:
        raw = (tel or "").strip()
        if not raw:
            continue
        try:
            num = phonenumbers.parse(raw, "AR")
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(num):
            continue
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        if e164 != raw:
            bind.execute(
                text("UPDATE taller_inscripciones SET telefono = :t WHERE id = :id"),
                {"t": e164, "id": rid},
            )


def downgrade() -> None:
    # Irreversible con precisión (no se puede reconstruir el formato crudo
    # original a partir del E.164) — no-op documentado, mismo criterio que los
    # demás backfills de datos del proyecto.
    pass
