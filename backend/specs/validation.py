"""Validación de datasets contra el registry.

Cada `docs/<cat>.json` debe cumplir el contrato declarado en el registry:
- Solo aparecen spec_keys declarados en la cat raíz
- Los valores enum están en enum_options
- Tipos números son numéricos, rangos son listas, booleans son bool
- Las claves obligatorias presentes

Usage:
    from specs.validation import validate_dataset, ValidationError
    errors = validate_dataset("Cámaras", products_dict)
    if errors:
        for e in errors:
            print(e)

Pensado para invocarse:
- Desde parsers/normalizers como step final antes de escribir docs/X.json
- En tests, contra los datasets actuales (regression guard)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import SpecDef
from .registry import REGISTRY


@dataclass
class ValidationError:
    producto_id: str
    spec_key: str
    mensaje: str

    def __str__(self) -> str:
        return f"[{self.producto_id}] {self.spec_key}: {self.mensaje}"


def _check_value(spec: SpecDef, value: Any) -> str | None:
    """Devuelve mensaje de error si el value no cumple el spec; None si OK."""
    if value is None:
        return None  # ausencia → OK salvo obligatorio (checked aparte)

    if spec.tipo == "bool":
        if not isinstance(value, bool):
            return f"esperaba bool, recibió {type(value).__name__}"
        return None

    if spec.tipo == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"esperaba number, recibió {type(value).__name__}"
        return None

    if spec.tipo == "string":
        if not isinstance(value, str):
            return f"esperaba string, recibió {type(value).__name__}"
        return None

    if spec.tipo == "enum":
        if not isinstance(value, str):
            return f"enum espera string, recibió {type(value).__name__}"
        if spec.enum_options and value not in spec.enum_options:
            return f"'{value}' no está en enum_options {spec.enum_options}"
        return None

    if spec.tipo == "multi_enum":
        if not isinstance(value, list):
            return f"multi_enum espera lista, recibió {type(value).__name__}"
        if spec.enum_options:
            invalid = [v for v in value if v not in spec.enum_options]
            if invalid:
                return f"valores fuera de enum_options: {invalid}"
        return None

    if spec.tipo == "rango":
        if not isinstance(value, list):
            return f"rango espera lista, recibió {type(value).__name__}"
        if not value or len(value) > 2:
            return f"rango debe tener 1 o 2 valores, recibió {len(value)}"
        for v in value:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return f"rango con valor no numérico: {v}"
        return None

    return f"tipo desconocido '{spec.tipo}' en registry"


def validate_dataset(categoria_raiz: str, products: dict) -> list[ValidationError]:
    """Valida un dataset completo. Devuelve lista de errores (vacía si OK).

    Args:
        categoria_raiz: nombre de la cat raíz en el registry.
        products: dict {prod_id: {specs: {key: value, ...}, ...}}.
    """
    cat = REGISTRY.get(categoria_raiz)
    if cat is None:
        return [ValidationError("", "", f"categoría '{categoria_raiz}' no está en registry")]

    by_key = {s.key: s for s in cat.specs}
    valid_keys = set(by_key)
    errors: list[ValidationError] = []

    for prod_id, prod in products.items():
        specs = prod.get("specs") or {}
        present = set(specs)

        # 1) Spec keys desconocidos
        for k in present - valid_keys:
            errors.append(ValidationError(prod_id, k, "spec_key no declarado en registry"))

        # 2) Obligatorios ausentes
        for spec in cat.specs:
            if spec.obligatorio and spec.key not in specs:
                errors.append(ValidationError(prod_id, spec.key, "obligatorio ausente"))

        # 3) Tipos / enums
        for k, v in specs.items():
            spec = by_key.get(k)
            if spec is None:
                continue  # ya reportado como desconocido
            msg = _check_value(spec, v)
            if msg:
                errors.append(ValidationError(prod_id, k, msg))

    return errors


def validate_or_raise(categoria_raiz: str, products: dict) -> None:
    """Como `validate_dataset` pero raisea si hay errores."""
    errors = validate_dataset(categoria_raiz, products)
    if errors:
        sample = "\n".join(str(e) for e in errors[:20])
        more = f"\n... (+{len(errors) - 20} más)" if len(errors) > 20 else ""
        raise ValueError(
            f"Validación de '{categoria_raiz}' falló con {len(errors)} errores:\n{sample}{more}"
        )
