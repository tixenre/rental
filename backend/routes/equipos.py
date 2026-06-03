"""
routes/equipos.py — CRUD de equipos, kits, etiquetas, categorías y fichas.
"""

import calendar as _cal
import datetime
import logging
import os
import re
import unicodedata
from datetime import date as _date
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Query, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field

from database import (
    get_db, row_to_dict, attach_tags, attach_kit, attach_categorias,
    attach_ficha, attach_specs_destacados, attach_specs_estructuradas,
    regenerate_auto_tags, MARCA_SUBQUERY,
)
from reservas import ESTADOS_RESERVADO, calcular_disponibilidad
from reservas.disponibilidad import _derivar_compuestos
from reservas.semantics import componentes_de
from routes.auth import get_session
from admin_guard import require_admin
from services.nombre_service import actualizar_nombres_de
from services.spec_render import (
    format_tabla_value,
    norm_spec_label,
)

router = APIRouter()


# ── Normalización de specs del autocompletar (#209) ───────────────────────────
# Las specs vienen de scrapers de B&H/Adorama en inglés con unidades imperiales.
# Acá las traducimos a español + métrico para tener ficha técnica consistente.

import re as _re_specs

# Mapping de labels EN → ES (case-insensitive sobre la clave). Si no está, el
# label queda como vino (el admin puede ajustar a mano).
_SPEC_KEY_TRANSLATIONS = {
    "weight": "Peso",
    "dimensions": "Dimensiones",
    "size": "Tamaño",
    "power consumption": "Consumo",
    "power": "Alimentación",
    "voltage": "Voltaje",
    "battery": "Batería",
    "battery life": "Duración de batería",
    "battery type": "Tipo de batería",
    "operating temperature": "Temperatura de operación",
    "image sensor": "Sensor",
    "sensor": "Sensor",
    "sensor type": "Tipo de sensor",
    "sensor size": "Tamaño del sensor",
    "effective pixels": "Píxeles efectivos",
    "lens mount": "Montura",
    "mount": "Montura",
    "format": "Formato",
    "iso": "Rango ISO",
    "iso range": "Rango ISO",
    "iso sensitivity": "Sensibilidad ISO",
    "shutter speed": "Velocidad de obturación",
    "video resolution": "Resolución de video",
    "resolution": "Resolución",
    "max resolution": "Resolución máxima",
    "frame rate": "Tasa de cuadros",
    "fps": "Cuadros por segundo",
    "memory card": "Tarjeta de memoria",
    "storage": "Almacenamiento",
    "internal storage": "Almacenamiento interno",
    "wireless": "Conectividad inalámbrica",
    "connectivity": "Conectividad",
    "interface": "Interfaz",
    "audio input": "Entrada de audio",
    "audio output": "Salida de audio",
    "headphone jack": "Salida auriculares",
    "microphone": "Micrófono",
    "viewfinder": "Visor",
    "lcd": "Pantalla LCD",
    "monitor": "Monitor",
    "display": "Pantalla",
    "focal length": "Distancia focal",
    "aperture": "Apertura",
    "max aperture": "Apertura máxima",
    "min aperture": "Apertura mínima",
    "filter size": "Tamaño de filtro",
    "minimum focus distance": "Distancia mínima de enfoque",
    "min focus distance": "Distancia mínima de enfoque",
    "elements/groups": "Elementos / grupos",
    "elements / groups": "Elementos / grupos",
    "lens construction": "Construcción óptica",
    "diaphragm": "Diafragma",
    "blades": "Hojas del diafragma",
    "image stabilization": "Estabilización",
    "autofocus": "Autoenfoque",
    "color": "Color",
    "material": "Material",
    "warranty": "Garantía",
    # ── Calibración con relevamiento Firecrawl (22 productos B&H) ─────
    # Labels detectados que no estaban en el mapping. Mantienen el espíritu
    # del normalizer: traducir al castellano canónico para que el observatorio
    # los matchee contra el catálogo (con el sistema de aliases agregado en
    # PR #359, varios mappean a specs ya existentes).
    #
    # Packaging / generales
    "package weight": "Peso del paquete",
    "box dimensions (lxwxh)": "Dimensiones del paquete",
    "item type": "Tipo de ítem",
    "key features": "Características clave",
    "mounting options": "Opciones de montaje",
    "controls": "Controles",
    "display type": "Tipo de pantalla",
    # Audio (mics, wireless, lavalier, shotgun)
    "audio i/o": "Entradas/salidas de audio",
    "polar pattern": "Patrón polar",
    "frequency response": "Respuesta de frecuencia",
    "maximum spl": "SPL máximo",
    "analog output": "Salida analógica",
    "microphone type": "Tipo de micrófono",
    "receiver type": "Tipo de receptor",
    "element type": "Tipo de elemento",
    "sound field": "Campo de sonido",
    "number of audio channels": "Canales de audio",
    "included transmitters": "Transmisores incluidos",
    "diversity": "Diversidad",
    "max operating range": "Rango máx. de operación",
    "max transmitters per band": "Máx. transmisores por banda",
    "encryption": "Encriptación",
    "built-in recorder": "Grabador interno",
    "timecode support": "Soporte timecode",
    "antenna": "Antena",
    "rf frequency band": "Banda RF",
    "wireless technology": "Tecnología inalámbrica",
    "gain range": "Rango de ganancia",
    # Cámaras
    "effective sensor resolution": "Resolución del sensor",
    "iso/gain sensitivity": "ISO/Ganancia",
    "max recording modes": "Modos de grabación máx",
    "max video output": "Salida video máx",
    "video i/o": "Entradas/salidas de video",
    "power i/o": "Entradas/salidas de poder",
    "other i/o": "Otras entradas/salidas",
    "media/memory card slot": "Tipo de memoria",
    # Lentes
    "lens format coverage": "Cobertura de formato",
    "angle of view": "Ángulo de visión",
    "magnification": "Magnificación",
    "optical design": "Construcción óptica",
    "aperture/iris blades": "Hojas del diafragma",
    "focus type": "Tipo de enfoque",
    # Iluminación
    "input power": "Potencia de entrada",
    "output": "Salida lumínica",
    "cct": "Temperatura color",
    "light loss/gain": "Pérdida/ganancia de luz",
    # Otros
    "included charging case": "Estuche de carga incluido",
    "mobile app compatible": "Compatible con app móvil",
    "power sources": "Fuentes de alimentación",
    "usb/lightning connectivity": "Conectividad USB/Lightning",
    "battery": "Batería",
    "lens mount": "Lens mount",
}


def _convert_dim_pattern(s: str, unit_regex: str, factor: float, target_unit: str) -> str:
    """Maneja casos `N x N x N <unit>` aplicando la conversión a TODOS los números."""
    pattern = rf"((?:\d+(?:\.\d+)?\s*x\s*)+\d+(?:\.\d+)?)\s*(?:{unit_regex})\b"
    def repl(m):
        nums_part = _re_specs.sub(
            r"\d+(?:\.\d+)?",
            lambda nm: f"{float(nm.group(0)) * factor:.1f}",
            m.group(1),
        )
        return f"{nums_part} {target_unit}"
    return _re_specs.sub(pattern, repl, s, flags=_re_specs.IGNORECASE)


def _convert_range_pattern(s: str, unit_regex: str, conv, target_unit: str) -> str:
    """Maneja casos `N to N <unit>` aplicando la conversión a ambos extremos."""
    pattern = rf"(-?\d+(?:\.\d+)?)\s*(?:to|-)\s*(-?\d+(?:\.\d+)?)\s*°?\s*(?:{unit_regex})\b"
    def repl(m):
        a, b = float(m.group(1)), float(m.group(2))
        return f"{conv(a):.1f} a {conv(b):.1f} {target_unit}"
    return _re_specs.sub(pattern, repl, s, flags=_re_specs.IGNORECASE)


def _convert_units_in_value(value: str) -> str:
    """Convierte unidades imperiales a métricas dentro de un string de spec.

    Handlea:
    - Single: `1.5 lbs` → `0.68 kg`
    - Dimensions: `10 x 5 x 3 in` → `25.4 x 12.7 x 7.6 cm`
    - Ranges: `32 to 104 °F` → `0.0 a 40.0 °C`

    No toca strings que no matchean (idempotente).
    """
    if not value or not isinstance(value, str):
        return value
    s = value

    # Rangos primero (sino el regex de single number se los come)
    s = _convert_range_pattern(s, "F", lambda x: (x - 32) * 5/9, "°C")

    # Dimensiones (N x N x N unit)
    s = _convert_dim_pattern(s, r"inches?|in\.?|\"", 2.54, "cm")
    s = _convert_dim_pattern(s, r"feet|ft\.?", 30.48, "cm")
    s = _convert_dim_pattern(s, r"lbs?", 0.4536, "kg")

    # Singles
    # lbs / lb → kg
    s = _re_specs.sub(
        r"(\d+(?:\.\d+)?)\s*lbs?\b",
        lambda m: f"{float(m.group(1)) * 0.4536:.2f} kg",
        s, flags=_re_specs.IGNORECASE,
    )
    # oz → g
    s = _re_specs.sub(
        r"(\d+(?:\.\d+)?)\s*oz\b",
        lambda m: f"{float(m.group(1)) * 28.35:.0f} g",
        s, flags=_re_specs.IGNORECASE,
    )
    # inches / in / " → cm (negative lookahead para no matchear "inn", "inch_word")
    s = _re_specs.sub(
        r"(\d+(?:\.\d+)?)\s*(?:inches?|in\.?|\")(?![a-zA-Z])",
        lambda m: f"{float(m.group(1)) * 2.54:.1f} cm",
        s, flags=_re_specs.IGNORECASE,
    )
    # feet / ft → m
    s = _re_specs.sub(
        r"(\d+(?:\.\d+)?)\s*(?:feet|ft\.?)\b",
        lambda m: f"{float(m.group(1)) * 0.3048:.2f} m",
        s, flags=_re_specs.IGNORECASE,
    )
    # °F → °C single
    s = _re_specs.sub(
        r"(-?\d+(?:\.\d+)?)\s*°?\s*F\b",
        lambda m: f"{(float(m.group(1)) - 32) * 5/9:.1f} °C",
        s, flags=_re_specs.IGNORECASE,
    )
    return s


def _translate_spec_label(label: str) -> str:
    """Traduce un label de spec EN→ES si está en el mapping."""
    if not label:
        return label
    key = label.strip().lower().rstrip(":").strip()
    return _SPEC_KEY_TRANSLATIONS.get(key, label)


def normalize_specs(specs: list[dict]) -> list[dict]:
    """Normaliza una lista de specs: traduce labels + convierte unidades.

    No toca specs que no reconocemos (label queda como vino).
    Idempotente: aplicar dos veces da el mismo resultado.
    """
    if not specs:
        return specs
    out = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        label = spec.get("label", "")
        value = spec.get("value", "")
        out.append({
            "label": _translate_spec_label(str(label)),
            "value": _convert_units_in_value(str(value)),
        })
    return out


# ── Constantes de fotos / scraping ───────────────────────────────────────────
# Antes estaban hardcodeadas como números mágicos en 3 lugares con valores
# distintos (6, 8, 10, 18). Centralizadas acá con nombres explícitos.

# Cuántos candidatos guarda cada scrape individual (B&H o sitio oficial).
# Más alto que esto = más data redundante; el merge ya deduplica entre fuentes.
MAX_PHOTO_CANDIDATES_PER_SCRAPE = 6

# Cuántos candidatos validamos vía HTTP en /enriquecer (B&H + alt mergeados).
# Validar es lento (HEAD por imagen) → mantener bajo.
MAX_PHOTO_CANDIDATES_TO_VALIDATE = 8

# /buscar-fotos: cuántos validamos y cuántos devolvemos. Este flow inspecciona
# más fuentes (Wikipedia, reviews, manufacturer) por eso el límite es mayor.
MAX_PHOTO_CANDIDATES_BUSCAR_VALIDATE = 18
MAX_PHOTO_CANDIDATES_BUSCAR_RETURN   = 10


# ── Modelos ──────────────────────────────────────────────────────────────────

def _validar_categoria_specs(v: Optional[str]) -> Optional[str]:
    """Valida que la categoría de specs sea una del registry (o None)."""
    if v is None or v == "":
        return None
    from specs import REGISTRY
    if v not in REGISTRY.categorias:
        validas = ", ".join(REGISTRY.categorias)
        raise ValueError(f"categoria_specs inválida: '{v}'. Opciones: {validas}")
    return v


_TIPOS_EQUIPO = frozenset({"simple", "kit", "combo"})


def _validar_tipo(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in _TIPOS_EQUIPO:
        raise ValueError(f"tipo inválido: '{v}'. Opciones: simple, kit, combo")
    return v


class EquipoCreate(BaseModel):
    from pydantic import field_validator
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
        if v is not None and v < 0:
            raise ValueError("precio_jornada no puede ser negativo")
        return v

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v):
        if v is not None and v < 0:
            raise ValueError("cantidad no puede ser negativa")
        return v

    @field_validator("categoria_specs")
    @classmethod
    def validate_categoria_specs(cls, v):
        return _validar_categoria_specs(v)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v):
        return _validar_tipo(v)


class EquipoUpdate(BaseModel):
    from pydantic import field_validator
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
        if v is not None and v < 0:
            raise ValueError("precio_jornada no puede ser negativo")
        return v

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v):
        if v is not None and v < 0:
            raise ValueError("cantidad no puede ser negativa")
        return v

    @field_validator("categoria_specs")
    @classmethod
    def validate_categoria_specs(cls, v):
        return _validar_categoria_specs(v)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v):
        return _validar_tipo(v)


class FichaUpdate(BaseModel):
    """Update parcial de equipo_fichas. Las specs físicas (montura/
    formato/resolucion/peso/dimensiones/alimentacion) viven en
    equipo_specs desde Fase F — actualizar vía PUT /admin/equipos/{id}/specs.
    `specs_json` y `raw_json` eliminados en Fase E."""
    descripcion:   Optional[str] = None
    notas:         Optional[str] = None
    keywords_json: Optional[str] = None
    nombre_publico_template: Optional[str] = None
    # Listas y multimedia del enriquecimiento (no son specs estructuradas)
    incluye_json:        Optional[str]   = None
    conectividad_json:   Optional[str]   = None
    compatible_con_json: Optional[str]   = None
    video_url:           Optional[str]   = None
    precio_bh_usd:       Optional[float] = None
    fuente_url:          Optional[str]   = None
    fuente_titulo:       Optional[str]   = None
    enriquecido_fuente:  Optional[str]   = None
    # B1 #635: contenido incluido (dim. 3) — JSON de [{nombre, cantidad, foto_url?}]
    contenido_incluido_json: Optional[str] = None

    from pydantic import field_validator as _fv
    import json as _json

    @_fv("contenido_incluido_json")
    @classmethod
    def _validar_contenido_incluido(cls, v):
        import json as _j
        if v is None:
            return v
        try:
            items = _j.loads(v)
        except Exception:
            raise ValueError("contenido_incluido_json: JSON inválido")
        if not isinstance(items, list):
            raise ValueError("contenido_incluido_json: debe ser una lista")
        if len(items) > 100:
            raise ValueError("contenido_incluido_json: máximo 100 ítems")
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"ítem {idx}: debe ser un objeto")
            nombre = item.get("nombre", "")
            if not isinstance(nombre, str) or not nombre.strip():
                raise ValueError(f"ítem {idx}: 'nombre' no puede estar vacío")
            cantidad = item.get("cantidad", 1)
            if not isinstance(cantidad, int) or not (1 <= cantidad <= 999):
                raise ValueError(f"ítem {idx}: 'cantidad' debe ser un entero entre 1 y 999")
        return v


class KitItem(BaseModel):
    componente_id: int
    cantidad:      int   = Field(default=1, ge=1, le=9999)
    # default 0.0 (NO None): la columna kit_componentes.descuento_pct es NOT NULL,
    # un NULL explícito la viola. Rango 0..100 (% de descuento por línea de combo).
    descuento_pct: float = Field(default=0.0, ge=0, le=100)
    esencial:      bool  = True


class KitReorder(BaseModel):
    orden: list[int]  # lista de componente_id en el orden deseado


class EtiquetasUpdate(BaseModel):
    # Lista ordenada de etiquetas MANUALES. Las auto (marca/modelo/nombre/categorías)
    # se regeneran solas, no las toques desde acá.
    etiquetas: list[str]


class CategoriasUpdate(BaseModel):
    # Lista de IDs de categorías hoja (o raíz) asignadas al equipo.
    categoria_ids: list[int]


class MantenimientoCreate(BaseModel):
    fecha:            str
    tipo:             Optional[str] = "revision"   # revision / reparacion / limpieza / otro
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None
    # Bloqueo de disponibilidad: si bloquea_stock=True, saca `cantidad`
    # unidades del equipo durante [fecha, fecha_hasta].
    fecha_hasta:      Optional[str] = None
    cantidad:         int = 1
    bloquea_stock:    bool = False


class MantenimientoUpdate(BaseModel):
    fecha:            Optional[str] = None
    tipo:             Optional[str] = None
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None
    fecha_hasta:      Optional[str] = None
    cantidad:         Optional[int] = None
    bloquea_stock:    Optional[bool] = None


# ── Disponibilidad en tiempo real ────────────────────────────────────────────

@router.get("/equipos/afuera")
def equipos_afuera():
    """
    Devuelve los equipos actualmente retirados (pedidos en estado 'retirado'
    con fecha_hasta >= hoy), con cantidad afuera y fecha de devolución.
    Respuesta: { "equipo_id": { cantidad_afuera, stock_total, devuelve, pedidos } }
    """
    conn  = get_db()
    today = datetime.date.today().isoformat()
    try:
        rows = conn.execute("""
            SELECT
                pi.equipo_id,
                e.cantidad                                              AS stock_total,
                SUM(pi.cantidad)                                        AS cantidad_afuera,
                MIN(p.fecha_hasta)                                      AS devuelve_pronto,
                MAX(p.fecha_hasta)                                      AS devuelve_ultimo,
                STRING_AGG(
                    COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre),
                    ', '
                )                                                       AS clientes
            FROM alquiler_items pi
            JOIN alquileres  p ON p.id  = pi.pedido_id
            JOIN equipos  e ON e.id  = pi.equipo_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado    = 'retirado'
              AND p.fecha_hasta >= ?
            GROUP BY pi.equipo_id, e.cantidad
        """, (today,)).fetchall()
        return {str(r["equipo_id"]): row_to_dict(r) for r in rows}
    finally:
        conn.close()


@router.get("/equipos/kpis")
def equipos_kpis(request: Request):
    """KPIs del inventario para el header de /admin/equipos:
    - total: equipos activos (no eliminados).
    - en_uso_hoy: unidades en pedidos retirados que solapan hoy.
    - mantenimiento: equipos con mantenimiento que bloquea stock activo hoy.
    """
    require_admin(request)
    conn = get_db()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM equipos WHERE eliminado_at IS NULL AND es_recurso_interno = FALSE"
        ).fetchone()[0]
        en_uso_hoy = conn.execute("""
            SELECT COALESCE(SUM(pi.cantidad), 0)
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE p.estado = 'retirado'
              AND p.fecha_desde::date <= CURRENT_DATE
              AND p.fecha_hasta::date >= CURRENT_DATE
        """).fetchone()[0]
        mantenimiento = conn.execute("""
            SELECT COUNT(DISTINCT equipo_id)
            FROM equipo_mantenimiento
            WHERE bloquea_stock = TRUE
              AND fecha::date <= CURRENT_DATE
              AND COALESCE(fecha_hasta, fecha)::date >= CURRENT_DATE
        """).fetchone()[0]
        return {
            "total": int(total or 0),
            "en_uso_hoy": int(en_uso_hoy or 0),
            "mantenimiento": int(mantenimiento or 0),
        }
    finally:
        conn.close()


# ── Rutas de equipos ─────────────────────────────────────────────────────────


def _stock_sin_reservas(conn) -> dict[int, int]:
    """Stock teórico de kits/combos derivado solo del stock de componentes, sin
    descontar ninguna reserva. Detecta kits imposibles de armar (components <
    cantidad requerida) independientemente de las fechas seleccionadas."""
    raw = {
        r["id"]: r["cantidad"]
        for r in conn.execute(
            "SELECT id, cantidad FROM equipos WHERE eliminado_at IS NULL"
        ).fetchall()
    }
    return _derivar_compuestos(raw, componentes_de(conn))


def _attach_disponibilidad(conn, equipos: list, desde: str, hasta: str) -> list:
    """Inyecta el campo `disponible` por equipo, usando la fuente única de
    lectura del motor (`reservas.calcular_disponibilidad`).

    Antes esta función tenía su propia query (directas + vía kit) que NO restaba
    mantenimiento ni aplicaba buffer → mostraba disponibilidad inflada respecto
    del gate real (bug #619). Ahora delega en el motor, así el catálogo refleja
    exactamente lo mismo que el chequeo de confirmación."""
    disp = calcular_disponibilidad(conn, desde, hasta)
    for eq in equipos:
        eid = eq["id"]
        # `calcular_disponibilidad` indexa por str(equipo_id); fallback al stock
        # propio si el equipo no aparece (ej. equipo nuevo sin filas asociadas).
        eq["disponible"] = disp.get(str(eid), eq.get("cantidad", 0))
    return equipos


@router.get("/equipos")
def list_equipos(
    request:       Request,
    q:                Optional[str]  = Query(None),
    etiqueta:         Optional[str]  = Query(None),
    categoria:        Optional[str]  = Query(None),
    marca:            Optional[str]  = Query(None, description="Filtra por nombre exacto de marca"),
    solo_visibles:    Optional[bool] = Query(None),
    solo_incompletos: Optional[bool] = Query(None),
    falta: Optional[str] = Query(None, description="Filtra equipos sin un campo: foto|categoria|nombre_publico|descripcion|serie|valor_reposicion (#350)"),
    incluir_eliminados: Optional[bool] = Query(None, description="Si true (solo admin), incluye soft-deleted"),
    solo_eliminados:  Optional[bool] = Query(None, description="Si true (solo admin), SOLO soft-deleted (vista papelera)"),
    sort:          Optional[str]  = Query(None, description="ranking | nombre | precio_asc | precio_desc | id"),
    spec:          Optional[list[str]] = Query(None, description="Filtros por specs: spec=key:valor"),
    page:          int = Query(1, ge=1),
    per_page:      int = Query(200, ge=1, le=500),
    desde:         Optional[str]  = Query(None, description="Fecha inicio (YYYY-MM-DD) para calcular disponibilidad"),
    hasta:         Optional[str]  = Query(None, description="Fecha fin (YYYY-MM-DD) para calcular disponibilidad"),
):
    """Lista equipos con sort y filtros.

    sort por defecto: "ranking" → ORDER BY relevancia_manual ASC,
    popularidad_score DESC, nombre ASC. Otros valores: nombre,
    precio_asc, precio_desc, id.

    spec: filtros por specs estructurados. Formato `key:valor`. Múltiples
    valores se AND-ean. Ej. `?spec=montura:E&spec=video_max:4K` filtra
    equipos con montura=E Y video_max=4K.
    """
    conn   = get_db()
    offset = (page - 1) * per_page
    base_sql = "FROM equipos e WHERE 1=1"
    params: list = []

    # El centinela del Estudio (es_recurso_interno) no es un producto del
    # catálogo: se excluye SIEMPRE (público y admin), filtros incluidos.
    base_sql += " AND e.es_recurso_interno = FALSE"

    is_admin = bool(get_session(request))
    if solo_visibles or not is_admin:
        base_sql += " AND e.visible_catalogo = 1 AND e.estado != 'fuera_servicio'"

    # Filtro admin: equipos cuya ficha el admin aún no marcó como completa.
    if solo_incompletos and is_admin:
        base_sql += " AND e.ficha_completa = FALSE"

    # Filtro por campo faltante (#350) — alimenta los CTAs del dashboard de calidad.
    # Mismos criterios que /api/admin/inventario/calidad para consistencia.
    if falta and is_admin:
        FALTA_SQL = {
            "foto":              " AND NULLIF(TRIM(COALESCE(e.foto_url, '')), '') IS NULL",
            "nombre_publico":    " AND NULLIF(TRIM(COALESCE(e.nombre_publico, '')), '') IS NULL",
            "serie":             " AND NULLIF(TRIM(COALESCE(e.serie, '')), '') IS NULL",
            "valor_reposicion":  " AND (e.valor_reposicion IS NULL OR e.valor_reposicion = 0)",
            "descripcion": (
                " AND NOT EXISTS ("
                " SELECT 1 FROM equipo_fichas f"
                " WHERE f.equipo_id = e.id"
                " AND NULLIF(TRIM(COALESCE(f.descripcion, '')), '') IS NOT NULL)"
            ),
            "categoria": (
                " AND NOT EXISTS ("
                " SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
            ),
        }
        if falta in FALTA_SQL:
            base_sql += FALTA_SQL[falta]

    # Soft delete (#206): por default solo activos. Admin puede pedir ver
    # eliminados (papelera) o todos.
    if is_admin and solo_eliminados:
        base_sql += " AND e.eliminado_at IS NOT NULL"
    elif is_admin and incluir_eliminados:
        pass  # no filter
    else:
        base_sql += " AND e.eliminado_at IS NULL"

    # ── Filtros por specs estructurados (PR E) ──
    # Cada `spec=key:valor` agrega un AND EXISTS sobre equipo_specs.
    # Post refactor unificar_specs_definitions: el key del query string sigue
    # siendo el spec_key humano (montura, formato, etc.); resolvemos a
    # spec_def_id vía JOIN.
    if spec:
        for s in spec:
            if ":" not in s:
                continue
            key, value = s.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if not key or not value:
                continue
            base_sql += (
                " AND EXISTS ("
                " SELECT 1 FROM equipo_specs es"
                " JOIN spec_definitions sd ON sd.id = es.spec_def_id"
                " WHERE es.equipo_id = e.id AND LOWER(sd.spec_key) = ?"
                " AND LOWER(es.value) = LOWER(?))"
            )
            params += [key, value]
    if q:
        # Búsqueda fuzzy global: ILIKE case-insensitive sobre nombre/marca/modelo
        # del equipo + serie + campos de la ficha (descripción, specs, keywords).
        # Convierte la barra en un find-anything: buscás "log3" o "iso 25600" y
        # aparece el equipo aunque la palabra esté en un spec, no en el nombre.
        like = f"%{q}%"
        base_sql += """ AND (
            e.nombre ILIKE ?
            OR COALESCE((SELECT nombre FROM marcas WHERE id = e.brand_id), '') ILIKE ?
            OR COALESCE(e.modelo, '') ILIKE ?
            OR COALESCE(e.serie, '') ILIKE ?
            OR EXISTS (
                SELECT 1 FROM equipo_fichas ef
                WHERE ef.equipo_id = e.id AND (
                    COALESCE(ef.descripcion, '') ILIKE ?
                    OR COALESCE(ef.keywords_json, '') ILIKE ?
                )
            )
        )"""
        params += [like] * 6
    if categoria:
        # Filtro recursivo: si es padre, incluye descendientes (árbol de `categorias`).
        # Acepta id numérico o nombre.
        try:
            cat_id_int = int(categoria)
            base_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM categorias WHERE id = ?
                        UNION ALL
                        SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                    )
                    SELECT id FROM sub
                )
              )"""
            params.append(cat_id_int)
        except (TypeError, ValueError):
            base_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM categorias WHERE nombre = ?
                        UNION ALL
                        SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                    )
                    SELECT id FROM sub
                )
              )"""
            params.append(categoria)
    if etiqueta:
        # Filtro plano por nombre de etiqueta (la bolsa ya no es jerárquica).
        base_sql += """
          AND e.id IN (
            SELECT ee.equipo_id FROM equipo_etiquetas ee
            JOIN etiquetas et ON et.id = ee.etiqueta_id
            WHERE LOWER(et.nombre) = LOWER(?)
          )"""
        params.append(etiqueta)

    if marca:
        # Filtro por marca exacta (case-insensitive) contra marcas.nombre (brand_id FK).
        base_sql += " AND LOWER(COALESCE((SELECT nombre FROM marcas WHERE id = e.brand_id), '')) = LOWER(?)"
        params.append(marca)

    # ── Sort ──
    # Default: ranking compuesto (relevancia_manual + popularidad_score).
    # Esto pone los flagship arriba y desempata por uso real.
    order_clause = {
        None: "ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC",
        "ranking": "ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC",
        "nombre": "ORDER BY COALESCE(e.nombre_publico, e.nombre) ASC",
        "precio_asc": "ORDER BY e.precio_jornada ASC NULLS LAST, e.nombre ASC",
        "precio_desc": "ORDER BY e.precio_jornada DESC NULLS LAST, e.nombre ASC",
        "id": "ORDER BY e.id ASC",
    }.get(sort, "ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC")

    try:
        total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT e.*, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca {base_sql} {order_clause} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        equipos = [row_to_dict(r) for r in rows]

        # Attach brand object (id, nombre, logo_url) — batched (#350 perf).
        # Antes era 1 query por equipo (N+1). Con 168 equipos sobre Railway
        # eso significaba 60s+ de latencia. Ahora una sola query.
        brand_ids = {e['brand_id'] for e in equipos if e.get('brand_id')}
        brands_map: dict = {}
        if brand_ids:
            placeholders = ",".join(["%s"] * len(brand_ids))
            brand_rows = conn.execute(
                f"SELECT id, nombre, logo_url FROM marcas WHERE id IN ({placeholders})",
                tuple(brand_ids),
            ).fetchall()
            brands_map = {r["id"]: row_to_dict(r) for r in brand_rows}
        for equipo in equipos:
            bid = equipo.get('brand_id')
            equipo['brand'] = brands_map.get(bid) if bid else None

        equipos = attach_tags(conn, equipos)
        equipos = attach_kit(conn, equipos)
        equipos = attach_categorias(conn, equipos)
        equipos = attach_ficha(conn, equipos)
        # Fase D: specs estructuradas para el catálogo público. Cada
        # equipo recibe `specs: {spec_key: {label, value, ...}}` desde
        # equipo_specs JOIN spec_definitions JOIN template.
        equipos = attach_specs_estructuradas(conn, equipos)
        equipos = attach_specs_destacados(conn, equipos)

        # Filtrar kits/combos que no pueden armarse ni una vez (stock de
        # componentes insuficiente, sin considerar reservas). Solo para catálogo
        # público — el admin los sigue viendo para poder corregirlos.
        # Solo aplica a kits (los que tienen kit_componentes) para no afectar
        # equipos hoja con cantidad=0. Las claves de stock_teo son str(id).
        if not is_admin:
            stock_teo = _stock_sin_reservas(conn)
            equipos = [
                e for e in equipos
                if not e.get("kit")
                or stock_teo.get(str(e["id"]), 0) > 0
            ]

        if desde and hasta:
            equipos = _attach_disponibilidad(conn, equipos, desde, hasta)

        return {"total": total, "page": page, "per_page": per_page, "items": equipos}
    finally:
        conn.close()


@router.get("/equipos/{id_or_slug}")
def get_equipo(id_or_slug: str):
    """Devuelve el detalle de un equipo.

    Acepta tanto ID numérico puro (`47`) como slug-id mixto al estilo
    Stack Overflow (`sony-fx3-cuerpo-47`). El slug es solo cosmético —
    el ID al final es lo que importa. Esto mejora SEO (keywords en URL)
    sin perder back-compat con URLs viejas `/equipo/47`.

    Si el cliente manda solo el slug sin ID (`sony-fx3-cuerpo`), devuelve
    400 — preferimos ser explícitos y no adivinar.
    """
    # Caso 1: ID puro (compat con URLs viejas)
    if id_or_slug.isdigit():
        actual_id = int(id_or_slug)
    else:
        # Caso 2: slug-id, extraer el ID del final.
        m = re.search(r"-(\d+)$", id_or_slug)
        if not m:
            raise HTTPException(400, "URL inválida — falta el id del equipo")
        actual_id = int(m.group(1))

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id = ?", (actual_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_ficha(conn, [equipo])[0]
        equipo = attach_categorias(conn, [equipo])[0]
        # Specs estructuradas (Fase D): el catálogo público lee
        # `equipo.specs` (dict keyed por spec_key) en vez de las columnas
        # legacy de equipo_fichas. Mantenemos `ficha` para back-compat.
        equipo = attach_specs_estructuradas(conn, [equipo])[0]
        kit = conn.execute("""
            SELECT kc.componente_id, kc.cantidad, kc.descuento_pct, kc.esencial,
                   e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.foto_url
            FROM kit_componentes kc JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?  ORDER BY kc.orden ASC, e.nombre ASC
        """, (actual_id,)).fetchall()
        equipo["kit"] = [row_to_dict(r) for r in kit]
        return equipo
    finally:
        conn.close()


# Series tipo "N/A", "ND", "-", "Sin serie" se aceptan duplicadas — son
# placeholders comunes para equipos sin serial real.
_PLACEHOLDER_SERIE_RE = re.compile(r"^(n/?a|n/?d|sin\s*serie|-+)$", re.IGNORECASE)


def _serie_es_placeholder(serie: Optional[str]) -> bool:
    if not serie:
        return True
    return bool(_PLACEHOLDER_SERIE_RE.match(serie.strip()))


def _check_serie_unica(conn, serie: Optional[str], exclude_id: Optional[int] = None) -> None:
    """Lanza 409 si la serie ya existe en otro equipo activo (no eliminado).
    Series placeholder (N/A, ND, -, sin serie) NO se chequean."""
    if _serie_es_placeholder(serie):
        return
    serie_norm = (serie or "").strip()
    if not serie_norm:
        return
    query = """
        SELECT id, nombre FROM equipos
        WHERE TRIM(LOWER(serie)) = LOWER(?)
          AND eliminado_at IS NULL
    """
    params: list = [serie_norm]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)
    query += " LIMIT 1"
    existing = conn.execute(query, tuple(params)).fetchone()
    if existing:
        ed = row_to_dict(existing) if not isinstance(existing, dict) else existing
        raise HTTPException(
            409,
            f"La serie '{serie_norm}' ya existe en el equipo #{ed['id']} ('{ed['nombre']}'). "
            "Las series deben ser únicas por equipo (excepto placeholders como N/A).",
        )


def _resolve_brand_id(conn, nombre: str | None) -> int | None:
    """Find-or-create de marca por nombre (case-insensitive). Devuelve el id
    o None si nombre vacío. La marca (`marcas.nombre`) es la fuente única del
    nombre de marca; equipos.brand_id la referencia."""
    if not nombre or not nombre.strip():
        return None
    nombre = nombre.strip()
    row = conn.execute(
        "SELECT id FROM marcas WHERE LOWER(nombre) = LOWER(?) LIMIT 1", (nombre,)
    ).fetchone()
    if row:
        return row["id"]
    conn.execute(
        "INSERT INTO marcas (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING", (nombre,)
    )
    row = conn.execute(
        "SELECT id FROM marcas WHERE LOWER(nombre) = LOWER(?) LIMIT 1", (nombre,)
    ).fetchone()
    return row["id"] if row else None


@router.post("/equipos", status_code=201)
def create_equipo(data: EquipoCreate):
    conn = get_db()
    try:
        # Validar serie única (rechaza 409 si choca con otro activo)
        _check_serie_unica(conn, data.serie)
        brand_id = _resolve_brand_id(conn, data.marca)
        cur  = conn.execute("""
            INSERT INTO equipos (nombre, brand_id, modelo, cantidad,
                                 precio_jornada, precio_usd, roi_pct,
                                 valor_reposicion, foto_url, fecha_compra,
                                 serie, bh_url, dueno, visible_catalogo, estado,
                                 ficha_completa, categoria_specs, tipo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (data.nombre, brand_id, data.modelo, data.cantidad,
              data.precio_jornada, data.precio_usd, data.roi_pct,
              data.valor_reposicion, data.foto_url, _normalize_fecha_compra(data.fecha_compra),
              data.serie, data.bh_url, data.dueno, data.visible_catalogo, data.estado,
              bool(data.ficha_completa), data.categoria_specs, data.tipo or "simple"))
        new_id = cur.lastrowid
        # Hook: calcular nombre_publico inicial. No falla el create si esto
        # rompe (ej. si los servicios no están disponibles).
        try:
            actualizar_nombres_de(conn, new_id, commit=False)
        except Exception:
            pass
        conn.commit()
        row    = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (new_id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _normalize_fecha_compra(value):
    """`equipos.fecha_compra` es DATE, pero el front (MonthYearPicker) manda
    "YYYY-MM" (mes/año — issue #109). Postgres no castea "YYYY-MM" a DATE
    ('2024-01'::date es inválido → 500), así que completamos al día 1.
    Vacío → None. "YYYY-MM-DD" se deja igual."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return f"{s}-01"
    return s


@router.patch("/equipos/{id}")
def update_equipo(id: int, data: EquipoUpdate):
    conn     = get_db()
    try:
        existing = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Equipo no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
        # marca → brand_id: marcas.nombre es la fuente única. Resolvemos la
        # FK y NO escribimos la columna marca (eliminada).
        marca_cambio = "marca" in updates
        if marca_cambio:
            updates["brand_id"] = _resolve_brand_id(conn, updates.pop("marca"))
        # fecha_compra es DATE; el front (MonthYearPicker) manda "YYYY-MM" →
        # completar a "YYYY-MM-01"; vacío → NULL (ver _normalize_fecha_compra).
        if "fecha_compra" in updates:
            updates["fecha_compra"] = _normalize_fecha_compra(updates["fecha_compra"])
        # Validar serie única si se está cambiando (excluyendo este equipo).
        # Rechaza si otra fila activa tiene la misma serie.
        if "serie" in updates:
            _check_serie_unica(conn, updates["serie"], exclude_id=id)
        # Registrar cambio de precio si cambió
        if "precio_jornada" in updates and updates["precio_jornada"] != existing["precio_jornada"]:
            conn.execute(
                "INSERT INTO equipo_precio_historial (equipo_id, precio_jornada) VALUES (?,?)",
                (id, updates["precio_jornada"]),
            )
        # Inferencia del flag `precio_jornada_manual` cuando el cliente
        # no lo manda explícito. Heurística:
        #   - Si llega precio_jornada SIN roi_pct → asumimos override
        #     manual del admin (editó el precio directamente).
        #   - Si llega precio_jornada JUNTO con roi_pct → asumimos
        #     cálculo automático (el frontend recalculó la fórmula
        #     desde el ROI nuevo).
        # El frontend puede enviar `precio_jornada_manual` para ser
        # explícito y este bloque se saltea.
        if (
            "precio_jornada" in updates
            and "precio_jornada_manual" not in updates
        ):
            updates["precio_jornada_manual"] = "roi_pct" not in updates
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        conn.execute(f"UPDATE equipos SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
        # Si cambió algo que alimenta auto-tags, regenerar.
        if marca_cambio or any(k in updates for k in ("nombre", "modelo")):
            regenerate_auto_tags(conn, id)
        # Hook: si cambió algo que afecta el nombre público, recalcular.
        # No falla el update si el recálculo rompe.
        if marca_cambio or any(k in updates for k in ("nombre", "modelo")):
            try:
                actualizar_nombres_de(conn, id, commit=False)
            except Exception:
                pass
        conn.commit()
        row    = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/equipos/{id}/duplicate")
def duplicate_equipo(id: int):
    """
    Duplica un equipo: copia equipo + ficha + categorías + kit. La nueva fila
    arranca con `serie` vacía (debe ser única por equipo), `ficha_completa = false`
    (para forzar al admin a revisar) y `cantidad = 1` (default seguro).
    Útil cuando comprás varias unidades del mismo modelo con series distintas.
    """
    conn = get_db()
    try:
        src = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (id,)).fetchone()
        if not src:
            raise HTTPException(404, "Equipo no encontrado")
        src_d = row_to_dict(src)

        cur = conn.execute("""
            INSERT INTO equipos (
                nombre, brand_id, modelo, cantidad,
                precio_jornada, precio_usd, roi_pct,
                valor_reposicion, foto_url, fecha_compra,
                serie, bh_url, dueno, visible_catalogo, estado,
                ficha_completa, tipo
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            f"{src_d['nombre']} (copia)",
            src_d.get("brand_id"), src_d.get("modelo"), 1,
            src_d.get("precio_jornada"), src_d.get("precio_usd"), src_d.get("roi_pct"),
            src_d.get("valor_reposicion"), src_d.get("foto_url"), _normalize_fecha_compra(src_d.get("fecha_compra")),
            None,  # serie vacía
            src_d.get("bh_url"), src_d.get("dueno"), src_d.get("visible_catalogo", 1), src_d.get("estado", "operativo"),
            False,  # ficha_completa false para que el admin la revise
            src_d.get("tipo", "simple"),  # hereda el tipo del original
        ))
        new_id = cur.lastrowid

        # Copiar ficha si existe
        ficha = conn.execute("SELECT * FROM equipo_fichas WHERE equipo_id=?", (id,)).fetchone()
        if ficha:
            f = row_to_dict(ficha)
            cols = [k for k in f.keys() if k not in ("equipo_id", "created_at", "updated_at")]
            placeholders = ", ".join(["?"] * (len(cols) + 1))
            conn.execute(
                f"INSERT INTO equipo_fichas (equipo_id, {', '.join(cols)}) VALUES ({placeholders})",
                [new_id] + [f.get(c) for c in cols],
            )

        # Copiar categorías (con orden manual preservado)
        cats = conn.execute(
            "SELECT categoria_id, orden FROM equipo_categorias WHERE equipo_id=?", (id,)
        ).fetchall()
        for cat in cats:
            conn.execute(
                "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (?, ?, ?)",
                (new_id, cat["categoria_id"], cat["orden"]),
            )

        # Copiar etiquetas MANUALES (las auto se regeneran al setear marca/
        # modelo/categorías). Sin esto, el duplicado pierde los tags que
        # el admin tipeó a mano.
        etqs = conn.execute(
            "SELECT etiqueta_id, orden FROM equipo_etiquetas "
            "WHERE equipo_id=? AND origen='manual'",
            (id,),
        ).fetchall()
        for e in etqs:
            conn.execute(
                "INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen) "
                "VALUES (?, ?, ?, 'manual')",
                (new_id, e["etiqueta_id"], e["orden"]),
            )

        # Copiar kit
        kit = conn.execute(
            "SELECT componente_id, cantidad, orden FROM kit_componentes WHERE equipo_id=?", (id,)
        ).fetchall()
        for (componente_id, cantidad, orden) in kit:
            conn.execute(
                "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, orden) VALUES (?, ?, ?, ?)",
                (new_id, componente_id, cantidad, orden),
            )

        # Regenerar etiquetas auto (categoría/marca/modelo/nombre) sobre el
        # duplicado. Las manuales ya las copiamos arriba; esto agrega las auto
        # que normalmente se generan en setCategorias.
        try:
            regenerate_auto_tags(conn, new_id)
        except Exception as e:
            logger.warning("regenerate_auto_tags falló para duplicado %s: %s", new_id, e)

        conn.commit()
        row = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (new_id,)).fetchone()
        return attach_tags(conn, [row_to_dict(row)])[0]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/equipos/{id}/restore")
def restore_equipo(id: int, request: Request):
    """Restaura un equipo soft-deleted (eliminado_at = NULL). #206."""
    require_admin(request)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, eliminado_at FROM equipos WHERE id=?", (id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        if row["eliminado_at"] is None:
            return {"ok": True, "message": "Ya estaba activo"}
        conn.execute(
            "UPDATE equipos SET eliminado_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id=?",
            (id,),
        )
        conn.commit()
        return {"ok": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class BulkActionInput(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    action: str   # "set_visible" | "set_ficha_completa" | "set_categoria" | "add_categoria" | "remove_categoria" | "delete"
    visible: Optional[bool] = None
    ficha_completa: Optional[bool] = None
    categoria_id: Optional[int] = None


@router.post("/admin/equipos/bulk")
def bulk_action(payload: BulkActionInput, request: Request):
    """Aplica una acción a varios equipos a la vez. Acciones soportadas:
    - set_visible (visible: bool)
    - set_ficha_completa (ficha_completa: bool)
    - set_categoria (categoria_id: int) — REEMPLAZA las categorías existentes
    - delete (soft delete — marca eliminado_at; #206)

    Retorna {"affected": N} con la cantidad de equipos modificados.
    """
    require_admin(request)
    ids = payload.ids
    if not ids:
        return {"affected": 0}

    conn = get_db()
    placeholders = ",".join(["?"] * len(ids))
    try:
        if payload.action == "set_visible":
            if payload.visible is None:
                raise HTTPException(400, "set_visible requiere visible: bool")
            v = 1 if payload.visible else 0
            conn.execute(
                f"UPDATE equipos SET visible_catalogo = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                [v, *ids],
            )

        elif payload.action == "set_ficha_completa":
            if payload.ficha_completa is None:
                raise HTTPException(400, "set_ficha_completa requiere ficha_completa: bool")
            conn.execute(
                f"UPDATE equipos SET ficha_completa = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                [bool(payload.ficha_completa), *ids],
            )

        elif payload.action == "set_categoria":
            if not payload.categoria_id:
                raise HTTPException(400, "set_categoria requiere categoria_id: int")
            cat_exists = conn.execute(
                "SELECT id FROM categorias WHERE id = ?", (payload.categoria_id,)
            ).fetchone()
            if not cat_exists:
                raise HTTPException(404, f"Categoría {payload.categoria_id} no existe")
            # Expandir a ancestros una sola vez (mismo set para todos los equipos
            # del bulk): si "Montura E" (hija) se asigna, también va "Lente" (madre).
            ancestor_ids = _expand_to_ancestors(conn, [payload.categoria_id])
            # Reemplaza las categorías existentes con el set expandido
            conn.execute(
                f"DELETE FROM equipo_categorias WHERE equipo_id IN ({placeholders})",
                ids,
            )
            for eid in ids:
                for orden, cid_int in enumerate(ancestor_ids):
                    conn.execute(
                        "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (?, ?, ?)",
                        (eid, cid_int, orden),
                    )
                try:
                    regenerate_auto_tags(conn, eid)
                except Exception as e:
                    logger.warning("regenerate_auto_tags falló para %s en bulk: %s", eid, e)

        elif payload.action == "add_categoria":
            # Igual que set_categoria pero NO borra las existentes — sólo
            # AGREGA. Útil para asignar masivamente una categoría desde
            # la vista de categorías sin perder las otras categorías que
            # cada equipo ya tenía.
            if not payload.categoria_id:
                raise HTTPException(400, "add_categoria requiere categoria_id: int")
            cat_exists = conn.execute(
                "SELECT id FROM categorias WHERE id = ?", (payload.categoria_id,)
            ).fetchone()
            if not cat_exists:
                raise HTTPException(404, f"Categoría {payload.categoria_id} no existe")
            # Expandimos a ancestros una sola vez para todos los equipos.
            ancestor_ids = _expand_to_ancestors(conn, [payload.categoria_id])
            for eid in ids:
                for orden, cid_int in enumerate(ancestor_ids):
                    conn.execute(
                        """
                        INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                        VALUES (?, ?, ?)
                        ON CONFLICT (equipo_id, categoria_id) DO NOTHING
                        """,
                        (eid, cid_int, orden),
                    )
                try:
                    regenerate_auto_tags(conn, eid)
                except Exception as e:
                    logger.warning("regenerate_auto_tags falló para %s en bulk: %s", eid, e)

        elif payload.action == "remove_categoria":
            # Saca UNA categoría de cada equipo sin tocar las otras. Si la
            # categoría es padre/abuela y los equipos tienen hijas suyas,
            # NO borramos esas hijas — solo la categoría exacta indicada.
            if not payload.categoria_id:
                raise HTTPException(400, "remove_categoria requiere categoria_id: int")
            placeholders_ids = ",".join("?" * len(ids))
            conn.execute(
                f"DELETE FROM equipo_categorias WHERE categoria_id = ? AND equipo_id IN ({placeholders_ids})",
                [payload.categoria_id, *ids],
            )
            for eid in ids:
                try:
                    regenerate_auto_tags(conn, eid)
                except Exception as e:
                    logger.warning("regenerate_auto_tags falló para %s en bulk remove: %s", eid, e)

        elif payload.action == "delete":
            # Soft delete: consistente con el endpoint single DELETE (#206).
            conn.execute(
                f"UPDATE equipos SET eliminado_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                ids,
            )

        elif payload.action == "delete_permanent":
            # Hard delete (DROP). Usado desde la vista papelera para vaciar
            # definitivamente. CASCADE borra ficha, kit, categorías, etiquetas
            # del equipo. Los alquiler_items quedan huérfanos pero el catálogo
            # público ya no los referencia. #punto4
            conn.execute(
                f"DELETE FROM equipos WHERE id IN ({placeholders})",
                ids,
            )

        else:
            raise HTTPException(400, f"Acción desconocida: {payload.action}")

        conn.commit()
        return {"affected": len(ids)}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.exception("bulk_action falló: %s", payload.action)
        raise HTTPException(500, f"Error bulk: {type(e).__name__}")
    finally:
        conn.close()


@router.delete("/equipos/{id}", status_code=204)
def delete_equipo(id: int):
    """Soft delete: marca eliminado_at = NOW(). Preserva historial de
    alquileres del equipo dado de baja. Restaurable vía POST /restore (#206)."""
    html_source_url = None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, html_source_url FROM equipos WHERE id=?", (id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        html_source_url = row["html_source_url"]
        conn.execute(
            "UPDATE equipos SET eliminado_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id=?",
            (id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Cleanup R2 blob after successful soft-delete (best-effort, no rollback if fails).
    if html_source_url:
        try:
            cfg = _r2_config()
            client = _get_r2_client(cfg)
            key = html_source_url.removeprefix(f"{cfg['public_base']}/")
            client.delete_object(Bucket=cfg["bucket"], Key=key)
        except Exception as _e:
            logger.warning("delete_equipo: no se pudo borrar HTML blob de R2: %s", _e)


# ── Ficha por equipo ─────────────────────────────────────────────────────────

@router.get("/equipos/{id}/ficha")
def get_ficha(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)
        ).fetchone()
        base = row_to_dict(row) if row else {
            "equipo_id": id, "descripcion": None, "notas": None,
            "keywords_json": None, "nombre_publico_template": None,
        }
        # Las specs estructuradas se sirven por separado vía
        # GET /admin/equipos/{id}/specs (post-PR #456). Este endpoint
        # devuelve sólo los campos de equipo_fichas (descripción, notas,
        # nombre_publico_template, keywords_json + columnas legacy que el
        # catálogo público todavía usa).
        return base
    finally:
        conn.close()


@router.put("/equipos/{id}/ficha")
def upsert_ficha(id: int, data: FichaUpdate):
    """
    PATCH-style upsert: solo actualiza columnas que vinieron en el body
    (no las nullea si el cliente no las mandó). Esto evita que enriquecer con
    IA borre montura/formato/resolución existentes.
    """
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        patch = data.model_dump(exclude_unset=True)
        # Inserta una fila vacía si no existe (para que el UPDATE encuentre algo).
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id) VALUES (?) ON CONFLICT(equipo_id) DO NOTHING",
            (id,),
        )
        if patch:
            set_clause = ", ".join(f"{k} = ?" for k in patch)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = ?",
                list(patch.values()) + [id],
            )
            # Hook: si cambió el template de nombre, recalcular nombre_publico.
            # (Post-Fase F las specs físicas viven en equipo_specs, no en
            # equipo_fichas — cambiarlas no pasa por este endpoint.)
            if "nombre_publico_template" in patch:
                try:
                    actualizar_nombres_de(conn, id, commit=False)
                except Exception:
                    pass
        conn.commit()
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Historial de alquileres por equipo ───────────────────────────────────────

@router.get("/equipos/{id}/historial")
def get_equipo_historial(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        rows = conn.execute("""
            SELECT
                p.id, p.numero_pedido, p.estado,
                p.fecha_desde, p.fecha_hasta,
                COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre) AS cliente,
                pi.cantidad, pi.precio_jornada AS precio_item,
                GREATEST(1, (p.fecha_hasta::date - p.fecha_desde::date))::INTEGER AS dias
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE pi.equipo_id = ?
            ORDER BY p.fecha_desde DESC
        """, (id,)).fetchall()

        items      = [row_to_dict(r) for r in rows]
        total_dias = sum(r["dias"] or 1 for r in items)
        total_rev  = sum((r["precio_item"] or 0) * (r["cantidad"] or 1) * (r["dias"] or 1) for r in items)

        return {
            "historial": items,
            "stats": {
                "total_alquileres": len(items),
                "total_dias":       total_dias,
                "total_revenue":    total_rev,
                "ultimo_alquiler":  items[0]["fecha_desde"] if items else None,
            },
        }
    finally:
        conn.close()


# ── Mantenimiento log ────────────────────────────────────────────────────────

@router.get("/equipos/{id}/mantenimiento")
def list_mantenimiento(id: int):
    """Lista los eventos de mantenimiento del equipo, más recientes primero."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT id, equipo_id, fecha, tipo, descripcion, costo, proxima_revision,
                   fecha_hasta, cantidad, bloquea_stock, created_at
            FROM equipo_mantenimiento WHERE equipo_id = ?
            ORDER BY fecha DESC, id DESC
        """, (id,)).fetchall()
        items = [row_to_dict(r) for r in rows]
        # Proxima revisión pendiente más cercana (futura o vencida).
        pendientes = [r for r in items if r.get("proxima_revision")]
        proxima = min(pendientes, key=lambda r: r["proxima_revision"]) if pendientes else None
        return {
            "items": items,
            "stats": {
                "total_eventos": len(items),
                "total_costo": sum((r.get("costo") or 0) for r in items),
                "proxima_revision": proxima["proxima_revision"] if proxima else None,
            },
        }
    finally:
        conn.close()


@router.post("/equipos/{id}/mantenimiento", status_code=201)
def add_mantenimiento(id: int, data: MantenimientoCreate):
    """Agrega un evento de mantenimiento al equipo."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        cur = conn.execute("""
            INSERT INTO equipo_mantenimiento
                (equipo_id, fecha, tipo, descripcion, costo, proxima_revision,
                 fecha_hasta, cantidad, bloquea_stock)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (id, data.fecha, data.tipo or "revision", data.descripcion, data.costo,
              data.proxima_revision or None, data.fecha_hasta or None, max(1, data.cantidad),
              data.bloquea_stock))
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM equipo_mantenimiento WHERE id = ?", (new_id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/equipos/{id}/mantenimiento/{log_id}")
def update_mantenimiento(id: int, log_id: int, data: MantenimientoUpdate):
    """Actualiza un evento de mantenimiento existente."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM equipo_mantenimiento WHERE id = ? AND equipo_id = ?",
            (log_id, id),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Evento no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
        # Columnas TIMESTAMP: '' rompe el cast → normalizar a NULL.
        for k in ("fecha_hasta", "proxima_revision"):
            if k in updates and not updates[k]:
                updates[k] = None
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE equipo_mantenimiento SET {set_clause} WHERE id = ?",
            list(updates.values()) + [log_id],
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM equipo_mantenimiento WHERE id = ?", (log_id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}/mantenimiento/{log_id}", status_code=204)
def delete_mantenimiento(id: int, log_id: int):
    """Elimina un evento de mantenimiento."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM equipo_mantenimiento WHERE id = ? AND equipo_id = ?",
            (log_id, id),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Evento no encontrado")
        conn.execute("DELETE FROM equipo_mantenimiento WHERE id = ?", (log_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Kit / Componentes ────────────────────────────────────────────────────────

@router.get("/equipos/{id}/kit")
def get_kit(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT kc.id, kc.componente_id, kc.cantidad, kc.orden,
                   kc.descuento_pct, kc.esencial,
                   e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo, e.foto_url, e.visible_catalogo
            FROM kit_componentes kc
            JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?
            ORDER BY kc.orden ASC, e.nombre ASC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _crea_ciclo_kit(conn, equipo_id: int, componente_id: int) -> bool:
    """¿Agregar `componente_id` como componente de `equipo_id` crearía un ciclo?

    Hay ciclo si `equipo_id` ya es alcanzable desde `componente_id` siguiendo
    la cadena de sus propios componentes (BFS hacia abajo desde el componente
    candidato). Auto-referencia directa (equipo_id == componente_id) la maneja
    el caller, pero también la detectamos acá por las dudas.

    Sin este check, dos endpoints concurrentes podrían crear A→B y B→A y
    dejar el grafo con un ciclo, que aunque las queries actuales no recursen,
    rompe la semántica de "un kit contiene componentes" y puede causar bugs
    si alguna vez se hace un traversal recursivo.
    """
    if equipo_id == componente_id:
        return True
    visitados: set[int] = set()
    pila: list[int] = [componente_id]
    while pila:
        actual = pila.pop()
        if actual == equipo_id:
            return True
        if actual in visitados:
            continue
        visitados.add(actual)
        hijos = conn.execute(
            "SELECT componente_id FROM kit_componentes WHERE equipo_id = ?", (actual,)
        ).fetchall()
        pila.extend(h["componente_id"] for h in hijos)
    return False


@router.post("/equipos/{id}/kit", status_code=201)
def add_kit_item(id: int, data: KitItem):
    if id == data.componente_id:
        raise HTTPException(400, "Un equipo no puede ser componente de sí mismo")
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        if not conn.execute(
            "SELECT id FROM equipos WHERE id=? AND eliminado_at IS NULL", (data.componente_id,)
        ).fetchone():
            raise HTTPException(404, "Componente no encontrado")
        if _crea_ciclo_kit(conn, id, data.componente_id):
            raise HTTPException(
                400,
                "Agregar este componente crearía un ciclo en los kits "
                "(el componente ya contiene a este equipo en su cadena).",
            )
        try:
            conn.execute("""
                INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, descuento_pct, esencial)
                VALUES (?,?,?,?,?)
                ON CONFLICT(equipo_id, componente_id) DO UPDATE SET
                    cantidad=excluded.cantidad,
                    descuento_pct=excluded.descuento_pct,
                    esencial=excluded.esencial
            """, (id, data.componente_id, data.cantidad, data.descuento_pct, data.esencial))
            conn.commit()
        except Exception as e:
            raise HTTPException(400, str(e))
        return get_kit(id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}/kit/{componente_id}", status_code=204)
def remove_kit_item(id: int, componente_id: int):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM kit_componentes WHERE equipo_id=? AND componente_id=?",
            (id, componente_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/admin/equipos/{id}/kit/reorder")
def reorder_kit(id: int, data: KitReorder, request: Request):
    """Reordena los componentes del kit según el array de componente_id."""
    require_admin(request)
    conn = get_db()
    try:
        for i, componente_id in enumerate(data.orden):
            conn.execute(
                "UPDATE kit_componentes SET orden=? WHERE equipo_id=? AND componente_id=?",
                (i, id, componente_id)
            )
        conn.commit()
        return {"ok": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Historial de precios ─────────────────────────────────────────────────────

@router.get("/equipos/{id}/precio-historial")
def get_precio_historial(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT precio_jornada, changed_at
            FROM equipo_precio_historial
            WHERE equipo_id = ?
            ORDER BY changed_at DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── Etiquetas por equipo (reemplaza todas) ────────────────────────────────────

@router.put("/equipos/{id}/etiquetas", status_code=200)
def set_etiquetas(id: int, data: EtiquetasUpdate):
    """Reemplaza SOLO las etiquetas manuales del equipo. Las auto se preservan."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        # Borrar solo manuales; las auto siguen vivas.
        conn.execute(
            "DELETE FROM equipo_etiquetas WHERE equipo_id = ? AND origen = 'manual'",
            (id,),
        )
        for orden, nombre in enumerate(data.etiquetas):
            nombre = (nombre or "").strip()
            if not nombre:
                continue
            conn.execute(
                "INSERT INTO etiquetas (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING",
                (nombre,),
            )
            row = conn.execute(
                "SELECT id FROM etiquetas WHERE nombre = ?", (nombre,)
            ).fetchone()
            if not row:
                continue
            conn.execute("""
                INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
                VALUES (?, ?, ?, 'manual')
                ON CONFLICT (equipo_id, etiqueta_id)
                DO UPDATE SET orden = EXCLUDED.orden, origen = 'manual'
            """, (id, row["id"], orden))
        conn.commit()
        row    = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Categorías por equipo ────────────────────────────────────────────────────

def _expand_to_ancestors(conn, ids) -> list[int]:
    """
    Expande una lista de categoria_ids agregando todos los ancestros
    (padres, abuelos, …) hasta la raíz.

    Hoy las categorías tienen máximo 2 niveles (raíz / hija), pero la
    implementación es recursiva por si más adelante se permite mayor
    profundidad.

    Ejemplo: si "Montura E" (id=42, parent_id=10) está en `ids` y "Lente"
    (id=10, parent_id=None) no, devuelve [42, 10].

    Issue: implementación de la regla "asigno hija → se asigna madre" del
    sistema de categorías sugeridas (rule of the project).
    """
    if not ids:
        return []
    out: set[int] = set()
    pending: list[int] = []
    for raw in ids:
        try:
            iv = int(raw)
        except (TypeError, ValueError):
            continue
        if iv not in out:
            out.add(iv)
            pending.append(iv)

    while pending:
        placeholders = ",".join(["?"] * len(pending))
        rows = conn.execute(
            f"SELECT id, parent_id FROM categorias WHERE id IN ({placeholders})",
            pending,
        ).fetchall()
        next_pending: list[int] = []
        for row in rows:
            pid = row["parent_id"]
            if pid is not None and int(pid) not in out:
                out.add(int(pid))
                next_pending.append(int(pid))
        pending = next_pending

    return list(out)


@router.put("/equipos/{id}/categorias", status_code=200)
def set_categorias(id: int, data: CategoriasUpdate):
    """
    Reemplaza la lista de categorías asignadas al equipo y regenera auto-tags
    (porque los nombres de categoría alimentan la bolsa de etiquetas auto).
    """
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        # Expandir a ancestros: si llega "Montura E" (hija), también se asigna
        # "Lente" (madre). Mantiene el orden original para las que ya vinieron;
        # los ancestros agregados van al final.
        expanded_ids = _expand_to_ancestors(conn, data.categoria_ids)
        # Preservar el orden del input para las que ya estaban, agregar las nuevas
        # (ancestros) al final.
        seen: set[int] = set()
        ordered: list[int] = []
        for cid in data.categoria_ids:
            try:
                iv = int(cid)
            except (TypeError, ValueError):
                continue
            if iv not in seen:
                seen.add(iv)
                ordered.append(iv)
        for iv in expanded_ids:
            if iv not in seen:
                seen.add(iv)
                ordered.append(iv)

        conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = ?", (id,))
        for orden, cid_int in enumerate(ordered):
            conn.execute("""
                INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                VALUES (?, ?, ?)
                ON CONFLICT (equipo_id, categoria_id) DO UPDATE SET orden = EXCLUDED.orden
            """, (id, cid_int, orden))
        regenerate_auto_tags(conn, id)
        # Hook: cambió la categoría → cambia el template de specs aplicable
        # → puede cambiar el nombre público auto-generado.
        try:
            actualizar_nombres_de(conn, id, commit=False)
        except Exception:
            pass
        conn.commit()
        row    = conn.execute("SELECT *, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_categorias(conn, [equipo])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Etiquetas / Categorías ───────────────────────────────────────────────────

@router.get("/etiquetas")
def list_etiquetas(incluir_auto: int = Query(0)):
    """
    Lista etiquetas. Por defecto devuelve solo las que tienen al menos un uso
    MANUAL (las auto inflan demasiado). `incluir_auto=1` devuelve todo.
    """
    conn = get_db()
    try:
        if incluir_auto:
            rows = conn.execute("""
                SELECT et.nombre, COUNT(ee.equipo_id) AS total
                FROM etiquetas et
                LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
                GROUP BY et.id, et.nombre
                ORDER BY LOWER(et.nombre)
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT et.nombre, COUNT(ee.equipo_id) AS total
                FROM etiquetas et
                JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
                WHERE ee.origen = 'manual'
                GROUP BY et.id, et.nombre
                ORDER BY LOWER(et.nombre)
            """).fetchall()
        return [{"nombre": r["nombre"], "total": r["total"]} for r in rows]
    finally:
        conn.close()


@router.get("/categorias")
def get_categorias(flat: int = Query(0)):
    """
    Devuelve el árbol de categorías desde la tabla `categorias`.
    `total` cuenta equipos asignados a esa categoría o a cualquier descendiente
    (vía `equipo_categorias`).
    """
    conn = get_db()
    try:
        # #131: agregamos popularidad_score como tiebreaker después de
        # prioridad (manual override del admin). Si todas tienen la misma
        # prioridad (default 100), gana la popularidad real.
        cats = conn.execute("""
            SELECT id, nombre, prioridad, parent_id, popularidad_score
            FROM categorias
            WHERE COALESCE(visible, TRUE) = TRUE
            ORDER BY prioridad ASC, popularidad_score DESC, LOWER(nombre) ASC
        """).fetchall()

        nodes = {
            r["id"]: {
                "id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
                "parent_id": r["parent_id"], "total": 0, "children": [],
            }
            for r in cats
        }
        roots = []
        for r in cats:
            n = nodes[r["id"]]
            if r["parent_id"] and r["parent_id"] in nodes:
                nodes[r["parent_id"]]["children"].append(n)
            else:
                roots.append(n)

        # Conteo por subárbol: equipos distintos asignados a la categoría o a un descendiente.
        eq_rows = conn.execute(
            "SELECT equipo_id, categoria_id FROM equipo_categorias"
        ).fetchall()
        from collections import defaultdict
        eq_cats: dict[int, set] = defaultdict(set)
        for r in eq_rows:
            eq_cats[r["equipo_id"]].add(r["categoria_id"])

        def descendants(nid: int) -> set:
            out = {nid}
            stack = [nid]
            while stack:
                cur = stack.pop()
                for n in nodes.values():
                    if n["parent_id"] == cur:
                        out.add(n["id"]); stack.append(n["id"])
            return out

        for nid, n in nodes.items():
            sub = descendants(nid)
            n["total"] = sum(1 for tags in eq_cats.values() if tags & sub)

        for n in nodes.values():
            n["children"].sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))
        roots.sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))

        if flat:
            return [
                {
                    "nombre": r["nombre"], "total": r["total"], "prioridad": r["prioridad"],
                    "subtags": [{"nombre": c["nombre"], "total": c["total"]} for c in r["children"]],
                }
                for r in roots
            ]

        def clean(n):
            return {
                "id": n["id"], "nombre": n["nombre"], "prioridad": n["prioridad"],
                "total": n["total"], "parent_id": n["parent_id"],
                "children": [clean(c) for c in n["children"]],
            }
        return [clean(r) for r in roots]
    finally:
        conn.close()


# ── Admin: gestión de etiquetas / categorías ─────────────────────────────────

class EtiquetaCreate(BaseModel):
    nombre:    str
    prioridad: Optional[int] = 100
    parent_id: Optional[int] = None


class EtiquetaPatch(BaseModel):
    nombre:    Optional[str] = None
    prioridad: Optional[int] = None
    parent_id: Optional[int] = None  # explícito None para "limpiar" no soportado vía PATCH; usar -1 para nullear
    set_parent_null: Optional[bool] = False


class EtiquetasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/dashboard/uso")
def admin_dashboard_uso(request: Request, dias_sin_uso: int = 90):
    """Dashboard de uso de equipos: top alquilados, sin movimiento, revenue
    por categoría. v1 con métricas clave (#205).

    `dias_sin_uso` (default 90): umbral para considerar un equipo "sin
    movimiento". Equipos cuyo último alquiler fue hace más días aparecen
    como candidatos a revisar/vender.
    """
    require_admin(request)
    conn = get_db()
    try:
        # ── Top 10 más alquilados (cantidad de pedidos + revenue total) ──
        top_alquilados = conn.execute("""
            SELECT
                e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo, e.foto_url,
                COUNT(DISTINCT p.id) AS cant_pedidos,
                SUM(
                    COALESCE(pi.precio_jornada, 0) * COALESCE(pi.cantidad, 1)
                    * GREATEST(1, (p.fecha_hasta::date - p.fecha_desde::date))::INTEGER
                ) AS revenue_total
            FROM equipos e
            JOIN alquiler_items pi ON pi.equipo_id = e.id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE e.eliminado_at IS NULL AND e.es_recurso_interno = FALSE
            GROUP BY e.id, e.nombre, e.modelo, e.foto_url
            ORDER BY cant_pedidos DESC, revenue_total DESC
            LIMIT 10
        """).fetchall()

        # ── Equipos sin movimiento (último alquiler hace > N días, o nunca) ──
        sin_uso = conn.execute("""
            SELECT
                e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo, e.foto_url, e.valor_reposicion,
                MAX(p.fecha_desde) AS ultimo_alquiler,
                COUNT(DISTINCT p.id) AS total_alquileres
            FROM equipos e
            LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
            LEFT JOIN alquileres p ON p.id = pi.pedido_id
            WHERE e.eliminado_at IS NULL AND e.es_recurso_interno = FALSE
            GROUP BY e.id, e.nombre, e.modelo, e.foto_url, e.valor_reposicion
            HAVING (MAX(p.fecha_desde) IS NULL OR MAX(p.fecha_desde) < (CURRENT_DATE - (? || ' days')::INTERVAL))
            ORDER BY ultimo_alquiler ASC NULLS FIRST
            LIMIT 25
        """, (dias_sin_uso,)).fetchall()

        # ── Revenue por categoría (top 10) ──
        por_categoria = conn.execute("""
            SELECT
                cat.id, cat.nombre,
                COUNT(DISTINCT p.id) AS cant_pedidos,
                SUM(
                    COALESCE(pi.precio_jornada, 0) * COALESCE(pi.cantidad, 1)
                    * GREATEST(1, (p.fecha_hasta::date - p.fecha_desde::date))::INTEGER
                ) AS revenue_total
            FROM categorias cat
            JOIN equipo_categorias ec ON ec.categoria_id = cat.id
            JOIN alquiler_items pi ON pi.equipo_id = ec.equipo_id
            JOIN alquileres p ON p.id = pi.pedido_id
            JOIN equipos e ON e.id = ec.equipo_id
            WHERE e.eliminado_at IS NULL
            GROUP BY cat.id, cat.nombre
            ORDER BY revenue_total DESC NULLS LAST
            LIMIT 10
        """).fetchall()

        # ── Stats globales ──
        totales = conn.execute("""
            SELECT
                COUNT(DISTINCT e.id) AS total_equipos,
                COUNT(DISTINCT CASE WHEN e.visible_catalogo = 1 THEN e.id END) AS total_visibles,
                COUNT(DISTINCT p.id) AS total_pedidos,
                SUM(
                    COALESCE(pi.precio_jornada, 0) * COALESCE(pi.cantidad, 1)
                    * GREATEST(1, (p.fecha_hasta::date - p.fecha_desde::date))::INTEGER
                ) AS revenue_total
            FROM equipos e
            LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
            LEFT JOIN alquileres p ON p.id = pi.pedido_id
            WHERE e.eliminado_at IS NULL AND e.es_recurso_interno = FALSE
        """).fetchone()

        # ── Cuentas por cobrar ───────────────────────────────────────────
        # Suma de (monto_total - monto_pagado) sobre pedidos confirmados pero
        # no totalmente pagos. Independiente de la fecha del alquiler — incluye
        # los que ya terminaron y siguen debiendo, y los futuros que ya están
        # confirmados.
        #
        # Excluye estados borrador / presupuesto (todavía no son ventas) y
        # cancelado (ventas que no van).
        por_cobrar_rows = conn.execute("""
            SELECT
                p.id,
                p.numero_pedido,
                p.estado,
                COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre) AS cliente,
                p.fecha_desde, p.fecha_hasta,
                p.monto_total,
                p.monto_pagado,
                (COALESCE(p.monto_total, 0) - COALESCE(p.monto_pagado, 0)) AS pendiente
            FROM alquileres p
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado IN ('confirmado', 'retirado', 'devuelto', 'finalizado')
              AND COALESCE(p.monto_total, 0) > COALESCE(p.monto_pagado, 0)
            ORDER BY (COALESCE(p.monto_total, 0) - COALESCE(p.monto_pagado, 0)) DESC
            LIMIT 50
        """).fetchall()

        por_cobrar_items = [row_to_dict(r) for r in por_cobrar_rows]
        por_cobrar_total = sum(r.get("pendiente") or 0 for r in por_cobrar_items)

        return {
            "totales": row_to_dict(totales) if totales else {},
            "top_alquilados": [row_to_dict(r) for r in top_alquilados],
            "sin_uso": [row_to_dict(r) for r in sin_uso],
            "por_categoria": [row_to_dict(r) for r in por_categoria],
            "dias_sin_uso_threshold": dias_sin_uso,
            "por_cobrar": {
                "total": por_cobrar_total,
                "count": len(por_cobrar_items),
                "items": por_cobrar_items[:20],   # top 20 mostrados; el resto suma al total
            },
        }
    finally:
        conn.close()


@router.get("/admin/equipos/sin-serie")
def admin_equipos_sin_serie(request: Request):
    """Lista equipos sin número de serie cargado.

    Útil para que el admin priorice completar el inventario (issue #91).
    Ordena por valor de reposición DESC — primero los equipos más caros
    (importantes para identificar en caso de pérdida/daño).

    Considera \"sin serie\" cualquier valor NULL, vacío o solo espacios.
    NOTA: 'N/A' es un valor válido — significa \"no aplica\" (reflectores,
    cables sin serie, etc.). El admin lo seteó explícitamente, no falta.
    """
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(f"""
            SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo, e.foto_url,
                   e.valor_reposicion, e.dueno, e.cantidad
            FROM equipos e
            WHERE e.es_recurso_interno = FALSE
              AND (e.serie IS NULL OR TRIM(e.serie) = '')
            ORDER BY COALESCE(e.valor_reposicion, 0) DESC, e.id ASC
        """).fetchall()
        return {
            "total": len(rows),
            "equipos": [row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/admin/etiquetas")
def admin_list_etiquetas(request: Request):
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT et.id, et.nombre, et.prioridad, et.parent_id,
                   COUNT(ee.equipo_id) AS total
            FROM etiquetas et
            LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
            GROUP BY et.id, et.nombre, et.prioridad, et.parent_id
            ORDER BY et.prioridad ASC, LOWER(et.nombre) ASC
        """).fetchall()
        return [
            {
                "id":        r["id"],
                "nombre":    r["nombre"],
                "prioridad": r["prioridad"],
                "parent_id": r["parent_id"],
                "total":     r["total"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.post("/admin/etiquetas", status_code=201)
def admin_create_etiqueta(data: EtiquetaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    conn = get_db()
    try:
        # Validar parent: debe existir y ser raíz (forzar 2 niveles).
        if data.parent_id is not None:
            prow = conn.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = ?", (data.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles (el padre ya es subcategoría)")
        cur = conn.execute("""
            INSERT INTO etiquetas (nombre, prioridad, parent_id)
            VALUES (?, ?, ?)
            ON CONFLICT (nombre) DO UPDATE
                SET prioridad = EXCLUDED.prioridad,
                    parent_id = EXCLUDED.parent_id
            RETURNING id, nombre, prioridad, parent_id
        """, (nombre, data.prioridad or 100, data.parent_id))
        row = cur.fetchone()
        conn.commit()
        return {
            "id": row["id"], "nombre": row["nombre"],
            "prioridad": row["prioridad"], "parent_id": row["parent_id"],
            "total": 0,
        }
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.patch("/admin/etiquetas/{eid}")
def admin_update_etiqueta(eid: int, patch: EtiquetaPatch, request: Request):
    require_admin(request)
    sets, vals = [], []
    if patch.nombre is not None:
        sets.append("nombre = ?"); vals.append(patch.nombre.strip())
    if patch.prioridad is not None:
        sets.append("prioridad = ?"); vals.append(int(patch.prioridad))
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == eid:
            raise HTTPException(400, "Una etiqueta no puede ser su propio padre")
        # Validar que el padre exista y sea raíz.
        conn0 = get_db()
        try:
            prow = conn0.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = ?", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            # Verificar que esta etiqueta no tenga hijos (sino bajaríamos un nivel raíz).
            chrow = conn0.execute(
                "SELECT 1 FROM etiquetas WHERE parent_id = ? LIMIT 1", (eid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta etiqueta tiene hijos; no puede convertirse en hija")
        finally:
            conn0.close()
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    conn = get_db()
    try:
        vals.append(eid)
        conn.execute(f"UPDATE etiquetas SET {', '.join(sets)} WHERE id = ?", tuple(vals))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/admin/etiquetas/{eid}", status_code=204)
def admin_delete_etiqueta(eid: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        # ON DELETE CASCADE en equipo_etiquetas + SET NULL en parent_id de hijos.
        conn.execute("DELETE FROM etiquetas WHERE id = ?", (eid,))
        conn.commit()
    finally:
        conn.close()


@router.post("/admin/etiquetas/reorder")
def admin_reorder_etiquetas(payload: EtiquetasReorder, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        for idx, eid in enumerate(payload.ids):
            conn.execute(
                "UPDATE etiquetas SET prioridad = ? WHERE id = ?",
                ((idx + 1) * 10, eid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
    finally:
        conn.close()


# ── Admin: clasificación automática de equipos ───────────────────────────────

# Reglas leaf → keywords. Orden importa: más específico primero.
# Cada equipo recibe TODAS las hojas que matcheen (multi-asignación).
# Se aplica sobre nombre + marca + modelo (lowercase).
_RULES_LEAF = [
    # ── CÁMARAS (multi: foto+video para mirrorless híbridas) ────────────
    ("Foto",           ["a7 v", "zv-e1"]),  # mirrorless híbridas → también foto
    ("Video",          ["a7 v", "zv-e1", "fx3", "komodo", "c200"]),
    ("Acción",         ["gopro", "insta360"]),
    # ── LENTES (taxonomía: Zoom / Fijos / Vintage / Especiales; montura es filtro) ─
    ("Vintage",        ["vintage", "carl zeiss jena", "m42"]),
    ("Especiales",     ["laowa", "probe macro", "cinema pl", "master prime"]),
    ("Zoom",           ["sony gm", "sigma art 18-35", "sigma art 24-70",
                        "tokina 11-16", "canon 70-200"]),
    ("Fijos",          ["sigma art 35mm", "sigma art 50mm"]),
    # ── ADAPTADORES (raíz separada) ────────────────────────────────────
    ("Adaptadores",    ["adaptador ", "speedbooster", "mc-11"]),
    # ── FILTROS (raíz separada) ────────────────────────────────────────
    ("Filtros",        ["filtro ", "pro-mist", "tiffen"]),
    # ── ILUMINACIÓN ────────────────────────────────────────────────────
    ("LED RGB",        ["rgb", "tl60", "m1 mini", "amaran 300c", "accent b7c"]),
    ("LED daylight/bicolor", ["led", "amaran", "nanlite", "godox vl", "spotlight"]),
    ("Tungsteno",      ["tungsteno", "fresnel arri", "mole richardson", "lowel par", "open face", "focus light"]),
    ("Fluorescente",   ["kino flo", "caselight", "pampa tubo", "fluorescente"]),
    ("On-camera / Flash", ["flash godox", "luz on-camera", "yongnuo yn300", "dracast bicolor"]),
    ("Práctica / efecto", ["globo china", "máquina de humo", "smokegenie"]),
    # ── MODIFICADORES ──────────────────────────────────────────────────
    ("Softbox",        ["softbox", "light dome", "ad-s60"]),
    ("Difusión / Frame", ["frame difusión", "fresnel attachment"]),
    ("Reflectores",    ["reflector"]),
    ("Banderas",       ["bandera"]),
    # ── SOPORTES ───────────────────────────────────────────────────────
    ("Trípodes video", ["manfrotto 502", "manfrotto 504", "manfrotto 529", "trípode fluido", "trípode galera"]),
    ("Trípodes foto",  ["xpro 4s", "trípode foto", "manfrotto elements"]),
    ("C-Stands",       ["c-stand"]),
    ("Estabilización", ["gimbal", "ronin", "steadicam", "glidecam", "tilta gravity"]),
    ("Slider / Dolly / Riel", ["slider", "dolly", "riel "]),
    ("Car Mount",      ["car mount", "tilta hydra"]),
    # ── GRIP ───────────────────────────────────────────────────────────
    ("Brazos",         ["brazo ", "boom arm", "magic arm", "superflex", "brazo mágico"]),
    ("Clamps",         ["clamp", "superclamp", "avenger c1510", "avenger c4462", "avenger e390"]),
    ("Wall plates / pins", ["wall plate", "baby pin", "junior pin"]),
    ("Pinzas",         ["pinza"]),
    ("Líneas de seguridad", ["línea de seguridad", "linea de seguridad"]),
    ("Sopapa",         ["sopapa"]),
    ("Lastre",         ["bolsa de arena", "saco de arena"]),
    # ── SONIDO ─────────────────────────────────────────────────────────
    ("Inalámbricos / Lavalier", ["dji mic", "wireless go", "lavalier"]),
    ("Shotgun / Boom", ["shotgun", "ntg2", "mke 600", "caña boom", "zeppelin"]),
    ("On-camera (sonido)", ["videomic", "mke 400"]),
    ("Estudio / Podcast", ["procaster", "rodecaster"]),
    ("Intercom",       ["intercom", "solidcom", "hollyland"]),
    # ── MONITORES Y VIDEO ──────────────────────────────────────────────
    ("Monitores",      ["monitor de campo", "smallhd", "lilliput", "viltrox 6", "monitor on-camera"]),
    ("Grabadores",     ["video assist", "grabador"]),
    ("Transmisión inalámbrica", ["sdr transmission", "transmisor inalámbrico"]),
    ("Follow Focus / Matebox", ["follow focus", "nucleus", "matebox", "matte box"]),
    # ── ENERGÍA ────────────────────────────────────────────────────────
    ("V-Mount",        ["v-mount", "vmount"]),
    ("NP / LP-E6",     ["np-f", "np-fz", "lp-e6", "np serie-l"]),
    ("Distribución eléctrica", ["zapatilla", "alargue eléctrico"]),
    # ── MEDIA Y DATOS ──────────────────────────────────────────────────
    ("Tarjetas SD",    ["tarjeta sd"]),
    ("Tarjetas CFexpress", ["cfexpress"]),
    ("Lectores",       ["lector"]),
    # ── ESTUDIO Y PRODUCCIÓN ───────────────────────────────────────────
    ("Set / Backdrops", ["backdrop", "mesa de producción"]),
    ("Paquetes",       ["rambla estudio", "estudio equipos promo"]),
]


def _propose_tags(nombre: str, marca: str, modelo: str) -> list[str]:
    """Devuelve la lista de etiquetas hoja propuestas para un equipo."""
    text = f"{nombre} {marca or ''} {modelo or ''}".lower()
    matches = []
    for leaf, kws in _RULES_LEAF:
        for kw in kws:
            if kw in text:
                matches.append(leaf)
                break
    # Dedupe preservando orden
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            out.append(m); seen.add(m)
    return out


# ── Admin: CRUD de categorías (árbol propio) ─────────────────────────────────

class CategoriaCreate(BaseModel):
    nombre:    str
    prioridad: Optional[int] = 100
    parent_id: Optional[int] = None


class CategoriaPatch(BaseModel):
    nombre:    Optional[str] = None
    prioridad: Optional[int] = None
    parent_id: Optional[int] = None
    set_parent_null: Optional[bool] = False
    visible:   Optional[bool] = None
    nombre_publico_template: Optional[str] = None


class CategoriasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/categorias")
def admin_list_categorias(request: Request):
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT c.id, c.nombre, c.prioridad, c.parent_id,
                   COALESCE(c.visible, TRUE) AS visible,
                   c.nombre_publico_template,
                   COUNT(e.id) AS total
            FROM categorias c
            LEFT JOIN equipo_categorias ec ON ec.categoria_id = c.id
            LEFT JOIN equipos e ON e.id = ec.equipo_id AND e.eliminado_at IS NULL
            GROUP BY c.id, c.nombre, c.prioridad, c.parent_id, c.visible, c.nombre_publico_template
            ORDER BY c.prioridad ASC, LOWER(c.nombre) ASC
        """).fetchall()
        return [
            {"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
             "parent_id": r["parent_id"], "visible": bool(r["visible"]),
             "nombre_publico_template": r["nombre_publico_template"],
             "total": r["total"]}
            for r in rows
        ]
    finally:
        conn.close()


@router.post("/admin/categorias", status_code=201)
def admin_create_categoria(data: CategoriaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    conn = get_db()
    try:
        if data.parent_id is not None:
            prow = conn.execute(
                "SELECT id, parent_id FROM categorias WHERE id = ?", (data.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            # Permitimos hasta 3 niveles (depth 0, 1, 2). El padre puede
            # estar en depth 0 (root) o depth 1 (sub). No puede estar a
            # depth 2 — eso convertiría a esta cat en depth 3.
            grandparent_id = prow["parent_id"]
            if grandparent_id is not None:
                grow = conn.execute(
                    "SELECT parent_id FROM categorias WHERE id = ?", (grandparent_id,)
                ).fetchone()
                if grow and grow["parent_id"] is not None:
                    raise HTTPException(400, "Solo se permiten 3 niveles de categorías")
        cur = conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id)
            VALUES (?, ?, ?)
            ON CONFLICT (nombre) DO UPDATE
                SET prioridad = EXCLUDED.prioridad,
                    parent_id = EXCLUDED.parent_id
            RETURNING id, nombre, prioridad, parent_id
        """, (nombre, data.prioridad or 100, data.parent_id))
        row = cur.fetchone()
        conn.commit()
        return {"id": row["id"], "nombre": row["nombre"],
                "prioridad": row["prioridad"], "parent_id": row["parent_id"], "total": 0}
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.patch("/admin/categorias/{cid}")
def admin_update_categoria(cid: int, patch: CategoriaPatch, request: Request):
    require_admin(request)
    sets, vals = [], []
    nuevo_nombre = None
    if patch.nombre is not None:
        nuevo_nombre = patch.nombre.strip()
        if not nuevo_nombre:
            raise HTTPException(400, "El nombre no puede estar vacío")
        sets.append("nombre = ?"); vals.append(nuevo_nombre)
    if patch.prioridad is not None:
        sets.append("prioridad = ?"); vals.append(int(patch.prioridad))
    if patch.visible is not None:
        sets.append("visible = ?"); vals.append(bool(patch.visible))
    if patch.nombre_publico_template is not None:
        # String vacío se guarda como NULL para distinguir "sin template".
        tpl = patch.nombre_publico_template.strip()
        sets.append("nombre_publico_template = ?"); vals.append(tpl or None)
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == cid:
            raise HTTPException(400, "Una categoría no puede ser su propio padre")
        conn0 = get_db()
        try:
            prow = conn0.execute(
                "SELECT id, parent_id FROM categorias WHERE id = ?", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            # Permitimos hasta 3 niveles (depth 0/1/2).
            # depth(new_parent) + 1 + max_descendant_depth(this) debe ser <= 2.
            def _depth_of(node_id: int) -> int:
                d = 0
                cur = node_id
                while True:
                    r = conn0.execute(
                        "SELECT parent_id FROM categorias WHERE id = ?", (cur,)
                    ).fetchone()
                    if not r or r["parent_id"] is None:
                        return d
                    d += 1
                    cur = r["parent_id"]
                    if d > 10:  # safety
                        return d

            def _max_descendant_depth(node_id: int) -> int:
                from collections import deque
                q = deque([(node_id, 0)])
                m = 0
                while q:
                    nid, d = q.popleft()
                    m = max(m, d)
                    children = conn0.execute(
                        "SELECT id FROM categorias WHERE parent_id = ?", (nid,)
                    ).fetchall()
                    for ch in children:
                        q.append((ch["id"], d + 1))
                return m

            new_parent_depth = _depth_of(patch.parent_id)
            own_max_depth = _max_descendant_depth(cid)
            if new_parent_depth + 1 + own_max_depth > 2:
                raise HTTPException(400, "Excede el máximo de 3 niveles")
            # Cycle check: el patch.parent_id no debe ser descendiente de cid.
            descendants = set()
            from collections import deque
            q = deque([cid])
            while q:
                nid = q.popleft()
                children = conn0.execute(
                    "SELECT id FROM categorias WHERE parent_id = ?", (nid,)
                ).fetchall()
                for ch in children:
                    descendants.add(ch["id"])
                    q.append(ch["id"])
            if patch.parent_id in descendants:
                raise HTTPException(400, "No se puede mover bajo un descendiente (ciclo)")
        finally:
            conn0.close()
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")

    # Pre-check: si hay rename, verificar que la categoría existe y que el
    # nuevo nombre no choca con otra. Mejor error de conflicto explícito que
    # 500 por UniqueViolation de psycopg2.
    if nuevo_nombre is not None:
        conn0 = get_db()
        try:
            existe = conn0.execute(
                "SELECT id FROM categorias WHERE id = ?", (cid,)
            ).fetchone()
            if not existe:
                raise HTTPException(404, f"Categoría {cid} no existe")
            choca = conn0.execute(
                "SELECT id, nombre FROM categorias WHERE LOWER(nombre) = LOWER(?) AND id != ?",
                (nuevo_nombre, cid),
            ).fetchone()
            if choca:
                raise HTTPException(409, f"Ya existe una categoría llamada '{choca['nombre']}'")
        finally:
            conn0.close()

    conn = get_db()
    try:
        vals.append(cid)
        conn.execute(f"UPDATE categorias SET {', '.join(sets)} WHERE id = ?", tuple(vals))
        # Si renombró, regenerar auto-tags de los equipos afectados.
        if nuevo_nombre is not None:
            eq_rows = conn.execute(
                "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = ?", (cid,)
            ).fetchall()
            for r in eq_rows:
                try:
                    regenerate_auto_tags(conn, r["equipo_id"])
                except Exception:
                    # No abortar el rename si un equipo falla regenerar tags.
                    logger.warning("regenerate_auto_tags falló para equipo %s tras rename de cat %s",
                                   r["equipo_id"], cid, exc_info=True)
        # Si cambió el template del nombre público, regenerar el nombre de
        # cada equipo asignado a esta categoría (directa o como sub-cat).
        # Sin esto, el admin guarda el template pero los equipos siguen con
        # su nombre publico viejo hasta que alguien los toca individualmente.
        nombres_regen = 0
        if patch.nombre_publico_template is not None:
            eq_rows = conn.execute(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id FROM categorias WHERE id = ?
                    UNION
                    SELECT c.id FROM categorias c
                    JOIN descendants d ON c.parent_id = d.id
                )
                SELECT DISTINCT ec.equipo_id
                FROM equipo_categorias ec
                JOIN descendants d ON d.id = ec.categoria_id
                """,
                (cid,),
            ).fetchall()
            for r in eq_rows:
                try:
                    actualizar_nombres_de(conn, r["equipo_id"], commit=False)
                    nombres_regen += 1
                except Exception:
                    logger.warning(
                        "actualizar_nombres_de falló para equipo %s tras cambio de template cat %s",
                        r["equipo_id"], cid, exc_info=True,
                    )
        conn.commit()
        return {"ok": True, "nombres_regenerados": nombres_regen}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error("Error en admin_update_categoria(cid=%s): %s", cid, e, exc_info=True)
        raise HTTPException(500, "Error al actualizar categoría — ver logs del servidor")
    finally:
        conn.close()


@router.delete("/admin/categorias/{cid}", status_code=204)
def admin_delete_categoria(cid: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        eq_rows = conn.execute(
            "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = ?", (cid,)
        ).fetchall()
        affected = [r["equipo_id"] for r in eq_rows]
        conn.execute("DELETE FROM categorias WHERE id = ?", (cid,))
        for eid in affected:
            regenerate_auto_tags(conn, eid)
        conn.commit()
    finally:
        conn.close()


@router.post("/admin/categorias/reorder")
def admin_reorder_categorias(payload: CategoriasReorder, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        for idx, cid in enumerate(payload.ids):
            conn.execute(
                "UPDATE categorias SET prioridad = ? WHERE id = ?",
                ((idx + 1) * 10, cid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
    finally:
        conn.close()


# ── Admin: clasificación automática (escribe en equipo_categorias) ───────────

@router.post("/admin/categorias/clasificar")
def admin_clasificar(request: Request, apply: int = Query(0)):
    """
    Calcula categorías hoja propuestas para todos los equipos.
    - apply=0: dry-run.
    - apply=1: REEMPLAZA las categorías de cada equipo que matchee al menos 1
      regla; los que no matchean no se tocan. Regenera auto-tags después.
    """
    require_admin(request)

    conn = get_db()
    try:
        equipos = conn.execute("""
            SELECT e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo
            FROM equipos e
            WHERE e.es_recurso_interno = FALSE
            ORDER BY e.nombre
        """).fetchall()

        # Categorías actuales por equipo (para mostrar el diff).
        rows = conn.execute("""
            SELECT ec.equipo_id, c.nombre
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
        """).fetchall()
        from collections import defaultdict
        actuales: dict[int, list[str]] = defaultdict(list)
        for r in rows:
            actuales[r["equipo_id"]].append(r["nombre"])

        # Mapa nombre→id de categorías hoja válidas.
        leaf_rows = conn.execute(
            "SELECT id, nombre FROM categorias WHERE parent_id IS NOT NULL"
        ).fetchall()
        leaf_id = {r["nombre"]: r["id"] for r in leaf_rows}

        items = []
        matched = 0
        applied = 0
        for eq in equipos:
            propuestas = _propose_tags(eq["nombre"], eq["marca"] or "", eq["modelo"] or "")
            propuestas = [p for p in propuestas if p in leaf_id]
            if propuestas:
                matched += 1
                if apply:
                    conn.execute(
                        "DELETE FROM equipo_categorias WHERE equipo_id = ?", (eq["id"],)
                    )
                    for orden, name in enumerate(propuestas):
                        conn.execute("""
                            INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                            VALUES (?, ?, ?)
                            ON CONFLICT (equipo_id, categoria_id)
                            DO UPDATE SET orden = EXCLUDED.orden
                        """, (eq["id"], leaf_id[name], orden))
                    regenerate_auto_tags(conn, eq["id"])
                    applied += 1
            items.append({
                "id":        eq["id"],
                "nombre":    eq["nombre"],
                "marca":     eq["marca"],
                "propuestas": propuestas,
                "actuales":  actuales.get(eq["id"], []),
            })

        if apply:
            conn.commit()

        return {
            "total":     len(equipos),
            "matched":   matched,
            "unmatched": len(equipos) - matched,
            "applied":   applied,
            "items":     items,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



@router.get("/equipos/{id}/calendario")
def get_equipo_calendario(id: int, year: int = Query(...), month: int = Query(...)):
    """Per-day available unit count for a given equipment and month."""
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mes inválido")

    conn = get_db()
    try:
        equipo = conn.execute(
            "SELECT id, cantidad FROM equipos WHERE id=?", (id,)
        ).fetchone()
        if not equipo:
            raise HTTPException(404, "Equipo no encontrado")

        stock_total     = equipo["cantidad"]
        _, days_in_month = _cal.monthrange(year, month)
        first_day       = _date(year, month, 1).isoformat()
        last_day        = _date(year, month, days_in_month).isoformat()

        # Direct reservations that overlap this month
        directas = conn.execute(f"""
            SELECT to_char(p.fecha_desde, 'YYYY-MM-DD') AS desde,
                   to_char(p.fecha_hasta, 'YYYY-MM-DD') AS hasta,
                   pi.cantidad
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE pi.equipo_id = ?
              AND p.estado IN {ESTADOS_RESERVADO}
              AND p.fecha_desde::date <= ?
              AND p.fecha_hasta::date > ?
        """, (id, last_day, first_day)).fetchall()

        # Via-kit reservations: this equipment is a component of a rented kit
        via_kit = conn.execute(f"""
            SELECT to_char(p.fecha_desde, 'YYYY-MM-DD') AS desde,
                   to_char(p.fecha_hasta, 'YYYY-MM-DD') AS hasta,
                   pi.cantidad * kc.cantidad AS cantidad
            FROM kit_componentes kc
            JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE kc.componente_id = ?
              AND p.estado IN {ESTADOS_RESERVADO}
              AND p.fecha_desde::date <= ?
              AND p.fecha_hasta::date > ?
        """, (id, last_day, first_day)).fetchall()

        reservations = [dict(r) for r in directas] + [dict(r) for r in via_kit]

        result: dict[str, int] = {}
        for day_num in range(1, days_in_month + 1):
            d_str    = _date(year, month, day_num).isoformat()
            reservado = sum(
                r["cantidad"]
                for r in reservations
                if r["desde"] <= d_str < r["hasta"]
            )
            result[d_str] = max(0, stock_total - reservado)

        return result
    finally:
        conn.close()




@router.post("/admin/equipos/{id}/upload-html-source")
async def admin_upload_html_source(
    id: int,
    request: Request,
    file: UploadFile = File(...),
    categoria_hint: Optional[str] = None,
) -> dict:
    """Sube y persiste el HTML guardado de B&H, extrae specs y los devuelve.

    Guarda el blob en R2 (equipos/{id}/source.html), actualiza html_source_url
    en la BD y devuelve AutocompletarResult con los specs extraídos. Una segunda
    llamada sobreescribe el blob anterior (path determinístico sin timestamp).

    Args:
        id: ID del equipo al que se asocia el HTML.
        file: HTML guardado (Cmd+S → Webpage Complete).
        categoria_hint: categoría opcional para saltear auto-detección.

    Returns: {html_source_url, ...AutocompletarResult}
    """
    require_admin(request)

    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
    finally:
        conn.close()

    content = await file.read()
    if not content:
        raise HTTPException(400, "Archivo vacío")
    if len(content) > 5_000_000:
        raise HTTPException(400, "HTML demasiado grande (máx 5MB)")

    try:
        html_content = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "HTML inválido (no es UTF-8)")

    path = f"equipos/{id}/source.html"
    html_source_url = _upload_to_r2(path, content, "text/html; charset=utf-8")

    conn = get_db()
    try:
        conn.execute(
            "UPDATE equipos SET html_source_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id=?",
            (html_source_url, id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        from services.equipo_html_extractor import extract_from_html
        result = extract_from_html(html_content, categoria_hint=categoria_hint)
    except Exception as e:
        logger.exception("Error extrayendo specs del HTML (equipo %d)", id)
        raise HTTPException(500, f"Error parseando HTML: {e}")

    return {"html_source_url": html_source_url, **result}



# ── Admin: búsqueda dedicada de fotos (separada del enriquecimiento) ─────────
#
# El enriquecedor general usa B&H/Adorama (mejor para specs) pero esos sitios
# bloquean hotlinking de fotos. Este endpoint busca específicamente en sitios
# con imágenes confiables (Wikipedia, manufacturer, sitios de review).

class BuscarFotosInput(BaseModel):
    nombre: Optional[str]      = None
    marca:  Optional[str]      = None
    modelo: Optional[str]      = None
    url:    Optional[str]      = None
    exclude: Optional[list[str]] = None  # URLs ya conocidas (para "buscar más")


@router.post("/admin/equipos/buscar-fotos")
def admin_buscar_fotos(payload: BuscarFotosInput, request: Request):
    """Busca fotos del equipo en fuentes optimizadas para imágenes (Wikipedia,
    manufacturer oficial, review sites). Devuelve lista validada de candidatos."""
    require_admin(request)

    import httpx
    import re

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url")

    exclude_lc: set[str] = {(u or "").strip().lower() for u in (payload.exclude or [])}

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    # Queries optimizados para fotos de producto con fondo blanco/neutro,
    # bien iluminadas — ideal para equipos audiovisuales de renta.
    # B&H primero: hero shots standarizados sobre fondo gris/blanco.
    PHOTO_QUERIES = [
        # 1. B&H Photo: fotos hero de producto, alta resolución, fondo neutro
        f"{query} product photo site:bhphotovideo.com",
        # 2. Adorama / KEH: misma categoría de retailers
        f"{query} product image (site:adorama.com OR site:keh.com)",
        # 3. Manufacturer oficial — página de producto
        f"{query} product page (site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        f"site:fujifilm.com OR site:panasonic.com OR site:blackmagicdesign.com OR site:aputure.com OR "
        f"site:godox.com OR site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        f"site:tilta.com OR site:smallrig.com OR site:saramonic.com OR site:zoom-na.com)",
        # 4. Wikipedia: fallback con imágenes limpias y sin paywall
        f"{query} (site:en.wikipedia.org OR site:commons.wikimedia.org OR site:es.wikipedia.org)",
    ]

    def _fc_search(q: str, client) -> list[str]:
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        data = r.json().get("data")
        rows = data if isinstance(data, list) else (data.get("web") if isinstance(data, dict) else None) or []
        urls = []
        for row in rows:
            u = (row.get("url") or "").strip() if isinstance(row, dict) else ""
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                urls.append(u)
        return urls

    def _extract_images_from_page(url: str, client, trust_url: bool = False) -> list[str]:
        """Scrapea una página y extrae URLs de imagen (meta + markdown img tags).
        Si trust_url=True (cuando el usuario pega el link explícitamente), no
        descarta candidatos por dimensiones pequeñas en la URL — solo filtra
        patrones obvios de basura (thumbs, iconos, logos)."""
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers,
                json={"url": url, "formats": ["markdown"], "onlyMainContent": False},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        sd = r.json().get("data") or {}
        meta = sd.get("metadata") or {}
        markdown = sd.get("markdown") or ""

        cands: list[str] = []
        seen: set[str] = set()

        def push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            # Filtrar tracking pixels y svgs decorativos
            if u.lower().endswith(".svg"):
                return
            lo = u.lower()
            # Filtrar thumbnails, iconos, logos y dimensiones pequeñas en la URL.
            # Patrones comunes que indican imagen de baja calidad:
            #   _thumb, -thumb, /thumbs/, _small, _sm, /icons/, /logos/,
            #   width=NN (≤200), w=NN (≤200), -100x100, _50x50, etc.
            LOW_QUALITY_PATTERNS = (
                "/thumb", "_thumb", "-thumb", "/thumbs/", "thumbnail",
                "/icon", "_icon", "-icon",
                "/logo", "_logo", "-logo", "favicon",
                "/avatar", "_avatar", "-avatar",
                "/sprite", "spacer.gif", "pixel.gif",
                "_sm.", "-sm.", "_small.", "-small.",
                # Ads, banners, promos, campaign creatives (B&H/Sony/etc.
                # incrustan estos en las páginas de producto; no son la
                # foto del equipo en sí).
                "/banner", "_banner", "-banner",
                "/promo", "_promo", "-promo",
                "/campaign", "_campaign", "-campaign",
                "/ads/", "/ad-", "_ad-", "adservice",
                "/marketing", "_marketing",
                "doubleclick", "googleads", "googlesyndication",
                "amazon-adsystem", "scorecardresearch",
                "/billboard", "_billboard",
                "/hero-banner", "homepage-banner",
                "watch-now", "/events/", "/event-",
                "in-residence", "panel-",
                "newsroom", "press-release", "press/",
            )
            if any(p in lo for p in LOW_QUALITY_PATTERNS):
                return
            if not trust_url:
                # Dimensiones pequeñas en URL: -100x100, _50x50, 200x150
                import re as _re
                m = _re.search(r"[-_/](\d{2,4})x(\d{2,4})", lo)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    if w < 800 or h < 800:
                        return
                # width=NN o w=NN <= 300 en query string
                m = _re.search(r"[?&](?:width|w|size)=(\d+)", lo)
                if m and int(m.group(1)) < 800:
                    return
            k = lo
            if k in seen or k in exclude_lc:
                return
            seen.add(k)
            cands.append(u)

        push(meta.get("ogImage") or meta.get("og:image"))
        push(meta.get("twitterImage") or meta.get("twitter:image"))
        # ![alt](url) en markdown
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", markdown):
            push(m.group(1))
        # <img src="..."> en HTML embebido
        for m in re.finditer(r'<img[^>]+src=["\']?([^"\'>\s]+)', markdown):
            push(m.group(1))

        # Ordenar: primero URLs con indicadores de foto de producto (fondo blanco/hero)
        PRODUCT_INDICATORS = (
            "/product/", "_hero", "-hero", "_main", "-main",
            "-product-", "/images/", "bhphotovideo.com",
            "_front", "-front", "_top", "-top",
        )
        def _product_score(u: str) -> int:
            lo = u.lower()
            return sum(1 for p in PRODUCT_INDICATORS if p in lo)

        cands.sort(key=_product_score, reverse=True)
        return cands[:10]

    # Validación rápida: HEAD/GET parcial, descarta lo que no sea imagen real
    def _is_valid_image(url: str, client) -> bool:
        try:
            from urllib.parse import urlparse as _up
            host = (_up(url).hostname or "").lower()
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
                "Referer": f"https://{host}/" if host else "",
            }
            # Bajamos los primeros 16KB para chequear:
            #   1. Que sea una imagen (content-type)
            #   2. Que las dimensiones no sean de banner (relación ancho/alto
            #      muy extrema descarta banners promo tipo 728x90, 970x250).
            hdrs["Range"] = "bytes=0-16384"
            rg = client.get(url, headers=hdrs, follow_redirects=True, timeout=8.0)
            if rg.status_code not in (200, 206):
                return False
            ct = rg.headers.get("content-type", "")
            if not ct.startswith("image/"):
                return False
            # Intentar parsear el header para sacar dimensiones (PIL solo
            # necesita la cabecera). Si falla, asumimos válida.
            try:
                from PIL import Image as _PILImage
                from io import BytesIO as _BIO
                img = _PILImage.open(_BIO(rg.content))
                w, h = img.size
                if w > 0 and h > 0:
                    ratio = max(w, h) / max(1, min(w, h))
                    # Banners típicos: 8:1+ (728x90 ≈ 8.1, 970x250 ≈ 3.88).
                    # Cualquier cosa > 3.5:1 muy probable que sea banner/strip.
                    if ratio > 3.5:
                        return False
                    # Imágenes muy chicas no sirven como hero del producto.
                    if min(w, h) < 240:
                        return False
            except Exception:
                pass
            return True
        except httpx.HTTPError:
            pass
        return False

    def _og_images_from_html(url: str, client) -> list[str]:
        """Extrae og:image y twitter:image directamente del HTML sin Firecrawl.
        Más rápido y confiable para páginas de producto de B&H y similares."""
        try:
            r = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=15.0,
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        html = r.text[:100_000]
        imgs: list[str] = []
        seen: set[str] = set()
        def _push_og(u: str | None) -> None:
            if not u:
                return
            u = u.strip()
            if u.lower().startswith(("http://", "https://")) and u.lower() not in seen:
                seen.add(u.lower())
                imgs.append(u)
        # og:image (dos posibles órdenes de atributos)
        for pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'og:image["\'][^>]*content=["\']([^"\']+)["\']',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _push_og(m.group(1))
                break
        # twitter:image
        for pat in [
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _push_og(m.group(1))
                break
        return imgs

    all_cands: list[str] = []
    seen_lc: set[str] = set()
    # Cuando el usuario pegó una URL directa, marcamos las fotos obtenidas para
    # saltear la validación HEAD (B&H CDN puede rechazar HEADs cross-origin).
    direct_url_cands: set[str] = set()

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            # 1) Si la URL es directamente una imagen, usarla tal cual.
            if direct_url.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "avif", "gif"):
                all_cands.append(direct_url)
                seen_lc.add(direct_url.lower())
                direct_url_cands.add(direct_url.lower())

            # 2) Extraer og:image directamente del HTML (rápido, sin Firecrawl).
            #    Más confiable para B&H y sitios JS-pesados.
            for u in _og_images_from_html(direct_url, client):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
                    direct_url_cands.add(u.lower())

            # 3) Firecrawl para más candidatos (especialmente imgs del body).
            for u in _extract_images_from_page(direct_url, client, trust_url=True):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
        else:
            for q in PHOTO_QUERIES:
                if len(all_cands) >= 18:
                    break
                for top in _fc_search(q, client)[:2]:
                    for u in _extract_images_from_page(top, client):
                        if u.lower() not in seen_lc:
                            seen_lc.add(u.lower())
                            all_cands.append(u)

        # Validar candidatos — los que vienen de URL directa se saltan la
        # validación (B&H CDN rechaza HEADs cross-origin; el og:image del propio
        # sitio es confiable sin necesidad de un round-trip extra).
        with httpx.Client(timeout=10.0) as vc:
            validated = [
                u for u in all_cands[:MAX_PHOTO_CANDIDATES_BUSCAR_VALIDATE]
                if u.lower() in direct_url_cands or _is_valid_image(u, vc)
            ][:MAX_PHOTO_CANDIDATES_BUSCAR_RETURN]

    return {"foto_candidates": validated, "total_inspeccionadas": len(all_cands)}



# ── Admin: descargar imagen externa y subirla a Cloudflare R2 ────────────────
#
# El frontend NO sube directamente al bucket porque eso requeriría exponer
# credenciales de R2 al browser. Acá lo hacemos en el backend con el secret
# guardado en env vars.
#
# SSRF guard
# ----------
# El admin autenticado puede pedir descargar cualquier URL externa. Sin
# allowlist, esto sería SSRF: un admin malicioso/comprometido podría hacer
# que el backend descargue http://localhost:5432/, http://169.254.169.254/
# (metadata cloud), o cualquier IP de la VPC interna de Railway. Filtramos:
# (1) sólo http(s) en puerto estándar (80/443), (2) host en allowlist de
# dominios conocidos, (3) la IP resuelta del host no es privada/loopback.


# Procesamiento/upload de imágenes: extraído a services/image_upload.py
# (issue #501 Fase 3). _foto_path se queda acá (usa get_db).
from services.image_upload import (
    _download_image_bytes,
    _ext_from_ctype,
    _get_r2_client,
    _optimize_image,
    _r2_config,
    _upload_to_r2,
    _upload_to_supabase_storage,
    _validate_external_image_url,
    _validate_ssrf_only,
)
from services.media import DISPLAY_SQUARE, collect_asset_keys, purge_r2, store_upload
from services.media_fastapi import media_http


def _foto_path(equipo_id: int, ext: str) -> str:
    """Genera path R2: equipos/{id}_{slug}/{id}_{slug}-{ts}.{ext}

    El timestamp en el nombre del archivo evita el problema del cache
    inmutable: R2 sirve los assets con Cache-Control: max-age=1año
    immutable, así que dos uploads al mismo path harían que el navegador
    siga mostrando el viejo durante un año. Con timestamp cada upload
    tiene URL nueva. El archivo anterior queda como huérfano en R2.
    """
    import time as _time
    try:
        conn = get_db()
        row = conn.execute("SELECT nombre FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
        conn.close()
        nombre = row[0] if row else ""
    except Exception:
        nombre = ""

    if nombre:
        slug = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:50]
    else:
        slug = ""

    ts = int(_time.time())
    if slug:
        folder   = f"{equipo_id}_{slug}"
        filename = f"{equipo_id}_{slug}-{ts}.{ext}"
    else:
        folder   = f"{equipo_id}"
        filename = f"{equipo_id}-{ts}.{ext}"
    return f"equipos/{folder}/{filename}"


class UploadFotoFromUrlInput(BaseModel):
    url: str


@router.post("/admin/equipos/{equipo_id}/upload-foto-from-url")
def admin_upload_foto_from_url(
    equipo_id: int,
    payload: UploadFotoFromUrlInput,
    request: Request,
):
    """Descarga imagen externa, la optimiza y la sube a Cloudflare R2.
    Crea una fila en equipo_fotos y sincroniza equipos.foto_url con la principal.
    Devuelve {public_url, path, size, content_type}.
    """
    require_admin(request)

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        return {"public_url": url, "path": None, "skipped": True}

    _validate_external_image_url(url)
    raw_content, _raw_ctype = _download_image_bytes(url)

    conn = get_db()
    try:
        with media_http():
            asset = store_upload(raw_content, kind="equipo", derive_specs=[DISPLAY_SQUARE], conn=conn)
        display = asset.variant("display")
        foto = _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "public_url": display.url,
        "path": display.key,
        "size": display.bytes,
        "size_original": len(raw_content),
        "content_type": display.content_type,
        "width": display.width or None,
        "height": display.height or None,
    }


# ── Admin: subir bytes de un archivo (multipart) directo a R2 ─────────────

@router.post("/admin/equipos/{equipo_id}/upload-foto")
async def admin_upload_foto_file(
    equipo_id: int,
    request: Request,
):
    """Sube un archivo (multipart/form-data, campo `file`) a R2 con pipeline
    no-destructivo: guarda el original + variante cuadrada 1200×1200.
    Crea una fila en equipo_fotos y sincroniza equipos.foto_url.
    """
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(400, "Archivo vacío")
    if len(raw_content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20MB)")

    conn = get_db()
    try:
        with media_http():
            asset = store_upload(raw_content, kind="equipo", derive_specs=[DISPLAY_SQUARE], conn=conn)
        display = asset.variant("display")
        foto = _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "public_url": display.url,
        "path": display.key,
        "size": display.bytes,
        "size_original": len(raw_content),
        "content_type": display.content_type,
        "width": display.width or None,
        "height": display.height or None,
    }


# ── Galería multi-foto de equipos (F2) ───────────────────────────────────────


def _get_equipo_fotos(conn, equipo_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, url, path, media_id, orden, es_principal, created_at "
        "FROM equipo_fotos WHERE equipo_id = ? ORDER BY orden, id",
        (equipo_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "url": r["url"],
            "path": r["path"],
            "media_id": r["media_id"],
            "orden": r["orden"],
            "es_principal": bool(r["es_principal"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def _insert_equipo_foto(conn, equipo_id: int, url: str, path: str, media_id: int | None = None) -> dict:
    """Inserta una fila en equipo_fotos y sincroniza equipos.foto_url con la principal.
    La primera foto del equipo se marca como principal automáticamente.
    """
    cur = conn.execute(
        "SELECT COALESCE(MAX(orden), -1) + 1 AS next_orden FROM equipo_fotos WHERE equipo_id = ?",
        (equipo_id,),
    )
    orden = cur.fetchone()["next_orden"]

    cur2 = conn.execute("SELECT COUNT(*) AS cnt FROM equipo_fotos WHERE equipo_id = ?", (equipo_id,))
    is_first = cur2.fetchone()["cnt"] == 0

    conn.execute(
        "INSERT INTO equipo_fotos (equipo_id, url, path, media_id, orden, es_principal) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (equipo_id, url, path, media_id, orden, is_first),
    )

    if is_first:
        conn.execute("UPDATE equipos SET foto_url = ? WHERE id = ?", (url, equipo_id))

    conn.commit()

    cur3 = conn.execute(
        "SELECT id, url, path, media_id, orden, es_principal, created_at "
        "FROM equipo_fotos WHERE equipo_id = ? ORDER BY id DESC LIMIT 1",
        (equipo_id,),
    )
    r = cur3.fetchone()
    return {
        "id": r["id"],
        "url": r["url"],
        "path": r["path"],
        "media_id": r["media_id"],
        "orden": r["orden"],
        "es_principal": bool(r["es_principal"]),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


@router.get("/admin/equipos/{equipo_id}/fotos")
def get_equipo_fotos(equipo_id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")
        return {"fotos": _get_equipo_fotos(conn, equipo_id)}
    finally:
        conn.close()


@router.post("/admin/equipos/{equipo_id}/fotos", status_code=201)
async def upload_equipo_foto(equipo_id: int, request: Request):
    """Sube una foto (multipart, campo 'file') al equipo. Guarda original + variante cuadrada."""
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file'")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20 MB)")

    conn = get_db()
    try:
        eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")
        with media_http():
            asset = store_upload(raw, kind="equipo", derive_specs=[DISPLAY_SQUARE], conn=conn)
        display = asset.variant("display")
        foto = _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return foto


class EquipoFotoFromUrlBody(BaseModel):
    url: str


@router.post("/admin/equipos/{equipo_id}/fotos/from-url", status_code=201)
def upload_equipo_foto_from_url(equipo_id: int, body: EquipoFotoFromUrlBody, request: Request):
    """Descarga URL externa y la agrega a la galería del equipo."""
    require_admin(request)

    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        raise HTTPException(400, "La URL ya está en el bucket — subí el archivo directamente")

    _validate_external_image_url(url)
    raw, _raw_ctype = _download_image_bytes(url)

    conn = get_db()
    try:
        eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")
        with media_http():
            asset = store_upload(raw, kind="equipo", derive_specs=[DISPLAY_SQUARE], conn=conn)
        display = asset.variant("display")
        foto = _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return foto


@router.delete("/admin/equipos/{equipo_id}/fotos/{foto_id}")
def delete_equipo_foto(equipo_id: int, foto_id: int, request: Request):
    require_admin(request)

    conn = get_db()
    try:
        cur = conn.execute(
            "SELECT url, path, media_id, es_principal FROM equipo_fotos "
            "WHERE id = ? AND equipo_id = ?",
            (foto_id, equipo_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Foto no encontrada")

        media_id = row["media_id"]
        path = row["path"]
        was_principal = bool(row["es_principal"])

        r2_keys: list[str] = []
        if media_id:
            r2_keys = collect_asset_keys(conn, media_id)

        conn.execute("DELETE FROM equipo_fotos WHERE id = ?", (foto_id,))
        if media_id:
            conn.execute("DELETE FROM media_assets WHERE id = ?", (media_id,))

        # Si era la principal, promover la siguiente en orden
        if was_principal:
            next_foto = conn.execute(
                "SELECT id, url FROM equipo_fotos WHERE equipo_id = ? ORDER BY orden, id LIMIT 1",
                (equipo_id,),
            ).fetchone()
            if next_foto:
                conn.execute(
                    "UPDATE equipo_fotos SET es_principal = TRUE WHERE id = ?", (next_foto["id"],)
                )
                conn.execute("UPDATE equipos SET foto_url = ? WHERE id = ?", (next_foto["url"], equipo_id))
            else:
                conn.execute("UPDATE equipos SET foto_url = NULL WHERE id = ?", (equipo_id,))

        conn.commit()
    finally:
        conn.close()

    if r2_keys:
        purge_r2(r2_keys)
    elif path:
        from services.image_upload import _delete_from_r2
        _delete_from_r2(path)

    return {"ok": True}


class EquipoFotoOrdenItem(BaseModel):
    id: int
    orden: int
    es_principal: bool


class EquipoFotoReorderBody(BaseModel):
    fotos: list[EquipoFotoOrdenItem]


@router.patch("/admin/equipos/{equipo_id}/fotos/orden")
def reorder_equipo_fotos(equipo_id: int, body: EquipoFotoReorderBody, request: Request):
    require_admin(request)

    conn = get_db()
    try:
        principal_url: str | None = None
        for f in body.fotos:
            conn.execute(
                "UPDATE equipo_fotos SET orden = ?, es_principal = ? "
                "WHERE id = ? AND equipo_id = ?",
                (f.orden, f.es_principal, f.id, equipo_id),
            )
            if f.es_principal:
                row = conn.execute(
                    "SELECT url FROM equipo_fotos WHERE id = ?", (f.id,)
                ).fetchone()
                if row:
                    principal_url = row["url"]

        if principal_url is not None:
            conn.execute("UPDATE equipos SET foto_url = ? WHERE id = ?", (principal_url, equipo_id))

        conn.commit()
        fotos = _get_equipo_fotos(conn, equipo_id)
    finally:
        conn.close()

    return {"fotos": fotos}


# ── Admin: diagnóstico de R2 (sin exponer secretos) ─────────────────────────

@router.get("/admin/storage/diag")
def admin_storage_diag(request: Request):
    """Verifica que R2 esté configurado correctamente. Sólo dice si las vars
    están presentes y si el upload+read end-to-end funciona. NUNCA devuelve
    el contenido del secret."""
    require_admin(request)

    import time as _time
    import httpx

    vars_status = {
        "R2_ACCOUNT_ID":         bool(os.getenv("R2_ACCOUNT_ID")),
        "R2_ACCESS_KEY_ID":      bool(os.getenv("R2_ACCESS_KEY_ID")),
        "R2_SECRET_ACCESS_KEY":  bool(os.getenv("R2_SECRET_ACCESS_KEY")),
        "R2_BUCKET":             os.getenv("R2_BUCKET") or "equipos-fotos",
        "R2_PUBLIC_BASE":        os.getenv("R2_PUBLIC_BASE") or None,
    }
    missing = [k for k, v in vars_status.items() if v is False]
    if missing:
        return {"ok": False, "vars": vars_status, "missing": missing, "tested": False}

    # Smoke test: subir un blob chico y leerlo
    try:
        sample = b"R2 smoke test " + str(int(_time.time())).encode()
        path = f"diag/smoke-{int(_time.time())}.txt"
        public_url = _upload_to_r2(path, sample, "text/plain")
        verify = httpx.get(public_url, timeout=10.0)
        ok = verify.status_code == 200 and verify.content == sample
        return {
            "ok":         ok,
            "vars":       vars_status,
            "tested":     True,
            "public_url": public_url,
            "verify":     verify.status_code,
        }
    except HTTPException as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": e.detail}
    except Exception as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": str(e)}
