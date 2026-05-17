"""Pydantic models para el registry de specs.

Single source of truth: cada categoría declara sus specs acá, los seeds
los importan desde `registry.py`, la DB se genera, los datasets se validan.

Diseño:
- `SpecKey` es local a la categoría. Dos categorías pueden tener una key
  con el mismo nombre PERO se persisten como filas distintas en
  `spec_definitions` con composite key (categoria_raiz_id, spec_key).
- Las "shared" specs (lens_mount, formato, diametro_filtro, peso_g)
  se declaran INDEPENDIENTEMENTE en cada categoría que las usa. El motor
  de compat matchea por igualdad de spec_key + value en JSONB de equipos.
- `CategoriaRegistry` agrupa los specs de una categoría raíz + su árbol
  de sub-categorías + metadata de compat (rol contenedor/contenido).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

SpecTipo = Literal["enum", "multi_enum", "number", "rango", "bool", "string"]
CompatMode = Literal["exacta", "jerarquia"]
CompatRol = Literal["contenedor", "contenido"]


class SpecDef(BaseModel):
    """Definición canónica de una spec dentro de una categoría."""

    key: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1)
    tipo: SpecTipo

    enum_options: list[str] | None = None
    unidad: str | None = None
    ayuda: str | None = None

    prioridad: int = 100
    en_card: bool = False
    en_filtros: bool = False
    en_nombre: bool = False
    destacado: bool = False
    obligatorio: bool = False

    # Compatibilidad (qué role juega esta spec en el motor de matching)
    es_compatibilidad: bool = False
    compatibilidad_modo: CompatMode | None = None
    rol_compatibilidad: CompatRol | None = None

    @model_validator(mode="after")
    def _validate_enum(self) -> SpecDef:
        if self.tipo in ("enum", "multi_enum") and not self.enum_options:
            raise ValueError(
                f"spec '{self.key}' tipo={self.tipo} requiere enum_options no vacío"
            )
        if self.tipo not in ("enum", "multi_enum") and self.enum_options:
            raise ValueError(
                f"spec '{self.key}' tipo={self.tipo} no debe tener enum_options"
            )
        if self.es_compatibilidad and not self.compatibilidad_modo:
            raise ValueError(
                f"spec '{self.key}' es_compatibilidad=True requiere compatibilidad_modo"
            )
        return self


class SubCategoria(BaseModel):
    nombre: str
    prioridad: int = 100
    parent: str | None = None  # nombre de sub-cat parent (para taxonomías 2-niveles)


class CategoriaRegistry(BaseModel):
    """Una categoría raíz + su árbol de sub-cats + specs."""

    nombre: str
    prioridad: int
    sub_categorias: list[SubCategoria] = Field(default_factory=list)
    specs: list[SpecDef]

    # Opciones para que el sidebar muestre cats agrupadas (ej. "Óptica" para Lentes+Filtros+Adaptadores)
    grupo_visual: str | None = None

    @model_validator(mode="after")
    def _check_unique_spec_keys(self) -> CategoriaRegistry:
        seen: set[str] = set()
        for spec in self.specs:
            if spec.key in seen:
                raise ValueError(
                    f"Categoría '{self.nombre}': spec_key '{spec.key}' duplicada"
                )
            seen.add(spec.key)
        return self

    def get_spec(self, key: str) -> SpecDef | None:
        return next((s for s in self.specs if s.key == key), None)


class Registry(BaseModel):
    """Registro completo. Mapea nombre_raiz → CategoriaRegistry."""

    categorias: dict[str, CategoriaRegistry]

    def get(self, nombre: str) -> CategoriaRegistry | None:
        return self.categorias.get(nombre)

    def all_spec_keys_for(self, categoria_raiz: str) -> set[str]:
        cat = self.get(categoria_raiz)
        return {s.key for s in cat.specs} if cat else set()
