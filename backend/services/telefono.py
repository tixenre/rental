"""services.telefono — puerta única (embudo) de validación/formateo de teléfonos a E.164.

TODO número que se guarda o se usa para contactar pasa por acá: si es válido, queda
en **E.164** (`+549...`, el formato que exige la Cloud API de WhatsApp); si no, según
el caso se descarta (`None`) o se guarda tal cual (best-effort). Región default **AR**.
Incluso el teléfono que trae Didit se re-chequea por este embudo (ya viene E.164, así
que es un no-op cuando está bien) — el objetivo es asegurarnos SIEMPRE de que el número
esté bien, no depender de que cada fuente lo mande formateado.

Capa fina sobre `phonenumbers` (libphonenumber de Google): no reimplementamos las
reglas de numeración de cada país (incluido el prefijo `15` de los móviles argentinos).
"""
from __future__ import annotations

from typing import Optional

import phonenumbers

REGION_DEFAULT = "AR"


def normalizar_e164(raw, region: str = REGION_DEFAULT) -> Optional[str]:
    """E.164 (`+549...`) si `raw` es un número **válido**, o `None`. Estricto: la boca
    de envío de WhatsApp usa esto para no mandarle basura a Meta."""
    if raw is None:
        return None
    texto = str(raw).strip()
    if not texto:
        return None
    try:
        num = phonenumbers.parse(texto, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def formatear_para_guardar(raw, region: str = REGION_DEFAULT) -> Optional[str]:
    """Versión para **persistir**: E.164 si el número es válido; si no, el texto
    `.strip()`eado tal cual (no se pierde el dato ni se bloquea el guardado). `None` si
    viene vacío. Los writers de teléfono llaman a esto — un solo embudo. Lenient a
    propósito: validar-y-formatear sin rechazar; el rechazo duro (bloquear el alta con
    un número inválido) es una decisión de UX aparte."""
    if raw is None:
        return None
    texto = str(raw).strip()
    if not texto:
        return None
    return normalizar_e164(texto, region) or texto


def es_valido(raw, region: str = REGION_DEFAULT) -> bool:
    """True si `raw` normaliza a un E.164 válido."""
    return normalizar_e164(raw, region) is not None
