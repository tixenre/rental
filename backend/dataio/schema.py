"""dataio/schema.py — Pydantic models para cada entidad del catálogo.

Estos modelos definen la forma exacta de los JSONs en `/data/catalog/*.json`.
Sirven tanto para validar al importar como para serializar al exportar.

Reglas:
- NUNCA incluir `id` SERIAL.
- FKs siempre como claves naturales (nombre, slug, path).
- M2M de equipos (categorías, etiquetas) embebidas dentro de `EquipoIn`
  para que `equipos.json` sea autosuficiente.
- `equipo_specs` y `equipo_fichas` viven en archivos aparte porque tienen
  más volumen y se editan independientemente de los datos básicos del equipo.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    """Base común — prohíbe campos extra para detectar typos en los JSONs."""

    model_config = ConfigDict(extra="forbid")


# ─────────────────────────────────────────────────────────────────────────────
# marcas.json
# ─────────────────────────────────────────────────────────────────────────────


class Marca(_Base):
    nombre: str
    logo_url: str | None = None
    visible: bool = True
    orden: int = 100
    destacada: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# categorias.json
# ─────────────────────────────────────────────────────────────────────────────


class Categoria(_Base):
    nombre: str
    parent_path: str | None = None  # Nombre del padre, None para raíces
    prioridad: int = 100
    visible: bool = True
    grupo_visual: str | None = None
    nombre_publico_template: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# etiquetas.json
# ─────────────────────────────────────────────────────────────────────────────


class Etiqueta(_Base):
    nombre: str
    prioridad: int = 100


# ─────────────────────────────────────────────────────────────────────────────
# spec_definitions.json
# ─────────────────────────────────────────────────────────────────────────────


class SpecRef(_Base):
    """Referencia composite a un spec_definition.

    `categoria_raiz_nombre` puede ser None para specs globales sin categoría
    (admin endpoint los crea como "free-floating").
    """

    categoria_raiz_nombre: str | None = None
    spec_key: str


class SpecDefinition(_Base):
    categoria_raiz_nombre: str | None = None  # FK → categorias.nombre
    spec_key: str
    label: str
    tipo: Literal["enum", "multi_enum", "number", "rango", "bool", "string"]
    unidad: str | None = None
    enum_options: list[Any] | None = None  # JSONB
    ayuda: str | None = None
    es_compatibilidad: bool = False
    compatibilidad_modo: Literal["exacta", "jerarquia"] = "exacta"
    rol_compatibilidad: str | None = None
    validado: bool = False
    tabla_columnas: list[dict[str, Any]] | dict[str, Any] | None = None
    output_config: dict[str, Any] | None = None
    favorito: bool = False
    en_nombre: bool = False
    en_filtros: bool = False
    prioridad: int = 100


# ─────────────────────────────────────────────────────────────────────────────
# categoria_spec_templates.json
# ─────────────────────────────────────────────────────────────────────────────


class CategoriaSpecTemplate(_Base):
    categoria_nombre: str  # FK → categorias.nombre
    spec_ref: SpecRef  # FK → spec_definitions(categoria_raiz_nombre, spec_key)
    prioridad: int = 100
    destacado: bool = False
    obligatorio: bool = False
    visible_en_card: bool = False
    visible_en_filtros: bool = False
    visible_en_nombre: bool = False
    ayuda: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# equipos.json (M2M embebidas)
# ─────────────────────────────────────────────────────────────────────────────


class EquipoEtiquetaRef(_Base):
    """Ref a una etiqueta dentro de un equipo, con metadata de la relación."""

    nombre: str
    origen: Literal["auto", "manual"] = "manual"
    orden: int = 0


class EquipoCategoriaRef(_Base):
    """Ref a una categoría dentro de un equipo (M2M embebida)."""

    nombre: str
    orden: int = 0


class Equipo(_Base):
    # Identidad
    slug: str  # clave natural (NEW: agregada por migración)
    nombre: str
    marca: str | None = None  # campo legacy TEXT, se mantiene
    modelo: str | None = None
    marca_nombre: str | None = None  # FK → marcas.nombre (resuelve brand_id)

    # Catálogo
    cantidad: int = 1
    precio_jornada: int | None = None
    precio_jornada_manual: bool = False
    precio_usd: float | None = None
    roi_pct: float | None = None
    valor_reposicion: float | None = None
    foto_url: str | None = None
    fecha_compra: str | None = None
    serie: str | None = None
    bh_url: str | None = None
    dueno: str | None = "Rambla"
    visible_catalogo: int = 1
    estado: str = "ok"
    ficha_completa: bool = False
    eliminado_at: str | None = None  # ISO timestamp o null

    # Nombre público
    nombre_publico_override: str | None = None
    nombre_publico_revisado: bool = False

    # Ranking
    relevancia_manual: int = 100

    # M2M embebida
    categorias: list[EquipoCategoriaRef] = Field(default_factory=list)
    etiquetas: list[EquipoEtiquetaRef] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# equipo_specs.json
# ─────────────────────────────────────────────────────────────────────────────


class EquipoSpec(_Base):
    equipo_slug: str
    spec_ref: SpecRef
    value: str  # serializado igual que en DB (TEXT)


# ─────────────────────────────────────────────────────────────────────────────
# equipo_fichas.json
# ─────────────────────────────────────────────────────────────────────────────


class EquipoFicha(_Base):
    equipo_slug: str
    descripcion: str | None = None
    notas: str | None = None
    specs_json: str | None = None
    montura: str | None = None
    formato: str | None = None
    resolucion: str | None = None
    keywords_json: str | None = None
    nombre_publico_template: str | None = None
    peso: str | None = None
    dimensiones: str | None = None
    alimentacion: str | None = None
    incluye_json: str | None = None
    conectividad_json: str | None = None
    compatible_con_json: str | None = None
    video_url: str | None = None
    precio_bh_usd: float | None = None
    fuente_url: str | None = None
    fuente_titulo: str | None = None
    raw_json: str | None = None
    enriquecido_at: str | None = None
    enriquecido_fuente: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# OPERATIONAL — clientes, alquileres (con items/pagos embebidos)
# ─────────────────────────────────────────────────────────────────────────────
#
# IMPORTANTE: estos JSONs NUNCA se commitean al repo (contienen datos
# personales y comerciales). Solo se generan ad-hoc vía /admin/dataio o
# CLI para backups o migración entre ambientes.


class Cliente(_Base):
    # Clave natural
    email: str  # UNIQUE en DB
    # Datos personales
    nombre: str
    apellido: str
    telefono: str | None = None
    direccion: str | None = None
    direccion_maps_url: str | None = None
    cuit: str | None = None
    notas: str | None = None
    # Comercial / fiscal
    descuento: float = 0.0
    perfil_impuestos: str = "consumidor_final"
    razon_social: str | None = None
    domicilio_fiscal: str | None = None
    email_facturacion: str | None = None
    # Link a Supabase Auth (opcional; no portable entre proyectos Supabase)
    supabase_uid: str | None = None


class AlquilerItemRef(_Base):
    """Item embebido dentro de un Alquiler (no es entidad top-level)."""
    equipo_slug: str  # FK → equipos.slug
    cantidad: int = 1
    precio_jornada: int = 0
    subtotal: int = 0


class AlquilerPagoRef(_Base):
    """Pago embebido dentro de un Alquiler. No tiene clave natural propia
    — la combinación (numero_pedido + fecha + monto + concepto) se trata
    como identidad para evitar duplicarlos en re-imports.
    """
    monto: int
    concepto: str | None = None
    fecha: str  # ISO date string


class Alquiler(_Base):
    # Clave natural
    numero_pedido: int  # UNIQUE en DB
    # FK natural → cliente (puede ser null si cliente fue eliminado).
    # Los campos cliente_* denormalizados preservan el snapshot histórico.
    cliente_email: str | None = None
    cliente_nombre: str
    cliente_telefono: str | None = None
    # Estado y fechas
    estado: str = "presupuesto"
    fecha_desde: str
    fecha_hasta: str
    # Montos
    monto_total: int = 0
    monto_pagado: int = 0
    descuento_pct: float = 0.0
    # Metadata
    notas: str | None = None
    fuente: str = "sistema"
    # Embebidas para autosuficiencia
    items: list[AlquilerItemRef] = Field(default_factory=list)
    pagos: list[AlquilerPagoRef] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Mapping entity → model (usado por exporters/importers)
# ─────────────────────────────────────────────────────────────────────────────

ENTITY_MODELS: dict[str, type[_Base]] = {
    "marcas": Marca,
    "categorias": Categoria,
    "etiquetas": Etiqueta,
    "spec_definitions": SpecDefinition,
    "categoria_spec_templates": CategoriaSpecTemplate,
    "equipos": Equipo,
    "equipo_specs": EquipoSpec,
    "equipo_fichas": EquipoFicha,
    "clientes": Cliente,
    "alquileres": Alquiler,
}
