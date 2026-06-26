"""talleres: tabla taller_sesiones + tipo_taller + template taller_cambio_datos.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

taller_sesiones: fuente de verdad de las fechas/horas de un taller. El tipo
(intensivo/semanal) es solo un asistente de UI para generar la lista; el
backend lee las sesiones literales para bloquear el estudio y mostrar el
calendario público.

tipo_taller: columna en talleres para que el asistente de sesiones recuerde
el modo de generación (intensivo | semanal). DEFAULT 'intensivo'.

taller_cambio_datos: template de email para notificar a inscriptos confirmados
cuando el admin cambia datos del taller (fechas, lugar, etc.).

Seed idempotente: inserta las sesiones de los dos talleres Jime Troncoso ya
existentes (2026-07-11 y 2026-07-18 para ed.1, 2026-08-15 y 2026-08-22 para
ed.2), 9-13 hs, solo si no existen aún.

Revision ID: t4ll3rs3s01
Revises: m3rg3h34ds03
Create Date: 2026-06-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "t4ll3rs3s01"
down_revision: Union[str, Sequence[str], None] = "m3rg3h34ds03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    # ── taller_sesiones ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS taller_sesiones (
            id          SERIAL PRIMARY KEY,
            taller_id   INTEGER NOT NULL REFERENCES talleres(id) ON DELETE CASCADE,
            fecha       DATE    NOT NULL,
            hora_inicio INTEGER NOT NULL,
            hora_fin    INTEGER NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_taller_sesiones_taller "
        "ON taller_sesiones(taller_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_taller_sesiones_fecha "
        "ON taller_sesiones(fecha)"
    )

    # ── tipo_taller ────────────────────────────────────────────────────────────
    op.execute(
        "ALTER TABLE talleres ADD COLUMN IF NOT EXISTS tipo_taller "
        "TEXT NOT NULL DEFAULT 'intensivo'"
    )

    # ── Seed sesiones Jime Troncoso (idempotente) ──────────────────────────────
    for slug, fecha in [
        ("direccion-de-arte-jime-troncoso", "2026-07-11"),
        ("direccion-de-arte-jime-troncoso", "2026-07-18"),
    ]:
        op.execute(f"""
            INSERT INTO taller_sesiones (taller_id, fecha, hora_inicio, hora_fin)
            SELECT t.id, '{fecha}', 9, 13
            FROM talleres t
            WHERE t.slug = {_q(slug)}
              AND NOT EXISTS (
                SELECT 1 FROM taller_sesiones
                WHERE taller_id = t.id AND fecha = '{fecha}'
              )
        """)

    for slug, fecha in [
        ("direccion-de-arte-jime-troncoso-2", "2026-08-15"),
        ("direccion-de-arte-jime-troncoso-2", "2026-08-22"),
    ]:
        op.execute(f"""
            INSERT INTO taller_sesiones (taller_id, fecha, hora_inicio, hora_fin)
            SELECT t.id, '{fecha}', 9, 13
            FROM talleres t
            WHERE t.slug = {_q(slug)}
              AND NOT EXISTS (
                SELECT 1 FROM taller_sesiones
                WHERE taller_id = t.id AND fecha = '{fecha}'
              )
        """)

    # ── Template taller_cambio_datos ───────────────────────────────────────────
    cambio_html = (
        "<p style=\"margin:0 0 12px;font-size:19px;font-weight:bold;color:#1a1714;\">"
        "Actualización: {{ taller_nombre }}</p>"
        "<p style=\"margin:0 0 8px;\">Hola <strong>{{ nombre_pila }}</strong>, "
        "hay una novedad sobre el workshop al que te inscribiste:</p>"
        "{% if mensaje %}"
        "<p style=\"margin:12px 0;padding:12px 16px;"
        "background:#f5f3f0;border-left:3px solid #c8a96e;"
        "border-radius:4px;\">{{ mensaje }}</p>"
        "{% endif %}"
        "<p style=\"margin:18px 0 0;color:#6b6457;font-size:14px;\">"
        "¿Preguntas? Respondé este mail o escribínos por WhatsApp.</p>"
        "<p style=\"margin:18px 0 0;\">— El equipo de Rambla</p>"
    )
    cambio_text = (
        "Hola {{ nombre_pila }}, hay una novedad sobre {{ taller_nombre }}.\n\n"
        "{% if mensaje %}{{ mensaje }}\n\n{% endif %}"
        "¿Preguntas? Respondé este mail.\n\n— El equipo de Rambla"
    )
    op.execute(f"""
        INSERT INTO email_templates (key, subject, body_html, body_text, updated_by)
        VALUES (
            'taller_cambio_datos',
            'Actualización sobre {{ taller_nombre }}',
            {_q(cambio_html)},
            {_q(cambio_text)},
            'system:migration'
        )
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS taller_sesiones")
    op.execute("ALTER TABLE talleres DROP COLUMN IF EXISTS tipo_taller")
    op.execute("DELETE FROM email_templates WHERE key = 'taller_cambio_datos'")
