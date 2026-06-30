"""services/checkout/ — portero del checkout.

Puerta única de validación antes de crear un pedido. No crea pedidos.
Ver `validar.py` y `docs/SISTEMA_CHECKOUT.md`.
"""
from services.checkout.validar import (
    validar_checkout,
    faltan_firma_tyc,
    FIRMA_CHECKOUT_OBLIGATORIA,
)
from services.checkout.tyc import TYC_VERSION_ACTUAL, ya_acepto, registrar_aceptacion

__all__ = [
    "validar_checkout",
    "faltan_firma_tyc",
    "FIRMA_CHECKOUT_OBLIGATORIA",
    "TYC_VERSION_ACTUAL",
    "ya_acepto",
    "registrar_aceptacion",
]
