"""services.facturacion.crypto — cifrado simétrico de credenciales ARCA.

Usa Fernet (AES-128-CBC + HMAC-SHA256, autenticado). Clave maestra en
`ARCA_MASTER_KEY` (único secreto que va a Railway). Para generar:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Nunca exponer el plaintext del cert/clave fuera de este módulo.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    key = os.getenv("ARCA_MASTER_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno ARCA_MASTER_KEY. "
            "Generala con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode())
    except Exception:
        raise RuntimeError(
            "ARCA_MASTER_KEY inválida. Debe ser una clave Fernet de 44 chars base64url."
        )


def encrypt(plaintext: bytes) -> bytes:
    """Cifra `plaintext` con la clave maestra. Devuelve ciphertext bytes."""
    return _get_fernet().encrypt(plaintext)


def decrypt(ciphertext: bytes) -> bytes:
    """Descifra `ciphertext`. Lanza RuntimeError si la clave no coincide."""
    try:
        return _get_fernet().decrypt(ciphertext)
    except InvalidToken:
        raise RuntimeError(
            "No se pudo descifrar la credencial ARCA. "
            "Verificá que ARCA_MASTER_KEY sea la misma con la que se cifró."
        )
