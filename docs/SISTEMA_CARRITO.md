# Sistema: Carrito — la lógica de "qué quiere reservar el cliente"

> Manual técnico (fuente única del **cómo funciona**). Las reglas de criterio y el
> _porqué_ viven en `MEMORIA.md`/`DECISIONES.md` y se **linkean**, no se copian.
> Índice maestro en `MANIFIESTO.md` §8.
>
> **Estado:** describe el módulo tal como quedó tras el epic #1110 (FASE 1 bug-prod,
> FASE 2 drift de combos, FASE 5 selección única + readiness). Lo que el epic dejó
> **fuera a propósito** (display de plata del front, split del god-module
> `alquileres/core.py`, features de FASE 6) está marcado al final como **pendiente**.

## Qué resuelve

Un **único lugar** para la **lógica** del carrito: la intención del cliente —"esto es
lo que quiero reservar"— desde que arma la selección hasta el handoff a la creación de
la reserva. Antes esa lógica estaba dispersa y **duplicada** (el `_normalizar_items` vivía
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
Submódulos construidos:

| Submódulo | Owna |
| --- | --- |
| `modelos.py` | La **forma** del dato: `SeleccionItem` (Pydantic `{equipo_id:int, cantidad:int}`) + caps únicos `CANTIDAD_MAX=99` / `MAX_ITEMS=200`. Sin lógica. |
| `seleccion.py` | El `normalizar_seleccion(conn, items)` **único** (dedup por `equipo_id` última-cantidad-gana, clamp `1..CANTIDAD_MAX`, filtro a equipos existentes vía `SELECT id ... WHERE id = ANY(%s)`, cap `MAX_ITEMS`, preserva orden) + helpers de proyección a `items_json` (dicts) y a tuplas `(eid, cant)` para los INSERT de listas. |
| `activos.py` | Carritos activos/abandonados: heartbeat upsert por `session_id`, enrichment de ítems + monto estimado, estampado de abandono (`ABANDONO_HORAS=24`), `marcar_confirmado`, y las agregaciones del dashboard admin (stats/demanda/por-día). Casa de la futura recuperación (#1111). |
| `readiness.py` | "Carrito listo para reservar" (lado plata): `precios_catalogo_para_reserva(conn, items)` resuelve el precio de cada ítem con el gate de seguridad (solo `visible_catalogo`, el cliente no decide el precio) vía el resolutor único; **404** si un ítem no es del catálogo. **No crea** la reserva — el route hace el handoff a `create_pedido_retry` con esos precios. |
| `__init__.py` | API pública (fachada). Único punto de import para los routes. |

- **Solo lectura sobre lo sagrado.** El módulo emite SELECTs de su propio estado y
  **lee** disponibilidad/precio/contenido; no toma los locks de reservas ni reimplementa
  el gate. La creación real (con advisory-lock) la hace `create_pedido_retry`.

## Owna vs Referencia

**OWNA** (vive acá, fuente única):

1. **La SELECCIÓN canónica** `{equipo_id, cantidad}` + el `normalizar_seleccion` único +
   los caps + los helpers de `items_json`. Consolida las formas hoy divergentes
   (`CartItem`, `CompartirItemIn`, `ListaItemIn`) en una sola forma de ítem.
2. **Carritos activos/abandonados**: heartbeat, enrichment, abandono, funnel admin,
   `marcar_confirmado`, y la futura recuperación #1111.
3. **Readiness** "carrito listo para reservar" (lado plata): resolver el precio de cada
   ítem con el gate (`visible_catalogo` + el cliente no decide el precio) antes del
   **handoff** a `create_pedido_retry` (NO se come la creación).

**REFERENCIA** (usa, NO owna ni reimplementa):

| Motor | Para qué | Frontera |
| --- | --- | --- |
| `backend/reservas/` (`calcular_disponibilidad`, `validar_stock`, `semantics`) | Stock / disponibilidad / overlap. **SAGRADO.** | Solo se **lee**. El conflicto de stock del dashboard se lo pide; no lo reimplementa. Candado AST `test_gate_not_bypassed` intacto. |
| `backend/services/precios` (`calcular_total`, `precio_combo`, `precio_jornada_efectivo`, `jornadas_periodo`, `bruto_linea`) | Toda la plata. El carrito **pide** el total/precio, no lo calcula. | El **switch** `tipo=='combo' → precio_combo() else precio_jornada` vive en **precios** como `precio_jornada_efectivo(conn, equipo_id)`; readiness y cotizar lo **consumen**. El TOTAL canónico (`cotizacion.py`) NO se reabre. |
| `backend/services/contenido/` (`contenido_de`, `ComponenteContenido`) | Qué incluye un kit/combo para mostrar. | Vecino, no se mezcla: el carrito muestra contenido **pidiéndoselo** a la puerta, no derivando `kit_componentes`. |
| `create_pedido` / `create_pedido_retry` (`routes/alquileres/core.py`) | La creación REAL de la reserva con advisory-lock. | El route hace el **handoff** (arma `PedidoCreate` con los precios que devuelve readiness y delega); NADIE copia ni toca el `FOR UPDATE`/advisory-lock. `_recalcular_total_pedido`/`_apply_pedido_items` quedan donde están. |

### Invariante de plata: cotizado == cobrado (la corrección de combo)

El precio por jornada de un ítem lo resuelve **una sola función**,
`precios.precio_jornada_efectivo(conn, equipo_id)` (combo → `precio_combo()`; kit/simple →
`equipos.precio_jornada`; `None` si no existe). Los **tres** caminos que ponen la plata que
se persiste la consumen: **cotizar** (`cotizacion.py`), **crear**
(`readiness.precios_catalogo_para_reserva`, que usa `cliente_crear_pedido`) y **modificar**
(`cliente_modificar_pedido` vía `_equipo_precio_catalogo`). Antes solo `cotizar` derivaba el
combo; `crear` y `modificar` persistían el `precio_jornada` crudo → el total mostrado no
coincidía con el cobrado en combos. Ahora **lo que el carrito cotiza es lo que se persiste**,
en los tres caminos.

## Consumidores (routes finos)

| Route | Delega en | Qué BAJÓ al módulo |
| --- | --- | --- |
| `routes/carritos.py` | `heartbeat_upsert`, `listar_carritos_admin`, `marcar_confirmado` (`activos`) | upsert SQL, enrichment, abandono, stats/demanda/por-día |
| `routes/compartir.py` | `normalizar_seleccion`, `a_items_json`, `desde_items_json` (`seleccion`) | el `_normalizar_items` propio (**eliminado**) + los caps |
| `routes/cliente_portal/listas.py` | `normalizar_seleccion`, `a_tuplas` (`seleccion`) | el `_normalizar_items` propio (**eliminado**) + los caps |
| `routes/cliente_portal/pedidos.py` | `precios_catalogo_para_reserva` (`readiness`) + handoff a `create_pedido_retry` | la resolución de precios + el gate `visible_catalogo` |
| `routes/cliente_portal/solicitudes.py` | `precio_jornada_efectivo` (`precios`) en `_equipo_precio_catalogo` | la resolución de precio del path de **modificación** (fix combo #2) |
| `routes/alquileres/cotizacion.py` | `precio_jornada_efectivo` (`precios`) para la rama combo | nada más (el TOTAL no se reabre) |

`compartir.py` y `listas.py` adoptan la **forma única del ítem** (el normalizador), pero
**conservan su propia lógica** de token/snapshot (compartir) y CRUD/scope (listas) y sus
**tablas propias** — no se unifican (ciclos de vida distintos; decisión del epic). Los **caps
de negocio** propios de cada superficie quedan en su route: `TITULO_MAX`/`TOKEN_BYTES`
(compartir), `NOMBRE_MAX`/`MAX_LISTAS` (listas), notas 500 / rango 120 días (límites del
cliente, en la capa cliente, no en `create_pedido`).

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
- `backend/services/carrito/readiness.py` — `precios_catalogo_para_reserva` (gate + handoff).
- `backend/services/precios.py::precio_jornada_efectivo` — resolutor único de precio por ítem.

## Candados

- `tests/test_carrito_seleccion.py` (unit, sin DB): dedup / clamp / filtro / cap / orden +
  las proyecciones del normalizador único.
- `tests/test_carrito_normalizar_safety.py` (unit): los consumidores migrados (compartir,
  listas) **no** redefinen el normalizador ni arman el SQL del filtro de equipos inline.
- `tests/test_carrito_precio_efectivo.py` (unit): el resolutor (combo/simple/inexistente/
  nulo) **+ source-scan** de que los tres caminos de plata persistida usan
  `precio_jornada_efectivo` y ninguno re-inlinea `precio_combo()` ni el SELECT de la rama de
  combo. La paridad **cotizado == cobrado** queda garantizada **por construcción** (un solo
  resolutor) — no hace falta un test de DB que compare "la misma función con la misma función".

## Pendiente (fuera de este epic, a tomar como trabajo propio)

- **FASE 3 — display de plata (front).** El `CartDrawer` y los teasers inline recalculan el
  estimado por jornada a mano (redondeo propio) en vez de derivarlo del desglose de
  `/api/cotizar`. Consolidar en un helper único `lib/pricing.ts`. Es del **front** (el módulo
  es backend-only); no reabre el invariante de plata, solo unifica el **display**.
- **Split de `routes/alquileres/core.py`** (god-module ~1057 líneas) en cortes move-verbatim
  de piezas **periféricas** (emails, enriquecer), 1 PR por corte, **sin tocar**
  create_pedido/advisory-lock. **Es lógica de `alquileres`, no del carrito** (se tocan, pero es
  otro motor; aclaración del dueño 2026-06-29) → su propio PR/iniciativa, con el supervisor.
- **FASE 6 — features** (recuperación de abandonado #1111, unificar agregar-vs-reemplazar
  #1108): definir alcance con el dueño antes de construir.

---

_Reglas/criterio en MEMORIA: **motor único de la lógica del carrito (2026-XX-XX, a proponer)**,
motor único de reservas sagrado (2026-05-30/31), creación concurrente con advisory-lock
(2026-06-22), plata/ítems congelados (2026-06-06), puerta única de contenido (2026-06-29),
notificaciones canal-agnósticas (2026-05-27), esquema en dos capas `init_db`+Alembic
(2026-06-03), DAL `database/core.py` (2026-06-27). Epic: issue #1110; recuperación #1111;
agregar-vs-reemplazar #1108._
