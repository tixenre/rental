"""Sincroniza el row del Estudio con el contenido canónico (one-off admin).

Idempotente. Preserva valores que el dueño ya cargó. Forza:
- descripcion: copy nuevo (corto, narrativo — sin specs duplicadas).
- features: lista de 16 entradas. Las que ya existían se preservan; las
  nuevas se agregan con value vacío (visibles en admin, ocultas en
  público hasta que el dueño las complete).
- ciclorama: se fuerza a "6×6 m" (era "Infinito").

NO toca: pack_*, faq, fotos, ni nada que no esté listado abajo.

Uso:
  # Desde el repo, contra el DB local:
  cd backend && source .venv/bin/activate && python scripts/sync_estudio_canonico.py

  # Contra prod (Railway), con DATABASE_URL apuntando a la BD de prod:
  cd backend && source .venv/bin/activate && \\
    DATABASE_URL='postgres://...' python scripts/sync_estudio_canonico.py
"""

import json
import os
import sys

# Permitimos que el script se ejecute desde scripts/ con el .venv del backend.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db  # noqa: E402

DESCRIPCION_NUEVA = (
    "Un espacio para producciones audiovisuales con todos los equipos de "
    "Rambla Rental a mano. Ideal para rodajes grandes — flexible para los chicos."
)

# Lista canónica de 16 features. Las que tienen value="" quedan ocultas en
# público (filtro en /estudio.tsx) y visibles en admin para que el dueño las
# complete. `force_value=True` ignora el valor existente y lo sobrescribe.
CANONICAS = [
    ("Superficie", "", False),
    ("Altura", "", False),
    ("Ciclorama", "6×6 m", True),  # forzamos: "Infinito" → "6×6 m"
    ("Climatización", "Sí", False),
    ("Living", "Sí", False),
    ("Área de trabajo", "Sí", False),
    ("Entrada para autos", "Sí", False),
    ("Cocina", "Sí", False),
    ("WiFi", "", False),
    ("Camarín / vestuario", "", False),
    ("Potencia eléctrica", "", False),
    ("Insonorización", "", False),
    ("Pet friendly", "", False),
    ("Acceso 24h", "", False),
    ("Estacionamiento", "", False),
    ("Rigging / tomas de techo", "", False),
]


def main() -> None:
    conn = get_db()
    try:
        cur = conn.execute("SELECT descripcion, features_json FROM estudio WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            print("ERROR: no existe el row id=1 en `estudio`. Corré init_db primero.")
            sys.exit(1)

        existing_features = []
        if row["features_json"]:
            try:
                existing_features = json.loads(row["features_json"])
            except json.JSONDecodeError:
                existing_features = []

        by_label = {f["label"]: f.get("value", "") for f in existing_features}

        nuevas = []
        for label, default_value, force in CANONICAS:
            if force or label not in by_label:
                value = default_value
            else:
                value = by_label[label]
            nuevas.append({"label": label, "value": value})

        # Resumen antes de escribir.
        print(f"Descripción actual: {row['descripcion'][:80]}…")
        print(f"Descripción nueva:  {DESCRIPCION_NUEVA[:80]}…")
        print(f"Features: {len(existing_features)} → {len(nuevas)}")
        for f in nuevas:
            mark = "✓" if f["value"].strip() else "·"
            preserved = f["label"] in by_label and not any(c[0] == f["label"] and c[2] for c in CANONICAS)
            tag = " (preservado)" if preserved else " (canónico)"
            print(f"  {mark} {f['label']}: \"{f['value']}\"{tag}")

        conn.execute(
            "UPDATE estudio SET descripcion = %s, features_json = %s, updated_at = NOW() WHERE id = 1",
            (DESCRIPCION_NUEVA, json.dumps(nuevas, ensure_ascii=False)),
        )
        conn.commit()
        print("\nOK — estudio sincronizado.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
