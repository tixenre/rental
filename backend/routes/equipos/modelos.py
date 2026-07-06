"""routes/equipos/modelos.py — modelos Pydantic del equipo (split de `core.py`).

Move-verbatim (issue de tracking #1258, Corte A): `EquipoCreate`/`EquipoUpdate`/
`BulkActionInput` + sus validadores. `core.py` re-importa estos nombres tal cual —
`routes/equipos/__init__.py` no cambia.

De paso (a pedido del dueño, "no quiero funciones repetidas entre los módulos"):
`validate_precio`/`validate_cantidad` estaban duplicados palabra por palabra entre
`EquipoCreate` y `EquipoUpdate` — se extraen a `_validar_precio_no_negativo`/
`_validar_cantidad_no_negativa`, mismo patrón que ya usaban `categoria_specs`/`tipo`
(que ya delegaban a `_validar_categoria_specs`/`_validar_tipo`).
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _validar_categoria_specs(v: Optional[str]) -> Optional[str]:
    """Valida que la categoría de specs sea una del registry (o None)."""
    if v is None or v == "":
        return None
    from services.specs import REGISTRY
    if v not in REGISTRY.categorias:
        validas = ", ".join(REGISTRY.categorias)
        raise ValueError(f"categoria_specs inválida: '{v}'. Opciones: {validas}")
    return v


_TIPOS_EQUIPO = frozenset({"simple", "kit", "combo"})


def _validar_tipo(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in _TIPOS_EQUIPO:
        raise ValueError(f"tipo inválido: '{v}'. Opciones: simple, kit, combo")
    return v


def _validar_precio_no_negativo(v):
    if v is not None and v < 0:
        raise ValueError("precio_jornada no puede ser negativo")
    return v


def _validar_cantidad_no_negativa(v):
    if v is not None and v < 0:
        raise ValueError("cantidad no puede ser negativa")
    return v


class EquipoCreate(BaseModel):
    nombre:           str
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         int             = Field(default=1, ge=0, le=9999)
    precio_jornada:   Optional[int]   = Field(default=None, ge=0)
    precio_usd:       Optional[float] = Field(default=None, ge=0)
    roi_pct:          Optional[float] = Field(default=None, ge=0, le=100)
    valor_reposicion: Optional[float] = Field(default=None, ge=0)
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = "Rambla"
    visible_catalogo: Optional[int]   = 1
    estado:           Optional[str]   = "operativo"   # operativo / en_mantenimiento / fuera_servicio
    ficha_completa:   Optional[bool]  = False
    # Categoría de specs (1 de las 5 del registry): define qué specs aplican.
    categoria_specs: Optional[str] = None
    # Tipo de producto: 'simple' = equipo suelto, 'kit' = con accesorios compartidos,
    # 'combo' = agrupación derivada. Gobierna precio, stock y disponibilidad.
    tipo:            Optional[str]   = "simple"

    @field_validator("precio_jornada")
    @classmethod
    def validate_precio(cls, v):
        return _validar_precio_no_negativo(v)

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v):
        return _validar_cantidad_no_negativa(v)

    @field_validator("categoria_specs")
    @classmethod
    def validate_categoria_specs(cls, v):
        return _validar_categoria_specs(v)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v):
        return _validar_tipo(v)


class EquipoUpdate(BaseModel):
    nombre:           Optional[str]   = None
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         Optional[int]   = Field(default=None, ge=0, le=9999)
    precio_jornada:   Optional[int]   = Field(default=None, ge=0)
    # Flag explícito que el frontend manda para indicar si el precio
    # viene de la fórmula (auto, false) o lo tipeó el admin a mano (true).
    # Si no se manda y se cambia precio_jornada, el endpoint infiere
    # según contexto (ver update_equipo).
    precio_jornada_manual: Optional[bool] = None
    precio_usd:       Optional[float] = Field(default=None, ge=0)
    roi_pct:          Optional[float] = Field(default=None, ge=0, le=100)
    valor_reposicion: Optional[float] = Field(default=None, ge=0)
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = None
    visible_catalogo: Optional[int]   = None
    estado:           Optional[str]   = None
    ficha_completa:   Optional[bool]  = None
    # Categoría de specs (1 de las 5 del registry): define qué specs aplican.
    categoria_specs: Optional[str] = None
    # Tipo de producto: 'simple' / 'kit' / 'combo'.
    tipo:            Optional[str]   = None

    @field_validator("precio_jornada")
    @classmethod
    def validate_precio(cls, v):
        return _validar_precio_no_negativo(v)

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v):
        return _validar_cantidad_no_negativa(v)

    @field_validator("categoria_specs")
    @classmethod
    def validate_categoria_specs(cls, v):
        return _validar_categoria_specs(v)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v):
        return _validar_tipo(v)


class BulkActionInput(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    action: str   # "set_visible" | "set_ficha_completa" | "set_categoria" | "add_categoria" | "remove_categoria" | "delete"
    visible: Optional[bool] = None
    ficha_completa: Optional[bool] = None
    categoria_id: Optional[int] = None
