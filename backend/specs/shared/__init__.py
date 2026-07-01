"""⏰ LEGACY — shim. Ver services/specs/registry/shared/ (Fase 1, #1163)."""

from services.specs.registry.shared import (
    FORMATO_ENUM,
    LENS_MOUNT_ENUM,
    MONTURA_LUZ_ENUM,
    autofocus,
    beam_angle,
    coating,
    diametro_filtro,
    dimensions_mm,
    estabilizacion,
    materials,
    montura_luz,
    peso_g,
)

__all__ = [
    "FORMATO_ENUM", "LENS_MOUNT_ENUM", "MONTURA_LUZ_ENUM",
    "beam_angle", "montura_luz",
    "autofocus", "coating", "diametro_filtro", "estabilizacion",
    "dimensions_mm", "materials", "peso_g",
]
