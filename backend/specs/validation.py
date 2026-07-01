"""⏰ LEGACY — shim. Ver services/specs/queries/validation.py (Fase 1, #1163)."""

from services.specs.queries.validation import (
    ValidationError,
    validate_dataset,
    validate_or_raise,
)

__all__ = ["ValidationError", "validate_dataset", "validate_or_raise"]
