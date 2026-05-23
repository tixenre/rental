"""normalizacion: fechas TEXT → TIMESTAMP/DATE

Las columnas de fecha se guardaban como strings ISO (TEXT). Las comparaciones
funcionaban porque ISO ordena lexicográficamente == cronológicamente, pero el
tipo no daba integridad ni permitía aritmética de fechas sin LEFT(...,10)::ts.

Se convierten a tipo nativo:
  - alquileres.fecha_desde / fecha_hasta            → TIMESTAMP (llevan hora)
  - equipo_mantenimiento.fecha / fecha_hasta /
    proxima_revision                                → TIMESTAMP
  - alquiler_pagos.fecha                            → TIMESTAMP
  - equipos.fecha_compra                            → DATE

Defensivo: limpia valores no-ISO ('' o basura) a NULL antes del cast, y
re-aplica NOT NULL solo si la columna quedó sin NULLs. Idempotente: solo
convierte columnas que siguen siendo 'text'.

Revision ID: e2c6f4a8b1d7
Revises: d5a8f2c4b6e9
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e2c6f4a8b1d7"
down_revision: Union[str, Sequence[str], None] = "d5a8f2c4b6e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columna, tipo destino, NOT NULL en el origen)
_COLS = (
    ("alquileres", "fecha_desde", "timestamp", False),
    ("alquileres", "fecha_hasta", "timestamp", False),
    ("equipo_mantenimiento", "fecha", "timestamp", True),
    ("equipo_mantenimiento", "fecha_hasta", "timestamp", False),
    ("equipo_mantenimiento", "proxima_revision", "timestamp", False),
    ("alquiler_pagos", "fecha", "timestamp", False),
    ("equipos", "fecha_compra", "date", False),
)


def upgrade() -> None:
    for tabla, col, tipo, not_null in _COLS:
        renotnull = (
            f"IF NOT EXISTS (SELECT 1 FROM {tabla} WHERE {col} IS NULL) THEN "
            f"ALTER TABLE {tabla} ALTER COLUMN {col} SET NOT NULL; END IF;"
            if not_null else ""
        )
        op.execute(f"""
            DO $$
            BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name = '{tabla}' AND column_name = '{col}') = 'text' THEN
                    ALTER TABLE {tabla} ALTER COLUMN {col} DROP NOT NULL;
                    UPDATE {tabla} SET {col} = NULL
                        WHERE {col} !~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}';
                    ALTER TABLE {tabla} ALTER COLUMN {col} TYPE {tipo}
                        USING NULLIF(TRIM({col}), '')::{tipo};
                    {renotnull}
                END IF;
            END $$;
        """)


def downgrade() -> None:
    for tabla, col, _tipo, not_null in _COLS:
        renotnull = (
            f"ALTER TABLE {tabla} ALTER COLUMN {col} SET NOT NULL;"
            if not_null else ""
        )
        op.execute(f"""
            DO $$
            BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name = '{tabla}' AND column_name = '{col}') <> 'text' THEN
                    ALTER TABLE {tabla} ALTER COLUMN {col} TYPE text
                        USING to_char({col}, 'YYYY-MM-DD"T"HH24:MI:SS');
                    {renotnull}
                END IF;
            END $$;
        """)
