"""normalizar_enums: fusionar opciones redundantes de specs

Cambios al registry.py + migración de los `equipo_specs.value` ya cargados:

- `iluminacion_subtipo`:
  - "Monolight" → "Monoled"
  - "COB Monolight" → "Monoled"
  - "Bulb / Lamp" → "Foco"
  - "Spotlight" → "Fresnel" (un spotlight de cine clásico usa lente
    Fresnel; los specs de "Spotlight" se absorben ahí)

- `color_modes` (multi_enum, JSON array):
  - Si tiene "Daylight" + "Tungsten" → reemplazar ambos por "Bicolor".
  - "Bicolor variable" → "Bicolor".
  - "HSI" → eliminar (es detalle interno del RGB, no un modo separado).

- `formato` (cámaras):
  - "M4/3" → "MFT" (mismo significado, MFT es más común).

- `camera_subtipo`:
  - "Camera" → no se reemplaza, se deja como string (el enum_options ya
    no lo lista pero el value existente queda en DB; queda fuera de
    opciones del select).

- `wireless` (multi_enum, JSON array):
  - "Wi-Fi 2.4 GHz" → "Wi-Fi"
  - "Wi-Fi 5 GHz" → "Wi-Fi"
  - Dedupe si quedan duplicados tras el reemplazo.

Post-migración: el seeder al boot va a sincronizar los `enum_options`
nuevos a `spec_definitions`. Para regenerar los nombres públicos que
incluyen estos specs en el template, correr
`POST /api/admin/equipos/regenerar-nombres`.

Revision ID: d9e3f1a5c2b7
Revises: b7e2c4f8a9d3
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import json
import sqlalchemy as sa
from alembic import op

revision: str = "d9e3f1a5c2b7"
down_revision: Union[str, Sequence[str], None] = "b7e2c4f8a9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. iluminacion_subtipo: 4 reemplazos directos
    conn.execute(sa.text("""
        UPDATE equipo_specs SET value = CASE value
            WHEN 'Monolight' THEN 'Monoled'
            WHEN 'COB Monolight' THEN 'Monoled'
            WHEN 'Bulb / Lamp' THEN 'Foco'
            WHEN 'Spotlight' THEN 'Fresnel'
            ELSE value
        END
        WHERE spec_def_id IN (
            SELECT id FROM spec_definitions WHERE spec_key = 'iluminacion_subtipo'
        )
        AND value IN ('Monolight', 'COB Monolight', 'Bulb / Lamp', 'Spotlight')
    """))

    # 2. formato: M4/3 → MFT
    conn.execute(sa.text("""
        UPDATE equipo_specs SET value = 'MFT'
        WHERE spec_def_id IN (
            SELECT id FROM spec_definitions WHERE spec_key = 'formato'
        )
        AND value = 'M4/3'
    """))

    # 3. color_modes (multi_enum JSON): Daylight+Tungsten → Bicolor; HSI eliminar;
    #    Bicolor variable → Bicolor.
    rows = conn.execute(sa.text("""
        SELECT es.equipo_id, es.spec_def_id, es.value
        FROM equipo_specs es
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        WHERE sd.spec_key = 'color_modes'
          AND es.value IS NOT NULL
          AND es.value != ''
    """)).fetchall()

    for row in rows:
        try:
            val = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(val, list):
            continue
        # Aplicar mapeos
        mapped = []
        for x in val:
            sx = str(x)
            if sx == "HSI":
                continue  # eliminar
            if sx == "Bicolor variable":
                mapped.append("Bicolor")
                continue
            mapped.append(sx)
        # Si están Daylight y Tungsten ambos → fusionar en Bicolor
        if "Daylight" in mapped and "Tungsten" in mapped:
            mapped = [x for x in mapped if x not in ("Daylight", "Tungsten")]
            if "Bicolor" not in mapped:
                mapped.insert(0, "Bicolor")
        # Dedupe preservando orden
        seen = set()
        new_val = [x for x in mapped if not (x in seen or seen.add(x))]
        if new_val != val:
            conn.execute(
                sa.text(
                    "UPDATE equipo_specs SET value = :v "
                    "WHERE equipo_id = :equipo_id AND spec_def_id = :spec_def_id"
                ),
                {"v": json.dumps(new_val), "equipo_id": row.equipo_id, "spec_def_id": row.spec_def_id},
            )

    # 4. wireless (multi_enum JSON): Wi-Fi 2.4 GHz / Wi-Fi 5 GHz → Wi-Fi
    rows = conn.execute(sa.text("""
        SELECT es.equipo_id, es.spec_def_id, es.value
        FROM equipo_specs es
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        WHERE sd.spec_key = 'wireless'
          AND es.value IS NOT NULL
          AND es.value != ''
    """)).fetchall()

    for row in rows:
        try:
            val = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(val, list):
            continue
        mapped = []
        for x in val:
            sx = str(x)
            if sx in ("Wi-Fi 2.4 GHz", "Wi-Fi 5 GHz"):
                mapped.append("Wi-Fi")
            else:
                mapped.append(sx)
        # Dedupe
        seen = set()
        new_val = [x for x in mapped if not (x in seen or seen.add(x))]
        if new_val != val:
            conn.execute(
                sa.text(
                    "UPDATE equipo_specs SET value = :v "
                    "WHERE equipo_id = :equipo_id AND spec_def_id = :spec_def_id"
                ),
                {"v": json.dumps(new_val), "equipo_id": row.equipo_id, "spec_def_id": row.spec_def_id},
            )

    # 5. Sincronizar enum_options en spec_definitions desde el registry.
    # El seeder al boot lo hace, pero forzamos acá para que el form refleje
    # los enums nuevos inmediatamente sin esperar al próximo reboot.
    enum_updates = [
        ("iluminacion_subtipo", [
            "Flash", "Foco", "Panel", "Tube Light", "Flexible Mat",
            "Monoled", "Fresnel", "On-Camera",
        ]),
        ("color_modes", ["RGB", "Bicolor", "Daylight", "Tungsten"]),
        ("formato", [
            "1\"", "MFT", "APS-C", "Super 35", "Full-frame", "Medium Format",
        ]),
        ("camera_subtipo", [
            "Cinema Camera", "Mirrorless", "DSLR", "Vlogging",
            "Action Camera", "Compact", "Medium Format",
        ]),
        ("wireless", ["Wi-Fi", "Bluetooth", "NFC", "5G", "LTE"]),
    ]
    for spec_key, opts in enum_updates:
        conn.execute(
            sa.text(
                "UPDATE spec_definitions SET enum_options = :opts, "
                "updated_at = CURRENT_TIMESTAMP WHERE spec_key = :sk"
            ),
            {"opts": json.dumps(opts), "sk": spec_key},
        )


def downgrade() -> None:
    # No revertimos: los valores fueron fusionados y no se puede recuperar
    # cuál era el original (ej. Monoled fue Monolight o COB Monolight).
    pass
