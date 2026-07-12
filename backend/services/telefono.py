"""Puerta única de normalización/validación de teléfonos → E.164.

FUENTE ÚNICA para toda la app: inscripciones a talleres, contacto de clientes y
la integración de WhatsApp (que necesita E.164). No reimplementar formateo de
teléfono ad-hoc en otro lado — importar de acá. Espeja el patrón de las demás
"puertas únicas" (`services/fechas.py`, `services/precios`, etc.). Reconciliado
2026-07-12 entre esta iniciativa (talleres) y la de WhatsApp Business, que
construyeron el mismo módulo en paralelo sin verse — nombres tomados de la
versión de WhatsApp (`normalizar_e164`/`formatear_para_guardar`) para minimizar
el roce en sus call sites.

E.164 = "+" + código de país + número nacional, sin espacios ni separadores
(ej. `+542236898641`). Es el formato canónico y el que espera la API de
WhatsApp — que además lo quiere **sin** el "+" (ver `solo_digitos`, para
wa.me / la Cloud API).

Región por defecto **AR**: un número local ("2236898641", "011 15 3166-1693")
se interpreta argentino. Se construye sobre `phonenumbers` (libphonenumber de
Google) — que ya conoce las reglas argentinas (códigos de área de 2-4 dígitos,
prefijo `15` legacy de celular, el `9` de móvil que WhatsApp necesita) — para
no reimplementar a mano un ruleset frágil.

Dos formas de normalizar, según qué hace el caller con el resultado:
  - `normalizar_e164` — ESTRICTA: inválido → `None`. Para lo que se ENVÍA
    (WhatsApp no debe recibir basura).
  - `formatear_para_guardar` — PERMISIVA: inválido → el crudo `.strip()`eado.
    Para lo que se PERSISTE (nunca se pierde el dato que cargó la persona ni
    se bloquea un alta por un formato raro).

Ninguna función levanta: entrada inválida → `None` (o el raw en el display).
"""

from __future__ import annotations

import phonenumbers

REGION_DEFAULT = "AR"


def normalizar_e164(raw: str | None, *, region: str = REGION_DEFAULT) -> str | None:
    """`raw` en cualquier formato → E.164 (`+54...`) si es un número **válido**,
    o `None` si está vacío / no parsea / no es un número válido para la región.

    Estricta: usar para lo que se ENVÍA (ej. el destinatario de WhatsApp).
    """
    if not raw or not raw.strip():
        return None
    try:
        num = phonenumbers.parse(raw.strip(), region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def formatear_para_guardar(raw: str | None, *, region: str = REGION_DEFAULT) -> str | None:
    """Versión para PERSISTIR: E.164 si `raw` es válido; si no, el `.strip()`eado
    tal cual (no se pierde el dato ni se bloquea el guardado). `None` si viene
    vacío. Los writers de teléfono llaman a esto — un solo embudo, permisivo
    a propósito (el rechazo duro es una decisión de UX aparte, por caller)."""
    if not raw or not raw.strip():
        return None
    return normalizar_e164(raw, region=region) or raw.strip()


def es_valido(raw: str | None, *, region: str = REGION_DEFAULT) -> bool:
    """¿`raw` es un teléfono válido (parseable a E.164) para la región?"""
    return normalizar_e164(raw, region=region) is not None


def solo_digitos(e164: str | None) -> str | None:
    """E.164 → solo dígitos, sin el "+" (formato de wa.me / la WhatsApp Cloud
    API, ej. `542236898641`). `None` si viene vacío."""
    if not e164:
        return None
    return e164.lstrip("+")


def formato_display(raw: str | None, *, region: str = REGION_DEFAULT) -> str | None:
    """Formato nacional legible para MOSTRAR (ej. `0223 689-8641`). Cae al raw
    stripeado si no parsea (nunca pierde el dato que cargó la persona). `None`
    si viene vacío."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    try:
        num = phonenumbers.parse(s, region)
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL)
    except phonenumbers.NumberParseException:
        pass
    return s
