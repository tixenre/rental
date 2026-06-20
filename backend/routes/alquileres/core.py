"""routes/alquileres/core.py — spine del paquete de alquileres (#501).

El `router` compartido + los modelos del pedido + los helpers reusables
(`create_pedido`, `_apply_pedido_*`, enriquecimiento, recálculo de total). Las
superficies HTTP (pedidos CRUD, cotización, disponibilidad, pagos, documentos,
descuentos) viven en submódulos que registran sus rutas sobre este router.
"""

import datetime
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from database import get_db, row_to_dict, to_datetime, to_iso, now_ar, MARCA_SUBQUERY, marca_subquery
from routes.clientes import nombre_completo_cliente
from services.email import send_email, Attachment
from services.email.service import get_admin_to
from services.ical import build_vcalendar, google_calendar_url, reserva_to_vevent
from services.precios import bruto_linea, calcular_total, jornadas_periodo
from config import SITE_URL

# Motor de reservas: la fuente única vive en el paquete `reservas`. Acá se
# importan solo los nombres que este módulo usa internamente (las transiciones
# de estado validan con `validar_stock`). `ESTADOS_RESERVADO` se re-exporta
# porque es la constante canónica del dominio. El resto de las primitivas se
# importan directo de `reservas` donde se usan (routes.estudio,
# routes.cliente_portal, routes.alquileres.disponibilidad). Ver issue #501, Fase 1.
from reservas import (
    ESTADOS_RESERVADO,  # noqa: F401 — re-export canónico (guard: test_reservas_sql_safety)
    validar_stock as _check_stock,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ESTADOS_VALIDOS    = {"borrador", "presupuesto", "confirmado", "retirado", "devuelto", "finalizado", "cancelado"}


def _es_historico(fuente: str | None) -> bool:
    """Pedidos historicos (importados) no validan fechas ni stock.

    Soporta `historico` y prefijos tipo `<sistema>-historico` (ej.
    `booqable-historico` que generan los converters de migracion). Asi un
    converter futuro puede usar su propio prefijo sin tocar el backend.
    """
    return bool(fuente) and fuente.endswith("historico")


# ── Helpers internos ─────────────────────────────────────────────────────────

def _maybe_finalizar(conn, pedido_id: int):
    """Si el pedido está 'devuelto' y monto_pagado >= monto_total → 'finalizado'."""
    p = conn.execute(
        "SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=?", (pedido_id,)
    ).fetchone()
    if not p:
        return
    if (p["estado"] == "devuelto"
            and (p["monto_pagado"] or 0) >= (p["monto_total"] or 0)
            and (p["monto_total"] or 0) > 0):
        conn.execute("UPDATE alquileres SET estado='finalizado' WHERE id=?", (pedido_id,))


def _get_alquiler_items(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute(f"""
        SELECT pi.*, COALESCE(e.nombre, pi.nombre_libre) AS nombre,
               {MARCA_SUBQUERY},
               e.modelo, e.serie, e.valor_reposicion,
               e.foto_url, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo,
               ef.contenido_incluido_json
        FROM alquiler_items pi
        LEFT JOIN equipos e ON e.id = pi.equipo_id
        LEFT JOIN equipo_fichas ef ON ef.equipo_id = e.id
        WHERE pi.pedido_id = ?
        ORDER BY pi.orden, pi.id
    """, (pedido_id,)).fetchall()
    items = [row_to_dict(r) for r in rows]
    if not items:
        return items

    # Batch fetch de componentes de kits: 1 query agregada en lugar de N+1
    # (antes hacía 1 query por cada item del pedido). Para pedidos con 10
    # items con kits, baja de 11 queries a 2. Las líneas personalizadas (#805)
    # no tienen equipo → se excluyen del set (equipo_id None).
    equipo_ids = list({item["equipo_id"] for item in items if item["equipo_id"] is not None})
    for item in items:
        item.setdefault("componentes", [])
    if not equipo_ids:
        return items
    placeholders = ",".join("?" for _ in equipo_ids)
    comp_rows = conn.execute(f"""
        SELECT kc.*, ec.nombre, {marca_subquery('ec')}, ec.foto_url, ec.cantidad AS stock_total,
               ec.modelo, ec.serie, ec.valor_reposicion,
               ec.nombre_publico, ec.nombre_publico_largo
        FROM kit_componentes kc
        JOIN equipos ec ON ec.id = kc.componente_id
        WHERE kc.equipo_id IN ({placeholders})
    """, equipo_ids).fetchall()
    # Group by equipo_id
    componentes_por_equipo: dict[int, list[dict]] = {}
    for c in comp_rows:
        d = row_to_dict(c)
        componentes_por_equipo.setdefault(d["equipo_id"], []).append(d)
    for item in items:
        item["componentes"] = componentes_por_equipo.get(item["equipo_id"], [])

    return items


def _next_numero_pedido(conn) -> int:
    """Devuelve el próximo número de pedido usando una SEQUENCE de PostgreSQL (race-free)."""
    return conn.execute("SELECT nextval('numero_pedido_seq')").fetchone()[0]


def _get_descuento_jornadas(conn, jornadas: int) -> float:
    """Interpolación lineal entre los puntos ancla de descuentos_jornada.

    Con puntos (1, 0%), (2, 3%), (7, 10%):
      - 4 jornadas → interpola entre (2,3%) y (7,10%) → 5.8%
      - 7+ jornadas → 10% (se queda en el último punto)
    """
    rows = conn.execute(
        "SELECT jornadas, pct FROM descuentos_jornada ORDER BY jornadas ASC"
    ).fetchall()
    if not rows:
        return 0.0
    # `pct` es NUMERIC en la DB (migración g1a2b3c4d5e6) → psycopg lo devuelve
    # como Decimal. Se coerce a float acá para que la interpolación
    # (`t * (p1 - p0)` con t float) no rompa con `float * Decimal` → TypeError
    # → cotizar 500 → totales en $0. Pasaba en alquileres de jornadas
    # intermedias (las que interpolan entre puntos ancla).
    puntos = [(int(r["jornadas"]), float(r["pct"])) for r in rows]
    if jornadas <= puntos[0][0]:
        return float(puntos[0][1])
    if jornadas >= puntos[-1][0]:
        return float(puntos[-1][1])
    for i in range(len(puntos) - 1):
        j0, p0 = puntos[i]
        j1, p1 = puntos[i + 1]
        if j0 <= jornadas <= j1:
            t = (jornadas - j0) / (j1 - j0)
            return round(p0 + t * (p1 - p0), 2)
    return 0.0


def _batch_get_alquiler_items(conn, pedido_ids: list[int]) -> dict[int, list[dict]]:
    """Trae items de múltiples pedidos en 2 queries en lugar de N+1.

    Retorna {pedido_id: [items...]} donde cada item ya tiene su lista 'componentes'.
    """
    if not pedido_ids:
        return {}

    ph = ",".join(["?"] * len(pedido_ids))
    rows = conn.execute(f"""
        SELECT pi.*, COALESCE(e.nombre, pi.nombre_libre) AS nombre,
               {MARCA_SUBQUERY},
               e.modelo, e.serie, e.valor_reposicion,
               e.foto_url, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo
        FROM alquiler_items pi
        LEFT JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id IN ({ph})
        ORDER BY pi.orden, pi.id
    """, pedido_ids).fetchall()

    all_items   = [row_to_dict(r) for r in rows]
    # Las líneas personalizadas (#805) no tienen equipo → fuera del set de kits.
    equipo_ids  = list({item["equipo_id"] for item in all_items if item["equipo_id"] is not None})
    comp_map: dict[int, list[dict]] = {eid: [] for eid in equipo_ids}

    if equipo_ids:
        cph = ",".join(["?"] * len(equipo_ids))
        comp_rows = conn.execute(f"""
            SELECT kc.*, ec.nombre, {marca_subquery('ec')}, ec.foto_url, ec.cantidad AS stock_total,
                   ec.modelo, ec.serie, ec.valor_reposicion,
                   ec.nombre_publico, ec.nombre_publico_largo
            FROM kit_componentes kc
            JOIN equipos ec ON ec.id = kc.componente_id
            WHERE kc.equipo_id IN ({cph})
        """, equipo_ids).fetchall()
        for c in comp_rows:
            cd = row_to_dict(c)
            comp_map[cd["equipo_id"]].append(cd)

    result: dict[int, list[dict]] = {pid: [] for pid in pedido_ids}
    for item in all_items:
        item["componentes"] = comp_map.get(item["equipo_id"], [])
        result[item["pedido_id"]].append(item)

    return result


def _get_alquiler_pagos(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM alquiler_pagos WHERE pedido_id = ? ORDER BY fecha, created_at
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def _get_alquiler_detail(conn, id: int) -> dict:
    row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Pedido no encontrado")
    pedido = row_to_dict(row)
    pedido["items"] = _get_alquiler_items(conn, id)
    pedido["pagos"] = _get_alquiler_pagos(conn, id)
    pedido["historial_modificaciones"] = _get_historial_modificaciones(conn, id)
    _enriquecer_pedido_con_cliente(conn, pedido)
    _enriquecer_pedido_con_total(conn, pedido)
    return pedido


def _enriquecer_pedido_con_total(conn, pedido: dict) -> dict:
    """Agrega al pedido el desglose canónico del total + IVA derivado.

    Fuente de verdad: `services/precios.calcular_total`. `monto_total`
    persistido sigue siendo NETO (con descuento, sin IVA). Acá se computa
    el desglose para que admin/portal/listados muestren EXACTAMENTE lo
    mismo, sin reimplementar la fórmula en el frontend.

    Cierra #496. Si el cliente del pedido es Responsable Inscripto, se
    discrimina IVA 21%; el resto ve total = neto.
    """
    # Perfil tributario del cliente (lo usa calcular_total para decidir IVA).
    perfil = pedido.get("cliente_perfil_impuestos")
    if perfil is None and pedido.get("cliente_id"):
        row = conn.execute(
            "SELECT perfil_impuestos FROM clientes WHERE id = ?",
            (pedido["cliente_id"],),
        ).fetchone()
        if row:
            perfil = row_to_dict(row).get("perfil_impuestos")
            pedido["cliente_perfil_impuestos"] = perfil

    # Jornadas vía fórmula única (ceil/24h). Si falta alguna fecha → 1.
    d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
    d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
    jornadas = jornadas_periodo(d0, d1)

    # Items con la forma que espera el helper (precios netos).
    items_para_total = [
        {
            "equipo_id": it["equipo_id"],
            "cantidad": it["cantidad"],
            "precio_jornada": it["precio_jornada"],
        }
        for it in pedido.get("items", [])
    ]

    desglose = calcular_total(
        items=items_para_total,
        jornadas=jornadas,
        descuento_cliente_pct=pedido.get("descuento_pct") or 0,
        descuento_jornadas_pct=pedido.get("descuento_jornadas_pct") or 0,
        perfil_impuestos=perfil,
    )

    # Agregamos el desglose al pedido. El frontend lo lee directo, sin
    # reimplementar la fórmula. NO sobreescribimos `monto_total` (que
    # sigue siendo el neto persistido y la fuente de verdad de la BD).
    pedido["bruto"] = desglose["bruto"]
    pedido["descuento_monto"] = desglose["descuento_monto"]
    pedido["monto_neto"] = desglose["neto"]
    pedido["iva_pct"] = desglose["iva_pct"]
    pedido["iva_monto"] = desglose["iva_monto"]
    pedido["total_con_iva"] = desglose["total_final"]
    pedido["con_iva"] = desglose["con_iva"]
    pedido["cantidad_jornadas"] = jornadas
    return pedido


def _enriquecer_pedido_con_cliente_fiscal(conn, pedido: dict) -> dict:
    """Mergea perfil_impuestos + datos de Factura A del cliente en el pedido.

    Usado por los endpoints de PDF para que `_pedido_html` pueda decidir si
    discriminar IVA (Factura A para Responsable Inscripto).
    """
    cid = pedido.get("cliente_id")
    if not cid:
        return pedido
    row = conn.execute(
        """SELECT perfil_impuestos, razon_social, domicilio_fiscal,
                  email_facturacion, cuit
           FROM clientes WHERE id = ?""",
        (cid,),
    ).fetchone()
    if not row:
        return pedido
    c = row_to_dict(row)
    pedido["cliente_perfil_impuestos"] = c.get("perfil_impuestos")
    pedido["cliente_razon_social"] = c.get("razon_social")
    pedido["cliente_domicilio_fiscal"] = c.get("domicilio_fiscal")
    pedido["cliente_email_facturacion"] = c.get("email_facturacion")
    if c.get("cuit"):
        pedido["cliente_cuit"] = c["cuit"]
    return pedido


def _aplicar_contacto_cliente(pedido: dict, c: dict) -> None:
    """Sobrescribe nombre/email/teléfono del pedido con los datos `c` del cliente.

    El nombre: si hay datos RENAPER (identidad verificada), se usa el nombre
    legal confirmado; si no, el nombre ingresado por el cliente. El email/teléfono
    se sobrescriben solo si el cliente tiene un valor. También pone `cliente_dni`
    si el DNI fue verificado por RENAPER, y `cliente_dni_validado_at` para que el
    back-office pueda mostrar el aviso de identidad sin verificar.
    """
    if c.get("nombre_renaper"):
        pedido["cliente_nombre"] = f"{c['nombre_renaper']} {c.get('apellido_renaper', '')}".strip()
    else:
        pedido["cliente_nombre"] = nombre_completo_cliente(c.get("nombre", ""), c.get("apellido", ""))
    if c.get("email"):
        pedido["cliente_email"] = c["email"]
    if c.get("telefono"):
        pedido["cliente_telefono"] = c["telefono"]
    if c.get("dni"):
        pedido["cliente_dni"] = c["dni"]
    pedido["cliente_dni_validado_at"] = c.get("dni_validado_at")


def _enriquecer_pedido_con_cliente(conn, pedido: dict) -> dict:
    """Muestra los datos de contacto/identidad SIEMPRE en vivo desde la ficha.

    Los pedidos guardan una foto de nombre/email/teléfono al crearse, pero el
    contacto se muestra con el dato ACTUAL del cliente (decisión 2026-06-06):
    corregir un apellido o un teléfono en la ficha se refleja en todos los
    pedidos del cliente, en cualquier estado, en el back-office y en el portal.
    Si el pedido no tiene cliente vinculado (carga manual) o el cliente ya no
    existe, se conserva la foto. La plata (precio/descuento) NO se toca acá: esa
    sí queda congelada en confirmados/finalizados.
    """
    cid = pedido.get("cliente_id")
    if not cid:
        return pedido
    row = conn.execute(
        """SELECT nombre, apellido, email, telefono,
                  dni, nombre_renaper, apellido_renaper, dni_validado_at
           FROM clientes WHERE id = ?""",
        (cid,),
    ).fetchone()
    if row:
        _aplicar_contacto_cliente(pedido, row_to_dict(row))
    return pedido


def _enriquecer_pedidos_con_cliente(conn, pedidos: list[dict]) -> None:
    """Versión batch de `_enriquecer_pedido_con_cliente` para listados (sin N+1)."""
    ids = sorted({p["cliente_id"] for p in pedidos if p.get("cliente_id")})
    if not ids:
        return
    ph = ",".join(["?"] * len(ids))
    rows = conn.execute(
        f"""SELECT id, nombre, apellido, email, telefono,
                   dni, nombre_renaper, apellido_renaper, dni_validado_at
            FROM clientes WHERE id IN ({ph})""",
        ids,
    ).fetchall()
    by_id = {r["id"]: row_to_dict(r) for r in rows}
    for p in pedidos:
        c = by_id.get(p.get("cliente_id"))
        if c:
            _aplicar_contacto_cliente(p, c)


def _get_historial_modificaciones(conn, pedido_id: int) -> list[dict]:
    """Timeline de cambios solicitados por el cliente sobre el pedido.

    Incluye tanto solicitudes de aprobación como cambios directos
    (autosave en `presupuesto`) — el admin se beneficia de ver todo.
    `cambios_aplicados` puede diferir de `cambios_json` cuando el admin
    aprobó con contrapropuesta.
    """
    rows = conn.execute("""
        SELECT id, mensaje, estado, respuesta, cambios_json, cambios_aplicados,
               tipo, resolved_at, resolved_by, created_at
        FROM solicitudes_modificacion
        WHERE pedido_id = ?
        ORDER BY created_at DESC
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


# ── Modelos ──────────────────────────────────────────────────────────────────

def _parse_precio(v) -> int:
    """Acepta int, float o string con formato '$15.000' → 15000."""
    if v is None:
        return 0
    s = str(v).replace("$", "").replace(".", "").replace(",", "").strip()
    try:
        return int(float(s)) if s else 0
    except (ValueError, TypeError):
        return 0


def _validar_fecha_iso(v):
    """Valida que una fecha sea ISO parseable (o None/''). Se usa como
    field_validator en los modelos de pedido para rechazar fechas malformadas
    en el borde (422) en vez de explotar como 500 más adentro al castear."""
    if v is None or v == "":
        return None
    try:
        datetime.datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        raise ValueError(
            f"fecha inválida: '{v}'. Formato esperado ISO (yyyy-mm-dd o yyyy-mm-ddThh:mm)"
        )
    return str(v)


class PedidoItem(BaseModel):
    # equipo_id None = línea personalizada (#805): no es del catálogo, no reserva
    # stock; lleva `nombre_libre`. `cobro_modo`: 'jornada' (× jornadas, default) |
    # 'fijo' (monto único).
    equipo_id:      Optional[int] = None
    cantidad:       int
    precio_jornada: int = 0
    nombre_libre:   Optional[str] = None
    cobro_modo:     str = "jornada"

    @field_validator("precio_jornada", mode="before")
    @classmethod
    def coerce_precio(cls, v):
        return _parse_precio(v)

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v is None or v < 1:
            raise ValueError("cantidad debe ser >= 1")
        if v > 999:
            raise ValueError("cantidad demasiado alta (máx 999)")
        return v

    @field_validator("precio_jornada")
    @classmethod
    def validate_precio(cls, v):
        if v is not None and v < 0:
            raise ValueError("precio_jornada no puede ser negativo")
        return v

    @field_validator("cobro_modo")
    @classmethod
    def validate_cobro_modo(cls, v):
        if v not in ("jornada", "fijo"):
            raise ValueError("cobro_modo debe ser 'jornada' o 'fijo'")
        return v

    @model_validator(mode="after")
    def validate_linea_libre(self):
        # Una línea personalizada (sin equipo_id) necesita un nombre; una de
        # catálogo no puede cobrarse 'fijo' (eso es solo para líneas libres).
        if self.equipo_id is None:
            if not (self.nombre_libre or "").strip():
                raise ValueError("una línea personalizada necesita un nombre")
        elif self.cobro_modo != "jornada":
            raise ValueError("solo las líneas personalizadas pueden cobrarse 'fijo'")
        return self


class PedidoCreate(BaseModel):
    cliente_nombre:   Optional[str] = ""
    cliente_email:    Optional[str] = None
    cliente_telefono: Optional[str] = None
    cliente_id:       Optional[int] = None
    notas:            Optional[str] = None
    fecha_desde:      Optional[str] = None
    fecha_hasta:      Optional[str] = None
    items:            list[PedidoItem] = []
    estado:           Optional[str] = "presupuesto"

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        return _validar_fecha_iso(v)


class PedidoEstado(BaseModel):
    estado: str


class PedidoDatos(BaseModel):
    from pydantic import field_validator
    cliente_id:       Optional[int]   = None
    cliente_nombre:   Optional[str]   = None
    cliente_email:    Optional[str]   = None
    cliente_telefono: Optional[str]   = None
    fecha_desde:      Optional[str]   = None
    fecha_hasta:      Optional[str]   = None
    notas:            Optional[str]   = None
    descuento_pct:    Optional[float] = None

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        return _validar_fecha_iso(v)

    @field_validator("descuento_pct")
    @classmethod
    def validate_descuento(cls, v):
        if v is None:
            return v
        if v < 0 or v > 100:
            raise ValueError("descuento_pct debe estar entre 0 y 100")
        return v


class PedidoItemUpdate(BaseModel):
    items: list[PedidoItem]


# ── Rutas de pedidos ─────────────────────────────────────────────────────────

def _fmt_ars(monto) -> str:
    """Formatea un monto en pesos estilo es-AR: $ 12.500."""
    try:
        n = int(round(float(monto or 0)))
    except (TypeError, ValueError):
        n = 0
    return "$ " + f"{n:,}".replace(",", ".")


def _fmt_fecha_amable(v) -> str:
    """ISO → '15 jun · 10:00' (sin año). Cae al ISO si no parsea."""
    iso = to_iso(v)
    if not iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(str(iso).replace("Z", ""))
    except (ValueError, TypeError):
        return str(iso)
    meses = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]
    fecha = f"{dt.day} {meses[dt.month - 1]}"
    if dt.hour or dt.minute:
        return f"{fecha} · {dt.hour:02d}:{dt.minute:02d}"
    return fecha


def _pedido_email_context(pedido: dict) -> dict:
    """Arma el dict de variables disponibles a todos los templates de
    pedido. Mantener en sincronía con la lista de variables que se muestra
    en el editor del frontend (`/admin/email-templates`).
    """
    from markupsafe import escape

    items = pedido.get("items") or []

    def _nombre(it) -> str:
        return it.get("nombre_publico") or it.get("nombre") or it.get("equipo_nombre") or ""

    items_text = "\n".join(
        f"- {_nombre(it)} × {it.get('cantidad', 1)}" for it in items
    )

    # Tabla estilizada (inline) para el mail. Los nombres (datos dinámicos) se
    # escapan; la estructura/estilo la pone el helper canónico de branding
    # (`services/email/branding.py`, fuente única del look de mail) → la plantilla
    # la inyecta con |safe.
    from services.email import branding as _eb

    filas = ""
    for it in items:
        nombre = escape(_nombre(it))
        cant = escape(str(it.get("cantidad", 1)))
        sub = it.get("subtotal")
        sub_html = escape(_fmt_ars(sub)) if sub is not None else None
        filas += _eb.item_row(nombre, cant, sub_html)
    items_html = _eb.items_table(filas)

    # Jornadas: si el pedido ya viene enriquecido (`_enriquecer_pedido_con_total`)
    # lo reusamos; si no, lo derivamos con la fórmula única (mismo helper).
    jornadas = pedido.get("cantidad_jornadas")
    if jornadas is None:
        d0 = to_datetime(pedido["fecha_desde"]) if pedido.get("fecha_desde") else None
        d1 = to_datetime(pedido["fecha_hasta"]) if pedido.get("fecha_hasta") else None
        jornadas = jornadas_periodo(d0, d1)

    # Estado de pago (info "estilo pasaje": total, lo abonado y el saldo). La
    # plata sigue siendo NETO persistido — no se recalcula acá, solo se formatea.
    def _num(v) -> float:
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    total_num = _num(pedido.get("monto_total"))
    pagado_num = _num(pedido.get("monto_pagado"))
    saldo_num = max(total_num - pagado_num, 0.0)
    total_pagado = _fmt_ars(pagado_num)
    saldo_pendiente = _fmt_ars(saldo_num)
    if total_num <= 0:
        pago_estado = ""
    elif saldo_num <= 0:
        pago_estado = "Pago completo ✓"
    elif pagado_num > 0:
        pago_estado = f"Pagado {total_pagado} · saldo pendiente {saldo_pendiente}"
    else:
        pago_estado = "Pendiente de pago"

    return {
        "cliente_nombre": pedido.get("cliente_nombre") or "",
        "cliente_email": pedido.get("cliente_email") or "",
        "cliente_telefono": pedido.get("cliente_telefono") or "",
        "numero_pedido": pedido.get("numero_pedido") or pedido.get("id"),
        "fecha_desde": _fmt_fecha_amable(pedido.get("fecha_desde")),
        "fecha_hasta": _fmt_fecha_amable(pedido.get("fecha_hasta")),
        "cantidad_jornadas": jornadas,
        "total": _fmt_ars(pedido.get("monto_total")),
        "total_pagado": total_pagado,
        "saldo_pendiente": saldo_pendiente,
        "pago_estado": pago_estado,
        "notas": pedido.get("notas") or "",
        "items_html": items_html,
        "items_text": items_text,
        # URLs absolutas: en un cliente de mail un link relativo no resuelve.
        "admin_url": f"{SITE_URL}/admin/pedidos/{pedido.get('id')}",
        "portal_url": f"{SITE_URL}/cliente/portal",
        # Link "Agregar a Google Calendar" para el cuerpo del mail (complementa
        # al adjunto .ics). Vacío si la reserva no tiene fecha → el template lo
        # renderiza como string vacía (Jinja Undefined) sin romper.
        "gcal_url": google_calendar_url(
            pedido, pedido.get("items") or [], link=f"{SITE_URL}/cliente/portal"
        ),
    }


def _ics_adjunto_pedido(pedido: dict) -> Optional[list[Attachment]]:
    """Genera el adjunto `.ics` de la reserva para el mail (estilo "pasaje de
    avión": el cliente toca "Agregar al calendario"). Best-effort: si algo
    falla, devuelve None y el mail igual sale (la confirmación no se rompe).

    Usa el generador canónico de `services/ical.py` — el mismo que el feed.
    """
    try:
        # Link al portal del cliente (NO al back-office) — el .ics se lo lleva él.
        # with_reminders: su calendario le avisa solo antes del retiro.
        vevent = reserva_to_vevent(
            pedido, pedido.get("items") or [],
            link=f"{SITE_URL}/cliente/portal", with_reminders=True,
        )
        if not vevent:
            return None
        ics = build_vcalendar([vevent], method="PUBLISH")
        numero = pedido.get("numero_pedido") or pedido.get("id")
        return [
            Attachment(
                filename=f"pedido-{numero}.ics",
                content=ics.encode("utf-8"),
                mimetype="text/calendar; method=PUBLISH; charset=utf-8",
            )
        ]
    except Exception:
        logger.warning("No se pudo generar el .ics del pedido %s", pedido.get("id"), exc_info=True)
        return None


def _dispatch_pedido_creado_emails(background: Optional[BackgroundTasks], pedido: dict):
    """Encola los mails de 'pedido creado' (cliente + admin) como
    background tasks. Si no hay BackgroundTasks (llamada desde script),
    los corre síncrono — el send_email() jamás propaga errores."""
    ctx = _pedido_email_context(pedido)
    pedido_id = pedido.get("id")
    cliente_email = pedido.get("cliente_email")

    if cliente_email:
        if background is not None:
            background.add_task(
                send_email, "pedido_creado_cliente", cliente_email, ctx, pedido_id,
            )
        else:
            send_email("pedido_creado_cliente", cliente_email, ctx, pedido_id)

    admin_to = get_admin_to()
    if admin_to:
        if background is not None:
            background.add_task(
                send_email, "pedido_creado_admin", admin_to, ctx, pedido_id,
            )
        else:
            send_email("pedido_creado_admin", admin_to, ctx, pedido_id)


def create_pedido(data: PedidoCreate, background: Optional[BackgroundTasks] = None,
                  es_admin: bool = False):
    """Lógica interna de creación de pedido. Llamada por el endpoint admin
    (`create_pedido_endpoint`) y también por `cliente_portal.cliente_crear_pedido`
    que tiene su propio `require_cliente`."""
    if not data.items and data.estado != "borrador":
        raise HTTPException(400, "El pedido debe tener al menos un ítem")

    cliente_nombre   = data.cliente_nombre
    cliente_email    = data.cliente_email
    cliente_telefono = data.cliente_telefono

    with get_db() as conn:
        try:
            descuento_pct = 0.0
            if data.cliente_id:
                c = conn.execute("SELECT * FROM clientes WHERE id=?", (data.cliente_id,)).fetchone()
                if c:
                    cliente_nombre   = nombre_completo_cliente(c["nombre"], c["apellido"])
                    cliente_email    = cliente_email    or c["email"]
                    cliente_telefono = cliente_telefono or c["telefono"]
                    descuento_pct    = c["descuento"] or 0.0

            # Ambas fechas o ninguna: un pedido con una sola fecha es incoherente
            # (no se puede calcular jornadas ni chequear stock).
            if bool(data.fecha_desde) != bool(data.fecha_hasta):
                raise HTTPException(400, "Indicá fecha de retiro y devolución, o ninguna")

            if data.fecha_desde and data.fecha_hasta:
                d0 = to_datetime(data.fecha_desde)
                d1 = to_datetime(data.fecha_hasta)
                hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)

                if d0 >= d1:
                    raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
                # El admin puede crear pedidos con fecha pasada (carga retroactiva);
                # el cliente no. La distinción la pasa `create_pedido_endpoint`.
                if d0 < hoy and not es_admin:
                    raise HTTPException(400, "fecha_desde no puede ser en el pasado")

            estado_inicial = data.estado if data.estado in {"borrador", "presupuesto"} else "presupuesto"
            next_num = _next_numero_pedido(conn)
            # Cabecera primero con totales en 0; los ítems se aplican vía el helper
            # canónico, que recalcula monto_total y descuento_jornadas_pct.
            cur = conn.execute("""
                INSERT INTO alquileres (cliente_nombre, cliente_email, cliente_telefono,
                                     cliente_id, notas, fecha_desde, fecha_hasta,
                                     monto_total, estado, numero_pedido,
                                     descuento_pct, descuento_jornadas_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cliente_nombre, cliente_email, cliente_telefono,
                  data.cliente_id, data.notas, data.fecha_desde or None, data.fecha_hasta or None,
                  0, estado_inicial, next_num,
                  descuento_pct, 0.0))
            pedido_id = cur.lastrowid

            # Ítems vía la fuente única `_apply_pedido_items` (#805): preserva las
            # líneas personalizadas (equipo_id None → nombre_libre/cobro_modo/orden),
            # consolida las de catálogo y respeta cobro_modo='fijo' (no × jornadas).
            # El armado inline anterior asumía equipo_id válido → 404 al crear con una
            # línea libre, y descartaba nombre_libre/cobro_modo. Borradores: sin ítems.
            if data.items:
                _apply_pedido_items(conn, pedido_id, data.items)

            if estado_inicial == "presupuesto" and data.fecha_desde and data.fecha_hasta:
                problemas = _check_stock(conn, pedido_id, data.fecha_desde, data.fecha_hasta)
                if problemas:
                    raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

            conn.commit()
            pedido = _get_alquiler_detail(conn, pedido_id)
        except Exception:
            logger.error("Error creando pedido", exc_info=True)
            conn.rollback()
            raise

    # Mails fuera del try/finally del DB: si fallan no rollbackean el pedido
    # (igual send_email no propaga, pero por las dudas). Solo se mandan si
    # el pedido salió de borrador — drafts no notifican.
    if pedido and pedido.get("estado") != "borrador":
        _dispatch_pedido_creado_emails(background, pedido)
    return pedido


def _recalcular_total_pedido(conn, id: int) -> None:
    """Recalcula y persiste el total de un pedido desde su estado YA guardado.

    Fuente ÚNICA del recálculo "desde lo que hay en la base": subtotales por
    línea, `descuento_jornadas_pct` (derivado de las jornadas) y `monto_total`
    (neto). Lee los ítems, las fechas y el `descuento_pct` del propio pedido —
    no recibe nada de afuera. No toca stock ni estado.

    Lo usan `_apply_pedido_datos` (editar fechas/cliente/descuento), la edición
    de ítems y la propagación del descuento del cliente a sus presupuestos.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not p:
        return
    d0 = to_datetime(p["fecha_desde"]) if p["fecha_desde"] else None
    d1 = to_datetime(p["fecha_hasta"]) if p["fecha_hasta"] else None
    jornadas = jornadas_periodo(d0, d1)
    items = conn.execute(
        "SELECT id, equipo_id, cantidad, precio_jornada, cobro_modo FROM alquiler_items WHERE pedido_id=?",
        (id,),
    ).fetchall()
    # Subtotales persistidos por línea (los usan los visores). `bruto_linea`
    # respeta el modo de cobro (las líneas 'fijo' no multiplican por jornadas).
    for it in items:
        sub = bruto_linea(
            {"precio_jornada": it["precio_jornada"], "cantidad": it["cantidad"],
             "cobro_modo": it["cobro_modo"]},
            jornadas,
        )
        conn.execute("UPDATE alquiler_items SET subtotal=? WHERE id=?", (sub, it["id"]))
    descuento_jornadas_pct = _get_descuento_jornadas(conn, jornadas)
    total_desglose = calcular_total(
        items=[
            {"equipo_id": it["equipo_id"], "cantidad": it["cantidad"],
             "precio_jornada": it["precio_jornada"], "cobro_modo": it["cobro_modo"]}
            for it in items
        ],
        jornadas=jornadas,
        descuento_cliente_pct=p["descuento_pct"] or 0,
        descuento_jornadas_pct=descuento_jornadas_pct,
        perfil_impuestos=None,  # persiste NETO; IVA es derivado al mostrar.
    )
    conn.execute(
        "UPDATE alquileres SET monto_total=?, descuento_jornadas_pct=? WHERE id=?",
        (total_desglose["neto"], descuento_jornadas_pct, id),
    )


def propagar_descuento_a_presupuestos(conn, cliente_id: int, nuevo_pct: float) -> int:
    """Aplica el nuevo descuento del cliente a sus pedidos NO confirmados y los
    recotiza. Devuelve cuántos presupuestos tocó.

    Solo afecta el estado `presupuesto` (no confirmado): los pedidos confirmados
    o cerrados conservan el snapshot del descuento con que se crearon — es un
    lock de precio deliberado (un pedido confirmado/facturado no debe cambiar de
    importe porque después se editó el perfil del cliente). Recibe una conexión
    abierta; el caller hace commit.
    """
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM alquileres WHERE cliente_id=? AND estado='presupuesto'",
            (cliente_id,),
        ).fetchall()
    ]
    for pid in ids:
        conn.execute("UPDATE alquileres SET descuento_pct=? WHERE id=?", (nuevo_pct or 0, pid))
        _recalcular_total_pedido(conn, pid)
    return len(ids)


def _apply_pedido_datos(conn, id: int, data: "PedidoDatos", es_admin: bool = False) -> dict:
    """Aplica un cambio parcial de datos (cliente/fechas/notas/descuento) al pedido.

    Lógica compartida entre el endpoint admin (`update_pedido_datos`) y la
    aplicación de propuestas del cliente (cliente_portal). Recibe una conexión
    abierta; el caller hace commit/rollback y close.

    `es_admin=True` permite fecha de retiro en el pasado (carga retroactiva del
    back-office). Las propuestas del cliente (cliente_portal) usan el default
    `False` → el cliente sigue sin poder fechar en el pasado.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not p:
        raise HTTPException(404, "Pedido no encontrado")

    payload = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    # Columnas TIMESTAMP: '' rompe el cast → normalizar a NULL.
    for _k in ("fecha_desde", "fecha_hasta"):
        if _k in payload and not payload[_k]:
            payload[_k] = None

    cliente_cambio = "cliente_id" in payload and payload["cliente_id"]
    if cliente_cambio:
        c = conn.execute("SELECT * FROM clientes WHERE id=?", (payload["cliente_id"],)).fetchone()
        if c:
            payload.setdefault("cliente_nombre",   nombre_completo_cliente(c["nombre"], c["apellido"]))
            payload.setdefault("cliente_email",    c["email"])
            payload.setdefault("cliente_telefono", c["telefono"])
            if "descuento_pct" not in payload:
                payload["descuento_pct"] = c["descuento"] or 0.0

    if "fecha_desde" in payload or "fecha_hasta" in payload:
        nueva_desde = payload.get("fecha_desde") or p["fecha_desde"]
        nueva_hasta = payload.get("fecha_hasta") or p["fecha_hasta"]
        if nueva_desde and nueva_hasta:
            d0 = to_datetime(nueva_desde)
            d1 = to_datetime(nueva_hasta)
            hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)

            if d0 >= d1:
                raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
            # Históricos importados tienen fechas en el pasado por diseño. El
            # frontend manda fecha_desde junto con cualquier cambio (ej. solo
            # el descuento), así que sin este bypass no se podría editar nada.
            # El admin además puede fijar fechas pasadas a propósito (carga
            # retroactiva); el cliente (es_admin=False) sigue sin poder.
            if d0 < hoy and not es_admin and not _es_historico(p["fuente"]):
                raise HTTPException(400, "fecha_desde no puede ser en el pasado")

    if not payload:
        return _get_alquiler_detail(conn, id)

    cols = ", ".join(f"{k}=?" for k in payload)
    conn.execute(f"UPDATE alquileres SET {cols} WHERE id=?", (*payload.values(), id))

    if (
        "fecha_desde" in payload
        or "fecha_hasta" in payload
        or "descuento_pct" in payload
        or cliente_cambio
    ):
        _recalcular_total_pedido(conn, id)

    return _get_alquiler_detail(conn, id)


def _apply_pedido_items(conn, id: int, items: list["PedidoItem"]) -> dict:
    """Reemplaza los ítems del pedido por `items`. Recalcula subtotales y monto.

    No valida stock — el caller debe llamar a `_check_stock` si corresponde.
    Lógica compartida entre admin y portal cliente.
    """
    p = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
    if not p:
        raise HTTPException(404, "Pedido no encontrado")
    if not items:
        raise HTTPException(400, "Debe tener al menos un ítem")

    d0 = to_datetime(p["fecha_desde"]) if p["fecha_desde"] else None
    d1 = to_datetime(p["fecha_hasta"]) if p["fecha_hasta"] else None
    jornadas = jornadas_periodo(d0, d1)

    # Armar las líneas preservando el orden de llegada (= el orden que arma el
    # front, incl. drag-reorder #806). Las de catálogo se CONSOLIDAN por equipo
    # (sumar cantidades) — sino dos rows del mismo equipo pasan el gate (que
    # consolida) pero quedan dos filas. Las líneas personalizadas (#805, sin
    # equipo_id) NO se consolidan: cada una es única (nombre/precio/modo propios).
    lineas: list[dict] = []
    equipo_idx: dict[int, int] = {}  # equipo_id → índice en `lineas`
    for it in items:
        if it.equipo_id is None:
            lineas.append({
                "equipo_id": None,
                "cantidad": it.cantidad,
                "precio_jornada": it.precio_jornada,
                "nombre_libre": (it.nombre_libre or "").strip(),
                "cobro_modo": it.cobro_modo or "jornada",
            })
        elif it.equipo_id in equipo_idx:
            e = lineas[equipo_idx[it.equipo_id]]
            e["cantidad"] += it.cantidad
            # Precios distintos para el mismo equipo: usamos el mayor (defensivo).
            e["precio_jornada"] = max(e["precio_jornada"], it.precio_jornada)
        else:
            equipo_idx[it.equipo_id] = len(lineas)
            lineas.append({
                "equipo_id": it.equipo_id,
                "cantidad": it.cantidad,
                "precio_jornada": it.precio_jornada,
                "nombre_libre": None,
                "cobro_modo": "jornada",
            })

    # `orden` por posición; subtotal por línea vía `bruto_linea` (respeta cobro_modo).
    rows = []
    for orden, ln in enumerate(lineas):
        if ln["equipo_id"] is not None and not conn.execute(
            "SELECT id FROM equipos WHERE id=?", (ln["equipo_id"],)
        ).fetchone():
            raise HTTPException(404, f"Equipo {ln['equipo_id']} no encontrado")
        subtotal = bruto_linea(ln, jornadas)
        rows.append((
            id, ln["equipo_id"], ln["cantidad"], ln["precio_jornada"],
            subtotal, orden, ln["nombre_libre"], ln["cobro_modo"],
        ))

    # Re-aplicar AMBOS descuentos (cliente + jornadas), como hacen las
    # otras 2 sedes. Antes solo se aplicaba el del cliente → editar ítems
    # perdía el descuento por jornadas (#500). Acá se calcula desde los ítems
    # en memoria (los que estamos por insertar), no desde la base.
    descuento_jornadas_pct = _get_descuento_jornadas(conn, jornadas)
    total_desglose = calcular_total(
        items=lineas,  # incluye cobro_modo por línea (líneas 'fijo' no × jornadas)
        jornadas=jornadas,
        descuento_cliente_pct=p["descuento_pct"] or 0,
        descuento_jornadas_pct=descuento_jornadas_pct,
        perfil_impuestos=None,  # persiste NETO; IVA derivado al mostrar.
    )
    monto_total = total_desglose["neto"]

    conn.execute("DELETE FROM alquiler_items WHERE pedido_id=?", (id,))
    conn.executemany("""
        INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal, orden, nombre_libre, cobro_modo)
        VALUES (?,?,?,?,?,?,?,?)
    """, rows)
    conn.execute(
        "UPDATE alquileres SET monto_total=?, descuento_jornadas_pct=? WHERE id=?",
        (monto_total, descuento_jornadas_pct, id),
    )

    return _get_alquiler_detail(conn, id)


