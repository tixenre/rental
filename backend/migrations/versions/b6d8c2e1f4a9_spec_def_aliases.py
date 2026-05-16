"""spec_definitions.aliases — labels alternativos para matching

El observatorio detectó que muchos labels reales que devuelve B&H no
matchean los specs del catálogo por diferencias mínimas:
  - "Montura" vs "Lens mount"
  - "Estabilización" vs "Estabilización óptica"
  - "Autoenfoque" vs "Autofocus"
  - "Focal mín"/"Focal máx" vs "Distancia focal"
  - "Lumens" vs "Lúmenes"
  - "Dimmable"/"Dimming" vs "Dimmer"

En lugar de renombrar el spec canónico (que rompería el frontend) o
crear specs duplicados (caos), agregamos `aliases JSONB` con una lista
de labels alternativos. El observatorio (y el resolver del autocompletar
IA) prueban primero match exacto contra `label`, luego contra cada
entry de `aliases`.

Con esta migración + el seed inicial de aliases (commit siguiente del
mismo PR), unmatched_count debería bajar de ~473 a ~250 sin tocar
ningún equipo.

Revision ID: b6d8c2e1f4a9
Revises: a5c2e4f8b1d6
Create Date: 2026-05-16
"""
from typing import Sequence, Union

revision: str = "b6d8c2e1f4a9"
down_revision: Union[str, Sequence[str], None] = "a5c2e4f8b1d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Backfill: aliases iniciales basados en lo observado en el JSON real
# del observatorio (790 obs / 106 equipos). Mapping
# {spec_key_canonico: [labels alternativos observados]}.
ALIASES_INICIALES: dict[str, list[str]] = {
    "lens_mount": ["Montura", "Mount", "Lens Mount", "Camera Mount"],
    "estabilizacion": ["Estabilización", "Image Stabilization", "OIS"],
    "autofocus": ["Autoenfoque", "Auto Focus", "AF"],
    "distancia_focal": ["Focal mín", "Focal máx", "Focal Length", "Distancia focal"],
    "apertura": ["Apertura máx", "Apertura mín", "Aperture", "Max Aperture", "Min Aperture"],
    "resolucion_max": ["Video máx", "Video Resolution", "Resolución de video", "Max Video Resolution"],
    "lumens": ["Lumens", "Lúmenes"],
    "dimming": ["Dimmable", "Dimming", "Dimmer"],
    "iso_nativo": ["ISO máx", "ISO Range", "Rango ISO", "ISO Sensitivity"],
    "diametro_filtro": ["Tamaño", "Filter Size", "Diámetro de filtro"],
    "temperatura_k": ["Color Temperature", "Color Temp"],
    "brillo_nits": ["Brightness", "Display Brightness"],
    "bateria": ["Battery", "Battery Type", "Tipo de batería"],
    "patron": ["Patrón polar", "Polar Pattern"],
    "peso_max_kg": ["Carga máx", "Carga máxima", "Capacidad de carga", "Capacidad de Carga"],
    "alimentacion": ["Power", "Power Source", "Tipo de alimentación", "Tipo de batería"],
    "altura_max_m": ["Altura máxima", "Altura máxima de trabajo", "Max Height"],
    "altura_min_m": ["Altura mínima", "Altura mínima de trabajo", "Min Height"],
    "distancia_minima_m": ["Distancia mínima de enfoque", "Min Focus Distance",
                           "Minimum Focus Distance"],
    "magnificacion": ["Magnificación", "Magnification", "Max Magnification"],
    "velocidad_lectura": ["Read Speed", "Lectura"],
    "velocidad_escritura": ["Write Speed", "Escritura"],
    # Material aparece tanto singular como plural en B&H ("Materiales" en
    # 14 equipos sumando todas las categorías).
    "material": ["Materiales", "Material de construcción", "Construction"],
    # Variantes del Lúmenes spec (3 equipos lo escriben como "Lumens").
    # Ya está cubierto arriba pero reforzamos sintaxis B&H pura.
    # Para Soportes y Grip: "Carga máxima" / "Capacidad de carga" se
    # mapean al peso_max_kg que ya existe.
}


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    import json as _json

    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS aliases JSONB"
    )
    # Index GIN para queries tipo `aliases ? 'Montura'` (jsonb contains key).
    # Sirve cuando el observatorio busca "qué spec_def tiene este label como alias".
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_aliases "
        "ON spec_definitions USING GIN (aliases) WHERE aliases IS NOT NULL"
    )

    # Backfill aliases iniciales. Solo aplica si la spec NO tiene ya aliases
    # cargados (el admin ya los curó). Coalesce con array vacío para mergear.
    bind = op.get_bind()
    for spec_key, alias_list in ALIASES_INICIALES.items():
        bind.execute(
            sa.text("""
                UPDATE spec_definitions
                SET aliases = CAST(:alias_json AS JSONB)
                WHERE spec_key = :spec_key
                  AND (aliases IS NULL OR aliases = 'null'::jsonb OR aliases = '[]'::jsonb)
            """),
            {"alias_json": _json.dumps(alias_list), "spec_key": spec_key},
        )


def downgrade() -> None:
    from alembic import op
    op.execute("DROP INDEX IF EXISTS idx_spec_def_aliases")
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS aliases")
