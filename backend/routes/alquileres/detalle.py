"""routes/alquileres/detalle.py — lectura del detalle de un pedido (split de `core.py`).

Move-verbatim desde `core.py` (issue de tracking #1254, Corte C): el armado del
pedido completo (`_get_alquiler_detail` + sus piezas — ítems con componentes de
kit, pagos, historial, enriquecimiento de cliente/total) y un par de helpers
chicos (`_next_numero_pedido`, `_maybe_finalizar`, `_es_historico`) que
`create_pedido`/`_apply_pedido_*` (que quedan en `core.py`) siguen usando. `core.py`
re-importa estos 8 nombres tal cual — `routes/alquileres/__init__.py` no cambia.
"""
from fastapi import HTTPException

from database import row_to_dict, MARCA_SUBQUERY, marca_subquery
from services.pedidos_enriquecimiento import _enriquecer_pedido_con_cliente


def _es_historico(fuente: str | None) -> bool:
    """Pedidos historicos (importados) no validan fechas ni stock.

    Soporta `historico` y prefijos tipo `<sistema>-historico` (ej.
    `booqable-historico` que generan los converters de migracion). Asi un
    converter futuro puede usar su propio prefijo sin tocar el backend.
    """
    return bool(fuente) and fuente.endswith("historico")


def _maybe_finalizar(conn, pedido_id: int):
    """Si el pedido está 'devuelto' y monto_pagado >= monto_total → 'finalizado'."""
    p = conn.execute(
        "SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=%s", (pedido_id,)
    ).fetchone()
    if not p:
        return
    if (p["estado"] == "devuelto"
            and (p["monto_pagado"] or 0) >= (p["monto_total"] or 0)
            and (p["monto_total"] or 0) > 0):
        conn.execute("UPDATE alquileres SET estado='finalizado' WHERE id=%s", (pedido_id,))


def _get_alquiler_items(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute(f"""
        SELECT pi.*, COALESCE(e.nombre, pi.nombre_libre) AS nombre,
               {MARCA_SUBQUERY},
               e.modelo, e.serie, e.valor_reposicion,
               e.foto_url, e.foto_url_sm, e.foto_url_thumb, e.cantidad AS stock_total,
               e.nombre_publico, e.nombre_publico_largo, e.tipo AS equipo_tipo,
               ef.contenido_incluido_json
        FROM alquiler_items pi
        LEFT JOIN equipos e ON e.id = pi.equipo_id
        LEFT JOIN equipo_fichas ef ON ef.equipo_id = e.id
        WHERE pi.pedido_id = %s
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
    placeholders = ",".join("%s" for _ in equipo_ids)
    comp_rows = conn.execute(f"""
        SELECT kc.*, ec.nombre, {marca_subquery('ec')}, ec.foto_url, ec.foto_url_sm, ec.foto_url_thumb, ec.cantidad AS stock_total,
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


def _get_alquiler_pagos(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM alquiler_pagos WHERE pedido_id = %s ORDER BY fecha, created_at
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def _get_alquiler_detail(conn, id: int) -> dict:
    row = conn.execute("SELECT * FROM alquileres WHERE id=%s", (id,)).fetchone()
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
    """Wrapper de compatibilidad — la lógica real vive en
    `services.finanzas_flujo.pedido.desglose_de_pedido` (fuente única del
    desglose de plata de un pedido: bruto/descuento/neto/IVA por línea,
    `cobro_modo`-aware). Código nuevo debería importar de ahí directo; este
    wrapper solo evita tocar los 6 call-sites existentes en la migración
    (auditoría cruzada de plata, 2026-07-02). Cierra #496.
    """
    from services.finanzas_flujo.pedido import desglose_de_pedido
    return desglose_de_pedido(conn, pedido)


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
        WHERE pedido_id = %s
        ORDER BY created_at DESC
    """, (pedido_id,)).fetchall()
    return [row_to_dict(r) for r in rows]
