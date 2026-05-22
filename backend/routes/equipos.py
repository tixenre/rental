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
    attach_ficha, attach_specs_destacados, regenerate_auto_tags,
)
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


class FichaUpdate(BaseModel):
    descripcion:   Optional[str] = None
    notas:         Optional[str] = None
    specs_json:    Optional[str] = None
    montura:       Optional[str] = None
    formato:       Optional[str] = None
    resolucion:    Optional[str] = None
    keywords_json: Optional[str] = None
    nombre_publico_template: Optional[str] = None
    # Ficha extendida (enriquecimiento)
    peso:                Optional[str]   = None
    dimensiones:         Optional[str]   = None
    alimentacion:        Optional[str]   = None
    incluye_json:        Optional[str]   = None
    conectividad_json:   Optional[str]   = None
    compatible_con_json: Optional[str]   = None
    video_url:           Optional[str]   = None
    precio_bh_usd:       Optional[float] = None
    fuente_url:          Optional[str]   = None
    fuente_titulo:       Optional[str]   = None
    raw_json:            Optional[str]   = None
    enriquecido_fuente:  Optional[str]   = None


class KitItem(BaseModel):
    componente_id: int
    cantidad:      int = 1


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


class MantenimientoUpdate(BaseModel):
    fecha:            Optional[str] = None
    tipo:             Optional[str] = None
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None


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


# ── Rutas de equipos ─────────────────────────────────────────────────────────

ESTADOS_RESERVADO = "('presupuesto','confirmado','retirado')"


def _attach_disponibilidad(conn, equipos: list, desde: str, hasta: str) -> list:
    """Calcula disponibilidad real por equipo e inyecta el campo `disponible`."""
    directas = conn.execute(f"""
        SELECT e.id, e.cantidad,
               COALESCE(SUM(CASE
                 WHEN p.estado IN {ESTADOS_RESERVADO}
                      AND p.fecha_desde < ?
                      AND p.fecha_hasta > ?
                 THEN pi.cantidad ELSE 0
               END), 0) AS reservado
        FROM equipos e
        LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
        LEFT JOIN alquileres p ON p.id = pi.pedido_id
        GROUP BY e.id
    """, (hasta, desde)).fetchall()

    reservado = {r["id"]: r["reservado"] for r in directas}
    cantidad  = {r["id"]: r["cantidad"]  for r in directas}

    via_kit = conn.execute(f"""
        SELECT kc.componente_id,
               SUM(pi.cantidad * kc.cantidad) AS extra
        FROM kit_componentes kc
        JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
        JOIN alquileres p ON p.id = pi.pedido_id
        WHERE p.estado IN {ESTADOS_RESERVADO}
          AND p.fecha_desde < ?
          AND p.fecha_hasta > ?
        GROUP BY kc.componente_id
    """, (hasta, desde)).fetchall()

    for r in via_kit:
        reservado[r["componente_id"]] = reservado.get(r["componente_id"], 0) + r["extra"]

    for eq in equipos:
        eid = eq["id"]
        eq["disponible"] = max(0, cantidad.get(eid, eq.get("cantidad", 0)) - reservado.get(eid, 0))

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
            OR COALESCE(e.marca, '') ILIKE ?
            OR COALESCE(e.modelo, '') ILIKE ?
            OR COALESCE(e.serie, '') ILIKE ?
            OR EXISTS (
                SELECT 1 FROM equipo_fichas ef
                WHERE ef.equipo_id = e.id AND (
                    COALESCE(ef.descripcion, '') ILIKE ?
                    OR COALESCE(ef.specs_json, '') ILIKE ?
                    OR COALESCE(ef.keywords_json, '') ILIKE ?
                )
            )
        )"""
        params += [like] * 7
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
        # Filtro por marca exacta (case-insensitive). Usa el campo TEXT que
        # se sincroniza con la tabla marcas en rename (#303).
        base_sql += " AND LOWER(COALESCE(e.marca, '')) = LOWER(?)"
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
            f"SELECT e.* {base_sql} {order_clause} LIMIT ? OFFSET ?",
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
        # Formatear specs_json values tipo tabla con conectores legibles.
        # Cargamos las defs UNA vez (no por equipo) para evitar N queries.
        tabla_defs_by_label = _load_tabla_defs_by_label(conn)
        if tabla_defs_by_label:
            for eq in equipos:
                ficha = eq.get("ficha") or {}
                if ficha.get("specs_json"):
                    ficha["specs_json"] = _apply_tabla_defs_to_specs_json(
                        ficha["specs_json"], tabla_defs_by_label
                    )
        equipos = attach_specs_destacados(conn, equipos)

        if desde and hasta:
            equipos = _attach_disponibilidad(conn, equipos, desde, hasta)

        return {"total": total, "page": page, "per_page": per_page, "items": equipos}
    finally:
        conn.close()


def _load_tabla_defs_by_label(conn) -> dict[str, dict]:
    """Carga TODAS las spec_definitions tipo 'tabla' y las indexa por label
    normalizado. Devuelve {} si no hay specs tabla en el catálogo."""
    import json as _json
    defs_rows = conn.execute(
        "SELECT label, tipo, tabla_columnas, output_config "
        "FROM spec_definitions WHERE tipo = 'tabla'"
    ).fetchall()
    out: dict[str, dict] = {}
    for r in defs_rows:
        d = row_to_dict(r) if not isinstance(r, dict) else r
        cols = d.get("tabla_columnas")
        if isinstance(cols, str):
            try:
                cols = _json.loads(cols)
            except Exception:
                cols = None
        oc = d.get("output_config")
        if isinstance(oc, str):
            try:
                oc = _json.loads(oc)
            except Exception:
                oc = None
        out[norm_spec_label(d.get("label") or "")] = {
            "tipo": d.get("tipo"),
            "tabla_columnas": cols,
            "output_config": oc,
        }
    return out


def _apply_tabla_defs_to_specs_json(
    raw_specs_json: Optional[str],
    defs_by_label: dict[str, dict],
) -> Optional[str]:
    """Post-procesa `specs_json` del ficha: para items cuyo label matchea
    una spec_definition tipo tabla, formatea el value crudo (JSON) a texto
    legible con conectores y agrega `value_raw` con el JSON original (sirve
    para placeholders tipo `{spec:Label.colKey}` que extraen celdas
    específicas en lugar del texto completo). El resto queda intacto."""
    import json as _json
    if not raw_specs_json or not defs_by_label:
        return raw_specs_json
    try:
        arr = _json.loads(raw_specs_json)
    except Exception:
        return raw_specs_json
    if not isinstance(arr, list):
        return raw_specs_json
    changed = False
    out: list[dict] = []
    for item in arr:
        if not isinstance(item, dict) or "label" not in item or "value" not in item:
            out.append(item)
            continue
        label = item.get("label") or ""
        value = item.get("value")
        if not isinstance(value, str):
            out.append(item)
            continue
        sd = defs_by_label.get(norm_spec_label(label))
        if sd and sd.get("tipo") == "tabla":
            cols = sd.get("tabla_columnas") or []
            output_config = sd.get("output_config")
            formatted = format_tabla_value(value, cols, output_config)
            if formatted != value:
                # Mantenemos `value_raw` con el JSON original para que el
                # frontend pueda extraer celdas via `{spec:Label.colKey}`.
                # Adjuntamos output_config para que el front aplique la
                # misma row_strategy en el preview live del editor.
                extra = {"value": formatted, "value_raw": value}
                if output_config:
                    extra["output_config"] = output_config
                out.append({**item, **extra})
                changed = True
                continue
        out.append(item)
    return _json.dumps(out, ensure_ascii=False) if changed else raw_specs_json


def _format_specs_json_with_definitions(conn, raw_specs_json: Optional[str]) -> Optional[str]:
    """Versión single-equipo: carga defs internamente. Usar para endpoints
    que sirven 1 equipo (detalle). Para listas, usar load_tabla_defs +
    apply_tabla_defs separados para evitar N queries."""
    defs = _load_tabla_defs_by_label(conn)
    return _apply_tabla_defs_to_specs_json(raw_specs_json, defs)


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
            "SELECT * FROM equipos WHERE id = ?", (actual_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_ficha(conn, [equipo])[0]
        equipo = attach_categorias(conn, [equipo])[0]
        # Post-procesar `specs_json` para formatear values tipo tabla con
        # sus conectores. El frontend recibe texto legible directo.
        ficha = equipo.get("ficha") or {}
        if ficha.get("specs_json"):
            ficha["specs_json"] = _format_specs_json_with_definitions(
                conn, ficha["specs_json"]
            )
        kit = conn.execute("""
            SELECT kc.componente_id, kc.cantidad, e.nombre, e.marca, e.foto_url
            FROM kit_componentes kc JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?  ORDER BY e.nombre
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


@router.post("/equipos", status_code=201)
def create_equipo(data: EquipoCreate):
    conn = get_db()
    try:
        # Validar serie única (rechaza 409 si choca con otro activo)
        _check_serie_unica(conn, data.serie)
        cur  = conn.execute("""
            INSERT INTO equipos (nombre, marca, modelo, cantidad,
                                 precio_jornada, precio_usd, roi_pct,
                                 valor_reposicion, foto_url, fecha_compra,
                                 serie, bh_url, dueno, visible_catalogo, estado,
                                 ficha_completa)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (data.nombre, data.marca, data.modelo, data.cantidad,
              data.precio_jornada, data.precio_usd, data.roi_pct,
              data.valor_reposicion, data.foto_url, data.fecha_compra,
              data.serie, data.bh_url, data.dueno, data.visible_catalogo, data.estado,
              bool(data.ficha_completa)))
        new_id = cur.lastrowid
        # Hook: calcular nombre_publico inicial. No falla el create si esto
        # rompe (ej. si los servicios no están disponibles).
        try:
            actualizar_nombres_de(conn, new_id, commit=False)
        except Exception:
            pass
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (new_id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/equipos/{id}")
def update_equipo(id: int, data: EquipoUpdate):
    conn     = get_db()
    try:
        existing = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Equipo no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
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
        if any(k in updates for k in ("nombre", "marca", "modelo")):
            regenerate_auto_tags(conn, id)
        # Hook: si cambió algo que afecta el nombre público, recalcular.
        # No falla el update si el recálculo rompe.
        if any(k in updates for k in ("nombre", "marca", "modelo")):
            try:
                actualizar_nombres_de(conn, id, commit=False)
            except Exception:
                pass
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
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
        src = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        if not src:
            raise HTTPException(404, "Equipo no encontrado")
        src_d = row_to_dict(src)

        cur = conn.execute("""
            INSERT INTO equipos (
                nombre, marca, modelo, cantidad,
                precio_jornada, precio_usd, roi_pct,
                valor_reposicion, foto_url, fecha_compra,
                serie, bh_url, dueno, visible_catalogo, estado,
                ficha_completa
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            f"{src_d['nombre']} (copia)",
            src_d.get("marca"), src_d.get("modelo"), 1,
            src_d.get("precio_jornada"), src_d.get("precio_usd"), src_d.get("roi_pct"),
            src_d.get("valor_reposicion"), src_d.get("foto_url"), src_d.get("fecha_compra"),
            None,  # serie vacía
            src_d.get("bh_url"), src_d.get("dueno"), src_d.get("visible_catalogo", 1), src_d.get("estado", "operativo"),
            False,  # ficha_completa false para que el admin la revise
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
        row = conn.execute("SELECT * FROM equipos WHERE id=?", (new_id,)).fetchone()
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
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
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
        if row:
            return row_to_dict(row)
        return {
            "equipo_id": id, "descripcion": None, "notas": None, "specs_json": None,
            "montura": None, "formato": None, "resolucion": None, "keywords_json": None,
            "nombre_publico_template": None,
        }
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
            # Hook: si cambió el template de nombre o specs estructuradas
            # (montura/formato/resolucion legacy), recalcular nombre_publico.
            keys_que_afectan_nombre = {
                "nombre_publico_template", "montura", "formato", "resolucion",
            }
            if any(k in patch for k in keys_que_afectan_nombre):
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
                GREATEST(1, DATE_PART('day', LEFT(p.fecha_hasta, 10)::TIMESTAMP - LEFT(p.fecha_desde, 10)::TIMESTAMP))::INTEGER AS dias
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
            SELECT id, equipo_id, fecha, tipo, descripcion, costo, proxima_revision, created_at
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
            INSERT INTO equipo_mantenimiento (equipo_id, fecha, tipo, descripcion, costo, proxima_revision)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (id, data.fecha, data.tipo or "revision", data.descripcion, data.costo, data.proxima_revision))
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
                   e.nombre, e.marca, e.modelo, e.foto_url, e.visible_catalogo
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
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (data.componente_id,)).fetchone():
            raise HTTPException(404, "Componente no encontrado")
        if _crea_ciclo_kit(conn, id, data.componente_id):
            raise HTTPException(
                400,
                "Agregar este componente crearía un ciclo en los kits "
                "(el componente ya contiene a este equipo en su cadena).",
            )
        try:
            conn.execute("""
                INSERT INTO kit_componentes (equipo_id, componente_id, cantidad)
                VALUES (?,?,?)
                ON CONFLICT(equipo_id, componente_id) DO UPDATE SET cantidad=excluded.cantidad
            """, (id, data.componente_id, data.cantidad))
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
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
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
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
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
                e.id, e.nombre, e.marca, e.modelo, e.foto_url,
                COUNT(DISTINCT p.id) AS cant_pedidos,
                SUM(
                    COALESCE(pi.precio_jornada, 0) * COALESCE(pi.cantidad, 1)
                    * GREATEST(1, DATE_PART('day', LEFT(p.fecha_hasta, 10)::TIMESTAMP - LEFT(p.fecha_desde, 10)::TIMESTAMP))::INTEGER
                ) AS revenue_total
            FROM equipos e
            JOIN alquiler_items pi ON pi.equipo_id = e.id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE e.eliminado_at IS NULL
            GROUP BY e.id, e.nombre, e.marca, e.modelo, e.foto_url
            ORDER BY cant_pedidos DESC, revenue_total DESC
            LIMIT 10
        """).fetchall()

        # ── Equipos sin movimiento (último alquiler hace > N días, o nunca) ──
        sin_uso = conn.execute("""
            SELECT
                e.id, e.nombre, e.marca, e.modelo, e.foto_url, e.valor_reposicion,
                MAX(p.fecha_desde) AS ultimo_alquiler,
                COUNT(DISTINCT p.id) AS total_alquileres
            FROM equipos e
            LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
            LEFT JOIN alquileres p ON p.id = pi.pedido_id
            WHERE e.eliminado_at IS NULL
            GROUP BY e.id, e.nombre, e.marca, e.modelo, e.foto_url, e.valor_reposicion
            HAVING (MAX(p.fecha_desde) IS NULL OR MAX(p.fecha_desde) < (CURRENT_DATE - (? || ' days')::INTERVAL)::TEXT)
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
                    * GREATEST(1, DATE_PART('day', LEFT(p.fecha_hasta, 10)::TIMESTAMP - LEFT(p.fecha_desde, 10)::TIMESTAMP))::INTEGER
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
                    * GREATEST(1, DATE_PART('day', LEFT(p.fecha_hasta, 10)::TIMESTAMP - LEFT(p.fecha_desde, 10)::TIMESTAMP))::INTEGER
                ) AS revenue_total
            FROM equipos e
            LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
            LEFT JOIN alquileres p ON p.id = pi.pedido_id
            WHERE e.eliminado_at IS NULL
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
        rows = conn.execute("""
            SELECT id, nombre, marca, modelo, foto_url,
                   valor_reposicion, dueno, cantidad
            FROM equipos
            WHERE serie IS NULL OR TRIM(serie) = ''
            ORDER BY COALESCE(valor_reposicion, 0) DESC, id ASC
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
            SELECT e.id, e.nombre, e.marca, e.modelo
            FROM equipos e
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

        ESTADOS = "('presupuesto','confirmado','retirado')"

        # Direct reservations that overlap this month
        directas = conn.execute(f"""
            SELECT LEFT(p.fecha_desde, 10) AS desde,
                   LEFT(p.fecha_hasta, 10) AS hasta,
                   pi.cantidad
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE pi.equipo_id = ?
              AND p.estado IN {ESTADOS}
              AND LEFT(p.fecha_desde, 10) <= ?
              AND LEFT(p.fecha_hasta, 10) > ?
        """, (id, last_day, first_day)).fetchall()

        # Via-kit reservations: this equipment is a component of a rented kit
        via_kit = conn.execute(f"""
            SELECT LEFT(p.fecha_desde, 10) AS desde,
                   LEFT(p.fecha_hasta, 10) AS hasta,
                   pi.cantidad * kc.cantidad AS cantidad
            FROM kit_componentes kc
            JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE kc.componente_id = ?
              AND p.estado IN {ESTADOS}
              AND LEFT(p.fecha_desde, 10) <= ?
              AND LEFT(p.fecha_hasta, 10) > ?
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


# ── Admin: enriquecimiento con IA (Firecrawl + Lovable AI) ────────────────────

class EnriquecerInput(BaseModel):
    nombre: Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    url:    Optional[str] = None   # Si está presente, salta la búsqueda y scrapea esa URL directo
    # categoria_ids: si vienen, el specs_guide se filtra a sólo esas categorías
    # (incluyendo padres en el árbol). Permite que la IA se enfoque en los
    # labels esperados para ese equipo. Si está vacío, guía con todas las cats. (#calidad)
    categoria_ids: Optional[list[int]] = None


class BatchEnriquecerInput(BaseModel):
    # Hasta 3 equipo_ids por request (evita timeouts). El frontend re-batchea.
    # `max_length=50` defensivo: aunque solo procesamos los primeros 3, evita
    # que el body de la request crezca arbitrariamente (DoS por payload size).
    equipo_ids: list[int] = Field(..., min_length=1, max_length=50)


@router.post("/admin/equipos/batch-enriquecer")
def admin_batch_enriquecer(payload: BatchEnriquecerInput, request: Request):
    """
    Procesa un chunk de equipos: para cada uno, scrapea su bh_url y guarda el
    resultado en `equipo_fichas.raw_json` (cache). El admin después aplica los
    campos por sección con los botones ✨ del form V2.

    Límite: 3 equipos por request. El frontend re-batchea hasta terminar.
    Entre cada scrape duerme 1s para no rate-limitear B&H.

    NO sobrescribe campos no vacíos del equipo. Solo llena marca/modelo/foto_url
    si están vacíos. Specs y descripción siempre van al cache; el admin decide
    qué aplicar después.
    """
    require_admin(request)

    import time as _time, json as _json

    ids = payload.equipo_ids[:3]   # hard cap defensivo
    if not ids:
        return {"results": []}

    conn = get_db()
    results = []
    try:
        for eid in ids:
            eq = conn.execute("SELECT id, nombre, marca, modelo, foto_url, bh_url FROM equipos WHERE id=?", (eid,)).fetchone()
            if not eq:
                results.append({"equipo_id": eid, "status": "error", "error": "no existe"})
                continue
            eq_d = row_to_dict(eq)
            if not eq_d.get("bh_url"):
                results.append({"equipo_id": eid, "status": "skipped", "reason": "sin bh_url"})
                continue

            # Defense-in-depth: aunque bh_url ya pasó por validación cuando se guardó
            # el equipo, revalidamos antes de scrapear (impide SSRF a IPs privadas si
            # el equipo viene de una migración vieja o de un campo no validado).
            try:
                _validate_ssrf_only(eq_d["bh_url"])
            except HTTPException as he:
                results.append({"equipo_id": eid, "status": "error", "error": f"URL inválida: {he.detail}"[:200]})
                continue

            try:
                # Llamada interna al enriquecer. Pasamos el mismo `request` ya
                # validado — require_admin se ejecuta de nuevo (idempotente)
                # pero no hace daño y mantiene el endpoint protegido si se
                # llama directo.
                scrape = admin_enriquecer_equipo(
                    EnriquecerInput(url=eq_d["bh_url"]),
                    request,
                )

                # Persistir raw_json en equipo_fichas (cache para botones ✨)
                conn.execute(
                    """INSERT INTO equipo_fichas (equipo_id, raw_json, fuente_url, enriquecido_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT (equipo_id) DO UPDATE
                       SET raw_json = EXCLUDED.raw_json,
                           fuente_url = COALESCE(EXCLUDED.fuente_url, equipo_fichas.fuente_url),
                           enriquecido_at = EXCLUDED.enriquecido_at""",
                    (eid, _json.dumps(scrape, ensure_ascii=False), scrape.get("fuente_url") or eq_d["bh_url"]),
                )

                # Llenar campos top-level del equipo si están vacíos
                patch = {}
                if not eq_d.get("marca") and scrape.get("marca"):
                    patch["marca"] = scrape["marca"]
                if not eq_d.get("modelo") and scrape.get("modelo"):
                    patch["modelo"] = scrape["modelo"]
                if not eq_d.get("foto_url") and scrape.get("foto_url"):
                    patch["foto_url"] = scrape["foto_url"]
                if patch:
                    set_clause = ", ".join(f"{k} = ?" for k in patch)
                    set_clause += ", updated_at = CURRENT_TIMESTAMP"
                    conn.execute(
                        f"UPDATE equipos SET {set_clause} WHERE id = ?",
                        list(patch.values()) + [eid],
                    )

                conn.commit()
                results.append({
                    "equipo_id": eid,
                    "status": "ok",
                    "specs_count": len(scrape.get("specs") or []),
                    "filled": list(patch.keys()),
                })
            except HTTPException as he:
                # Errores HTTP del scrape: mostrar el detail (que ya está
                # sanitizado por el endpoint upstream).
                conn.rollback()
                results.append({"equipo_id": eid, "status": "error", "error": str(he.detail)[:200]})
            except Exception as e:
                # Errores no esperados: NO exponer str(e) al frontend (puede
                # contener paths/internals). Log completo server-side; al user
                # un mensaje genérico.
                conn.rollback()
                logger.exception("batch-enriquecer falló para equipo %s", eid)
                results.append({
                    "equipo_id": eid,
                    "status": "error",
                    "error": f"Error inesperado ({type(e).__name__})",
                })

            # Rate limit B&H — saltamos el sleep en la última iteración del
            # chunk para no demorar la respuesta gratis.
            if eid != ids[-1]:
                _time.sleep(1)

        return {"results": results}
    finally:
        conn.close()


@router.post("/admin/equipos/autocompletar")
def admin_autocompletar_equipo(payload: EnriquecerInput, request: Request):
    """Endpoint canónico — alias de /enriquecer (legacy).
    El frontend ya usa "autocompletar" como nombre del feature; este endpoint
    coherente con el naming. /enriquecer queda como alias deprecated."""
    return admin_enriquecer_equipo(payload, request)


@router.post("/admin/equipos/autocompletar-from-html")
async def admin_autocompletar_from_html(
    request: Request,
    file: UploadFile = File(...),
    categoria_hint: Optional[str] = None,
) -> dict:
    """Acepta un HTML guardado de B&H y devuelve specs canónicos normalizados.

    Workaround para el bot-detection de B&H que bloquea scrapers server-side:
    el admin guarda la página con Cmd+S → Webpage Complete y sube el .html acá.

    Usa los mismos parsers que el seed (tools/{iluminacion,camaras,lentes}_parser.py)
    via el dispatcher `services/equipo_html_extractor.py`. Calidad idéntica al
    dataset curado en todas las categorías:

      - Cámaras → camaras_parser
      - Lentes / Adaptadores / Filtros → lentes_parser (clasifica internamente)
      - Iluminación → iluminacion_parser (vía luces_html_extractor)

    Args:
        file: HTML B&H (.html guardado completo).
        categoria_hint: opcional ("Cámaras", "Lentes", etc.) — si el frontend
            ya sabe la categoría (ej. usuario la eligió antes), evita la
            detección automática.

    Returns: AutocompletarResult con specs canónicos + keywords derivadas
    de specs (no LLM) + `categoria_sugerida`.
    """
    require_admin(request)

    content = await file.read()
    if len(content) > 5_000_000:  # 5MB cap defensivo
        raise HTTPException(400, "HTML demasiado grande (máx 5MB)")
    if not content:
        raise HTTPException(400, "Archivo vacío")

    try:
        html_content = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "HTML inválido (no es UTF-8)")

    try:
        from services.equipo_html_extractor import extract_from_html
        result = extract_from_html(html_content, categoria_hint=categoria_hint)
    except Exception as e:
        logger.exception("Error extrayendo specs del HTML")
        raise HTTPException(500, f"Error parseando HTML: {e}")

    return result


@router.post("/admin/equipos/enriquecer", deprecated=True)
def admin_enriquecer_equipo(payload: EnriquecerInput, request: Request):
    """
    Busca el equipo en B&H/Adorama, scrapea la página y usa Lovable AI para
    extraer marca/modelo/specs/foto en JSON estructurado. Devuelve un preview;
    el frontend decide qué campos aplicar via PATCH normal.

    DEPRECATED: usar /admin/equipos/autocompletar.
    """
    require_admin(request)
    import os, httpx

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado en el backend")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida (debe empezar con http:// o https://)")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url para enriquecer")

    # ── Specs guiados por template ─────────────────────────────────────────
    # Cargamos los specs definidos en `categoria_spec_templates` y los inyectamos
    # al prompt para que la IA use labels canónicos consistentes con nuestro modelo.
    # (Schema sigue siendo `specs: [{label,value}]` para mantener compat con el
    # migrador y los flujos viejos — solo guiamos al LLM con los labels esperados.)
    def _build_specs_guide() -> str:
        try:
            conn = get_db()
            try:
                # Si vienen categoria_ids, filtramos la guía a esas categorías
                # más sus ancestros (para que las specs de los padres también
                # aparezcan en el prompt). Sino, mostramos todas las
                # categorías (comportamiento legacy).
                if payload.categoria_ids:
                    placeholders = ",".join(["%s"] * len(payload.categoria_ids))
                    rows = conn.execute(f"""
                        WITH RECURSIVE chain AS (
                            SELECT id, parent_id FROM categorias WHERE id IN ({placeholders})
                            UNION
                            SELECT c.id, c.parent_id FROM categorias c
                              JOIN chain ON c.id = chain.parent_id
                        )
                        SELECT c.nombre AS categoria, sd.label, sd.tipo, sd.unidad,
                               sd.enum_options, t.prioridad
                        FROM categoria_spec_templates t
                        JOIN categorias c ON c.id = t.categoria_id
                        JOIN spec_definitions sd ON sd.id = t.spec_def_id
                        WHERE c.id IN (SELECT id FROM chain)
                        ORDER BY c.prioridad NULLS LAST, c.nombre,
                                 t.prioridad NULLS LAST, sd.label
                    """, payload.categoria_ids).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT c.nombre AS categoria, sd.label, sd.tipo, sd.unidad, sd.enum_options, t.prioridad
                        FROM categoria_spec_templates t
                        JOIN categorias c ON c.id = t.categoria_id
                        JOIN spec_definitions sd ON sd.id = t.spec_def_id
                        ORDER BY c.prioridad NULLS LAST, c.nombre, t.prioridad NULLS LAST, sd.label
                    """).fetchall()
            finally:
                conn.close()
        except Exception:
            return ""

        if not rows:
            return ""

        # Agrupamos por categoría
        from collections import defaultdict
        by_cat: dict[str, list[str]] = defaultdict(list)
        for r in rows:
            r = row_to_dict(r) if not isinstance(r, dict) else r
            label = r.get("label") or ""
            tipo = r.get("tipo") or ""
            unidad = r.get("unidad") or ""
            enum_options = r.get("enum_options")
            hint = label
            if tipo == "enum" and enum_options:
                import json as _json
                try:
                    opts = enum_options if isinstance(enum_options, list) else _json.loads(enum_options)
                    if opts:
                        hint = f"{label} (uno de: {', '.join(map(str, opts[:8]))})"
                except Exception:
                    pass
            elif tipo == "number" and unidad:
                hint = f"{label} (numérico en {unidad})"
            elif tipo == "number":
                hint = f"{label} (numérico, sin unidad — ej. cantidad)"
            elif tipo == "rango" and unidad:
                hint = f"{label} (un valor o rango con guión en {unidad} — ej. '50' o '24-70')"
            elif tipo == "bool":
                hint = f"{label} (sí/no)"
            by_cat[r["categoria"]].append(hint)

        if payload.categoria_ids:
            header = (
                "LABELS CANÓNICOS DE LA CATEGORÍA SELECCIONADA — usá EXACTAMENTE "
                "estos labels y formatos. Si la página dice algo similar, "
                "normalizalo al label de acá:"
            )
        else:
            header = "LABELS CANÓNICOS DE SPECS POR CATEGORÍA — usá estos labels exactos cuando aplique:"
        lines = [header]
        for cat, specs in by_cat.items():
            lines.append(f"  • {cat}: {' / '.join(specs)}.")
        lines.append(
            "Para enums, devolvé exactamente uno de los valores listados (case-sensitive). "
            "Para rangos, devolvé un solo valor (fijo) o dos separados por guión "
            "(zoom/range). Si el equipo no encaja en ninguna categoría, "
            "usá los labels más naturales."
        )
        return "\n".join(lines)

    specs_guide = _build_specs_guide()

    # ── Labels canónicos del template (para enum del JSON schema) ──────
    # Si tenemos categoría, recolectamos los labels EXACTOS de las specs
    # asignadas. Lo pasamos como enum dinámico en specs[].label así el LLM
    # se ve OBLIGADO a usar el label canónico (ej. "Formato de sensor")
    # en lugar de inventar variaciones ("Formato", "Sensor format", etc).
    def _build_template_labels() -> list[str]:
        try:
            conn = get_db()
            try:
                if payload.categoria_ids:
                    placeholders = ",".join(["%s"] * len(payload.categoria_ids))
                    rows = conn.execute(
                        f"""
                        WITH RECURSIVE chain AS (
                            SELECT id, parent_id FROM categorias WHERE id IN ({placeholders})
                            UNION
                            SELECT c.id, c.parent_id FROM categorias c
                              JOIN chain ON c.id = chain.parent_id
                        )
                        SELECT DISTINCT sd.label
                        FROM categoria_spec_templates t
                        JOIN spec_definitions sd ON sd.id = t.spec_def_id
                        WHERE t.categoria_id IN (SELECT id FROM chain)
                        ORDER BY sd.label
                        """,
                        payload.categoria_ids,
                    ).fetchall()
                else:
                    rows = []
                return [r["label"] for r in rows if r["label"]]
            finally:
                conn.close()
        except Exception:
            return []

    template_labels = _build_template_labels()

    # ── Categorías disponibles en la DB ─────────────────────────────────────
    # La IA elige UNA categoría sugerida de las que existen REALMENTE en la DB
    # (raíces + hijas), no de un enum hardcoded. Así las categorías nuevas que
    # el admin cree se aprovechan, y la IA puede sugerir subcategorías
    # específicas (ej. "Montura E" en vez de la madre "Lente").
    def _build_categorias_enum() -> str:
        try:
            conn = get_db()
            try:
                rows = conn.execute(
                    "SELECT nombre FROM categorias ORDER BY parent_id NULLS FIRST, nombre"
                ).fetchall()
                names = [r["nombre"] for r in rows if r.get("nombre")]
                if not names:
                    return "'Cámara','Lente','Iluminación','Audio','Soporte','Monitor','Accesorio'"
                return ",".join(f"'{n}'" for n in names)
            finally:
                conn.close()
        except Exception:
            return "'Cámara','Lente','Iluminación','Audio','Soporte','Monitor','Accesorio'"

    categorias_enum = _build_categorias_enum()

    headers_fc = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    def _extract_results(j: dict) -> list[dict]:
        data = j.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("web", []) or []
        return []

    OFFICIAL_SITES = (
        "site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        "site:fujifilm.com OR site:fujifilm-x.com OR site:panasonic.com OR "
        "site:blackmagicdesign.com OR site:aputure.com OR site:godox.com OR "
        "site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        "site:tilta.com OR site:smallrig.com OR site:zoom-na.com OR site:zhiyun-tech.com"
    )

    def _search(q: str, client: "httpx.Client") -> list[dict]:
        try:
            rr = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers_fc,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if rr.status_code != 200:
            return []
        return _extract_results(rr.json())

    def _first_valid(results: list[dict]) -> dict | None:
        for r in results:
            u = (r.get("url") or "").strip()
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                return r
        return None

    json_format = {
        "type": "json",
        "prompt": (
            "Extraé información completa del equipo audiovisual (cámara, lente, "
            "luz, audio, soporte) desde la ficha de producto. "
            "Descripcion: 1-2 oraciones en español neutral. "
            "Specs: máximo 10, label corto y value conciso (ej. 'Sensor': 'Full-frame 24MP'). "
            "Keywords: 3-6 palabras clave cortas en español lowercase que describan la "
            "PERSONALIDAD/diferenciales del equipo (ej: 'bicolor', 'silenciosa', "
            "'v-mount', 'global shutter', 'weather sealed', 'cri 96', 'cine-ready'). "
            "Distintas y específicas — nada genérico como 'profesional' o 'calidad'. "
            "Peso: con unidad (ej '640g', '1.2kg'). "
            "Dimensiones: WxHxD con unidad (ej '129.7 x 77.8 x 84.5 mm'). "
            "Montura: nombre canónico (ej 'Sony E', 'Canon RF', 'EF', 'MFT', 'PL'). "
            "Formato: 'Full-frame' | 'APS-C' | 'MFT' | 'Super 35' | etc. para cámaras/lentes. "
            "Resolucion: para cámaras/monitores (ej '4K 120p', '6K Open Gate', '1080p'). "
            "Alimentacion: tipo de batería o fuente (ej 'NP-FZ100', 'V-mount', 'AC 220V', '2x AA'). "
            "Incluye: array de items que vienen en la caja (ej ['Cuerpo','Tapa','Cargador']). "
            "Conectividad: array de puertos (ej ['USB-C','HDMI Type-A','XLR x2','Mini-jack 3.5mm']). "
            "Compatible_con: array de etiquetas de compatibilidad (montura, formato, sistemas). "
            "Precio_usd: precio listado en USD si está visible (sólo número). "
            "Video_url: URL absoluta a un video YouTube de demo si aparece linkeado. "
            f"Categoria_sugerida: UNA de [{categorias_enum}]. "
            "Elegí la MÁS ESPECÍFICA disponible — si hay una subcategoría que aplica "
            "(ej. 'Montura E', 'Cinema'), preferila sobre la madre genérica (ej. 'Lente', 'Cámara'). "
            "Foto_urls: array con hasta 5 URLs ABSOLUTAS (http/https) de imágenes del producto, "
            "ordenadas de MÁS A MENOS relevante para el producto principal. "
            "Incluí ángulos distintos (frente, lateral, detalle) si están disponibles. "
            "JPG/PNG/WebP únicamente — NO uses placeholders, sprites, SVGs decorativos, "
            "tracking pixels, banners de categoría, fotos de productos relacionados, ni rutas relativas. "
            "Si no estás 100% seguro de que una URL existe y apunta al producto, NO la incluyas. "
            "Cualquier campo que no esté en la ficha → dejalo vacío. NO inventes."
            + ("\n\n" + specs_guide if specs_guide else "")
        ),
        "schema": {
            "type": "object",
            "properties": {
                "marca":  {"type": "string"},
                "modelo": {"type": "string"},
                "nombre_normalizado": {"type": "string"},
                "descripcion": {"type": "string"},
                "foto_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "specs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            # Si hay template para la categoría, FORZAMOS al LLM
                            # a usar uno de esos labels canónicos via enum.
                            # Sin template (autocompletar genérico), free-text.
                            "label": (
                                {"type": "string", "enum": template_labels}
                                if template_labels
                                else {"type": "string"}
                            ),
                            "value": {"type": "string"},
                        },
                        "required": ["label", "value"],
                    },
                },
                "keywords":          {"type": "array", "items": {"type": "string"}},
                "peso":              {"type": "string"},
                "dimensiones":       {"type": "string"},
                # NOTA: monturas/formato/resolución se devuelven dentro de `specs`
                # como label canónico del template de la categoría (ej. "Lens mount",
                # "Formato de sensor", etc.). El matching estructurado los conecta
                # al spec_def_id correcto vía _matchear_y_persistir_specs.
                "alimentacion":      {"type": "string"},
                "incluye":           {"type": "array", "items": {"type": "string"}},
                "conectividad":      {"type": "array", "items": {"type": "string"}},
                "compatible_con":    {"type": "array", "items": {"type": "string"}},
                "precio_usd":        {"type": "number"},
                "video_url":         {"type": "string"},
                "categoria_sugerida": {"type": "string"},
            },
            "required": ["marca", "modelo", "descripcion", "specs"],
        },
    }

    def _scrape(url: str, client: "httpx.Client") -> dict | None:
        """Devuelve {extracted, foto_candidates, meta} o None si falló.
        foto_candidates es una lista ordenada de URLs candidatas (LLM primero,
        luego og:image, twitter:image, dedupe).

        Si el URL es de B&H, también solicitamos `rawHtml` para correr el
        dispatcher determinístico (services/equipo_html_extractor.py) que
        cubre TODAS las categorías activas (Cámaras / Lentes / Adaptadores /
        Filtros / Iluminación). Si el parser detecta ≥3 specs canónicos, su
        resultado OVERRIDE marca/modelo/specs/keywords/foto del LLM extract.
        Si no detecta nada (parser falla o categoría desconocida), se
        mantiene el flujo LLM intacto como fallback.
        """
        try:
            # rawHtml es necesario para correr iluminacion_parser sobre el HTML
            # completo (JSON-LD structured data). Mismo costo de scrape.
            rs = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers_fc,
                json={
                    "url": url,
                    "formats": ["markdown", "rawHtml", json_format],
                    "onlyMainContent": False,  # JSON-LD vive fuera de mainContent
                },
            )
        except httpx.HTTPError:
            return None
        if rs.status_code == 402:
            raise HTTPException(402, "Sin créditos de Firecrawl. Recargá tu plan.")
        if rs.status_code == 429:
            raise HTTPException(429, "Rate-limit de Firecrawl. Probá en un minuto.")
        if rs.status_code != 200:
            return None
        sj = rs.json()
        sd = sj.get("data") or sj
        meta      = sd.get("metadata") or {}
        extracted = sd.get("json") or {}
        raw_html  = sd.get("rawHtml") or sd.get("html") or ""

        # ── Intento de mejora con parser determinístico ───────────────────
        # Si tenemos rawHtml, intentamos correr el parser del seed. Si
        # detecta >=3 specs de iluminación, overridamos los campos clave del
        # extracted con la versión normalizada (calidad seed). Esto cierra
        # la brecha entre URL-based autocompletar y HTML upload.
        if raw_html and len(raw_html) > 5000:
            try:
                # Dispatcher por categoría (cámaras/lentes/adaptadores/filtros/iluminación)
                from services.equipo_html_extractor import extract_from_html
                parser_result = extract_from_html(raw_html)
                if parser_result and len(parser_result.get("specs", [])) >= 3:
                    # Override fields con calidad seed (incluye keywords canónicas)
                    if parser_result.get("marca"):
                        extracted["marca"] = parser_result["marca"]
                    if parser_result.get("modelo"):
                        extracted["modelo"] = parser_result["modelo"]
                    if parser_result.get("specs"):
                        extracted["specs"] = parser_result["specs"]
                    # Keywords canónicas (override del LLM-output)
                    if parser_result.get("keywords"):
                        extracted["keywords"] = parser_result["keywords"]
                    if parser_result.get("foto_url"):
                        foto = parser_result["foto_url"]
                        existing_fotos = extracted.get("foto_urls") or []
                        if foto not in existing_fotos:
                            extracted["foto_urls"] = [foto] + existing_fotos
                    # Ficha extendida del parser
                    for k in ("peso", "dimensiones", "alimentacion", "incluye", "montura", "formato", "resolucion"):
                        v = parser_result.get(k)
                        if v and not extracted.get(k):
                            extracted[k] = v
                    extracted["_parser_source"] = parser_result.get("enriquecido_fuente", "equipo_html_extractor")
            except Exception as e:
                logger.warning("equipo_html_extractor falló sobre rawHtml de %s: %s", url, e)
                # Silenciosamente seguimos con el extracted LLM
                pass

        # Candidatos: LLM (array) primero (mejor ranking), después meta tags
        candidates: list[str] = []
        seen_lower: set[str] = set()

        def _push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            key = u.lower()
            if key in seen_lower:
                return
            seen_lower.add(key)
            candidates.append(u)

        # 1. LLM array (foto_urls) — orden de relevancia ya viene de la IA
        for u in (extracted.get("foto_urls") or []):
            _push(u)
        # 2. Backwards-compat: si vino foto_url scalar (esquema viejo)
        _push(extracted.get("foto_url"))
        # 3. Meta tags
        _push(meta.get("ogImage") or meta.get("og:image"))
        _push(meta.get("twitterImage") or meta.get("twitter:image"))

        return {
            "extracted": extracted,
            "foto_candidates": candidates[:MAX_PHOTO_CANDIDATES_PER_SCRAPE],
            "meta": meta,
            "source_url": url,   # URL original scrapeada (para trazabilidad)
        }

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            # Modo URL directa: scrape de esa página, sin búsqueda.
            # Si la URL es de B&H la tratamos como bh_top, sino como alt_top
            # (esto sólo afecta dónde queda el canonical_url y el labelling).
            from urllib.parse import urlparse as _up
            host = (_up(direct_url).hostname or "").lower()
            top_entry = {"url": direct_url, "title": direct_url}
            if "bhphotovideo" in host:
                bh_top, alt_top = top_entry, None
                bh_scrape, alt_scrape = _scrape(direct_url, client), None
            else:
                bh_top, alt_top = None, top_entry
                bh_scrape, alt_scrape = None, _scrape(direct_url, client)

            if bh_scrape is None and alt_scrape is None:
                raise HTTPException(422, "No se pudo scrapear la URL")
        else:
            # Etapa A: B&H (canónico para bh_url)
            bh_results = _search(f"{query} site:bhphotovideo.com", client)
            bh_top = _first_valid(bh_results)

            # Etapa B: sitios oficiales del fabricante
            alt_results = _search(f"{query} ({OFFICIAL_SITES})", client)
            alt_top = _first_valid(alt_results)

            # Etapa C: Adorama / Amazon (último recurso)
            if not alt_top:
                adoram_results = _search(f"{query} site:adorama.com OR site:amazon.com", client)
                alt_top = _first_valid(adoram_results)

            if not bh_top and not alt_top:
                raise HTTPException(404, "No se encontraron resultados en internet")

            bh_scrape  = _scrape(bh_top["url"], client) if bh_top else None
            alt_scrape = None
            # Sólo scrapeamos alternativa si B&H no aportó datos o foto
            needs_alt = (
                alt_top is not None and (
                    bh_scrape is None
                    or not bh_scrape.get("foto_candidates")
                    or not (bh_scrape.get("extracted") or {}).get("descripcion")
                )
            )
            if needs_alt:
                alt_scrape = _scrape(alt_top["url"], client)

    # ── Merge B&H + alt (B&H pisa, alt rellena gaps) ────────────────────────
    primary = bh_scrape or alt_scrape or {}
    secondary = alt_scrape if bh_scrape else None
    extracted = dict(primary.get("extracted") or {})
    _MERGE_KEYS = (
        "descripcion", "specs", "keywords", "marca", "modelo", "nombre_normalizado",
        "peso", "dimensiones", "montura", "formato", "resolucion", "alimentacion",
        "incluye", "conectividad", "compatible_con", "precio_usd", "video_url",
        "categoria_sugerida",
    )
    if secondary:
        sec_ext = secondary.get("extracted") or {}
        for k in _MERGE_KEYS:
            if not extracted.get(k):
                extracted[k] = sec_ext.get(k)

    # `not {}` es True, pero `not {"a": None}` es False — necesitamos también
    # rechazar dicts donde todos los valores son falsy/vacíos (caso real:
    # Firecrawl devuelve el schema con todas las keys pero todas en None).
    if not extracted or not any(extracted.values()):
        raise HTTPException(422, "No se pudo extraer información estructurada")

    # ── Validación de foto: HEAD/GET parcial antes de devolver ──────────────
    def _validate_image(url: str | None) -> tuple[bool, str]:
        """Devuelve (ok, motivo). motivo es '' si ok=True."""
        if not url:
            return False, "sin candidata"
        if not url.lower().startswith(("http://", "https://")):
            return False, "URL no absoluta"
        from urllib.parse import urlparse as _up
        host = (_up(url).hostname or "").lower()
        ref = f"https://{host}/" if host else None
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if ref:
            hdrs["Referer"] = ref
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as c:
                # HEAD primero
                try:
                    rh = c.head(url, headers=hdrs)
                    if rh.status_code == 200:
                        ct = rh.headers.get("content-type", "")
                        cl = int(rh.headers.get("content-length", "0") or "0")
                        if ct.startswith("image/") and (cl == 0 or cl > 1024):
                            return True, ""
                        if not ct.startswith("image/"):
                            return False, f"content-type {ct or 'desconocido'}"
                        if cl and cl <= 1024:
                            return False, "imagen muy chica (<1KB)"
                except httpx.HTTPError:
                    pass
                # GET con Range como fallback (HEAD a veces no está soportado)
                hdrs["Range"] = "bytes=0-2048"
                rg = c.get(url, headers=hdrs)
                if rg.status_code in (200, 206):
                    ct = rg.headers.get("content-type", "")
                    if ct.startswith("image/"):
                        return True, ""
                    return False, f"content-type {ct or 'desconocido'}"
                return False, f"HTTP {rg.status_code} en origen"
        except httpx.HTTPError as e:
            return False, f"error de red: {type(e).__name__}"

    # Juntar todos los candidatos: B&H primero, después alt (sin dedupe-cross,
    # se dedupe cuando los unimos)
    bh_cands  = (bh_scrape or {}).get("foto_candidates") or []
    alt_cands = (alt_scrape or {}).get("foto_candidates") or []

    # Si alt no se scrapeó pero existe URL, scrape ahora para sumar candidatos
    if not alt_scrape and alt_top:
        try:
            with httpx.Client(timeout=45.0) as c2:
                alt_scrape = _scrape(alt_top["url"], c2)
            alt_cands = (alt_scrape or {}).get("foto_candidates") or []
        except Exception:
            pass

    all_candidates: list[str] = []
    seen_lc: set[str] = set()
    for u in (bh_cands + alt_cands):
        k = u.lower()
        if k in seen_lc:
            continue
        seen_lc.add(k)
        all_candidates.append(u)

    # Validar cada candidato (HEAD/GET); guardar los que pasen + motivo de los que no
    foto_validas: list[str] = []
    foto_invalidas: list[dict] = []
    for u in all_candidates[:MAX_PHOTO_CANDIDATES_TO_VALIDATE]:
        ok, motivo = _validate_image(u)
        if ok:
            foto_validas.append(u)
        else:
            foto_invalidas.append({"url": u, "motivo": motivo})

    foto_url = foto_validas[0] if foto_validas else None
    fuente_foto_url = (bh_top or alt_top or {}).get("url") if foto_url else None
    foto_motivo = ""
    if not foto_url:
        if foto_invalidas:
            foto_motivo = " | ".join(f"{(d['motivo'] or 'inválida')}" for d in foto_invalidas[:3])
        else:
            foto_motivo = "no se encontró imagen en ninguna fuente"

    # bh_url canónico = el de B&H si hubo, sino el alternativo (como referencia)
    canonical_url = (bh_top or alt_top)["url"]
    canonical_title = (bh_top or alt_top).get("title") or canonical_url

    # Sanitizar keywords: lowercase, trim, dedupe, max 6
    raw_kws = extracted.get("keywords") or []
    seen_kw: set[str] = set()
    keywords: list[str] = []
    for k in raw_kws:
        if not isinstance(k, str):
            continue
        kk = k.strip().lower()
        if not kk or kk in seen_kw or len(kk) > 40:
            continue
        seen_kw.add(kk)
        keywords.append(kk)
        if len(keywords) >= 6:
            break

    # ── Sanitización de listas de strings ──────────────────────────────────
    def _clean_str_list(raw, max_items: int = 12, max_len: int = 80) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        if not isinstance(raw, list):
            return out
        for v in raw:
            if not isinstance(v, str):
                continue
            s = v.strip()
            if not s or len(s) > max_len or s.lower() in seen:
                continue
            seen.add(s.lower())
            out.append(s)
            if len(out) >= max_items:
                break
        return out

    incluye        = _clean_str_list(extracted.get("incluye"),        max_items=15)
    conectividad   = _clean_str_list(extracted.get("conectividad"),   max_items=10)
    compatible_con = _clean_str_list(extracted.get("compatible_con"), max_items=8)

    # video_url: validar http(s), nada de javascript: ni rutas relativas
    video_url = extracted.get("video_url")
    if isinstance(video_url, str) and not video_url.lower().startswith(("http://", "https://")):
        video_url = None

    # precio_usd: aceptar número o string numérico, sino None
    precio_bh_usd = None
    raw_precio = extracted.get("precio_usd")
    if isinstance(raw_precio, (int, float)) and raw_precio > 0:
        precio_bh_usd = float(raw_precio)
    elif isinstance(raw_precio, str):
        try:
            v = float(raw_precio.replace(",", "").replace("$", "").strip())
            if v > 0:
                precio_bh_usd = v
        except ValueError:
            pass

    # Trazabilidad: distinguir de qué tipo de fuente vino la data ayuda a
    # debuggear "¿por qué este equipo tiene esta info rara?". Antes era
    # genérico ("firecrawl" para todo lo no-B&H), ahora distinguimos
    # bh / adorama / amazon / manufacturer / generic.
    def _fuente_for(scrape: dict | None) -> str | None:
        if not scrape:
            return None
        from urllib.parse import urlparse as _up
        url = scrape.get("source_url") or (scrape.get("meta") or {}).get("sourceURL") or ""
        host = (_up(url).hostname or "").lower()
        if "bhphotovideo.com" in host:
            return "firecrawl-bh"
        if "adorama.com" in host:
            return "firecrawl-adorama"
        if "amazon." in host:
            return "firecrawl-amazon"
        if host:
            return "firecrawl-manufacturer"
        return "firecrawl"

    fuente_de_enriquecimiento = (
        _fuente_for(bh_scrape) or _fuente_for(alt_scrape) or "firecrawl"
    )

    return {
        "marca":  (extracted.get("marca")  or payload.marca  or "").strip() or None,
        "modelo": (extracted.get("modelo") or payload.modelo or "").strip() or None,
        "nombre_normalizado": (extracted.get("nombre_normalizado") or payload.nombre or "").strip() or None,
        "descripcion": (extracted.get("descripcion") or "").strip(),
        # Specs normalizados: labels en español + unidades métricas (#209).
        # Idempotente: si ya vinieron en español/métrico no toca nada.
        "specs": normalize_specs((extracted.get("specs") or [])[:12]),
        "keywords": keywords,
        "foto_url": foto_url,
        "foto_candidates": foto_validas,  # todas las URLs válidas (la primera es la elegida por defecto)
        # Ficha técnica extendida — peso/dimensiones también se pasan por el
        # conversor de unidades (sin traducir label, ya están en español).
        "peso":           _convert_units_in_value((extracted.get("peso") or "").strip()) or None,
        "dimensiones":    _convert_units_in_value((extracted.get("dimensiones") or "").strip()) or None,
        "montura":        (extracted.get("montura") or "").strip() or None,
        "formato":        (extracted.get("formato") or "").strip() or None,
        "resolucion":     (extracted.get("resolucion") or "").strip() or None,
        "alimentacion":   (extracted.get("alimentacion") or "").strip() or None,
        "incluye":        incluye,
        "conectividad":   conectividad,
        "compatible_con": compatible_con,
        "video_url":      video_url,
        "precio_bh_usd":  precio_bh_usd,
        "categoria_sugerida": (extracted.get("categoria_sugerida") or "").strip() or None,
        # Trazabilidad
        "fuente_url":      canonical_url,
        "fuente_titulo":   canonical_title,
        "fuente_foto_url": fuente_foto_url,
        "foto_motivo":     foto_motivo or None,
        "enriquecido_fuente": fuente_de_enriquecimiento,
        # Raw para guardar tal cual (preserva todo lo que la IA devolvió)
        "raw": extracted,
    }


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


# ── Admin: aplicar resultado de enriquecimiento en una sola llamada ──────────
#
# El frontend manda el preview (parcial o completo) + flags "apply_*" para
# decidir qué piezas grabar. Esto evita N round-trips PATCH equipo + PUT ficha.

class AplicarEnriquecimientoInput(BaseModel):
    # Núcleo equipo
    marca:    Optional[str]   = None
    modelo:   Optional[str]   = None
    foto_url: Optional[str]   = None
    bh_url:   Optional[str]   = None
    # Ficha
    descripcion:   Optional[str] = None
    specs:         Optional[list[dict]] = None
    keywords:      Optional[list[str]]  = None
    peso:          Optional[str]   = None
    dimensiones:   Optional[str]   = None
    montura:       Optional[str]   = None
    formato:       Optional[str]   = None
    resolucion:    Optional[str]   = None
    alimentacion:  Optional[str]   = None
    incluye:        Optional[list[str]] = None
    conectividad:   Optional[list[str]] = None
    compatible_con: Optional[list[str]] = None
    video_url:     Optional[str]   = None
    precio_bh_usd: Optional[float] = None
    fuente_url:    Optional[str]   = None
    fuente_titulo: Optional[str]   = None
    raw:           Optional[dict]  = None
    enriquecido_fuente: Optional[str] = None


# ── Matching estructurado de specs entrantes ──────────────────────────
#
# El autocompletar trae specs como dict {label: value}. Para conectarlas
# al sistema estructurado (equipo_specs con spec_def_id) tenemos que:
#   1. Resolver cada label al spec_def_id correcto (case-insensitive,
#      ignorando espacios y prefijos como "(en mm)").
#   2. Solo aplicar las specs ASIGNADAS a las categorías del equipo.
#   3. Para los labels que no matchean nada asignado, generar propuestas
#      en spec_propuestas_pendientes (assign_spec si la spec global
#      existe, spec_nueva si no).

def _normalize_label(s: str) -> str:
    """Para matching: lowercase, sin espacios extra, sin paréntesis finales."""
    import re
    s = s.lower().strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)   # "Peso (g)" → "peso"
    s = re.sub(r"\s+", " ", s)
    return s


def _matchear_y_persistir_specs(
    conn,
    equipo_id: int,
    specs_entrantes: dict,
    *,
    crear_propuestas: bool = True,
) -> dict:
    """Mapea {label: value} entrantes a spec_def_id del equipo y persiste:
       - Matches con specs asignadas → INSERT en equipo_specs.
       - No-matches → propuestas en spec_propuestas_pendientes.

    Retorna {aplicadas: [{label, spec_def_id, value}], propuestas: [...],
             saltadas: [{label, motivo}]}.
    """
    import json as _json

    if not specs_entrantes:
        return {"aplicadas": [], "propuestas": [], "saltadas": []}

    # 1. Cargar specs asignadas al equipo (vía sus categorías + ancestros).
    rows_asignadas = conn.execute(
        """
        WITH RECURSIVE chain AS (
            SELECT c.id, c.parent_id
            FROM equipo_categorias ec JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ?
            UNION
            SELECT c2.id, c2.parent_id FROM categorias c2 JOIN chain ON c2.id = chain.parent_id
        )
        SELECT DISTINCT sd.id, sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.enum_options
        FROM categoria_spec_templates t
        JOIN spec_definitions sd ON sd.id = t.spec_def_id
        WHERE t.categoria_id IN (SELECT id FROM chain)
        """,
        (equipo_id,),
    ).fetchall()

    # Index por label normalizado y spec_key
    index_asignadas: dict[str, dict] = {}
    for r in rows_asignadas:
        rd = row_to_dict(r) if not isinstance(r, dict) else r
        index_asignadas[_normalize_label(rd["label"])] = rd
        index_asignadas[_normalize_label(rd["spec_key"])] = rd

    # 2. Cargar TODAS las specs globales para detectar candidatos a assign_spec.
    all_global = conn.execute(
        "SELECT id, spec_key, label, tipo, unidad, enum_options FROM spec_definitions"
    ).fetchall()
    index_global: dict[str, dict] = {}
    for r in all_global:
        rd = row_to_dict(r) if not isinstance(r, dict) else r
        index_global[_normalize_label(rd["label"])] = rd
        index_global[_normalize_label(rd["spec_key"])] = rd

    # Categoría principal del equipo (para sugerir asignación a esa cat).
    cat_principal = conn.execute(
        "SELECT categoria_id FROM equipo_categorias WHERE equipo_id = ? ORDER BY categoria_id LIMIT 1",
        (equipo_id,),
    ).fetchone()
    cat_principal_id = cat_principal["categoria_id"] if cat_principal else None

    aplicadas: list[dict] = []
    propuestas: list[dict] = []
    saltadas: list[dict] = []

    for raw_label, value in specs_entrantes.items():
        # Skip vacíos / nulls
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        value_str = (
            ", ".join(str(v) for v in value) if isinstance(value, list)
            else str(value).strip()
        )
        if not value_str:
            continue

        norm = _normalize_label(raw_label)
        # Match contra specs asignadas
        match = index_asignadas.get(norm)
        if match:
            try:
                conn.execute(
                    """
                    INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                    VALUES (?, ?, ?)
                    ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
                        SET value = EXCLUDED.value
                    """,
                    (equipo_id, match["id"], value_str),
                )
                aplicadas.append({
                    "label": match["label"],
                    "spec_def_id": match["id"],
                    "value": value_str,
                })
            except Exception as e:
                saltadas.append({"label": raw_label, "motivo": f"error guardando: {e}"})
            continue

        # No matchea asignadas. ¿Existe en el catálogo global?
        if not crear_propuestas:
            saltadas.append({"label": raw_label, "motivo": "no asignada a esta categoría"})
            continue

        global_match = index_global.get(norm)
        if global_match and cat_principal_id:
            # Propuesta: asignar spec existente a la categoría
            payload = {
                "spec_def_id": global_match["id"],
                "spec_key": global_match["spec_key"],
                "categoria_id": cat_principal_id,
                "valor_sugerido": value_str,
                "source_equipo_id": equipo_id,
                "razon": f"detectada por autocompletar en equipo {equipo_id}",
            }
            conn.execute(
                """
                INSERT INTO spec_propuestas_pendientes (tipo, payload, origen, confianza)
                VALUES (?, ?::jsonb, ?, ?)
                """,
                ("assign_spec", json.dumps(payload), f"autocompletar-equipo-{equipo_id}", 0.8),
            )
            propuestas.append({"tipo": "assign_spec", "label": raw_label, "valor": value_str})
        elif cat_principal_id:
            # Propuesta: crear spec nueva
            payload = {
                "spec_key": _slugify(raw_label),
                "label": raw_label,
                "tipo": "string",   # default conservador, el dueño elige al aplicar
                "valor_sugerido": value_str,
                "source_equipo_id": equipo_id,
                "categoria_id_sugerida": cat_principal_id,
                "razon": f"detectada por autocompletar en equipo {equipo_id}, no existe en el catálogo",
            }
            conn.execute(
                """
                INSERT INTO spec_propuestas_pendientes (tipo, payload, origen, confianza)
                VALUES (?, ?::jsonb, ?, ?)
                """,
                ("spec_nueva", json.dumps(payload), f"autocompletar-equipo-{equipo_id}", 0.6),
            )
            propuestas.append({"tipo": "spec_nueva", "label": raw_label, "valor": value_str})
        else:
            saltadas.append({"label": raw_label, "motivo": "equipo sin categoría — no se puede sugerir asignación"})

    return {"aplicadas": aplicadas, "propuestas": propuestas, "saltadas": saltadas}


def _slugify(s: str) -> str:
    import re
    s = s.lower().strip()
    s = re.sub(r"[áéíóúüñ]", lambda m: "aeiouun"[("áéíóúüñ").index(m.group())], s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s[:64] or "spec"


@router.post("/admin/equipos/{id}/aplicar-autocompletado")
def admin_aplicar_autocompletado(id: int, payload: AplicarEnriquecimientoInput, request: Request):
    """Endpoint canónico — alias de /aplicar-enriquecimiento (legacy)."""
    return admin_aplicar_enriquecimiento(id, payload, request)


@router.post("/admin/equipos/{id}/aplicar-enriquecimiento", deprecated=True)
def admin_aplicar_enriquecimiento(id: int, payload: AplicarEnriquecimientoInput, request: Request):
    """
    Toma el resultado del endpoint /enriquecer (parcial o completo) y graba
    en una sola transacción los campos que el cliente decidió aplicar.
    Cualquier campo NO incluido en el body queda como está (no se nullea).
    """
    require_admin(request)

    import json as _json

    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        body = payload.model_dump(exclude_unset=True)

        # ── Equipos (núcleo) ────────────────────────────────────────────
        eq_fields = {}
        for k in ("marca", "modelo", "foto_url", "bh_url"):
            if k in body and body[k] is not None:
                eq_fields[k] = body[k]
        if eq_fields:
            set_clause = ", ".join(f"{k} = ?" for k in eq_fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipos SET {set_clause} WHERE id = ?",
                list(eq_fields.values()) + [id],
            )

        # ── Ficha (asegurar fila) ───────────────────────────────────────
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id) VALUES (?) ON CONFLICT(equipo_id) DO NOTHING",
            (id,),
        )

        # Mapeo: API → columna DB. Listas/dicts → JSON string.
        ficha_fields: dict = {}
        if "descripcion" in body:
            ficha_fields["descripcion"] = body["descripcion"]
        if "specs" in body and body["specs"] is not None:
            ficha_fields["specs_json"] = _json.dumps(body["specs"], ensure_ascii=False)
        if "keywords" in body and body["keywords"] is not None:
            ficha_fields["keywords_json"] = _json.dumps(body["keywords"], ensure_ascii=False)
        if "incluye" in body and body["incluye"] is not None:
            ficha_fields["incluye_json"] = _json.dumps(body["incluye"], ensure_ascii=False)
        if "conectividad" in body and body["conectividad"] is not None:
            ficha_fields["conectividad_json"] = _json.dumps(body["conectividad"], ensure_ascii=False)
        if "compatible_con" in body and body["compatible_con"] is not None:
            ficha_fields["compatible_con_json"] = _json.dumps(body["compatible_con"], ensure_ascii=False)
        for k in ("peso", "dimensiones", "montura", "formato", "resolucion",
                  "alimentacion", "video_url", "precio_bh_usd",
                  "fuente_url", "fuente_titulo", "enriquecido_fuente"):
            if k in body:
                ficha_fields[k] = body[k]
        if "raw" in body and body["raw"] is not None:
            ficha_fields["raw_json"] = _json.dumps(body["raw"], ensure_ascii=False)

        # Si vino algún dato de ficha, marcar enriquecido_at
        if ficha_fields:
            ficha_fields["enriquecido_at"] = datetime.datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in ficha_fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = ?",
                list(ficha_fields.values()) + [id],
            )

        # ── Matching estructurado de specs ──────────────────────────────
        # Las specs que matchean con lo asignado al equipo se cargan en
        # equipo_specs (estructurado). Lo que no matchea genera propuestas
        # en spec_propuestas_pendientes (assign_spec o spec_nueva).
        matching_result = {"aplicadas": [], "propuestas": [], "saltadas": []}
        if "specs" in body and isinstance(body["specs"], dict) and body["specs"]:
            matching_result = _matchear_y_persistir_specs(conn, id, body["specs"])

        conn.commit()

        # Devolver equipo + ficha actualizados + resumen del matching
        eq_row = conn.execute("SELECT * FROM equipos WHERE id = ?", (id,)).fetchone()
        ficha_row = conn.execute("SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)).fetchone()
        return {
            "equipo": row_to_dict(eq_row),
            "ficha":  row_to_dict(ficha_row) if ficha_row else None,
            "specs_matching": {
                "aplicadas": len(matching_result["aplicadas"]),
                "propuestas_creadas": len(matching_result["propuestas"]),
                "saltadas": len(matching_result["saltadas"]),
                "detalle": matching_result,
            },
        }
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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

_ALLOWED_PHOTO_HOSTS = frozenset([
    # Retailers
    "bhphotovideo.com", "adorama.com", "amazon.com", "amazon.ca",
    "amazonaws.com",
    # Wikipedia / commons
    "wikimedia.org", "wikipedia.org",
    # Reviews / press
    "dpreview.com", "fstoppers.com", "petapixel.com", "cinema5d.com",
    # Manufacturer (cámaras, lentes, audio, video, iluminación, soportes)
    "sony.com", "sonycreativesoftware.com",
    "canon.com", "usa.canon.com", "canon-europe.com",
    "nikon.com", "nikonusa.com",
    "fujifilm.com", "fujifilm-x.com",
    "panasonic.com",
    "blackmagicdesign.com", "red.com", "atomos.com",
    "tilta.com", "smallrig.com", "manfrotto.com",
    "saramonic.com", "rode.com", "shure.com", "sennheiser.com",
    "sigmaphoto.com", "tamron.com", "samyangopticsamericas.com",
    "leofoto.com", "godox.com", "aputure.com", "nanlite.com",
    "zhiyun-tech.com", "dji.com", "insta360.com", "gopro.com",
    # CDNs comunes que sirven assets de los hosts de arriba
    "cloudfront.net", "akamaized.net", "akamaihd.net",
    "shopifycdn.com", "wp.com", "googleusercontent.com",
])


def _is_photo_host_allowed(host: str) -> bool:
    """True si `host` es un dominio del allowlist o subdominio de uno."""
    host = (host or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_PHOTO_HOSTS)


def _host_resolves_to_private(host: str) -> bool:
    """True si el host resuelve a alguna IP privada/loopback/link-local/
    multicast/reserved. Defense-in-depth: bloquea el caso (improbable pero
    posible) de un dominio del allowlist apuntando a IPs internas.
    """
    import ipaddress as _ip
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(host, None)
    except (_socket.gaierror, OSError):
        return True   # No resolver → no descargar
    for info in infos:
        addr = info[4][0]
        try:
            ip = _ip.ip_address(addr)
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
                return True
        except ValueError:
            continue
    return False


def _validate_ssrf_only(url: str) -> None:
    """Anti-SSRF sin whitelist de dominios. Usado cuando el admin selecciona
    manualmente una URL (no batch import). Protege contra IPs privadas/loopback
    pero no restringe el dominio."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, f"Puerto no permitido: {port}")
    if _host_resolves_to_private(host):
        raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")


def _validate_external_image_url(url: str) -> None:
    """Anti-SSRF con whitelist de dominios. Eleva HTTPException si la URL no es segura."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, f"Puerto no permitido: {port}")
    if not _is_photo_host_allowed(host):
        raise HTTPException(
            403,
            f"Host no permitido para descarga: {host}. Si es un sitio "
            "legítimo, agregar a _ALLOWED_PHOTO_HOSTS.",
        )
    if _host_resolves_to_private(host):
        raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")


def _download_image_bytes(url: str) -> tuple[bytes, str]:
    """Descarga una imagen externa con todos los fallbacks del proxy
    (Referer del host, sin Referer, Referer=google, weserv).
    Devuelve (bytes, content_type). Eleva HTTPException si no se pudo.

    NOTA: el caller debe haber pasado `url` por `_validate_external_image_url`
    antes (SSRF guard). Acá hacemos una validación final por las dudas.
    """
    import httpx
    from urllib.parse import urlparse, quote

    _validate_external_image_url(url)
    host = (urlparse(url).hostname or "").lower()

    def _headers(referer: str | None) -> dict:
        h = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Cache-Control": "no-cache",
        }
        if referer:
            h["Referer"] = referer
        return h

    referer_map = {
        "bhphotovideo.com": "https://www.bhphotovideo.com/",
        "www.bhphotovideo.com": "https://www.bhphotovideo.com/",
        "adorama.com": "https://www.adorama.com/",
        "www.adorama.com": "https://www.adorama.com/",
    }
    primary_referer = next(
        (v for k, v in referer_map.items() if host.endswith(k)),
        f"https://{host}/",
    )

    last_status = None
    last_body = b""
    r = None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, http2=False, max_redirects=3) as client:
            r = client.get(url, headers=_headers(primary_referer))
            last_status, last_body = r.status_code, r.content
            if r.status_code == 403:
                r2 = client.get(url, headers=_headers(None))
                if r2.status_code == 200:
                    r = r2
                else:
                    last_status, last_body = r2.status_code, r2.content
            if r.status_code == 403:
                r3 = client.get(url, headers=_headers("https://www.google.com/"))
                if r3.status_code == 200:
                    r = r3
                else:
                    last_status, last_body = r3.status_code, r3.content
            if r.status_code in (401, 403, 404, 429) or r.status_code >= 500:
                stripped = url.split("://", 1)[1] if "://" in url else url
                weserv_url = f"https://images.weserv.nl/?url={quote(stripped, safe='')}"
                r4 = client.get(weserv_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/*,*/*;q=0.8",
                })
                if r4.status_code == 200 and r4.headers.get("content-type", "").startswith("image/"):
                    r = r4
                else:
                    last_status, last_body = r4.status_code, r4.content
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo descargar la imagen: {e}")

    if r is None or r.status_code != 200:
        snippet = ""
        try:
            snippet = last_body[:200].decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise HTTPException(
            502,
            f"Origen devolvió {last_status} para host {host}. {snippet}".strip(),
        )

    ctype = r.headers.get("content-type", "image/jpeg")
    if not ctype.startswith("image/"):
        raise HTTPException(415, f"La URL no devolvió una imagen ({ctype})")

    if len(r.content) < 1024:
        raise HTTPException(415, f"Imagen muy chica ({len(r.content)} bytes)")

    return r.content, ctype


def _ext_from_ctype(ct: str) -> str:
    ct = (ct or "").lower()
    if "png" in ct:  return "png"
    if "webp" in ct: return "webp"
    if "avif" in ct: return "avif"
    if "gif" in ct:  return "gif"
    return "jpg"


def _trim_and_square(img, padding_pct: float = 0.06):
    """Recorta bordes (transparentes o casi blancos) y empareja a cuadrado
    con fondo blanco + padding. Sirve para que productos con mucho whitespace
    queden visualmente del mismo tamaño que productos con poco whitespace.

    Args:
        img: PIL.Image (RGB o RGBA)
        padding_pct: porcentaje de padding alrededor del bbox encontrado.
                     0.06 = 6% del lado más largo.
    Returns:
        PIL.Image en modo RGB cuadrado con fondo blanco.
    """
    from PIL import Image, ImageChops

    # 1) Encontrar el bbox del contenido
    if img.mode == "RGBA":
        # Bbox por canal alpha — funciona perfecto con PNG transparente
        bbox = img.split()[-1].getbbox()
        if bbox:
            img = img.crop(bbox)
        img_rgb = Image.new("RGB", img.size, (255, 255, 255))
        img_rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = img_rgb
    else:
        img = img.convert("RGB")
        # Bbox por diferencia con un fondo blanco — captura productos sobre fondo blanco
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        # Reducir ruido (compresión JPEG deja píxeles "casi blancos")
        diff = ImageChops.add(diff, diff, 2.0, -30)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)

    # 2) Hacer cuadrado: pegar centrado en un canvas blanco más grande
    w, h = img.size
    side = max(w, h)
    pad = int(side * padding_pct)
    canvas_side = side + 2 * pad
    canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
    offset = ((canvas_side - w) // 2, (canvas_side - h) // 2)
    canvas.paste(img, offset)
    return canvas


def _optimize_image(content: bytes) -> tuple[bytes, str, int, int]:
    """Optimiza la imagen: auto-orient + trim de bordes + cuadrado con fondo
    blanco + resize a 1200x1200 + WebP q=85. Devuelve (bytes, ct, w, h).
    Si algo falla, devuelve el contenido original como fallback.

    El trim+cuadrado normaliza el tamaño visual de los productos en el grid:
    sin esto, los PNG con mucho whitespace alrededor se ven chicos comparados
    con los que llenan el frame.
    """
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
    except ImportError:
        return content, "image/jpeg", 0, 0

    try:
        img = Image.open(BytesIO(content))
        img = ImageOps.exif_transpose(img)  # auto-orient

        # Normalizar a RGBA o RGB según corresponda (preservamos transparencia en PNG)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        # Trim + cuadrado con fondo blanco (#8 — tamaños inconsistentes)
        try:
            img = _trim_and_square(img, padding_pct=0.06)
        except Exception as e:
            logger.warning("optimize_image: trim_and_square falló, sigo sin trim: %s", e)

        # Resize a 1200x1200 (cuadrado) si excede
        TARGET_SIDE = 1200
        if img.width > TARGET_SIDE:
            img = img.resize((TARGET_SIDE, TARGET_SIDE), Image.Resampling.LANCZOS)

        out = BytesIO()
        img.save(out, format="WEBP", quality=85, method=6)
        return out.getvalue(), "image/webp", img.width, img.height
    except Exception as e:
        logger.warning("optimize_image: fallback (no se pudo optimizar): %s", e, exc_info=True)
        return content, "image/jpeg", 0, 0


def _r2_config() -> dict:
    """Lee la configuración de Cloudflare R2 desde env. Eleva 500 si falta algo."""
    import os
    cfg = {
        "account_id":      os.getenv("R2_ACCOUNT_ID") or "",
        "access_key_id":   os.getenv("R2_ACCESS_KEY_ID") or "",
        "secret_key":      os.getenv("R2_SECRET_ACCESS_KEY") or "",
        "bucket":          os.getenv("R2_BUCKET") or "equipos-fotos",
        "public_base":     (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/"),
    }
    missing = [k for k in ("account_id", "access_key_id", "secret_key") if not cfg[k]]
    if missing:
        raise HTTPException(
            500,
            f"R2 no configurado: faltan env vars {', '.join('R2_'+m.upper() for m in missing)}. "
            "Configurá en Railway: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
            "R2_BUCKET, R2_PUBLIC_BASE.",
        )
    if not cfg["public_base"]:
        # Default al endpoint público de R2 (sin custom domain) — válido si activaste public bucket
        cfg["public_base"] = f"https://pub-{cfg['account_id']}.r2.dev"
    return cfg


# Cliente boto3 singleton: crearlo cuesta ~50ms (parse config, init session,
# resolver endpoint) y antes lo creabamos en cada upload. Con singleton, el
# costo es one-time. Cacheamos la tupla (config, client) y la invalidamos
# si cambia la config (ej. rotación de credenciales en runtime).
_r2_client_cache: tuple[tuple, object] | None = None


def _get_r2_client(cfg: dict) -> object:
    """Devuelve un cliente boto3 reutilizable para el bucket R2."""
    global _r2_client_cache
    cfg_key = (cfg["account_id"], cfg["access_key_id"], cfg["secret_key"])
    if _r2_client_cache is not None and _r2_client_cache[0] == cfg_key:
        return _r2_client_cache[1]
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise HTTPException(500, "boto3 no instalado en el backend")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )
    _r2_client_cache = (cfg_key, client)
    return client


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


def _upload_to_r2(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket R2 vía S3 API (boto3). Devuelve la URL pública."""
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    try:
        client.put_object(
            Bucket=cfg["bucket"],
            Key=path,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        raise HTTPException(502, f"R2 upload falló: {e}")

    return f"{cfg['public_base']}/{path}"


def _upload_to_supabase_storage(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket equipos-fotos vía REST API usando service role.
    Devuelve la URL pública. Eleva HTTPException si falla.
    """
    import os
    import httpx

    base = (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_PROJECT_URL")
        or "https://ytujjqoffcdsdowfqaex.supabase.co"
    ).rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        raise HTTPException(
            500,
            "Falta SUPABASE_SERVICE_ROLE_KEY en el backend. "
            "Configurala como env var en Railway.",
        )

    bucket = "equipos-fotos"
    upload_url = f"{base}/storage/v1/object/{bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": content_type,
        "x-upsert": "false",
        "Cache-Control": "3600",
    }
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo subir a Storage: {e}")

    if r.status_code not in (200, 201):
        snippet = (r.text or "")[:300]
        raise HTTPException(
            r.status_code if r.status_code >= 400 else 502,
            f"Storage devolvió {r.status_code}: {snippet}",
        )

    return f"{base}/storage/v1/object/public/{bucket}/{path}"


class UploadFotoFromUrlInput(BaseModel):
    url: str
    bypass_whitelist: bool = False


@router.post("/admin/equipos/{equipo_id}/upload-foto-from-url")
def admin_upload_foto_from_url(
    equipo_id: int,
    payload: UploadFotoFromUrlInput,
    request: Request,
):
    """Descarga imagen externa, la optimiza (resize + WebP) y la sube a Cloudflare R2.
    Devuelve {public_url, path, size, content_type}.

    Reemplaza el upload directo desde el browser y el storage de Supabase.
    """
    require_admin(request)

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    # Si ya es una URL del propio bucket R2 (público), no rehospedamos
    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        return {"public_url": url, "path": None, "skipped": True}

    # SSRF guard: validar host antes de descargar.
    if payload.bypass_whitelist:
        _validate_ssrf_only(url)
    else:
        _validate_external_image_url(url)

    raw_content, raw_ctype = _download_image_bytes(url)
    # Optimización: resize a max 1600px + WebP q=85
    content, ctype, w, h = _optimize_image(raw_content)
    ext = _ext_from_ctype(ctype)

    path = _foto_path(equipo_id, ext)
    public_url = _upload_to_r2(path, content, ctype)

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


# ── Admin: subir bytes de un archivo (multipart) directo a R2 ─────────────

@router.post("/admin/equipos/{equipo_id}/upload-foto")
async def admin_upload_foto_file(
    equipo_id: int,
    request: Request,
):
    """Sube un archivo (multipart/form-data, campo `file`) a R2 después de
    optimizarlo. Devuelve {public_url, path, ...}.
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

    content, ctype, w, h = _optimize_image(raw_content)
    ext = _ext_from_ctype(ctype)

    path = _foto_path(equipo_id, ext)
    public_url = _upload_to_r2(path, content, ctype)

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


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


# ── Admin: migración de paths R2 al nuevo esquema {id}_{slug}/ ───────────────

@router.post("/admin/storage/migrate-paths")
def admin_migrate_storage_paths(request: Request, dry_run: bool = True):
    """Renombra todos los objetos R2 que están bajo el prefijo 'equipos/'
    al nuevo esquema {id}_{slug}/{id}_{slug}.ext.
    Con dry_run=true (default) solo lista los cambios sin aplicarlos.
    Llamar con ?dry_run=false para ejecutar la migración real."""
    require_admin(request)

    cfg    = _r2_config()
    client = _get_r2_client(cfg)
    bucket = cfg["bucket"]
    public_base = cfg["public_base"]

    # 1. Cargar todos los equipos para construir el mapa id → slug
    conn = get_db()
    try:
        equipo_rows = conn.execute("SELECT id, nombre FROM equipos").fetchall()
    finally:
        conn.close()

    def _make_slug(nombre: str) -> str:
        s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]

    equipo_slugs: dict[int, str] = {}
    for row in equipo_rows:
        eid, nombre = int(row[0]), row[1] or ""
        equipo_slugs[eid] = _make_slug(nombre) if nombre else ""

    # 2. Listar objetos con prefix equipos/ (paginado)
    old_keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="equipos/"):
        for obj in page.get("Contents", []):
            old_keys.append(obj["Key"])

    # 3. Calcular nuevos paths
    renames: list[dict] = []
    skipped: list[str] = []
    for old_key in old_keys:
        parts = old_key.split("/")
        if len(parts) < 3:
            skipped.append(old_key)
            continue
        try:
            equipo_id = int(parts[1])
        except ValueError:
            skipped.append(old_key)
            continue
        filename = parts[-1]
        m = re.search(r"\.([a-z0-9]+)$", filename, re.IGNORECASE)
        if not m:
            skipped.append(old_key)
            continue
        ext  = m.group(1).lower()
        slug = equipo_slugs.get(equipo_id, "")
        if slug:
            new_key = f"equipos/{equipo_id}_{slug}/{equipo_id}_{slug}.{ext}"
        else:
            new_key = f"equipos/{equipo_id}/{equipo_id}.{ext}"
        if old_key == new_key:
            continue
        renames.append({
            "equipo_id": equipo_id,
            "old": old_key,
            "new": new_key,
            "old_url": f"{public_base}/{old_key}",
            "new_url": f"{public_base}/{new_key}",
        })

    if dry_run:
        return {
            "dry_run":  True,
            "to_rename": len(renames),
            "skipped":  len(skipped),
            "detail":   renames,
        }

    # 4. Ejecutar copias + actualizaciones + borrado
    moved:      list[dict] = []
    db_updated: list[dict] = []
    errors:     list[dict] = []

    _CT_MAP = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg",
               "png": "image/png", "avif": "image/avif", "gif": "image/gif"}

    for r in renames:
        ext_new = r["new"].rsplit(".", 1)[-1].lower()
        ctype   = _CT_MAP.get(ext_new, "image/webp")
        try:
            client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": r["old"]},
                Key=r["new"],
                CacheControl="public, max-age=31536000, immutable",
                MetadataDirective="REPLACE",
                ContentType=ctype,
            )
        except Exception as e:
            errors.append({"key": r["old"], "stage": "copy", "error": str(e)})
            continue

        # Actualizar foto en DB si coincide con la URL vieja
        try:
            db_conn = get_db()
            try:
                db_conn.execute(
                    "UPDATE equipos SET foto = %s WHERE id = %s AND foto = %s",
                    (r["new_url"], r["equipo_id"], r["old_url"]),
                )
                db_conn.commit()
                db_updated.append({"equipo_id": r["equipo_id"], "new_url": r["new_url"]})
            finally:
                db_conn.close()
        except Exception as e:
            errors.append({"key": r["old"], "stage": "db_update", "error": str(e)})

        try:
            client.delete_object(Bucket=bucket, Key=r["old"])
            moved.append({"old": r["old"], "new": r["new"]})
        except Exception as e:
            errors.append({"key": r["old"], "stage": "delete", "error": str(e)})

    return {
        "dry_run":   False,
        "moved":     len(moved),
        "db_updated": len(db_updated),
        "errors":    len(errors),
        "error_detail": errors,
    }
