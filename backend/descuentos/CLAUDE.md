# `backend/descuentos/` — motor único de "qué % de descuento gana"

> Invariantes locales. El _por qué_ completo: `docs/DECISIONES.md` _2026-07-03 — `backend/descuentos/`
> reorganizado CQRS-lite_.

**Toda la decisión de "cuál descuento aplica"** (cliente vs. jornadas, y las fuentes que se sumen a
futuro) vive acá; los routes son solo transporte HTTP. No re-implementar la comparación a mano en un route
ni en `services/precios.py`.

## Estructura (CQRS-lite, espeja `contabilidad/` y `services/specs/`)

```
descuentos/
  __init__.py       # barrel (docstring, sin __all__ — no hay re-exports públicos)
  queries/            # LECTURA — nunca mutan
    decision.py         # calcular_descuento_aplicable (PURA), calcular_descuento_origen (PURA),
                         # resolver_descuento_pedido/resolver_origen_pedido (jerarquía C-1, PURA),
                         # resolver_descuento_monto_pedido/resolver_origen_pedido_monto (C-2, PURA)
    jornadas.py           # interpolar_descuento_jornadas (PURA), obtener_descuento_jornadas,
                           # listar_descuentos_jornada, obtener_descuento_jornada_por_jornadas
    cliente.py             # obtener_descuento_cliente (descuento fijo del cliente, en vivo)
  commands/           # ESCRITURA — única puerta de mutación
    jornadas.py          # validar_descuento_jornada (PURA), crear_descuento_jornada,
                          # eliminar_descuento_jornada
```

**Invariante commands↔queries (igual que `contabilidad`/`specs`):** `commands/` puede importar de
`queries/`; `queries/` **nunca** de `commands/`.

## Reglas que no se rompen

- **Descuentos NO acumulativos:** gana la fuente de mayor %, vía `calcular_descuento_aplicable(fuentes:
  dict[str, float])`. La firma toma una **colección con nombre**, no parámetros posicionales fijos — sumar
  una fuente nueva es agregar una key (`{"cliente": pct, "jornadas": pct, "lo-que-venga": pct}`), no
  rediseñar la función ni tocar todos sus callers. En empate gana la primera fuente declarada (hoy:
  `"cliente"`).
- **`calcular_descuento_origen` deriva del mismo dict normalizado** que `calcular_descuento_aplicable` —
  las dos funciones comparten el paso de `max(0.0, float(v or 0))` antes de decidir, así nunca pueden
  divergir en el criterio de empate o de clamping de negativos (antes vivían como dos implementaciones
  separadas — una en `services/precios.py`, otra a mano en `routes/alquileres/cotizacion.py`).
- **Combos (`kit_componentes.descuento_pct`) están fuera de este dominio.** Arman el precio BASE de un
  combo (`services/precios.py::precio_combo`) — un concepto de composición de precio por línea, no de "qué
  descuento gana". Los dos no se cruzan en código; sí se apilan en cascada (el combo entra ya rebajado como
  precio base, y el descuento de `descuentos/` actúa encima de ese precio).
- **`eliminar_descuento_jornada` hace DELETE real, no soft-delete.** `descuentos_jornada` es una tabla de
  configuración/escala, no una entidad de plata con `created_by`/`anulado_*` como las de `contabilidad/` —
  agregarle esa infraestructura es decisión aparte, no algo que este módulo asuma.
- **`_recalcular_total_pedido` y `propagar_descuento_a_presupuestos` NO viven acá** — son orquestación de
  *pedidos* (recalculan `alquileres.monto_total`/`alquiler_items.subtotal`, se disparan también por cambios
  de fecha/ítems, no solo de descuento), y quedan en `routes/alquileres/core.py`. Moverlas invertiría la
  dirección de dependencia (`descuentos/` importando de un módulo de rutas) sin ganar nada — este paquete
  las consume solo indirectamente, vía `obtener_descuento_jornadas`.
- **`services/precios.py::calcular_total` no se mueve acá.** Es el motor de TOTALES (subtotal/IVA/neto,
  también combos) — consume las funciones de `descuentos/queries/decision.py` para la porción de descuento,
  pero el resto de su trabajo no es de este dominio.
- **Jerarquía de 3 niveles (Fase C-1, #1219):** un override manual del pedido (≠0) gana *outright* (sin
  competir por tamaño) sobre cliente/jornadas; si es 0, cae al 2-way de siempre. `resolver_descuento_pedido`/
  `resolver_origen_pedido` se COMPONEN sobre `calcular_descuento_aplicable`/`calcular_descuento_origen` (no
  las reemplazan). Requirió un snapshot nuevo, `alquileres.descuento_cliente_pct` (mismo patrón que
  `descuento_jornadas_pct`) — sin él, el desglose de un pedido confirmado divergiría de `monto_total` si el
  cliente cambia de descuento después (clase de bug #405). Migración de backfill
  (`v9w0x1y2z3a4`) mueve todo `descuento_pct` histórico ≠0 a `descuento_cliente_pct` y resetea el manual a 0
  — preserva el % mostrado de los pedidos preexistentes (identidad algebraica, ver el docstring de la
  migración; hallazgo del supervisor en PR #1220, no tenerlo hubiera roto pedidos viejos con descuento).
- **Descuento manual en % o en $ fijo (Fase C-2, #1219):** mismo campo del builder de pedidos, un selector al
  lado (`alquileres.descuento_manual_tipo`/`descuento_manual_monto`). `resolver_descuento_monto_pedido`
  resuelve el monto en pesos (capeado al bruto DESCONTABLE, no al bruto total — ver C-3) y deriva el %
  efectivo para mostrar; con tipo="pct" es byte-idéntico al cálculo de C-1.
- **Combos no acumulables con el descuento global (Fase C-3, #1219)** — decisión de *composición de precio
  por línea*, vive en `services/precios.py::calcular_total`/`bruto_linea` (no en este paquete): las líneas
  `es_combo=True` quedan afuera del bruto que alimenta la jerarquía de arriba. `tipos_equipo_batch`
  (`services/precios.py`) resuelve qué líneas son combo, batch, sin N+1. Limitación aceptada: `es_combo` se
  resuelve EN VIVO del `tipo` actual del equipo (no hay snapshot por línea) — si un equipo se reclasifica de
  combo↔simple después de que un pedido confirmado lo usó, ese desglose puede moverse (muy baja probabilidad).

El supervisor marca: lógica de decisión de descuento reimplementada fuera de `descuentos/queries/decision.py`,
un `commands/` importado desde `queries/`, `_recalcular_total_pedido`/`propagar_descuento_a_presupuestos`
movidas acá sin una razón nueva que invalide la nota de arriba, un descuento global aplicado a una línea de
combo, o una competencia por tamaño reintroducida entre el override manual y cliente/jornadas.
