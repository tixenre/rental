#!/usr/bin/env python3
"""
Convierte el `customers.csv` exportado de Booqable al formato `clientes.json`
que espera el importer de dataio (backend/dataio/importers.py::import_clientes).

Uso:
    python3 tools/booqable_to_clientes.py \
        --input  /path/to/customers.csv \
        --outdir /path/to/out

Produce dos artefactos en --outdir:
    clientes.json   — array de objetos validos contra schema.Cliente
    clientes.zip    — el JSON dentro de un ZIP, listo para POST /admin/dataio/import

Reporta un resumen por stderr con los saltados y un CSV con los rechazados.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

# Claves canonicas dentro del campo `properties` de Booqable, segun se observo
# en el export real. Si tu cuenta usa otras, ajustarlas aqui.
PROP_PHONE = "telefono"
PROP_ADDRESS = "direccion_principal"
PROP_CUIT = "cuil_cuit"


def split_name(full: str) -> tuple[str, str]:
    """Booqable guarda un unico campo `name`. El schema requiere nombre y
    apellido. Convencion: primera palabra -> nombre, resto -> apellido.
    Si solo hay una palabra, apellido = "-" (placeholder, editable despues).
    """
    parts = (full or "").strip().split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "-")
    return (parts[0], " ".join(parts[1:]))


def parse_properties(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_float(raw: str, default: float = 0.0) -> float:
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def convert_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Convierte una fila de Booqable a un dict compatible con schema.Cliente,
    o devuelve None si la fila no es importable (sin email)."""
    email = (row.get("email") or "").strip()
    if not email:
        return None

    name = (row.get("name") or "").strip()
    nombre, apellido = split_name(name)
    if not nombre:
        # nombre vacio: usar el local-part del email como fallback
        nombre = email.split("@", 1)[0]
        apellido = "-"

    props = parse_properties(row.get("properties") or "")
    telefono = (props.get(PROP_PHONE) or "").strip() or None
    direccion = (props.get(PROP_ADDRESS) or "").strip() or None
    cuit = (props.get(PROP_CUIT) or "").strip() or None

    descuento = parse_float(row.get("discount_percentage") or "0")
    legal_type = (row.get("legal_type") or "").strip().lower()
    is_commercial = legal_type == "commercial"

    cliente: dict[str, Any] = {
        "email": email,
        "nombre": nombre,
        "apellido": apellido,
        "telefono": telefono,
        "direccion": direccion,
        "cuit": cuit,
        "descuento": descuento,
        "perfil_impuestos": "responsable_inscripto" if is_commercial else "consumidor_final",
    }
    if is_commercial:
        cliente["razon_social"] = name

    # Notas: dejamos rastro del numero de cliente de Booqable para auditoria
    number = (row.get("number") or "").strip()
    if number:
        cliente["notas"] = f"Booqable #{number}"

    # Limpiar None de campos no-required asi el JSON queda mas chico
    return {k: v for k, v in cliente.items() if v is not None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="customers.csv de Booqable")
    ap.add_argument("--outdir", required=True, help="Directorio de salida")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    converted: list[dict[str, Any]] = []
    skipped_no_email: list[dict[str, str]] = []
    seen_emails: dict[str, int] = {}
    dupes: list[dict[str, str]] = []

    with in_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = convert_row(row)
            if c is None:
                skipped_no_email.append({"id": row.get("id", ""), "name": row.get("name", "")})
                continue
            email_key = c["email"].lower()
            if email_key in seen_emails:
                dupes.append({
                    "id": row.get("id", ""),
                    "name": row.get("name", ""),
                    "email": c["email"],
                    "first_seen_index": str(seen_emails[email_key]),
                })
                continue
            seen_emails[email_key] = len(converted)
            converted.append(c)

    # Escribir clientes.json
    json_path = out_dir / "clientes.json"
    json_path.write_text(
        json.dumps(converted, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Empaquetar ZIP listo para /admin/dataio/import
    zip_path = out_dir / "clientes.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(json_path, arcname="clientes.json")

    # CSV con los saltados (para revision manual)
    if skipped_no_email:
        skipped_path = out_dir / "skipped_no_email.csv"
        with skipped_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "name"])
            w.writeheader()
            w.writerows(skipped_no_email)
    if dupes:
        dupes_path = out_dir / "skipped_duplicates.csv"
        with dupes_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "name", "email", "first_seen_index"])
            w.writeheader()
            w.writerows(dupes)

    print(f"Convertidos:        {len(converted)}", file=sys.stderr)
    print(f"Saltados sin email: {len(skipped_no_email)}", file=sys.stderr)
    print(f"Duplicados:         {len(dupes)}", file=sys.stderr)
    print(f"JSON: {json_path}", file=sys.stderr)
    print(f"ZIP:  {zip_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
