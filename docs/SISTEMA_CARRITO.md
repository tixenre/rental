# Sistema: Carrito — la lógica de "qué quiere reservar el cliente"

> Manual técnico (fuente única del **cómo funciona**). Las reglas de criterio y el
> _porqué_ viven en `MEMORIA.md`/`DECISIONES.md` y se **linkean**, no se copian.
> Índice maestro en `MANIFIESTO.md` §8.
>
> **Estado:** este manual describe el **estado-target** del módulo (epic #1110). Las
> secciones marcadas **[YA-CIERTO]** describen lo que el repo hace hoy; las marcadas
> **[TARGET]** describen lo que el epic consolida. Se actualiza fase por fase.

## Qué resuelve

Un **único lugar** para la **lógica** del carrito: la intención del cliente —"esto es
lo que quiero reservar"— desde que arma la selección hasta el handoff a la creación de
la reserva. Antes esa lógica estaba dispersa y **duplicada** (el `normalizar_items` vivía
byte-por-byte en `routes/compartir.py` y `routes/cliente_portal/listas.py`, con los caps
copiados; el precio de un combo se cotizaba con `precio_combo()` pero se **persistía** con
`equipos.precio_jornada` crudo → total mostrado ≠ cobrado). El módulo cierra ese drift por
**construcción**: una sola forma del ítem, una sola validación, una sola fuente de la plata.

### El invariante raíz: carrito = intención, gate = verdad

El carrito **expresa la intención** del cliente (qué equipos, cuántos, qué fechas). **No
decide nada de lo que es verdad del sistema**: la **disponibilidad/stock** la dicta el motor
sagrado (`backend/reservas/`), la **plata** la dicta el motor de precios
(`backend/services/precios`), y el **qué-incluye-un-kit** lo dicta la puerta de contenido
(`backend/services/contenido/`). El carrito **pide**, no **calcula**; y para reservar de
verdad hace **handoff** a `create_pedido_retry` (no se come la creación). Si el carrito y el
gate discrepan, **gana el gate** — el carrito es una propuesta hasta que el gate la confirma.

## La casa (`backend/services/carrito/`)

Patrón del repo: **route = transporte, service = lógica** (como `routes/alquileres` ↔
`backend/reservas`, `routes/* ↔ backend/contabilidad`/`reportes`/`services.contenido`).
`routes/carritos.py`, `routes/compartir.py` y `routes/cliente_portal/listas.py` quedan
**finos** (parsean, autentican, arman la respuesta HTTP) sobre el módulo. Submódulos:

| Submódulo | Owna | Estado |
| --- | --- | --- |
| `modelos.py` | La **forma** del dato: `SeleccionItem` (Pydantic `{equipo_id:int, cantidad:int}`) + caps únicos `CANTIDAD_MAX=99` / `MAX_ITEMS=200`. Sin lógica (recibe-conn, espeja `contenido/modelos.py`). | [TARGET] |
| `seleccion.py` | El `normalizar_seleccion(conn, items)` **único** (dedup por `equipo_id` última-cantidad-gana, clamp `1..CANTIDAD_MAX`, filtro a equipos existentes vía `SELECT id ... WHERE id = ANY(%s)`, cap `MAX_ITEMS`, preserva orden) + helpers de proyección a `items_json` (dicts) y a tuplas `(eid, cant)` para los INSERT de listas. | [TARGET] |
| `activos.py` | Carritos activos/abandonados: heartbeat upsert por `session_id`, enrichment de ítems + monto estimado, estampado de abandono (`ABANDONO_HORAS`), `marcar_confirmado`, y las agregaciones del dashboard admin (stats/demanda/por-día). Casa de la futura recuperación (#1111). | [TARGET] |
| `compartido.py` | Lógica de compartir link/snapshot (crear con token único, traer-para-rearmar, sumar vista, `clean_titulo`). Mantiene su tabla `carritos_compartidos`. | [TARGET] |
| `listas.py` | Lógica de listas/kits guardados del cliente (CRUD + proyección canónica, scope por `cliente_id`, cap `MAX_LISTAS`). Mantiene sus tablas `cliente_listas`/`cliente_listas_items`. | [TARGET] |
| `readiness.py` | Orquesta "carrito listo para reservar": validar items + fechas + **pedir** disponibilidad (a `reservas`) + **pedir** precio (a `precios`) + **handoff** a `create_pedido_retry`. Puerta única del gate "el cliente no decide precio" + "solo `visible_catalogo`". | [TARGET] |
| `__init__.py` | API pública (fachada). Único punto de import para los routes. | [TARGET] |

- **Solo lectura sobre lo sagrado.** El módulo emite SELECTs de su propio estado y
  **lee** disponibilidad/precio/contenido; no toma los locks de reservas ni reimplementa
  el gate. La creación real (con advisory-lock) la hace `create_pedido_retry`.

## Owna vs Referencia

**OWNA** (vive acá, fuente única):

1. **La SELECCIÓN canónica** `{equipo_id, cantidad}` + el `normalizar_seleccion` único +
   los caps + los helpers de `items_json`. Consolida las TRES formas hoy divergentes
   (`CartItem`, `CompartirItemIn`, `ListaItemIn`). **[TARGET]**
2. **Carritos activos/abandonados**: heartbeat, enrichment, abandono, funnel admin,
   `marcar_confirmado`, y la futura recuperación #1111. **[TARGET]**
3. **Compartir** (link/snapshot) — lógica; mantiene su tabla. **[TARGET]**
4. **Listas/kits guardados** — lógica; mantiene sus tablas. **[TARGET]**
5. **Readiness** "carrito listo para reservar": orquestar validación + disponibilidad +
   precio y el **handoff** a `create_pedido_retry` (NO se come la creación). **[TARGET]**

**REFERENCIA** (usa, NO owna ni reimplementa):

| Motor | Para qué | Frontera |
| --- | --- | --- |
| `backend/reservas/` (`calcular_disponibilidad`, `validar_stock`, `semantics`) | Stock / disponibilidad / overlap. **SAGRADO.** | Solo se **lee**. El conflicto de stock del dashboard y el chequeo de readiness lo piden; no lo reimplementan. Candado AST `test_gate_not_bypassed` intacto. |
| `backend/services/precios` (`calcular_total`, `precio_combo`, `precio_jornada_efectivo`, `jornadas_periodo`, `bruto_linea`) | Toda la plata. El carrito **pide** el total/precio, no lo calcula. | El **switch** `tipo=='combo' → precio_combo() else precio_jornada` vive en **precios** como `precio_jornada_efectivo(conn, equipo_id)`; carrito y cotizar lo **consumen**. El TOTAL canónico (`cotizacion.py`) NO se reabre. |
| `backend/services/contenido/` (`contenido_de`, `ComponenteContenido`) | Qué incluye un kit/combo para mostrar. | Vecino, no se mezcla: el carrito muestra contenido **pidiéndoselo** a la puerta, no derivando `kit_componentes`. |
| `create_pedido` / `create_pedido_retry` (`routes/alquileres/core.py:697,803`) | La creación REAL de la reserva con advisory-lock. | El readiness hace el **handoff** (arma `PedidoCreate` con precios resueltos y delega); NO copia ni toca el `FOR UPDATE`/advisory-lock. `_recalcular_total_pedido`/`_apply_pedido_items` quedan donde están. |

### Invariante de plata: cotizado == cobrado (la corrección de combo)

**[TARGET]** El precio por jornada de un ítem lo resuelve **una sola función**,
`precios.precio_jornada_efectivo(conn, equipo_id)` (combo → `precio_combo()`; kit/simple →
`equipos.precio_jornada`). Los **tres** caminos client-facing la consumen: **cotizar**
(`cotizacion.py`), **crear** (`cliente_crear_pedido`) y **modificar**
(`cliente_modificar_pedido` vía el reemplazo de `_equipo_precio_catalogo`). **[YA-CIERTO]**
hoy solo `cotizar` deriva el combo; `crear` y `modificar` persisten el `precio_jornada`
crudo → el total mostrado no coincide con el cobrado en combos. Tras el fix: **lo que el
carrito cotiza es lo que se persiste**, en los tres caminos.

## Consumidores (routes finos)

| Route | Queda como transporte; delega en | Qué BAJA al módulo |
| --- | --- | --- |
| `routes/carritos.py` | `heartbeat_upsert`, `listar_carritos_admin`, `marcar_confirmado` | upsert SQL, enrichment, abandono, stats/demanda/por-día |
| `routes/compartir.py` | `crear_compartido`, `get_compartido` (servicio) | `_normalizar_items` (**se elimina**), `_clean_titulo` |
| `routes/cliente_portal/listas.py` | los 6 endpoints → servicio | `_normalizar_items` (**se elimina**), `_clean_nombre`, `_fetch_lista` |
| `routes/cliente_portal/pedidos.py` | `readiness.preparar_para_reserva` + handoff | resolución de precios + gate `visible_catalogo` (con `precio_jornada_efectivo`) |
| `routes/cliente_portal/solicitudes.py` | `_equipo_precio_catalogo` → `precio_jornada_efectivo` | la resolución de precio del path de **modificación** (fix combo #2) |
| `routes/alquileres/cotizacion.py` | `precio_jornada_efectivo` para la rama combo | nada más (el TOTAL no se reabre) |

Los **caps de negocio** propios de cada superficie quedan en su route/servicio:
`TITULO_MAX`/`TOKEN_BYTES` (compartir), `NOMBRE_MAX`/`MAX_LISTAS` (listas), notas 500 /
rango 120 días (límites del cliente, en la capa cliente, no en `create_pedido`).

## Fronteras (qué NO toca)

- `backend/reservas/` (motor sagrado — stock/overlap/locks): solo se **lee**. Candado AST
  `test_gate_not_bypassed` intacto.
- `create_pedido` / `create_pedido_retry` / `_apply_pedido_items` /
  `_recalcular_total_pedido` (advisory-lock, MEMORIA 2026-06-22): quedan donde están; el
  carrito los **llama**, no los reimplementa. El fix de combo cambia **qué precio reciben**,
  no su lógica.
- **El TOTAL del carrito** (`cotizacion.py` ↔ `services/precios.calcular_total`): ya es
  fuente única real (el submit ignora el precio del front). **No se reabre.**
- `backend/services/contenido/`: vecino, no se fusiona.
- **Las 3 tablas NO se unifican** (`carritos_activos` / `carritos_compartidos` /
  `cliente_listas`): ciclos de vida distintos. Sí se unifica la **forma del item** y su
  **validación**.
- La **línea personalizada** del admin (`equipo_id=None` + `nombre_libre` + `cobro_modo`,
  #805): es exclusiva del builder admin de pedidos; el carrito del cliente es **siempre**
  catálogo real → fuera de la selección canónica.

## Puntos de entrada (código)

- `backend/services/carrito/__init__.py` — API pública.
- `backend/services/carrito/seleccion.py` — `normalizar_seleccion` + helpers `items_json`.
- `backend/services/carrito/activos.py` — heartbeat / abandono / funnel.
- `backend/services/carrito/readiness.py` — orquestación + handoff.
- `backend/services/precios.py::precio_jornada_efectivo` — resolutor único de precio por ítem.

## Candados

- `tests/test_carrito_normalizar_safety.py` (unit): los consumidores migrados (compartir,
  listas) **no** redefinen el normalizador ni arman la validación canónica inline.
- `tests/test_carrito_combo_paridad_db.py` (integración, Postgres real): para un combo, el
  precio por jornada de **cotizar** == el de **persistir**, en **crear Y modificar**.
- `tests/test_carrito_reservas_safety.py` (unit, liviano): readiness no reimplementa
  disponibilidad/stock — delega en `reservas`.

---

_Reglas/criterio en MEMORIA: **motor único de la lógica del carrito (2026-XX-XX, a proponer)**,
motor único de reservas sagrado (2026-05-30/31), creación concurrente con advisory-lock
(2026-06-22), plata/ítems congelados (2026-06-06), puerta única de contenido (2026-06-29),
notificaciones canal-agnósticas (2026-05-27), esquema en dos capas `init_db`+Alembic
(2026-06-03), DAL `database/core.py` (2026-06-27). Epic: issue #1110; recuperación #1111;
agregar-vs-reemplazar #1108._
