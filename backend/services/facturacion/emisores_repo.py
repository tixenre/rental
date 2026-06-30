"""services.facturacion.emisores_repo — DAL para la tabla `emisores_arca`.

Gestiona los emisores de facturas electrónicas. Cada fila representa un
CUIT habilitado ante ARCA con sus credenciales cifradas.

DAL psycopg3 %s style (regla 2026-06-27). NUNCA se expone cert/key en texto.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class EmisorArca:
    id: int
    nombre: str
    cuit: str
    pto_vta: int
    condicion_iva: str       # 'responsable_inscripto' | 'monotributo'
    cert_cargado: bool       # True si cert_enc y key_enc no son null
    activo: bool
    razon_social: Optional[str]   # nombre legal para imprimir en el PDF
    notas: Optional[str]
    created_at: datetime
    updated_at: datetime


def _row_to_emisor(row: dict) -> EmisorArca:
    return EmisorArca(
        id=row["id"],
        nombre=row["nombre"],
        cuit=row["cuit"],
        pto_vta=row["pto_vta"],
        condicion_iva=row["condicion_iva"],
        cert_cargado=bool(row["cert_enc"] and row["key_enc"]),
        activo=row["activo"],
        razon_social=row.get("razon_social"),
        notas=row["notas"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------


def list_emisores(conn) -> list[EmisorArca]:
    rows = conn.execute(
        "SELECT * FROM emisores_arca ORDER BY condicion_iva, id"
    ).fetchall()
    return [_row_to_emisor(r) for r in rows]


def get_by_id(emisor_id: int, conn) -> Optional[EmisorArca]:
    row = conn.execute(
        "SELECT * FROM emisores_arca WHERE id = %s", (emisor_id,)
    ).fetchone()
    return _row_to_emisor(row) if row else None


def get_by_nombre(nombre: str, conn) -> Optional[EmisorArca]:
    row = conn.execute(
        "SELECT * FROM emisores_arca WHERE nombre = %s", (nombre,)
    ).fetchone()
    return _row_to_emisor(row) if row else None


def get_activo_para_condicion(condicion_iva: str, conn) -> Optional[EmisorArca]:
    """Primer emisor activo que coincide con la condición IVA."""
    row = conn.execute(
        "SELECT * FROM emisores_arca WHERE condicion_iva = %s AND activo = true ORDER BY id LIMIT 1",
        (condicion_iva,),
    ).fetchone()
    return _row_to_emisor(row) if row else None


def get_cert_pem(emisor_id: int, conn) -> tuple[bytes, bytes]:
    """Devuelve (cert_pem, key_pem) descifrados. Lanza ValueError si no hay cert."""
    row = conn.execute(
        "SELECT cert_enc, key_enc FROM emisores_arca WHERE id = %s", (emisor_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Emisor {emisor_id} no encontrado")
    if not row["cert_enc"] or not row["key_enc"]:
        raise ValueError(
            f"Emisor {emisor_id} no tiene certificado cargado. "
            "Subí el cert + clave desde el back-office → Facturación ARCA."
        )
    from services.facturacion.crypto import decrypt
    return decrypt(bytes(row["cert_enc"])), decrypt(bytes(row["key_enc"]))


# ---------------------------------------------------------------------------
# Escrituras
# ---------------------------------------------------------------------------


def create_emisor(
    conn,
    *,
    nombre: str,
    cuit: str,
    pto_vta: int,
    condicion_iva: str,
    razon_social: Optional[str] = None,
    notas: Optional[str] = None,
) -> int:
    _validate_condicion_iva(condicion_iva)
    row = conn.execute(
        """
        INSERT INTO emisores_arca (nombre, cuit, pto_vta, condicion_iva, razon_social, notas)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (nombre, cuit.strip(), pto_vta, condicion_iva, razon_social or None, notas),
    ).fetchone()
    return row["id"]


def update_emisor(
    emisor_id: int,
    conn,
    *,
    nombre: Optional[str] = None,
    cuit: Optional[str] = None,
    pto_vta: Optional[int] = None,
    condicion_iva: Optional[str] = None,
    activo: Optional[bool] = None,
    razon_social: Optional[str] = None,
    notas: Optional[str] = None,
) -> None:
    sets: list[str] = ["updated_at = now()"]
    params: list[Any] = []

    if nombre is not None:
        sets.append("nombre = %s"); params.append(nombre)
    if cuit is not None:
        sets.append("cuit = %s"); params.append(cuit.strip())
    if pto_vta is not None:
        sets.append("pto_vta = %s"); params.append(pto_vta)
    if condicion_iva is not None:
        _validate_condicion_iva(condicion_iva)
        sets.append("condicion_iva = %s"); params.append(condicion_iva)
    if activo is not None:
        sets.append("activo = %s"); params.append(activo)
    if razon_social is not None:
        sets.append("razon_social = %s"); params.append(razon_social or None)
    if notas is not None:
        sets.append("notas = %s"); params.append(notas)

    params.append(emisor_id)
    conn.execute(f"UPDATE emisores_arca SET {', '.join(sets)} WHERE id = %s", params)


def set_cert(emisor_id: int, conn, *, cert_pem: bytes, key_pem: bytes) -> None:
    """Cifra y persiste cert + clave privada en la tabla."""
    from services.facturacion.crypto import encrypt
    cert_enc = encrypt(cert_pem)
    key_enc = encrypt(key_pem)
    conn.execute(
        "UPDATE emisores_arca SET cert_enc = %s, key_enc = %s, updated_at = now() WHERE id = %s",
        (cert_enc, key_enc, emisor_id),
    )


def delete_emisor(emisor_id: int, conn) -> None:
    """Soft-delete: marca activo=false."""
    conn.execute(
        "UPDATE emisores_arca SET activo = false, updated_at = now() WHERE id = %s",
        (emisor_id,),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CONDICIONES_VALIDAS = ("responsable_inscripto", "monotributo", "exento")


def _validate_condicion_iva(condicion: str) -> None:
    if condicion not in _CONDICIONES_VALIDAS:
        raise ValueError(
            f"condicion_iva inválida: '{condicion}'. "
            f"Valores válidos: {', '.join(_CONDICIONES_VALIDAS)}"
        )
