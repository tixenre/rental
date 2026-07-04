# SISTEMA_CHECKOUT — portero del checkout

> **Fuente única del "cómo funciona" el checkout.** Las reglas de criterio y el
> _por qué_ viven en `MEMORIA.md` y `DECISIONES.md`. Este doc describe qué hace el
> portero, qué puntos de entrada tiene, y cómo se encadena con el motor de reservas.

## Qué es

`backend/services/checkout/` es el **portero del checkout**: valida todas las
precondiciones antes de crear un pedido del cliente. No falla rápido — corre todos
los checks y devuelve la lista completa de lo que falta, para que la UI muestre
exactamente qué hay que resolver.

**No crea pedidos.** La creación sigue siendo exclusiva de `create_pedido_retry`
(`routes/alquileres/core.py`) — advisory lock por equipo, 5 reintentos, motor sagrado.

## Flujo del checkout

```
Cliente → route /api/checkout/validar
    → require_cliente (guard: valida sesión, 401 si no hay)
    → validar_checkout(conn, cliente_id, session_id, firma_ok, es_admin)
        → lee carritos_activos (owner-scoped: session_id + cliente_id)
        → corre los 10 checks
        → retorna {listo, faltan}

Si listo:
    route → create_pedido_retry(conn, ...) [motor sagrado]
```

## Puntos de entrada

| Función | Módulo | Qué hace |
|---|---|---|
| `validar_checkout(conn, cliente_id, session_id, firma_ok, es_admin)` | `services/checkout/validar.py` | Portero principal |
| `ya_acepto(conn, cliente_id, version?)` | `services/checkout/tyc.py` | Consulta T&C |
| `registrar_aceptacion(conn, cliente_id, version?)` | `services/checkout/tyc.py` | Registra aceptación de T&C |

## Contrato de respuesta

```json
{
  "listo": true | false,
  "faltan": [
    {
      "check": "identidad",
      "mensaje": "Necesitás verificar tu identidad antes de hacer un pedido.",
      "accion": "/cliente/identidad"
    }
  ]
}
```

`faltan` es la fuente de verdad de lo que muestra la UI. El campo `accion` es
opcional: una ruta interna o una clave de acción que el front maneja.

## Los 10 checks (en orden de ejecución)

| # | Check | Lógica | Activo |
|---|---|---|---|
| 1 | **identidad** | `clientes.dni_validado_at IS NOT NULL` (vía `auth.guards.cliente_verificado`) | ✅ |
| 2 | **carrito** | ≥ 1 ítem, todos con `visible_catalogo = 1` | ✅ |
| 3 | **fechas** | fecha_desde y fecha_hasta válidas y consistentes; fecha_desde ≥ hoy (no-admin) | ✅ |
| 4 | **stock** | Pre-chequeo READ-ONLY (`reservas.disponibilidad.calcular_disponibilidad`). Estimado — el gate real es `create_pedido_retry`. | ✅ |
| 5 | **precio** | Todos los ítems tienen precio en el catálogo visible (`services.carrito.readiness.precios_catalogo_para_reserva`) | ✅ |
| 6 | **contacto** | Hay un email de contacto (`identity.contacts.email_comunicacion`) | ✅ |
| 7 | **tyc** | Cliente aceptó la versión actual de T&C (`TYC_VERSION_ACTUAL`, tabla `aceptaciones_tyc`) | ✅ |
| 8 | **firma** | `firma_ok = True` (el route computa `has_recent_stepup() OR confirmed_by_session`) | ✅ |
| 9 | **bloqueo** | Flag `bloqueado` en `clientes` | ⏸ cableado-apagado (#1125) |
| 10 | **antelación** | Lead-time mínimo configurable | ⏸ cableado-apagado (#1126) |

### Nota sobre el check de autenticación

El check "logueado" **NO vive en el portero** — lo dueña el guard del route
(`require_cliente`). El portero recibe `cliente_id` ya validado y asume que
la sesión es legítima.

### Nota sobre el stock preflight

El check #4 es READ-ONLY (sin lock `FOR UPDATE`). Puede dar "OK" y que el gate
real falle si otra reserva se concretó entre el check y la creación. Esto es
comportamiento normal de un sistema de reservas concurrente; el gate real
(`create_pedido_retry`) maneja la race condition con advisory lock + retry → 503.

## Robustez: cada check corre aislado (`_run_check`)

Con 10 checks corriendo en secuencia, un bug INESPERADO dentro de uno (no la
falla de negocio que el check ya modela con su propio `_falta` — eso retorna
normal) no debe tirar abajo a los que faltan correr. `_run_check` envuelve
cada llamada:

- Si `fn` levanta cualquier excepción no anticipada, se loguea
  (`logger.exception`) con el **nombre del check + cliente_id + session_id**
  — el contexto para diagnosticar sin tener que reproducir el request.
- Se agrega un `_falta(nombre, "No pudimos validar esto — reintentá en unos
  segundos.")` — **fail-closed**: bloquea el checkout, nunca deja pasar en
  silencio.
- Los checks siguientes en la secuencia **siguen corriendo** — la garantía
  fail-not-fast se mantiene incluso ante una falla inesperada, no solo ante
  faltantes de negocio.

La lectura del carrito (`_leer_carrito` + parseo de `items_json`) tiene la
misma protección: un carrito con JSON corrupto no tira un 500 crudo, se
trata como "carrito en mal estado" (check `carrito`).

**Red residual en el route** (`routes/checkout.py::checkout_validar`): si algo
escapa a `_run_check` (ej. un bug en el propio `validar_checkout`, fuera de
los checks), el route atrapa cualquier excepción, loguea con el mismo
contexto, y devuelve **503** ("No pudimos validar tu pedido. Reintentá en
unos segundos.") — nunca un 500 con detalle interno de Postgres/Python.

## T&C: versionado

La versión actual vive en `TYC_VERSION_ACTUAL = "v1"` (`services/checkout/tyc.py`).
Cuando el texto de los T&C cambie, sube la versión (→ `"v2"`, etc.) y todos los
clientes deberán aceptar de nuevo.

La tabla `aceptaciones_tyc` es inmutable: un registro de aceptación nunca se borra.
Solo se agrega (`ON CONFLICT DO NOTHING`).

## Firma: dos modalidades

El route pre-computa `firma_ok` antes de llamar al portero:

```python
firma_ok = (
    has_recent_stepup(request, cliente_id)  # passkey step-up (FaceID/huella/PIN)
    or session_confirmed                     # fallback: "Confirmo" por sesión
)
```

El **passkey step-up** es la modalidad preferida: usa WebAuthn (la misma tecnología
que Face ID / huella dactilar) y deja una cookie `stepup` firmada (~5 min). Si el
cliente no tiene passkey configurada, cae al fallback.

El **fallback por sesión** (botón "Confirmo y acepto") es válido si la sesión activa
es reciente (no revocada). Es weaker que passkey pero evita bloquear clientes sin
passkey.

## Checks cableado-apagado

Los checks de **bloqueo** (#1125) y **antelación** (#1126) están implementados en
el portero pero siempre retornan OK. Para activarlos:
1. Implementar la feature (columna `bloqueado` en `clientes` / setting de lead-time).
2. Descomentar la lógica dentro de `_check_bloqueo` / `_check_antelacion`.

Los comentarios `TODO (#NNNN)` marcan exactamente dónde.

## Preview del contrato (antes de crear el pedido)

`POST /api/checkout/contrato-preview` (`routes/checkout.py::checkout_contrato_preview`)
arma un `pedido` equivalente **en memoria** desde el carrito de la sesión (mismo
`_leer_carrito` que usa el portero + `equipos`/`contenido_de_batch`/`clientes`) y llama
al **mismo `_contrato_html`** (`pdf_templates.py`), con **`mostrar_locador=False`** —
omite el bloque de datos institucionales de Rambla (nombre/CUIL/domicilio/contacto,
fijos, no cambian por pedido) y la firma del Locador: en un preview lo que importa es
que el cliente pueda leer las **cláusulas**, no la ficha del Locador. El contrato REAL
(de un pedido ya creado) sigue llamando a `_contrato_html(pedido)` sin el flag —
default `True`, los sigue mostrando siempre. No persiste nada, no crea el pedido. Deja
que el cliente **lea el contrato antes de confirmar** (sienta base para la firma
digital de #1098 Fase 5).

El HTML vuelve marcado como **SIMULACIÓN** (`_marcar_como_simulacion`: banner fijo +
marca de agua diagonal) — el documento definitivo recién existe cuando el pedido se
confirma (queda en el portal del cliente + se manda por mail). El front (`lib/checkout.ts
::obtenerContratoPreviewHtml` + `components/rental/ContratoPreviewModal.tsx`) lo muestra
en un iframe sandboxed dentro de un modal, sin salir del checkout (mismo patrón que
`FacturacionModal`/`TerminosModal`).

## Archivos clave

```
backend/services/checkout/
├── __init__.py          — re-exporta la API pública
├── validar.py           — el portero (validar_checkout + 10 checks)
└── tyc.py               — T&C (TYC_VERSION_ACTUAL, ya_acepto, registrar_aceptacion)

backend/routes/checkout.py                     — validar / aceptar-tyc / contrato-preview
backend/tests/test_checkout_portero.py         — candados unitarios (sin DB real)
backend/tests/test_checkout_route_robustez.py  — candado del 503 limpio a nivel HTTP
backend/tests/test_checkout_contrato_preview_db.py — candado del preview (Postgres real)
backend/database/schema.py               — tabla aceptaciones_tyc (init_db)
backend/migrations/versions/b1a2c3d4e5f6_checkout_aceptaciones_tyc.py
```

## Qué NO toca

- `backend/reservas/` (motor sagrado, FOR UPDATE, lock de concurrencia) — intacto.
- `create_pedido` / `create_pedido_retry` — el portero no los llama, los llama el route.
- `services/precios` — el portero delega los precios, no los recalcula.
- La identidad base del cliente (nombre/email) — la lee pero no la escribe.
