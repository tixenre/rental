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
    decision.py         # calcular_descuento_aplicable (PURA), calcular_descuento_origen (PURA)
    jornadas.py           # interpolar_descuento_jornadas (PURA), obtener_descuento_jornadas,
                           # listar_descuentos_jornada, obtener_descuento_jornada_por_jornadas
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
  también combos) — consume `calcular_descuento_aplicable` para la porción de descuento, pero el resto de
  su trabajo no es de este dominio.

## Roadmap (documentado, no implementado — ver `docs/DECISIONES.md` para el detalle completo)

- **Jerarquía manual > cliente/jornadas:** un override manual del pedido (≠0) va a ganar *outright* (sin
  competir por tamaño); si es 0, cae al 2-way de siempre entre cliente y jornadas. Se compone SOBRE
  `calcular_descuento_aplicable` (no la reemplaza) con una función nueva, `resolver_descuento_pedido`.
- **Descuento manual en % o en $ fijo**, en el mismo campo del builder de pedidos.
- **Combos no acumulables con el descuento global** — decisión de *composición de precio por línea*, vive en
  `services/precios.py::calcular_total`/`bruto_linea`, no en este paquete.

El supervisor marca: lógica de decisión de descuento reimplementada fuera de `descuentos/queries/decision.py`,
un `commands/` importado desde `queries/`, o `_recalcular_total_pedido`/`propagar_descuento_a_presupuestos`
movidas acá sin una razón nueva que invalide la nota de arriba.
