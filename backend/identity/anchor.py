"""identity/anchor.py — el ancla CUIL (normalización + validación mod-11).

El CUIL es el ancla de identidad: **una persona = una cuenta**. Lo escribe SOLO
`identity/kyc.py` al aprobar Didit; acá viven solo los helpers de valor (puro, no
toca DB). CUIL ≠ CUIT (facturación, columna aparte).
"""

# Pesos del dígito verificador de CUIT/CUIL (Argentina), para los 10 primeros dígitos.
_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalizar_cuil(raw: str | None) -> str | None:
    """Deja solo los 11 dígitos del CUIL/CUIT. None si no quedan exactamente 11."""
    if not raw:
        return None
    digitos = "".join(c for c in str(raw) if c.isdigit())
    return digitos if len(digitos) == 11 else None


def cuil_valido(cuil: str | None) -> bool:
    """Valida el dígito verificador (mod-11) de un CUIL/CUIT de 11 dígitos.

    Sanity check para descartar un CUIL malformado que devolviera Didit antes de
    anclarlo. No reemplaza la verificación de RENAPER (eso lo hace Didit); solo
    confirma que el número está bien formado.
    """
    n = normalizar_cuil(cuil)
    if n is None:
        return False
    suma = sum(int(d) * p for d, p in zip(n[:10], _PESOS))
    resto = 11 - (suma % 11)
    verificador = 0 if resto == 11 else (9 if resto == 10 else resto)
    return verificador == int(n[10])
