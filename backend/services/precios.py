"""services/precios.py — Cálculo canónico de totales de pedidos.

Una sola fuente de verdad para el cálculo del total de un pedido. Lo
consumen los 3 sitios que lo calculaban distinto:

- ``routes.alquileres.create_pedido``
- ``routes.alquileres._apply_pedido_datos``
- ``routes.alquileres._apply_pedido_items``  (← este perdía el descuento por jornadas → bug #500)

y también el PDF (``pdf.py``), que recomputaba a mano sin descuento y con
jornadas truncadas (bug #502).

Modelo (alineado bit a bit con ``src/lib/cart-total.ts`` del front):

- Precios del catálogo son **netos** (sin IVA).
- Descuento NO acumulativo: gana el mayor entre las fuentes vigentes — la
  decisión de "quién gana" vive en ``descuentos.queries.decision.
  calcular_descuento_aplicable`` (paquete ``backend/descuentos/``, no acá).
- ``monto_total`` se PERSISTE neto (con descuento aplicado, sin IVA).
  El IVA es derivado al mostrar/facturar: solo para
  ``perfil_impuestos == 'responsable_inscripto'`` se suma 21%.

Tests: ``backend/tests/test_precios_service.py``.
"""

from __future__ import annotations

from math import ceil
from datetime import datetime
from typing import Optional, TypedDict

from descuentos.queries.decision import calcular_descuento_aplicable


IVA_PCT = 21.0
"""Alícuota de IVA (Argentina). Solo se aplica a Responsable Inscripto."""

PERFIL_RI = "responsable_inscripto"


# ── Tipos ────────────────────────────────────────────────────────────────


class ItemPrecio(TypedDict, total=False):
    """Forma mínima de un ítem para calcular total.

    `cobro_modo` (opcional, #805): 'jornada' (default — precio × cantidad ×
    jornadas, como los equipos del catálogo) o 'fijo' (monto único — precio ×
    cantidad, SIN multiplicar por jornadas; para líneas personalizadas tipo flete).
    `equipo_id` puede faltar/ser None en líneas personalizadas (no del catálogo).
    """
    equipo_id: Optional[int]
    cantidad: int
    precio_jornada: int
    cobro_modo: str


class TotalDesglose(TypedDict):
    bruto: int               # Σ(precio_jornada × cantidad × jornadas)
    descuento_pct: float     # % aplicado (el ganador: max(cliente, jornadas))
    descuento_monto: int     # bruto - neto
    neto: int                # bruto - descuento_monto — lo que se PERSISTE en monto_total
    con_iva: bool            # True si el perfil es responsable_inscripto
    iva_pct: float
    iva_monto: int           # 0 si no es RI
    total_final: int         # neto + iva_monto — lo que ve el cliente RI


# ── Funciones puras ──────────────────────────────────────────────────────


def jornadas_periodo(
    fecha_desde: Optional[datetime], fecha_hasta: Optional[datetime]
) -> int:
    """Cantidad de jornadas entre dos fechas.

    Fórmula canónica: ``ceil((hasta - desde) / 24h)``. Mínimo 1.
    Si falta alguna fecha o son iguales/invertidas devuelve 1.

    Esto reemplaza ``(d2 - d1).days`` (trunca, no cuenta jornadas con
    horas) que usaba ``pdf.py`` y daba una jornada de menos cuando había
    diferencia horaria.
    """
    if not fecha_desde or not fecha_hasta:
        return 1
    delta = fecha_hasta - fecha_desde
    horas = delta.total_seconds() / 3600
    if horas <= 0:
        return 1
    return max(1, ceil(horas / 24))


def es_responsable_inscripto(perfil_impuestos: Optional[str]) -> bool:
    """Predicado canónico para Factura A / IVA discriminado."""
    return (perfil_impuestos or "") == PERFIL_RI


def _precio_combo_calc(componentes) -> int:
    """Precio NETO por jornada de un combo: Σ(precio_componente × cantidad ×
    (1 − descuento_línea/100)), redondeado. PURO (testeable sin DB).

    `componentes`: iterable de filas con `precio_jornada`, `cantidad`,
    `descuento_pct` (el descuento por línea del combo, de `kit_componentes`)."""
    total = 0.0
    for c in componentes:
        precio = c["precio_jornada"] or 0
        cant = c["cantidad"] or 0
        desc = (c["descuento_pct"] or 0) / 100.0
        total += precio * cant * (1.0 - desc)
    return int(round(total))


def precio_combo(conn, equipo_id: int) -> int:
    """C3 #635 — precio por jornada derivado de un COMBO: DINÁMICO (sigue el
    precio actual de cada componente) con el descuento por línea de cada uno.

    Lo usa `cotizar` para los equipos `tipo='combo'` en vez de su `precio_jornada`
    propio. Los kits y simples siguen con su precio propio (manual). Cómo compone
    este precio con los descuentos de cliente/jornada es decisión de negocio
    abierta (ver #635) — hoy se aplica como base y los demás descuentos stackean.
    """
    rows = conn.execute(
        "SELECT e.precio_jornada, kc.cantidad, kc.descuento_pct "
        "FROM kit_componentes kc JOIN equipos e ON e.id = kc.componente_id "
        "WHERE kc.equipo_id = %s AND e.eliminado_at IS NULL",
        (equipo_id,),
    ).fetchall()
    return _precio_combo_calc(rows)


def precios_combo_batch(conn, equipo_ids) -> dict[int, int]:
    """Precio efectivo por jornada de varios COMBOS en UNA sola query (evita N+1 en
    el catálogo). Devuelve `{equipo_id: precio_efectivo}` para los ids que tengan
    componentes vivos; un combo sin componentes no aparece (el caller cae a 0). Mismo
    cálculo que `precio_combo` (reusa `_precio_combo_calc`)."""
    ids = list(equipo_ids)
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT kc.equipo_id, e.precio_jornada, kc.cantidad, kc.descuento_pct "
        "FROM kit_componentes kc JOIN equipos e ON e.id = kc.componente_id "
        "WHERE kc.equipo_id = ANY(%s) AND e.eliminado_at IS NULL",
        (ids,),
    ).fetchall()
    por_combo: dict[int, list] = {}
    for r in rows:
        por_combo.setdefault(r["equipo_id"], []).append(r)
    return {eid: _precio_combo_calc(comps) for eid, comps in por_combo.items()}


def precio_jornada_efectivo(conn, equipo_id: int) -> Optional[int]:
    """Precio por jornada EFECTIVO de un equipo, resuelto en UN solo lugar: para un
    COMBO se deriva en vivo de sus componentes (`precio_combo`, C3 #635); un kit/simple
    usa su `precio_jornada` propio. `None` si el equipo no existe (o está soft-deleted).

    Fuente ÚNICA de "qué precio por jornada toma este equipo": la consumen `cotizar`,
    `cliente_crear_pedido` y `cliente_modificar_pedido` → lo que el carrito COTIZA es lo
    que se PERSISTE (cierra el drift de combos cotizado≠cobrado). El gate de seguridad
    "solo equipos de catálogo / el cliente no decide el precio" vive en cada consumidor,
    no acá — esto solo resuelve plata.
    """
    row = conn.execute(
        "SELECT precio_jornada, tipo FROM equipos WHERE id = %s AND eliminado_at IS NULL",
        (equipo_id,),
    ).fetchone()
    if not row:
        return None
    if row["tipo"] == "combo":
        return precio_combo(conn, equipo_id)
    return int(row["precio_jornada"] or 0)


def bruto_linea(it: ItemPrecio, jornadas: int) -> int:
    """Bruto (neto sin descuento) de UNA línea — fuente única del subtotal por línea.

    'jornada' (default): precio × cantidad × jornadas (equipos del catálogo).
    'fijo' (#805, líneas personalizadas tipo flete): precio × cantidad, SIN jornadas.
    """
    cant = int(it.get("cantidad") or 0)
    precio = int(it.get("precio_jornada") or 0)
    mult = 1 if (it.get("cobro_modo") or "jornada") == "fijo" else max(1, int(jornadas or 1))
    return precio * cant * mult


def calcular_total(
    items: list[ItemPrecio],
    jornadas: int,
    descuento_cliente_pct: Optional[float] = 0.0,
    descuento_jornadas_pct: Optional[float] = 0.0,
    perfil_impuestos: Optional[str] = None,
) -> TotalDesglose:
    """Cálculo canónico del total de un pedido.

    Argumentos:
      items:                       [{equipo_id, cantidad, precio_jornada}], precios NETOS.
      jornadas:                    cantidad de jornadas (usar ``jornadas_periodo``).
      descuento_cliente_pct:       ``clientes.descuento`` (0..100).
      descuento_jornadas_pct:      interpolado por ``descuentos.queries.jornadas.obtener_descuento_jornadas``.
      perfil_impuestos:            ``'responsable_inscripto'`` para sumar IVA 21%.

    El backend debe PERSISTIR ``neto`` en ``alquileres.monto_total`` (sin IVA).
    El ``total_final`` (con IVA si aplica) es lo que se MUESTRA al cliente RI.
    """
    j = max(1, int(jornadas or 1))
    bruto = sum(bruto_linea(it, j) for it in items)
    pct = calcular_descuento_aplicable(
        {"cliente": descuento_cliente_pct, "jornadas": descuento_jornadas_pct}
    )
    descuento_monto = int(round(bruto * pct / 100))
    neto = int(bruto - descuento_monto)
    con_iva = es_responsable_inscripto(perfil_impuestos)
    iva_monto = int(round(neto * IVA_PCT / 100)) if con_iva else 0
    return {
        "bruto": int(bruto),
        "descuento_pct": pct,
        "descuento_monto": descuento_monto,
        "neto": neto,
        "con_iva": con_iva,
        "iva_pct": IVA_PCT,
        "iva_monto": iva_monto,
        "total_final": neto + iva_monto,
    }
