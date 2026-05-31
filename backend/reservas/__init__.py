"""Paquete `reservas` — fuente única de la semántica del motor de reservas.

Acá viven las primitivas de disponibilidad/confirmación (qué cuenta como
reservado, overlap, buffer, mantenimiento, consolidación de items) para que las
consuman tanto la LECTURA (catálogo/calendario) como el GATE de escritura, sin
copiar SQL en cada call-site.

**El core de reservas es sagrado:** estas funciones son la semántica compartida,
pero el lock pesimista (`SELECT ... FOR UPDATE`) y la transacción del gate viven
en el flujo de confirmación (no acá) — ver `routes/alquileres._check_stock`.

Migración incremental (issue #501, Fase 1): este paquete se va poblando por
pasos. `routes/alquileres.py` mantiene alias a estos nombres para no romper los
imports existentes (`routes.estudio`, `routes.cliente_portal`).
"""
from reservas.estados import ESTADOS_RESERVADO
from reservas.disponibilidad import calcular_disponibilidad, dias_no_disponibles
from reservas.gate import validar_stock
from reservas.semantics import (
    componentes_de,
    consolidar_items_por_equipo,
    expandir_demanda,
    get_buffer_horas,
    invalidate_buffer_cache,
    parientes_de,
    rango_con_buffer,
    reservado_directo,
    reservado_total,
    unidades_en_mantenimiento,
)

__all__ = [
    "ESTADOS_RESERVADO",
    "calcular_disponibilidad",
    "componentes_de",
    "consolidar_items_por_equipo",
    "dias_no_disponibles",
    "expandir_demanda",
    "get_buffer_horas",
    "invalidate_buffer_cache",
    "parientes_de",
    "rango_con_buffer",
    "reservado_directo",
    "reservado_total",
    "unidades_en_mantenimiento",
    "validar_stock",
]
