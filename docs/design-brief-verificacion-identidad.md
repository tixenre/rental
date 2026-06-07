# Brief de diseño — Verificación de identidad (portal del cliente)

> **Para qué sirve esto:** es el _brief_ que se abre desde **Claude Design** para generar el
> **handoff** del rediseño de los estados del flujo de verificación de identidad. NO es el handoff.
> El flujo es: este brief → Claude Design (mockups) → `design_handoff_verificacion/` en el repo →
> se implementa con el skill `importar-diseno`.
>
> **Por qué importa (lo dijo el dueño):** la verificación es **para la seguridad de Rambla**
> (saber con quién se está alquilando equipo caro) y, del lado del cliente, **tiene que dar
> confianza para que no duden**. Es un momento sensible: le pedimos a alguien su DNI y una selfie.
> Si la pantalla se siente trucha, lenta sin explicación, o lo deja en un limbo, abandona. El
> objetivo del rediseño es que **cada estado del flujo transmita seguridad y control**.

---

## Qué se rediseña

Los **estados visuales del flujo de verificación**, que hoy viven en la pestaña **Identidad** del
portal del cliente (`src/routes/cliente.portal.tsx`, componente `IdentidadSection`). El flujo
funcional ya está implementado y andando — esto es **piel**, no plomería. Claude Design decide
_cómo se ven_; este brief dice _qué_ estados hay, _qué dato_ tiene cada uno y _qué tiene que
sentir_ el cliente.

### El flujo de punta a punta (para entender el contexto)

1. Cliente entra al portal. Si no está verificado, ve un **banner** en la pestaña Pedidos que lo
   empuja a verificarse (no puede hacer pedidos sin verificar).
2. Va a la pestaña **Identidad** → ve el **llamado a verificar** → toca "Verificar mi identidad".
3. Se va del sitio al flujo de **Didit** (DNI + selfie — pantallas de Didit, NO las diseñamos).
4. Termina y **vuelve al portal** (`/cliente/portal?verificacion=pendiente`). La confirmación real
   llega por un webhook **asíncrono** (server-to-server) que puede tardar unos segundos → mientras
   tanto el portal está en estado **"confirmando"** y consulta el estado cada pocos segundos.
5. Cuando el webhook confirma → **éxito** → queda en estado **verificado** (datos de RENAPER a la
   vista, bloqueados con candado).
6. Si Didit **rechaza** la verificación → estado **rechazado** con próximos pasos. _(Ver dependencia
   de backend abajo — este estado todavía no tiene dato real.)_

---

## Los estados a diseñar

> Todos viven en la **misma pestaña Identidad** (mobile-first: la mayoría del tráfico es celular).
> Pensalos como variaciones de una misma pantalla, no 6 pantallas sueltas. El tono general:
> **sobrio, confiable, sin alarmismo**. Nada de rojos agresivos ni de celebraciones infantiles —
> es un trámite de seguridad, no un juego.

### 1. Llamado a verificar (estado: sin verificar) — **la primera impresión**

Es lo que ve un cliente nuevo. Hoy es un panel ámbar + un párrafo + un botón. **Es la pantalla más
importante para la confianza** porque es donde el cliente decide si nos da su DNI o no.

- **Qué tiene que transmitir:** por qué se lo pedimos (seguridad, alquilamos equipo de valor), que
  es **rápido** (< 2 min), **oficial** (consulta RENAPER vía Didit, un proveedor serio) y **seguro**
  (Ley 25.326: guardamos solo texto — nombre, DNI, dirección — **nunca la foto del DNI ni la
  selfie**). Que es **un solo paso** y queda hecho para siempre.
- **Dato disponible:** nada del cliente todavía (no está verificado). Copy + CTA.
- **CTA principal:** "Verificar mi identidad" → dispara el redirect a Didit.

### 2. En proceso (estado: confirmando) — **el limbo, que no se sienta roto**

El cliente acaba de volver de Didit. Hizo su parte. Estamos esperando el webhook (segundos, a veces
más). **Este es el estado más delicado del flujo:** si parece un error o se queda mudo, el cliente
cree que falló y abandona o reintenta de más.

- **Qué tiene que transmitir:** "ya está, lo estamos confirmando, es normal que tarde unos
  segundos". Calma + progreso. Que **no se vaya** ni reintente. Pensar un estado de espera con
  movimiento sutil (no un spinner técnico frío — algo que diga "trabajando para vos").
- **Dato disponible:** ninguno nuevo todavía. Es puramente un estado de espera.
- **Tiempo real:** el portal reintenta ~8 veces cada 3s (~24s). Diseñar también el caso
  **"está tardando más de lo normal"** (cuando se agotan los reintentos sin confirmación): un
  mensaje tranquilizador de que le vamos a avisar / que refresque en un rato, **sin** dar a entender
  que falló.

### 3. Éxito (recién verificado) — **el momento de confianza**

La transición de "confirmando" → "verificado". Hoy es un `toast` + el panel verde la próxima vez que
entra. Merece un **beat de éxito** propio: el cliente cumplió un trámite de seguridad, hay que
cerrarlo con una sensación de logro y seriedad (no confeti — más bien "listo, sos parte").

- **Qué tiene que transmitir:** verificación exitosa, identidad confirmada por RENAPER, ya puede
  hacer pedidos. Idealmente un puente claro a la acción siguiente ("ahora sí, armá tu pedido").
- **Dato disponible:** nombre legal (RENAPER), DNI, CUIL, fecha de nacimiento, domicilio.

### 4. Verificado (estado estable) — **la ficha de identidad**

Lo que ve un cliente ya verificado cada vez que entra. Hoy: panel verde + lista de datos de RENAPER
con candados. Funciona; el rediseño debe darle coherencia con el resto y reforzar que **estos datos
son oficiales y no se editan** (vienen del DNI, no los cargó el cliente).

- **Dato disponible:**
  - `nombre_renaper` + `apellido_renaper` → nombre legal
  - `dni` → número de documento
  - `cuil` → CUIL
  - `fecha_nacimiento_renaper` → fecha de nacimiento
  - `direccion_renaper` → domicilio oficial
  - **Apodo** (`apodo`): campo **editable** (el único). Sirve para saludar informal en los mails
    ("Hola Nacho"). Es lo opuesto a los datos de RENAPER: casual y cambiable. El diseño tiene que
    dejar clarísima la diferencia entre "esto es oficial y fijo" vs "esto es tu apodo, cambialo
    cuando quieras".

### 5. Rechazado / no se pudo verificar — **NUEVO, no existe hoy**

Si Didit no aprueba (foto borrosa, DNI no reconocido, no coincide con RENAPER, etc.), hoy el cliente
**vuelve y ve "sin verificar" sin ninguna explicación** — el peor resultado para la confianza.

- **Qué tiene que transmitir:** que **no es una acusación** — pudo ser una foto mal sacada. Próximos
  pasos claros: **reintentar** (CTA) y, si sigue fallando, **cómo contactar a Rambla**. Tono
  empático, cero culpa, cero alarma roja.
- **Dato disponible:** _(depende del backend — ver abajo)_. En el mejor caso, un motivo legible
  ("la foto no se vio bien"). En el mínimo, solo "no se pudo verificar, reintentá".
- ⚠️ **Dependencia de backend (hay que aprobarla):** hoy el webhook **ignora** los estados que no
  sean `Approved`. Para que este estado tenga dato real, el backend tiene que **guardar el último
  estado de verificación** (ej. una columna `dni_verificacion_estado` + opcional `motivo`). Es un
  cambio de schema (patrón de dos capas: `init_db()` + migración). **No está hecho.** Diseñar la
  pantalla igual; la sesión lo implementa cuando el dueño dé el OK.

### 6. Banner "verificá tu identidad" (en la pestaña Pedidos)

El empujón que aparece arriba de la lista de pedidos cuando el cliente no está verificado, y lo lleva
a la pestaña Identidad. Hoy es una barra ámbar. Mantener coherencia con el rediseño; que sea un
nudge claro, no un bloqueo agresivo.

---

## Identidad de marca a aplicar

Fuente canónica: [`docs/DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md). Resumen para el handoff:

### Color (tokens reales del repo — usar estos, no Tailwind genérico)

- **Acento:** `amber` (`--color-amber #FAB428`) + `amber-soft` para fondos suaves. Único acento.
- **Texto/ink:** `ink` (casi negro cálido). Secundario: `muted-foreground`.
- **Éxito / verificado:** `verde` (`--color-verde #009971`) — usar `text-verde`, `bg-verde/8`,
  `border-verde/30`. **No** `green-*` de Tailwind.
- **Fondos/superficies:** `surface` / `card` / `bg-background`. Bordes: `hairline` (ink al ~12%).
- **Disciplina de un solo acento:** sin paletas multicolor. El `verde` es semántico (éxito), no
  decorativo. Para el estado de rechazo, **evitar rojo agresivo** — preferir un tono sobrio
  (ámbar/neutro) que no alarme.

### Tipografía

- **TT Commons** (`font-sans`, `font-display`) → títulos y body de la UI.
- **JetBrains Mono** (`font-mono`) → eyebrows, números, IDs, DNI/CUIL, fechas (uppercase, tracking
  ancho, `tabular-nums`).

### Forma e interacción

- Radios 8–12px, hairlines finos, aire generoso. **Mobile-first.**
- **Tap targets ≥ 44×44px** (Apple HIG — `h-11`; lo hace cumplir el supervisor).
- Inputs ≥ 16px en mobile (evita el zoom de iOS).

---

## Datos y endpoints (para los `TODO:` del handoff)

Todo el dato del cliente sale de `GET /api/cliente/me` (ya devuelve los campos de RENAPER + apodo).
No hace falta endpoint nuevo para el flujo del cliente. Referencia de campos: el tipo `Perfil` en
`src/routes/cliente.portal.tsx`.

- **Disparar verificación:** `POST /api/cliente/verificacion/sesion` → `{ url }` → redirect.
- **Volver:** Didit redirige a `/cliente/portal?verificacion=pendiente`; el portal ya rutea a la
  pestaña Identidad y hace polling de `/api/cliente/me` hasta ver `dni_validado_at`.
- **Apodo:** `PATCH /api/cliente/me` con `{ apodo }` (es el único campo editable tras verificar).

---

## Fuera de alcance (ya resuelto — NO rediseñar)

- **El bug del redirect** (el cliente volvía a un endpoint técnico roto en vez del portal): **ya
  arreglado** en backend.
- **La lógica de polling** del estado "confirmando": **ya implementada**. Claude Design diseña el
  _visual_ del estado; la mecánica existe.
- **Las pantallas de Didit** (DNI + selfie): son de Didit, no se diseñan acá.
- **El gate de pedidos** (no se puede pedir sin verificar): es lógica de backend, ya está.

## Relacionado (posible follow-up, no en este brief)

- **Back-office (admin):** existe `POST /api/admin/verificacion/sesion/{cliente_id}` para que el
  admin genere un link de verificación y se lo mande al cliente (ej. por WhatsApp), pero **no hay
  botón en la UI admin** que lo use. Si se quiere, va como pantalla aparte (vista admin de cliente).
