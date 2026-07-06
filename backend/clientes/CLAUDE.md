# `backend/clientes/` — cuenta del cliente (consultada por admin y portal)

> Invariantes locales. El _por qué_ completo: `docs/DECISIONES.md` _2026-07-05 — Módulo
> `backend/clientes/` CQRS-lite: cuenta unificada para admin y portal_.

**Todo lo que compone "la cuenta de un cliente" fuera de la identidad y los pedidos en sí
vive acá** (nombre/dirección a mostrar, historial resumido de pedidos, perfiles fiscales +
productoras vinculadas); los routes son solo transporte HTTP. No re-implementar estas
queries ad-hoc en un route nuevo.

**No es un motor de identidad** — eso vive en `identity/` (KYC, verificación Didit/RENAPER,
merge de cuentas). Este paquete lo **consulta**, nunca lo duplica: `queries/identidad.py`
es un wrapper fino sobre `identity.nombre_validado`/`identity.direccion_validada`.

**No es el motor de pedidos** — el historial acá es un resumen liviano para la ficha admin;
el detalle rico de "mis pedidos" del portal (items completos, pagos, desglose, documentos)
sigue siendo dominio de `routes/cliente_portal/pedidos.py`, con otro caso de uso.

## Estructura (CQRS-lite, espeja `contabilidad/` y `descuentos/`)

```
clientes/
  __init__.py       # barrel (docstring, sin __all__ — no hay re-exports públicos)
  queries/            # LECTURA — nunca mutan
    identidad.py        # nombre_legal, direccion_legal — delega en identity/
    fiscal.py             # perfiles_fiscales, productoras_vinculadas, resumen_fiscal
    historial.py            # resumen (pedidos, para la ficha admin)
    cliente.py                 # listar, obtener, duplicados, duplicados_de (CRUD admin — lectura)
  commands/           # ESCRITURA — la única puerta de mutación
    cliente.py          # crear, actualizar, eliminar (soft delete)
```

**Consultado por AMBOS lados**: `routes/clientes.py` (admin, `require_admin`) y
`routes/cliente_portal/cuenta.py` (portal, `require_cliente`) llaman a las MISMAS
funciones de `queries/identidad.py` y `queries/fiscal.py` — cada guard de permisos vive en
el route que llama, no en el módulo (las funciones acá no saben quién las está llamando).

**Invariante commands↔queries**: `commands/` puede importar de `queries/` (ej. `crear`
devuelve `queries.cliente.obtener(...)` para no reconstruir la fila a mano); `queries/`
**nunca** importa de `commands/`.

## Reglas que no se rompen

- **`nombre_legal`/`direccion_legal` se calculan UNA vez**, acá — un consumidor nuevo que
  necesite mostrar "quién es" un cliente importa `clientes.queries.identidad`, no recompone
  `nombre_validado(d) or f"{...}"` a mano.
- **`fiscal.py` siempre trae el superset de columnas** (incluye `email_facturacion` y el
  `domicilio_fiscal` de la productora) — el admin y el portal comparten la query aunque
  cada uno muestre un subconjunto distinto; no bifurcar el SELECT por consumidor.
- **La escritura de perfiles fiscales/productoras (verificación AFIP) NO vive acá** — sigue
  en `services/facturacion/padron.py` (dominio de facturación) y `routes/productoras.py`
  (admin, membership). Este paquete solo lee esas tablas.
- **`commands/cliente.py` levanta `ValueError`** para lo que anticipa (nada-para-actualizar);
  el route lo traduce a `HTTPException`. Lo que se escapa (constraint de Postgres, etc.) lo
  cubre `@map_pg_errors` en el route — no un `except Exception` genérico que filtre el
  mensaje interno de Postgres.
- **`eliminar` es soft delete** (`eliminado_at`, mismo patrón que equipos #206) — nunca un
  `DELETE FROM clientes` físico. `queries.cliente.listar` lo oculta por default;
  `queries.cliente.obtener` NO lo filtra (un pedido viejo puede seguir apuntando a un
  cliente borrado — la ficha admin tiene que poder mostrarlo).

El supervisor marca: un `nombre_validado(d) or f"..."` recompuesto fuera de
`queries/identidad.py`, un SELECT de `cliente_perfiles_fiscales`/`productoras` duplicado
fuera de `queries/fiscal.py`, un `import` de `commands/` dentro de `queries/`, o un `DELETE
FROM clientes` reintroducido en vez de `commands.cliente.eliminar`.
