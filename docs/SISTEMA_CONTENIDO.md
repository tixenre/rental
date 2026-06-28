# Sistema: Contenido de producto — "qué incluye un kit/combo"

> Manual técnico (fuente única del **cómo funciona**). Las reglas de criterio y el
> _porqué_ viven en `MEMORIA.md`/`DECISIONES.md` y se **linkean**, no se copian.
> Índice maestro en `MANIFIESTO.md` §8.

## Qué resuelve

Un **único lugar** que responde "¿qué trae este kit/combo?" para **mostrar**
(catálogo, ficha, documentos). Antes esa lista se armaba en ~6 lugares con queries
sueltas contra `kit_componentes` → riesgo de drift. Ahora todos derivan de la misma
fuente que el motor **reserva**, así **lo mostrado no se desincroniza de lo
reservado** — por construcción, no por sincronizar copias.

## La puerta (`backend/services/contenido/`)

- **`contenido_de(conn, equipo_id, solo_activos=True)`** y
  **`contenido_de_batch(conn, equipo_ids, solo_activos=True)`** (`contenido.py`):
  devuelven los componentes **directos (1 nivel)** de un kit/combo, decorados con
  los campos de equipo que cualquier consumidor necesita (superset). Dicts con la
  forma de `ComponenteContenido` (`modelos.py`).
- **Solo lectura.** Emite SELECTs; no toma locks ni transacciones. NO toca el motor
  de reservas.
- **`solo_activos`** (filtro de soft-delete) **no es universal**:
  - `True` (catálogo/ficha): un componente retirado (`eliminado_at`) **no** se
    muestra.
  - `False` (documentos/detalle de pedido): se muestran **todos** los componentes
    que la receta referencia — un remito de un pedido existente debe reflejar lo
    que lleva, aunque una pieza se haya dado de baja después.

### Granularidad: display ≠ stock

La puerta devuelve componentes **directos (1 nivel)** — "este combo trae este kit".
El **gate de reservas** (`backend/reservas/`), en cambio, expande **recursivamente
hasta las hojas** para el stock. Son granularidades distintas, las dos correctas.
La garantía no es "lista idéntica" sino **misma fuente** (`kit_componentes`): el
conjunto de aristas directas de la puerta == el de `reservas.semantics.componentes_de`
(restringido a equipos no retirados). Lo clava `tests/test_contenido_puerta_db.py`.

## Consumidores

Derivan de la puerta (no arman SQL inline de `kit_componentes` para display):

| Consumidor | Superficie | `solo_activos` |
| --- | --- | --- |
| `database/equipos.py::attach_kit` | catálogo (`e.kit`) | `True` |
| `routes/equipos/kit.py::get_kit` | editor de kit (admin) | `False` |
| `routes/equipos/core.py::get_equipo` | ficha | `False` |
| `routes/alquileres/documentos.py::_add_componentes` | albarán/contrato/packing | `False` |

**Excepción documentada:** `routes/alquileres/core.py::_get_alquiler_items` y
`::_batch_get_alquiler_items` (detalle de pedido) devuelven `kc.*` crudo y alimentan
mails/cotización (superficie de plata); su consolidación es follow-up con test
dedicado. El guard de abajo NO las marca.

## Los tres conceptos de "qué incluye" (por tipo)

- **`kit_componentes`** (tabla): la **receta real** — única verdad de lo
  **reservable** para `kit`/`combo`. La lee el motor (stock) y la puerta (display).
- **`contenido_incluido_json`** (`equipo_fichas`): descriptivo manual "qué viene en
  la caja" para equipos `simple` (accesorios no reservables: cable, estuche). **Se
  queda.**
- **`incluye_json`** (`equipo_fichas`): legacy del enriquecimiento IA, **DROPEADO**
  (F5) — quedó muerto en la UI; reemplazado por `kit_componentes`.

## Frontend

El catálogo y la ficha ya derivan de la **receta real** (`e.kit` →
`includes`, en `src/hooks/useEquipos.ts`), renderizada por `IncludesLine` /
`KitSection`. No usan ningún campo descriptivo para los componentes.

## Candados

- `tests/test_contenido_sql_safety.py` (unit): falla si un consumidor migrado
  vuelve a armar SQL inline contra `kit_componentes` (debe derivar de la puerta).
- `tests/test_contenido_puerta_db.py` (integración, Postgres real): misma-fuente
  que el gate, granularidad de 1 nivel, y el filtro `solo_activos`.

## Fronteras (qué NO toca)

- `backend/reservas/` (motor sagrado — stock/overlap/locks): la puerta solo lee.
- `services/precios` (precio del combo): la puerta no lo replica.
- **El Estudio** (`estudio_pack_equipos`): modelo aparte (espacio + pack curado),
  no usa `kit_componentes` → fuera de este sistema.

## Puntos de entrada (código)

- `backend/services/contenido/contenido.py` — la puerta.
- `backend/services/contenido/modelos.py` — `ComponenteContenido`.
- `backend/services/contenido/__init__.py` — API pública.

---

_Reglas/criterio en MEMORIA: motor único de reservas sagrado (2026-05-30/31),
plata/ítems congelados (2026-06-06), esquema en dos capas `init_db`+Alembic
(2026-06-03), guardrail `⏰ LEGACY` (2026-06-25). Iniciativa: issue #1087._
