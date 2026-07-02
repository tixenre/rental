# Sistema: Plata — mapa cruzado de todos los motores que tocan dinero

> Manual técnico **cruzado** (fuente única del **cómo se conecta la plata entre motores**).
> Cada motor individual ya tiene su propio manual/invariantes (`backend/contabilidad/CLAUDE.md`,
> `backend/reservas/CLAUDE.md`, `docs/SISTEMA_FACTURACION.md`, `docs/SISTEMA_CARRITO.md`) — **este
> doc no los repite**, los referencia y muestra cómo encajan. Las reglas de criterio y el _porqué_
> viven en `MEMORIA.md`/`DECISIONES.md`. Índice maestro en `MANIFIESTO.md` §8.
>
> **Origen:** nace de la auditoría 2026-07-02 (post fix #405 + auditoría de `contabilidad/`), a
> pedido del dueño ante el miedo de "drift de plata" — demasiados lugares tocan dinero y no había
> un mapa único de quién gobierna qué número. Verificado con 6 auditorías paralelas sobre los
> motores no cubiertos por la auditoría de `contabilidad/` (precios ×2, reportes/liquidación,
> facturación, el camino de congelamiento de precio, y un trace end-to-end + estado de la
> reconciliación) — y descubrió, de paso, que el fix original del bug #405 (#1181) nunca se
> mergeó a `dev`/`main`.

## Qué resuelve

Nadie recalcula "el mismo número" dos veces por caminos independientes. Cada pregunta de plata
tiene **un solo motor dueño**; el resto **consume**, nunca reimplementa.

## Fuente única de cada número

| Pregunta | Motor dueño | Función/archivo | Quién consume |
| --- | --- | --- | --- |
| ¿Cuánto cuesta un ítem por jornada? | `backend/services/precios.py` | `precio_jornada_efectivo` | cotizar, crear, editar, carrito (`readiness.py`), catálogo (listado/ficha) |
| ¿Cuál es el total de un pedido (al cotizar)? | `backend/services/precios.py` | `calcular_total` | `/api/cotizar`, creación, portal cliente |
| ¿Cuál es el total YA CONFIRMADO de un pedido? | `alquileres.monto_total` | snapshot congelado (`_apply_pedido_items`/`_recalcular_total_pedido`, `routes/alquileres/core.py`) | detalle de pedido, reportes, facturación — **nunca se recalcula contra catálogo** |
| ¿Cuánto se cobró de un pedido? | `alquiler_pagos` | única tabla (`routes/alquileres/pagos.py`) | `monto_pagado` (cache derivado), liquidación, contabilidad |
| ¿Hay stock/está disponible? | `backend/reservas/` | motor sagrado | gate único `create_pedido_retry` |
| ¿Qué % de lo facturado es de Rambla vs. de un dueño de equipo? | `backend/reportes/liquidacion.py` + `comisiones.py` | `liquidar`, `repartir` | `contabilidad` (`partes_socios`, llama literal a `liquidar`), reporte mensual |
| ¿Cuánta plata tiene Rambla en sus cajas / cuánto le debe cada socio? | `backend/contabilidad/` | `queries/saldos.py::calcular_saldos` | tablero, reporte mensual |
| ¿La factura discrimina IVA correctamente? | `backend/services/facturacion/` (`docs/SISTEMA_FACTURACION.md`) | `arca_fe/comprobante.py` | deriva de `monto_total`/`iva_monto` ya persistidos — **no recalcula** |
| ¿Qué ve el cliente en pantalla? | — | — | **nunca calcula**: solo renderiza lo que el backend ya resolvió (regla dura, `MEMORIA.md` 2026-06-29) — con **una excepción confirmada**, ver Hallazgos |

## Los motores (referencia, no reimplementación)

- **`backend/reservas/`** — disponibilidad/stock/overlap. Sagrado, `contabilidad`/`reportes` no lo tocan.
- **`backend/services/precios.py`** — precio por jornada/combo/total. Único resolutor; 4 call-sites
  reales lo llaman (`core.py:854,1024,259`, `cotizacion.py:140`), ninguno reimplementa la fórmula.
- **`backend/services/carrito/`** (`docs/SISTEMA_CARRITO.md`) — la intención del cliente; pide precio
  a `precios`, hace handoff a `create_pedido_retry`. No decide plata ni stock.
- **`alquiler_pagos`** (`routes/alquileres/pagos.py`) — el cobro. Actor + soft-delete desde la
  auditoría de `contabilidad` (2026-07-02): `created_by`/`anulado`/`anulado_por`/`anulado_motivo`.
- **`backend/reportes/`** (`CLAUDE.md` propio) — liquidación (reparto de comisiones por dueño de
  equipo) + su propio cierre mensual (`liquidacion_cierres`, **distinto** del cierre de
  `contabilidad`) + reconciliación (semáforo, ver abajo).
- **`backend/contabilidad/`** (`CLAUDE.md` propio) — la plata interna: cajas, cuenta corriente de
  socios, movimientos, P&L, su propio cierre mensual (`movimientos` bloqueados). **Consume**
  `reportes.liquidacion.liquidar()` para `partes_socios` — no recalcula el reparto.
- **`backend/services/facturacion/`** (`docs/SISTEMA_FACTURACION.md`) — Factura A/B/C, IVA, ARCA.
  Deriva de `monto_total`/`iva_monto` ya persistidos; la Nota de Crédito usa el snapshot de la
  factura ORIGINAL (no el pedido en vivo), para no quedar descuadrada ante ARCA si el precio cambió.

## El semáforo de reconciliación (dos capas, ambas 100% manuales)

- `reportes/reconciliacion.py::reconciliar` — `GET /admin/reportes/reconciliacion` (pagados-sin-
  ledger, `monto_pagado` divergente, sobrepagados).
- `contabilidad/queries/reconciliacion.py::reconciliar` — `GET /admin/contabilidad/reconciliacion`
  (saldos negativos, movimientos a cuenta inactiva, pagos sin cobrador válido) — **hereda** el de
  arriba, no lo duplica.

**Ninguno de los dos corre solo.** `backend/jobs/scheduler.py` (el único scheduler in-process del
repo) solo corre `enviar_recordatorios_retiro` y `purgar_cuentas_livianas_stale` — nada de
reconciliación. No hay badge/contador en el dashboard admin. Es la pieza de gobernanza que hoy
**falta** — ver Hallazgos.

## Candados (tests que fijan la garantía)

- `backend/tests/test_contabilidad_db.py` / `test_contabilidad_movimientos.py` — motor de
  contabilidad (soft-delete, candado de mes, validación tipo-cuenta).
- `backend/tests/test_carrito_precio_efectivo.py` — source-scan: los 3 caminos de plata persistida
  (cotizar/crear/modificar) usan `precio_jornada_efectivo`, ninguno reinlinea el switch de combo.
- `backend/tests/test_reportes_cierres_db.py` — cierre de la liquidación.
- Facturación: candados propios en `docs/SISTEMA_FACTURACION.md`.

## Hallazgos de la auditoría cruzada (2026-07-02) — estado: por priorizar con el dueño

Verificado con 6 auditorías paralelas independientes (no solo lectura de código — cruzando
call-sites reales). Priorizado por impacto real, no por tier de origen.

### 🚨 Descubrimiento crítico de proceso (no de código)
**El PR #1181 — el fix ORIGINAL del bug #405 (editor de pedidos cotizando con precio de catálogo en
vez del precio de línea congelado) — nunca se mergeó.** Sigue **abierto, sin tocar `dev` ni `main`**
(confirmado: `respetar_precio_item` no existe en ningún branch real, solo en la rama de PR sin
mergear). El registro en `MEMORIA.md`/`DECISIONES.md` lo daba por shippeado — era incorrecto. **El
bug #405 está potencialmente activo en producción hoy mismo.** Mergeable state: `clean`. Prioridad
máxima: mergear #1181 antes que cualquier otra cosa de esta lista.

### Bugs reales (activos hoy)
1. **`_enriquecer_pedido_con_total` (`routes/alquileres/core.py`) ignora `cobro_modo`** — ALTO. Una
   línea personalizada `cobro_modo='fijo'` (ej. flete, no debe multiplicarse por jornadas, #805) se
   multiplica igual por jornadas en este desglose de *display*. Se usa en **6 lugares reales**: detalle
   de pedido (admin y portal cliente), 2 generadores de PDF, y **`services/facturacion/engine.py`** —
   el motor de facturación real puede mostrar/facturar un desglose incorrecto para pedidos con líneas
   "fijo" + jornadas > 1. `monto_total` persistido (el que se cobra) sigue siendo correcto — es el
   desglose que se MUESTRA/factura el que puede no cuadrar. `test_alquiler_detail_desglose.py` no
   tiene ningún caso con `cobro_modo='fijo'` — gap de test real.
2. **Mismo bug en el PDF** — `pdf_templates.py` (fila de subtotal del presupuesto) multiplica
   `precio_jornada × cantidad × jornadas` sin mirar `cobro_modo` — un cliente puede ver la fila
   "Flete" no sumar con el total del PDF.
3. **`routes/facturacion.py` (`enviar_mail_factura`)** — consulta `c.owner_email`, columna que **no
   existe** en `clientes` (vive en otra tabla). Rompe con `UndefinedColumn` cada vez que un admin usa
   "enviar factura por mail". Sin test que lo cubra. Fix trivial: `c.owner_email` → `c.email`.
4. **`reportes/liquidacion.py::filas_atribucion`** — si `suma_items = 0` pero `monto_total > 0` (ítems
   con subtotal 0, ej. 100% descuento a nivel ítem), el prorrateo da `NULL` → se trata como 0 → la
   plata de ese pedido **desaparece en silencio** del reporte de liquidación, sin que ningún chequeo
   de reconciliación lo detecte. Edge case raro, pero real.
5. **Front — 3 lugares reimplementan el cálculo de línea en vez de leer lo que ya calculó el
   backend** (viola "el front no calcula plata", 2026-06-29):
   - `PedidoPageCards.tsx` vs `PedidoPageHelpers.tsx` (editor admin) — **ya divergidas**: Cards ignora
     `cobro_modo`, Helpers sí lo respeta.
   - `CartDrawerView.tsx`/`CartMiniBarView.tsx` (carrito público) — recalculan el desglose con
     `pricePerDay` cacheado del store en vez de usar el helper `lineaPorEquipo()` que **ya existe**
     para esto (`lib/cotizacion.ts`) — puede divergir si el precio cambió y el store quedó stale.
   - En los 3 casos lo persistido/cobrado sigue siendo correcto — es el número que se MUESTRA el que
     puede no coincidir.
6. **`frontend/src/lib/pricing.ts`** — TODO explícito en el código dice "por ahora es lineal, sin
   descuentos" (#73) pero el backend YA implementó descuentos hace tiempo. Se usa en `PriceBlock`
   (la pieza canónica de precio del catálogo, `equipment/shared/`) — el precio que ve el cliente en
   la card/ficha **no incluye descuentos**, mientras el total real al cotizar/confirmar sí. Puede ser
   intencional ("precio de lista" vs. "precio final"), pero vale la pena que el dueño lo confirme —
   hoy es discrepancia visual entre catálogo y checkout.

### Bug dormido (no activo hoy, pero listo para revivir)
7. **`PedidoPage.tsx` (editor de pedido del portal CLIENTE)** — mismo patrón que el bug original
   #405: no usa `respetarPrecioItem: true`, recotiza contra catálogo en vez del precio de línea
   congelado. Hoy inalcanzable porque `MODIFICAR_PEDIDOS_HABILITADO = false`
   (`frontend/src/lib/features.ts`). Si ese flag se reactiva alguna vez, revive el bug en el portal
   cliente — **y dado que #1181 tampoco se mergeó, el editor ADMIN también sigue expuesto hoy**.

### Robustez / concurrencia (mismo patrón ya arreglado en `contabilidad`, sin mitigar acá)
8. **`reportes/cierres.py::cerrar_mes`** — sin `pg_advisory_xact_lock` contra escrituras concurrentes
   de `alquiler_pagos` del mismo mes. Mismo tipo de carrera que se cerró en `contabilidad` (2026-07-02)
   — acá solo hay detección reactiva (`mes_cerrado_desactualizado`), no un candado preventivo.
9. **Reconciliación 100% manual** (ver arriba) — el riesgo de gobernanza más directo: nada avisa
   proactivamente si algo se desincroniza.

### Seguridad / limpieza (bajo impacto, documentado para no perderlo)
10. `routes/reportes.py` — sin `@limiter.limit` en los endpoints de escritura (cerrar/reabrir mes,
    enviar mail) — mismo gap ya cerrado en `contabilidad.py`/`pagos.py`.
11. `/api/cotizar`, rama de línea personalizada (`equipo_id=None`) — no chequea `es_admin` en ese
    punto específico del código (aunque los endpoints que sí persisten ya exigen `require_admin` por
    fuera). Bajo riesgo real hoy; vale la pena que quede explícito si se toca ese código.
12. **N+1 en 2 caminos que resuelven precio por ítem** — `services/carrito/readiness.py` (creación
    real de pedido del cliente, no solo preview) y `services/carrito/activos.py` (heartbeat del
    carrito, se llama en cada autosave) — ninguno usa `precios_combo_batch`, que ya existe y evita
    exactamente este patrón en el catálogo. El de `/api/cotizar` es DELIBERADO (revertido un batch
    tras causar totales en $0 en prod, incidente #643) — ese no es un hallazgo, es una decisión.
13. `ingresos_derivados` (contabilidad) vs. `SALDADO_CTE` (liquidación) — dos queries SQL
    independientes sobre `alquiler_pagos` (percibido vs. devengado, intencional) que podrían divergir
    si el criterio de filtrado de una cambia sin replicarse en la otra. Documentado, no roto hoy.
14. **`PedidoItem.precio_jornada` sin guardarraíl propio** — la garantía "el cliente no decide el
    precio" depende 100% de que el caller use el resolutor correcto (hoy los 2 callers de cliente lo
    hacen bien), no de un candado mecánico en el modelo. Candidato a un test source-scan como
    `test_carrito_precio_efectivo.py`, pero para "todo constructor de `PedidoItem` pasa por un
    resolutor de precio conocido".

**Lo que está BIEN hecho (confirmado, no solo ausencia de bug):** comisiones con `validar_modelo`
que fuerza sumar 100%; `SALDADO_CTE` ya filtra `NOT anulado`; IVA en `Decimal` con `assert
total==neto+iva`; sin secretos hardcodeados en facturación (`ARCA_MASTER_KEY` por env, certs con
Fernet); sin IDOR en factura de cliente; `create_pedido_retry` persiste la plata de forma atómica
(una transacción, un commit); el cliente portal descarta el precio que manda el body y resuelve
100% server-side con gate `visible_catalogo`; cotas de `descuento_pct`/`cantidad` en múltiples capas
(clamp 1-999 en 3 lugares espejados, `descuento_pct` 0-100 en Pydantic Y en la fórmula pura); `IVA`
calculado sobre el neto post-descuento, no sobre el bruto (regresión #502 cubierta por test);
`test_carrito_precio_efectivo.py` hace *source-scan* real (no solo unit test) verificando que
ningún consumidor reinlinea el switch de combo — candado poco común de ver, efectivo contra el
drift #635; el N+1 de `/api/cotizar` es un trade-off DELIBERADO y documentado (revertido tras un
incidente real en prod), no un descuido.

---

_Reglas/criterio en MEMORIA: **auditoría cruzada de plata (2026-07-02, a proponer)**. Motores
referenciados: `backend/contabilidad/CLAUDE.md`, `backend/reservas/CLAUDE.md`,
`docs/SISTEMA_FACTURACION.md`, `docs/SISTEMA_CARRITO.md`. Iniciativa: #1184 (fase 3)._
