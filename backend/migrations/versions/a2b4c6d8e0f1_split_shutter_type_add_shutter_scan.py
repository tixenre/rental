"""split_shutter_type: separar mecanismo de obturador de readout del sensor.

`shutter_type` tenía 5 valores mezclando dos conceptos distintos:
  - Mecanismo: Mechanical / Electronic / Hybrid
  - Readout del sensor: Global Shutter / Rolling Shutter

Este migration:
1. Crea spec_definitions 'shutter_scan' para Cámaras (Readout del sensor).
2. Mueve equipo_specs con value IN ('Global Shutter','Rolling Shutter') de
   shutter_type → shutter_scan.
3. Actualiza enum_options de shutter_type a solo [Mechanical, Electronic, Hybrid].
4. Crea la asignación categoria_spec_templates para shutter_scan.

El seeder al boot sincroniza el resto de la metadata desde el registry.

Revision ID: a2b4c6d8e0f1
Revises: f9a3c5d8b1e7
Create Date: 2026-05-26
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b4c6d8e0f1"
down_revision: Union[str, Sequence[str], None] = "b3d5e7f9a1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCAN_VALUES = ("Global Shutter", "Rolling Shutter")
_MECH_ENUM = ["Mechanical", "Electronic", "Hybrid"]
_SCAN_ENUM = ["Global Shutter", "Rolling Shutter"]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Cámaras root id
    row = conn.execute(sa.text("SELECT id FROM categorias WHERE nombre = 'Cámaras'")).fetchone()
    if row is None:
        return  # DB vacía — el seeder crea todo desde cero
    camaras_id = row[0]

    # 2. shutter_type spec_def
    st_row = conn.execute(sa.text(
        "SELECT id FROM spec_definitions "
        "WHERE categoria_raiz_id = :cid AND spec_key = 'shutter_type'"
    ), {"cid": camaras_id}).fetchone()
    if st_row is None:
        return  # aún no seedeado
    shutter_type_id = st_row[0]

    # 3. Crear shutter_scan spec_def (idempotente)
    ss_row = conn.execute(sa.text(
        "SELECT id FROM spec_definitions "
        "WHERE categoria_raiz_id = :cid AND spec_key = 'shutter_scan'"
    ), {"cid": camaras_id}).fetchone()

    if ss_row is None:
        ss_row = conn.execute(sa.text("""
            INSERT INTO spec_definitions
              (categoria_raiz_id, spec_key, label, tipo, enum_options,
               ayuda, es_compatibilidad, compatibilidad_modo, rol_compatibilidad,
               favorito, en_nombre, en_filtros, prioridad, aliases)
            VALUES
              (:cid, 'shutter_scan', 'Readout del sensor', 'enum', :enum,
               NULL, false, 'exacta', NULL,
               false, false, true, 156, :aliases)
            RETURNING id
        """), {
            "cid": camaras_id,
            "enum": json.dumps(_SCAN_ENUM),
            "aliases": json.dumps(["Sensor Readout", "Shutter Readout"]),
        }).fetchone()
    shutter_scan_id = ss_row[0]

    # 4. Mover equipo_specs: shutter_type rows con valor de readout → shutter_scan
    # Guard NOT EXISTS para evitar conflicto de PK (equipo_id, spec_def_id).
    for val in _SCAN_VALUES:
        conn.execute(sa.text("""
            UPDATE equipo_specs
            SET spec_def_id = :scan_id
            WHERE spec_def_id = :type_id
              AND value = :val
              AND NOT EXISTS (
                  SELECT 1 FROM equipo_specs es2
                  WHERE es2.equipo_id = equipo_specs.equipo_id
                    AND es2.spec_def_id = :scan_id
              )
        """), {"scan_id": shutter_scan_id, "type_id": shutter_type_id, "val": val})

    # 5. Actualizar enum_options de shutter_type
    conn.execute(sa.text(
        "UPDATE spec_definitions SET enum_options = :opts, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = :id"
    ), {"opts": json.dumps(_MECH_ENUM), "id": shutter_type_id})

    # 6. Asignar shutter_scan a categoria_spec_templates (idempotente)
    conn.execute(sa.text("""
        INSERT INTO categoria_spec_templates
          (categoria_id, spec_def_id, prioridad, destacado, obligatorio,
           visible_en_card, visible_en_filtros, visible_en_nombre, ayuda)
        VALUES (:cat_id, :sd_id, 156, false, false, false, true, false, NULL)
        ON CONFLICT (categoria_id, spec_def_id) DO NOTHING
    """), {"cat_id": camaras_id, "sd_id": shutter_scan_id})


def downgrade() -> None:
    # No revertimos el movimiento de datos: no hay forma de saber cuáles de los
    # shutter_scan actuales venían de shutter_type sin un log externo.
    pass
