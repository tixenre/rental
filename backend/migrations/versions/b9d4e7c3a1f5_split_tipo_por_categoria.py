"""split spec_key="tipo" en subtipos por categoría

El seed original (`backend/seeds/spec_templates.py`) declaraba un spec con
`key="tipo"` en 8 categorías distintas (Modificadores, Soportes, Grip,
Sonido, Monitores y Video, Adaptadores y Filtros, Energía, Media y Datos).
Como `spec_definitions` es global y `_collect_spec_definitions` unifica
enum_options por spec_key, la única spec "tipo" terminaba con TODAS las
opciones mezcladas: `["Softbox", "Trípode video", "Brazo", "Lavalier",
"SD", "V-mount"...]`. Bug latente — un equipo de cámara podía aceptar
"Softbox" como valor.

Esta migración resuelve la colisión:
  1. Crea 8 specs nuevas con `spec_key` propio por categoría:
     `modificador_subtipo`, `soporte_subtipo`, `grip_subtipo`,
     `mic_subtipo`, `monitor_subtipo`, `adaptador_subtipo`,
     `energia_subtipo`, `media_subtipo`.
  2. Reasigna `categoria_spec_templates` que apuntaban a la "tipo" antigua
     a la nueva spec correspondiente según la categoría raíz.
  3. Migra `equipo_specs` reasignando el `spec_def_id` por la categoría
     del equipo (heurística: primera categoría matcheante).
  4. Deja la spec_def "tipo" antigua sin asignaciones para que el admin
     decida si borrarla o mantenerla para legacy.

Idempotente: si las specs nuevas ya existen, no las recrea; si la spec
"tipo" antigua no existe, solo asegura que las nuevas estén creadas.

Downgrade no automático: el rollback requiere intervención manual o
restore desde backup (las labels/enum_options nuevas no son trivialmente
unificables sin perder información).

Revision ID: b9d4e7c3a1f5
Revises: a8c1b3d5e9f2
Create Date: 2026-05-15
"""
import json
from typing import Sequence, Union

revision: str = "b9d4e7c3a1f5"
down_revision: Union[str, Sequence[str], None] = "a8c1b3d5e9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mapeo categoría raíz → nueva spec. Mantener en sync con
# backend/seeds/spec_templates.py.
CATEGORIA_SUBTIPOS: list[dict] = [
    {
        "categoria_nombre": "Modificadores",
        "new_spec_key": "modificador_subtipo",
        "label": "Tipo de modificador",
        "enum_options": ["Softbox", "Frame de difusión", "Bandera", "Reflector",
                         "Octobox", "Strip", "Beauty Dish", "Fresnel", "Snoot"],
    },
    {
        "categoria_nombre": "Soportes",
        "new_spec_key": "soporte_subtipo",
        "label": "Tipo de soporte",
        "enum_options": ["Trípode video", "Trípode foto", "C-Stand", "Slider",
                         "Dolly", "Car Mount", "Camera Cage", "Gimbal"],
    },
    {
        "categoria_nombre": "Grip",
        "new_spec_key": "grip_subtipo",
        "label": "Tipo de grip",
        "enum_options": ["Brazo", "Clamp", "Wall plate", "Pinza", "Línea de seguridad",
                         "Sopapa", "Lastre", "Cage", "Plate", "Junior pin", "Apple box"],
    },
    {
        "categoria_nombre": "Sonido",
        "new_spec_key": "mic_subtipo",
        "label": "Tipo de micrófono",
        "enum_options": ["Lavalier", "Shotgun", "On-camera", "Estudio",
                         "Inalámbrico", "Boom", "Intercom"],
    },
    {
        "categoria_nombre": "Monitores y Video",
        "new_spec_key": "monitor_subtipo",
        "label": "Tipo de monitor/video",
        "enum_options": ["Monitor", "Grabador", "Tx wireless", "Rx wireless",
                         "Combo Tx/Rx", "Follow Focus", "Matebox"],
    },
    {
        "categoria_nombre": "Adaptadores y Filtros",
        "new_spec_key": "adaptador_subtipo",
        "label": "Tipo de adaptador/filtro",
        "enum_options": ["Adaptador montura", "Speedbooster", "Filtro ND",
                         "Filtro polarizador", "Filtro UV", "Filtro variable",
                         "Macro tube"],
    },
    {
        "categoria_nombre": "Energía",
        "new_spec_key": "energia_subtipo",
        "label": "Tipo de energía",
        "enum_options": ["V-mount", "NP-F", "LP-E6", "BP-U", "AA",
                         "Generador", "Distribución", "Cargador", "Alargue", "Zapatilla"],
    },
    {
        "categoria_nombre": "Media y Datos",
        "new_spec_key": "media_subtipo",
        "label": "Tipo de media",
        "enum_options": ["SD", "microSD", "CFexpress B", "CFexpress A", "CFast",
                         "SSD externo", "Lector"],
    },
]


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    bind = op.get_bind()

    # 1) Buscar la spec antigua "tipo" si existe.
    old_row = bind.execute(
        sa.text("SELECT id FROM spec_definitions WHERE spec_key = 'tipo'")
    ).fetchone()
    old_id = old_row[0] if old_row else None

    # 2) Por cada categoría: crear nueva spec, reasignar templates y equipos.
    for cat in CATEGORIA_SUBTIPOS:
        # Crear spec nueva (idempotent).
        bind.execute(
            sa.text("""
                INSERT INTO spec_definitions
                  (spec_key, label, tipo, enum_options, es_compatibilidad,
                   compatibilidad_modo, validado)
                VALUES (:key, :label, 'enum', CAST(:options AS JSONB),
                        FALSE, 'exacta', FALSE)
                ON CONFLICT DO NOTHING
            """),
            {
                "key": cat["new_spec_key"],
                "label": cat["label"],
                "options": json.dumps(cat["enum_options"]),
            },
        )
        new_row = bind.execute(
            sa.text("SELECT id FROM spec_definitions WHERE spec_key = :key"),
            {"key": cat["new_spec_key"]},
        ).fetchone()
        new_id = new_row[0]

        if old_id is None:
            continue  # No hay spec antigua; nada que migrar.

        # Buscar la categoría raíz.
        cat_row = bind.execute(
            sa.text("""
                SELECT id FROM categorias
                WHERE nombre = :name AND parent_id IS NULL
            """),
            {"name": cat["categoria_nombre"]},
        ).fetchone()
        if cat_row is None:
            continue  # Categoría no existe en esta BD; skip.
        cat_id = cat_row[0]

        # Reasignar categoria_spec_templates de "tipo" → nueva en esta categoría.
        # Si ya hay un template apuntando a la nueva (porque la migración corrió
        # antes), no falla — el ON CONFLICT del UNIQUE lo evita: detectamos a
        # mano antes para conservar idempotencia.
        existing_new_template = bind.execute(
            sa.text("""
                SELECT id FROM categoria_spec_templates
                WHERE spec_def_id = :new_id AND categoria_id = :cat_id
            """),
            {"new_id": new_id, "cat_id": cat_id},
        ).fetchone()
        if existing_new_template is None:
            bind.execute(
                sa.text("""
                    UPDATE categoria_spec_templates
                    SET spec_def_id = :new_id
                    WHERE spec_def_id = :old_id AND categoria_id = :cat_id
                """),
                {"new_id": new_id, "old_id": old_id, "cat_id": cat_id},
            )
        else:
            # Ya existe una asignación a la nueva spec en esa categoría.
            # Borrar la asignación residual a la spec vieja (si quedó).
            bind.execute(
                sa.text("""
                    DELETE FROM categoria_spec_templates
                    WHERE spec_def_id = :old_id AND categoria_id = :cat_id
                """),
                {"old_id": old_id, "cat_id": cat_id},
            )

        # Migrar equipo_specs: equipos en esta categoría que tienen value
        # cargado para la spec antigua "tipo".
        # Edge case: si el equipo está en MÚLTIPLES categorías de las 8, gana
        # la primera que itera (orden de CATEGORIA_SUBTIPOS). Las siguientes
        # iteraciones no lo encuentran porque ya cambió de spec_def_id.
        # Edge case 2: si ya existe un equipo_specs para (equipo, new_id), no
        # se duplica — la PK (equipo_id, spec_def_id) lo previene; salteamos
        # esos equipos con un NOT EXISTS.
        bind.execute(
            sa.text("""
                UPDATE equipo_specs es
                SET spec_def_id = :new_id
                WHERE es.spec_def_id = :old_id
                  AND es.equipo_id IN (
                      SELECT equipo_id FROM equipo_categorias
                      WHERE categoria_id = :cat_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM equipo_specs es2
                      WHERE es2.equipo_id = es.equipo_id
                        AND es2.spec_def_id = :new_id
                  )
            """),
            {"new_id": new_id, "old_id": old_id, "cat_id": cat_id},
        )


def downgrade() -> None:
    # Rollback automático no soportado: las 8 specs nuevas tienen labels y
    # enum_options propios; unificarlas de vuelta en una "tipo" pierde
    # información. Si necesitás revertir, restaurar desde backup de DB.
    #
    # Para una reversión "soft" que NO toque datos: borrar las 8 specs
    # nuevas si quedaron sin asignaciones ni equipos.
    import sqlalchemy as sa
    from alembic import op
    bind = op.get_bind()
    for cat in CATEGORIA_SUBTIPOS:
        bind.execute(
            sa.text("""
                DELETE FROM spec_definitions
                WHERE spec_key = :key
                  AND NOT EXISTS (
                      SELECT 1 FROM categoria_spec_templates
                      WHERE spec_def_id = spec_definitions.id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM equipo_specs
                      WHERE spec_def_id = spec_definitions.id
                  )
            """),
            {"key": cat["new_spec_key"]},
        )
