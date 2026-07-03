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
- `CategoriaRegistry` agrupa los specs de una categoría raíz (ancla por
  `nombre`) + metadata de compat (rol contenedor/contenido). No declara
  navegación ni jerarquía visual — eso lo maneja el dueño desde el árbol
  de categorías del catálogo (#1163 F6, desenredo categorías↔specs).
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

    # Labels alternativos (inglés B&H, variantes) → se usan en el matcheo
    # para resolver crudos como "Weight" → peso_g, "Focal Length" → distancia_focal.
    # Se seedean a spec_definitions.aliases (JSONB). Single source: vive acá.
    aliases: list[str] = Field(default_factory=list)

    # Sinónimos de VALOR (no de concepto): {"Full-frame": ["FF", "full frame"]}.
    # Distinto de `aliases` (arriba, matchea la COLUMNA "Weight"→peso_g); esto
    # matchea el VALOR de una columna enum ("FF"→"Full-frame"). Se seedea a
    # `spec_value_aliases` (tabla, no JSONB — ver services/specs/CLAUDE.md).
    # Solo válido en tipo enum/multi_enum, y cada clave debe ser un canónico
    # real (∈ enum_options) — se valida abajo.
    value_aliases: dict[str, list[str]] = Field(default_factory=dict)

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
        if self.value_aliases:
            if self.tipo not in ("enum", "multi_enum"):
                raise ValueError(
                    f"spec '{self.key}' tipo={self.tipo} no debe tener value_aliases "
                    "(solo enum/multi_enum)"
                )
            invalidos = sorted(set(self.value_aliases) - set(self.enum_options or []))
            if invalidos:
                raise ValueError(
                    f"spec '{self.key}': value_aliases tiene claves fuera de "
                    f"enum_options: {invalidos}"
                )
        return self


class CategoriaRegistry(BaseModel):
    """Una categoría raíz (ancla por `nombre` a una `categorias` real) + sus specs.

    Solo declara specs — no navegación ni jerarquía visual (#1163 F6, desenredo
    de categorías↔specs): el árbol del catálogo (prioridad, grupo_visual,
    sub-categorías) lo maneja el dueño 100% a mano desde /admin/categorias.
    El seeder (`commands/seed.py`) solo RESUELVE `nombre` contra una categoría
    ya existente para colgar los `spec_definitions` de su id — nunca crea ni
    edita la categoría.
    """

    nombre: str
    specs: list[SpecDef]

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
