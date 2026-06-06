"""dataio/csv_exporters.py — Export plano (planilla) a CSV.

A diferencia de los exporters JSON (normalizados, un archivo por tabla), esto
hace los JOINs y devuelve una sola hoja lista para Excel. NO toca el esquema:
las specs del equipo se colapsan en una columna de texto ("label: value; ...").

Cada función devuelve el CSV completo como `str`, con BOM UTF-8 al inicio para
que Excel renderice bien acentos y ñ.
"""

import csv
import io

from database import to_iso, MARCA_SUBQUERY


def _csv_from_rows(columns: list[str], rows: list) -> str:
    """Arma un CSV (con BOM) a partir de columnas + filas dict-like.

    Coacciona None→'' y date/datetime→ISO. Todo lo demás vía str()."""
    buf = io.StringIO()
    buf.write("﻿")  # BOM para Excel
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        out = []
        for col in columns:
            v = r[col]
            if v is None:
                out.append("")
            elif hasattr(v, "isoformat"):  # date / datetime
                out.append(to_iso(v))
            else:
                out.append(str(v))
        writer.writerow(out)
    return buf.getvalue()


def export_equipos_csv(conn) -> str:
    """Una fila por equipo activo. Specs colapsadas en una columna de texto."""
    columns = [
        "id", "nombre", "marca", "modelo", "categorias", "cantidad",
        "precio_jornada", "precio_usd", "dueno", "estado", "visible_catalogo",
        "serie", "fecha_compra", "specs",
    ]
    rows = conn.execute(f"""
        SELECT
            e.id, e.nombre,
            {MARCA_SUBQUERY},
            e.modelo,
            (SELECT string_agg(c.nombre, ' / ' ORDER BY c.nombre)
               FROM equipo_categorias ec
               JOIN categorias c ON c.id = ec.categoria_id
               WHERE ec.equipo_id = e.id) AS categorias,
            e.cantidad, e.precio_jornada, e.precio_usd, e.dueno, e.estado,
            e.visible_catalogo, e.serie, e.fecha_compra,
            (SELECT string_agg(sd.label || ': ' || es.value, '; '
                                ORDER BY sd.prioridad, sd.label)
               FROM equipo_specs es
               JOIN spec_definitions sd ON sd.id = es.spec_def_id
               WHERE es.equipo_id = e.id) AS specs
        FROM equipos e
        WHERE e.eliminado_at IS NULL
        ORDER BY e.nombre
    """).fetchall()
    return _csv_from_rows(columns, rows)


def export_alquileres_csv(conn) -> str:
    """Una fila por pedido. Incluye resumen legible de los items."""
    columns = [
        "numero_pedido", "cliente_nombre", "cliente_email", "estado",
        "fecha_desde", "fecha_hasta", "monto_total", "descuento_pct",
        "monto_pagado", "saldo", "items", "fuente", "notas",
    ]
    rows = conn.execute("""
        SELECT
            a.numero_pedido, a.cliente_nombre, a.cliente_email, a.estado,
            a.fecha_desde, a.fecha_hasta, a.monto_total, a.descuento_pct,
            a.monto_pagado,
            (COALESCE(a.monto_total, 0) - COALESCE(a.monto_pagado, 0)) AS saldo,
            (SELECT string_agg(e.nombre || ' x' || ai.cantidad, '; ')
               FROM alquiler_items ai
               JOIN equipos e ON e.id = ai.equipo_id
               WHERE ai.pedido_id = a.id) AS items,
            a.fuente, a.notas
        FROM alquileres a
        ORDER BY a.numero_pedido NULLS LAST, a.id
    """).fetchall()
    return _csv_from_rows(columns, rows)


def export_clientes_csv(conn) -> str:
    """Una fila por cliente."""
    columns = [
        "nombre", "apellido", "email", "telefono", "direccion", "cuit",
        "perfil_impuestos", "razon_social", "domicilio_fiscal", "descuento",
    ]
    rows = conn.execute("""
        SELECT nombre, apellido, email, telefono, direccion, cuit,
               perfil_impuestos, razon_social, domicilio_fiscal, descuento
        FROM clientes
        ORDER BY apellido, nombre
    """).fetchall()
    return _csv_from_rows(columns, rows)


CSV_EXPORTERS = {
    "equipos": export_equipos_csv,
    "alquileres": export_alquileres_csv,
    "clientes": export_clientes_csv,
}
