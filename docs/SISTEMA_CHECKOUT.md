# SISTEMA_CHECKOUT — portero del checkout + UI del resumen

> **Fuente única del "cómo funciona" el checkout**, de punta a punta: el
> **portero** (`backend/services/checkout/`, qué precondiciones corre) y la
> **UI del resumen** (`CheckoutResumen.tsx` + sus 3 modales) que lo consume. Las
> reglas de criterio y el _por qué_ viven en `MEMORIA.md` y `DECISIONES.md`.

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
`_leer_carrito` que usa el portero + `equipos`/`contenido_de_batch`) y llama al
**mismo `_contrato_html`** (`pdf_templates.py`) que genera el contrato real — no
persiste nada, no crea el pedido. Deja que el cliente **lea el contrato antes de
confirmar** (sienta base para la firma digital de #1098 Fase 5).

El HTML vuelve marcado como **SIMULACIÓN** (`_marcar_como_simulacion`: banner fijo +
marca de agua diagonal) — el documento definitivo recién existe cuando el pedido se
confirma (queda en el portal del cliente + se manda por mail). El front (`lib/checkout.ts
::obtenerContratoPreviewHtml` + `components/rental/ContratoPreviewModal.tsx`) lo muestra
en un iframe sandboxed dentro de un modal, sin salir del checkout (mismo patrón que
`FacturacionModal`/`TerminosModal`).

### Datos de muestra, no los reales del cliente/inventario

Es un documento que queda en el DOM del browser marcado "no válido" — no hace falta
(ni conviene) exponer ahí datos reales que no aportan a la simulación. `routes/
checkout.py::_CLIENTE_DE_MUESTRA` reemplaza nombre/dirección/teléfono/email/CUIT/
razón social del Locatario por placeholders fijos ("Juan Pérez", etc.); `_serie_y_
valor_de_muestra(idx)` hace lo mismo con el número de serie y el valor de reposición
de cada equipo (`EJEMPLO-0001`, `$100.000`). **Lo único real del cliente es el perfil
fiscal** (`cliente_perfil_impuestos` — decide si aparece el bloque de Responsable
Inscripto; no es un dato personal sensible). Con el Locatario ya ficticio, el Locador
(datos institucionales fijos de Rambla) **sí se muestra** — no hay nada sensible que
cuidar de ese lado, y así el preview se lee como el contrato real completo. El
nombre/cantidad/marca/modelo del equipo siguen siendo los reales (el cliente necesita
verificar QUÉ está por pedir); solo serie y valor son de mentira.

### Performance: sin fuentes de marca embebidas, sin el isologo

`fonts_ligeras=True` (parámetro de `_contrato_html`/`_document`/`_membrete`, propio de
este endpoint) salta:
- El `@font-face` en base64 (~1.2MB — TT Commons + Champ Black, el mismo `_fonts_css()`
  que necesitan los PDFs reales vía Playwright) y el link a Google Fonts. `--font-sans`/
  `--font-mono` (`_DOC_CSS`) caen a `ui-sans-serif`/`ui-monospace` del sistema.
- El isologo SVG (`_active_wordmark()`, que hace su propia consulta a `app_settings.
  wordmark_svg`) — se reemplaza por el texto plano "Rambla".

Motivo: **este documento lo pinta el browser real del cliente, no Playwright.** Un
`<iframe srcDoc={html}>`/`<iframe src={blobUrl}>` con ~1.3MB tarda 10s+ en parsear
(confirmado navegando la app en vivo, no solo con curl) — con `fonts_ligeras=True` el
mismo documento pesa ~18KB y pinta en <500ms. El contrato REAL (de un pedido ya
creado, generado por Playwright) sigue llamando a `_contrato_html(pedido)` sin el
flag — default `False`, sigue embebiendo todo siempre.

**Iframe por Blob URL, no `srcDoc`** — `ContratoPreviewModal.tsx` arma un
`URL.createObjectURL(new Blob([html]))` y lo navega vía `<iframe src={blobUrl}>`. Con
`fonts_ligeras=True` esto ya es rápido; independientemente, el spinner del modal queda
visible hasta el evento `onLoad` del iframe — nunca una pantalla en blanco sin
explicación, incluso si el documento creciera de nuevo en el futuro.

**Robustez del armado en memoria** (edge cases reales, con candado en
`test_checkout_contrato_preview_db.py`): la lectura de `items_json` reusa
`services.carrito.desde_items_json` (resuelve lista-ya-deserializada vs.
string JSON — no reimplementa esa ambigüedad); el SELECT de `equipos` filtra
`eliminado_at IS NULL`, porque un carrito no se purga ni se re-valida solo
(sin heartbeat nuevo, puede seguir apuntando a un equipo que se borró del
catálogo después) — sin el filtro, ese equipo se colaba en el preview; el
timestamp "Emitido" usa `now_ar()` (no `datetime.now()` crudo, que en la nube
corre en UTC). **NO** hay fallback para un ítem sin `cantidad`: el único
escritor de `items_json` (`services.carrito.activos.heartbeat_upsert`) la
recibe de un modelo Pydantic que la exige (`CartItem.cantidad: int`, sin
default) — no existe, ni existió, una forma que la omita.

## UI del resumen (`CheckoutResumen.tsx`)

Es el paso entre "Revisar pedido" (carrito) y la creación real del pedido — fuente
única, la usan el drawer desktop y el sheet mobile por igual. NO hardcodea el orden
de las validaciones: al montarse (y cada vez que hace falta re-chequear) llama a
`POST /api/checkout/validar` y renderiza `faltan` tal cual lo manda el backend. Un
solo botón **"Confirmar pedido"** resuelve T&C + firma en el mismo click (sin
tarjetas intermedias por check) y recién ahí llama a `onCrearPedido` (que termina en
`create_pedido_retry`, motor sagrado). **Identidad** es la única excepción que no se
resuelve en un click (exige salir a Didit) — mientras falte, el botón queda
deshabilitado y se muestra `VerificacionRequeridaPanel`.

Tarjetas del resumen, en orden:

| Tarjeta | Qué muestra | Fuente del dato |
|---|---|---|
| **Fechas** | Rango + horario elegido, jornadas, dirección de retiro | Props del caller + `useBusinessContact()` |
| **Tus datos** | Nombre/email/teléfono/dirección — RENAPER si está verificado, si no el dato base; contacto canónico (Didit-preferido) | `GET /api/cliente/me` → `nombre_legal`/`direccion_legal`/`email_comunicacion`/`telefono_contacto` (resueltos por `identity/__init__.py` + `identity/contacts.py` — el front NO reimplementa la regla RENAPER-si-verificado) |
| **Facturación** | Perfil fiscal + qué tipo de factura le corresponde (`facturaTipoLabel`), con botón "Modificar" | Estado local `perfilImpuestosLive`, sembrado por prop y actualizado en vivo por `FacturacionModal` |
| **Disclaimer de seguro** | Responsabilidad del cliente por daños/pérdida/robo desde el retiro + link a T&C | Copy estático; el link abre `TerminosModal` |
| **Documentos de tu pedido** | Los 4 docs disponibles desde "presupuesto" (Remito/Contrato/Detalle de seguro/Checklist de retiro) con descripción breve; "Leer" en Contrato abre `ContratoPreviewModal` | `DOC_LABEL`/`DOC_DESCRIPTION` (`ClientePortalTypes.ts`, fuente única compartida con el portal) |
| **Total** | Subtotal, descuento (si aplica), total (+ IVA si `conIva`) | Props (`totalNeto`/`conIva`/etc.) — el front NUNCA calcula plata, solo muestra lo que ya vino resuelto de `/api/cotizar` |

Después de las tarjetas: estados de carga/error, el panel de identidad si falta, y
cualquier otro faltante (carrito/fechas/stock/precio/contacto/antelación) como alert.
Con 2+ faltantes simultáneos hay **un solo botón "Volver al carrito"** al final de
la lista, no uno por mensaje — son la misma acción repetida; antes cada `alert`
tenía su propio "Volver" y quedaban varios botones idénticos apilados.

### Los 3 modales in-place (no navegan fuera del checkout)

Mismo patrón los tres: envuelven contenido existente en un `Dialog` del design
system, para que el cliente resuelva algo **sin perder el paso del carrito en el
que estaba** (antes, "Modificar facturación" y "Ver T&C" navegaban a otra pantalla).

**Escape cierra solo el modal, no el carrito entero** — `CartDrawer.tsx` tiene su
propio listener de `Escape` en `document` (independiente del de Radix, que gestiona
estos 3 modales) para cerrar el drawer. Sin un guard, un solo Escape cerraba AMBOS:
el modal chico Y todo el checkout, devolviendo al cliente al catálogo. El guard
chequea si el foco sigue dentro del drawer (`dialogRef.current.contains(document
.activeElement)`) — si está en un modal anidado (que Radix enfoca al abrir), ese
Escape lo resuelve Radix solo.

| Modal | Qué hace | Se cierra solo al guardar |
|---|---|---|
| `FacturacionModal.tsx` | Fetchea `/api/cliente/me`, renderiza `FacturacionForm` (`ClientePortalHelpers.tsx`, compartido con el portal) | Sí (`onSaved`) |
| `TerminosModal.tsx` | Renderiza `TERMS_SECTIONS`/`LAST_UPDATED` de `data/legal.ts` (mismo contenido que `/terminos`) | No (solo lectura) |
| `ContratoPreviewModal.tsx` | Llama a `lib/checkout.ts::obtenerContratoPreviewHtml(sessionId)` y muestra el HTML en un `<iframe sandbox="" srcDoc={html}>` (ver sección de abajo) | No (solo lectura) |

### Verificación de CUIT contra ARCA (dentro de `FacturacionForm`)

`FacturacionForm` valida el **formato** del CUIT/CUIL en el input (`lib/cuit.ts
::cuitValido`, mod-11 — mismo checksum que `identity/anchor.py::cuil_valido` en el
backend, verificado byte-idéntico) antes de habilitar "Verificar". Al verificar:

```
Cliente tipea CUIT → cuitValido() lo formatea/valida en el input
    → botón "Verificar" → POST /api/cliente/facturacion/verificar-cuit
        → cuil_valido() (formato; 400 si inválido, NO llama a ARCA)
        → services.facturacion.padron.verificar_y_actualizar_receptor (WSAA/padrón AFIP)
        → encontrado=True: persiste cuit + corrige perfil_impuestos/razon_social/
          domicilio_fiscal desde el padrón → UI muestra card "Verificado con ARCA"
          (read-only) → invalidateClienteSession() (refresca /api/cotizar: el Total
          puede haber cambiado el "+ IVA")
        → encontrado=False (ARCA no lo tiene / servicio caído): NO persiste nada,
          la UI cae a los inputs manuales (dropdown de perfil + razón social/
          domicilio a mano) — "como si fuera Didit": se verifica una vez, después
          se trae de la cuenta.
```

Este es el **mismo criterio "verificar y persistir en el momento"** que usa Didit
para identidad — la diferencia es que acá es opcional (el cliente puede seguir con
carga manual si ARCA no lo encuentra). El endpoint vive en
`routes/cliente_portal/cuenta.py::cliente_verificar_cuit`; el padrón real en
`docs/SISTEMA_ARCA.md` (no se duplica acá el detalle del WSAA).

## Archivos clave

```
backend/services/checkout/
├── __init__.py          — re-exporta la API pública
├── validar.py           — el portero (validar_checkout + 10 checks)
└── tyc.py               — T&C (TYC_VERSION_ACTUAL, ya_acepto, registrar_aceptacion)

backend/routes/checkout.py                     — validar / aceptar-tyc / contrato-preview
backend/routes/cliente_portal/cuenta.py        — GET /api/cliente/me + verificar-cuit
backend/pdf_templates.py::_contrato_html        — genera el contrato (real Y preview)
backend/tests/test_checkout_portero.py         — candados unitarios (sin DB real)
backend/tests/test_checkout_route_robustez.py  — candado del 503 limpio a nivel HTTP
backend/tests/test_checkout_contrato_preview_db.py — candado del preview (Postgres real)
backend/tests/test_pdf_helpers.py::TestContratoHtmlMostrarLocador — candado mostrar_locador
backend/tests/test_cliente_portal_cuenta_facturacion_db.py — candado facturación + ARCA
backend/database/schema.py               — tabla aceptaciones_tyc (init_db)
backend/migrations/versions/b1a2c3d4e5f6_checkout_aceptaciones_tyc.py

frontend/src/components/rental/CartDrawer.tsx          — estado del carrito (paso/Esc/focus-trap)
frontend/src/components/rental/CheckoutResumen.tsx     — la UI del resumen (fuente única)
frontend/src/components/rental/FacturacionModal.tsx    — editar perfil fiscal in-place
frontend/src/components/rental/TerminosModal.tsx       — T&C in-place
frontend/src/components/rental/ContratoPreviewModal.tsx — preview del contrato in-place
frontend/src/routes/ClientePortalHelpers.tsx::FacturacionForm — form fiscal (portal + checkout)
frontend/src/lib/checkout.ts    — validarCheckout / aceptarTyc / obtenerContratoPreviewHtml
frontend/src/lib/cuit.ts        — cuitValido (mod-11) + verificarCuitArca
frontend/src/lib/iva.ts         — useClienteSession, aplicaIva, facturaTipoLabel
frontend/src/routes/ClientePortalTypes.ts — DOC_LABEL/DOC_DESCRIPTION (fuente única)
```

## Qué NO toca

- `backend/reservas/` (motor sagrado, FOR UPDATE, lock de concurrencia) — intacto.
- `create_pedido` / `create_pedido_retry` — el portero no los llama, los llama el route.
- `services/precios` — el portero delega los precios, no los recalcula.
- La identidad base del cliente (nombre/email) — la lee pero no la escribe.
