"""⏰ LEGACY — shim. Ver services/specs/commands/coerce.py (Fase 1, #1163).

Re-exporta también los helpers privados (`_coerce_*`) porque
tests/test_spec_coerce.py los importa directo — no tocar sin actualizar ese
test también."""

from services.specs.commands.coerce import (
    _coerce_bool,
    _coerce_enum,
    _coerce_multi_enum,
    _coerce_number,
    _coerce_rango,
    coerce_and_serialize,
    derive_lumens_from_lux,
)

__all__ = [
    "coerce_and_serialize", "derive_lumens_from_lux",
    "_coerce_number", "_coerce_bool", "_coerce_enum",
    "_coerce_rango", "_coerce_multi_enum",
]
