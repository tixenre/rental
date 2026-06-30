# `services/catalogo/` — motor de catálogo

Puerta única de proyección del "equipo de display": el dict que `/api/equipos`
y `/api/equipos/{id}` sirven al front, armado orquestando los motores que ya
existen.

## Qué orquesta (fuente única de cada pieza)

| Pieza                        | Fuente canónica                              |
|------------------------------|----------------------------------------------|
| Stock / disponibilidad       | `reservas.calcular_disponibilidad`           |
| Kit / contenido              | `services.contenido` (puerta única)          |
| Precios combo                | `services.precios.precios_combo_batch`       |
| Attach tags/categorías/specs | `database/equipos.py` (attach_*)             |
| Búsqueda / ranking           | `busqueda.construir` + `MARCA_SUBQUERY`      |

## Qué NO hace

- **No toca `reservas/`** — solo lee `calcular_disponibilidad` (sin locks,
  sin FOR UPDATE, sin `_expandir_mult`, sin `create_pedido_retry`).
- **No duplica lógica de reservas.** El stock teórico (`_stock_sin_reservas`)
  vive acá como move-verbatim; su optimización es un PR futuro (no tocar
  sin test de regresión).
- **No toca `dataio/`** — ni slug ni columnas de exportación.
- **No accede directo a `kit_componentes`** (va vía `services.contenido`).
  El candado `test_contenido_sql_safety.py` falla si se bypasea.

## Candado C1 (PR-B): `main.py` no hace FROM equipos

Cuando `proyectar_seed` esté adoptado en `main.py`, el test
`test_catalogo_motor_shape.py::TestSeedShape::test_main_no_query_equipos`
verificará que `main._get_initial_catalog` delega en `proyectar_seed` (y
no arma su propio SQL contra `equipos`). Hasta entonces, ambos coexisten.

## Nota de performance: GLOBAL FIXED COST

`calcular_disponibilidad` (cuando se piden fechas) corre UNA sola vez para
TODO el catálogo — costo fijo independiente del tamaño del lote. No llamar
en un loop por equipo.
