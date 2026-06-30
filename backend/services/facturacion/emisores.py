"""Resolver único de emisor: perfil fiscal del receptor → quién factura.

Compartido con firma de contratos (#1138): la misma regla decide el Locador
del contrato y el emisor de la factura.
"""
from __future__ import annotations


def emisor_para(perfil_impuestos: str) -> str:
    """Devuelve 'pablo' o 'santini' según el perfil fiscal del receptor.

    - 'responsable_inscripto' → Pablo (RI, emite Factura A con IVA discriminado).
    - Cualquier otro perfil    → Santini (Monotributo, emite Factura C sin IVA).

    Los valores de `perfil_impuestos` vienen de la tabla `clientes` y se
    editan en el formulario de alta/edición de cliente del back-office.
    """
    if (perfil_impuestos or "").strip().lower() == "responsable_inscripto":
        return "pablo"
    return "santini"
