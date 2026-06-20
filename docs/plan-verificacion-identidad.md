# Plan — Integración robusta de la verificación de identidad (Didit)

> **Estado:** PR1 mergeado a `dev` (gate 403 + flujo Didit + retorno al carrito/estudio). PR2 en PR
> (estados webhook rechazado/en_revision + tab Identidad fusionada en Perfil + panel inline en Estudio).
> PR3 pendiente: vista admin + estados en la ficha + re-verificación. Issue de tracking: #939.
> Doc hermano: `docs/design-brief-verificacion-identidad.md`.

## Diagnóstico (lo que se encontró)

1. **El gate de pedidos NO existe.** `POST /api/cliente/pedidos` y `POST /api/estudio/reservas`
   solo chequean login. **Hoy un cliente sin verificar puede mandar pedidos.** (El design-brief, línea
   174, dice que el gate "ya está" — es falso.)
2. **El webhook solo entiende `Approved`.** Ignora `Declined / In Review / Expired / Abandoned` → el
   estado "rechazado" no tiene dato real.
3. **Identidad y Perfil son dos solapas separadas** en el portal.
4. **La URL de retorno de Didit está hardcodeada** al portal → no se puede "volver al punto donde estabas".
5. Hay **tres bocas de checkout** que hay que cubrir: `CartDrawer` (desktop), `CartSheet` dentro de
   `CatalogoMovil` (mobile — la mayoría del tráfico) y `StudioBookingForm` (estudio).

## Decisiones tomadas por el dueño

- **A todos:** la verificación aplica a todos los clientes (sin verificar no se pide), no solo a nuevos.
- **Admin = aviso fuerte salteable:** al confirmar/entregar a un cliente sin verificar, el admin ve una
  alerta + botón para mandar el link, pero puede confirmar igual (criterio propio).
- **Por fases:** se entrega en 3 PRs testeables por separado.

## Fases

| PR | Alcance |
|----|---------|
| **PR1 (este plan)** | El gate en pedidos + estudio (front y backend) + la **redirección de vuelta** al punto donde estaba. |
| PR2 | Fusionar **Identidad dentro de Perfil** + estados nuevos (rechazado / en revisión) + robustez del webhook (columna de estado, idempotencia por orden de eventos, re-verificación por vencimiento) + tests e2e. |
| PR3 | **Vista admin:** estado de verificación en la ficha del pedido/cliente + aviso fuerte salteable al confirmar/entregar + botón para mandar link de verificación. |

---

# PR1 — el gate en el flujo de pedidos

## Comportamiento (qué va a ver el cliente)

**Cliente sin verificar que intenta pedir:**
1. Arma el carrito, elige fechas, toca **"Confirmar solicitud"**.
2. En vez de mandarse el pedido, aparece **un paso de verificación ahí mismo** — panel sobrio: por qué
   pedimos el DNI (alquilamos equipo de valor), que es rápido (< 2 min) y seguro (solo texto, nunca la
   foto), y un botón **"Verificar mi identidad"**.
3. Toca el botón → va al flujo de Didit (DNI + selfie).
4. **Vuelve al punto donde estaba:** se reabre el carrito con todo cargado; cuando el webhook confirma,
   ya puede tocar Confirmar y completar el pedido.

**Estudio:** igual, en su propio botón "Reservar" (vuelve con las fechas elegidas cargadas).
**Mobile:** igual, en su carrito propio (`CartSheet`).

**Backend = la pared:** aunque alguien saltee el front (llamada directa a la API), `POST /api/cliente/pedidos`
y `POST /api/estudio/reservas` responden **403** si el cliente no está verificado.

## La redirección de vuelta ("al mismo punto donde estaba")

`return_to` viaja por toda la cadena, **con allowlist anti open-redirect** (solo paths internos que
empiezan con `/`, sin `//`, sin esquema):

```
carrito (sin verificar)
  → POST /api/cliente/verificacion/sesion  { return_to: "/?pedido=retomar" }
  → backend arma callback = {SITE_URL}/cliente/portal?verificacion=pendiente&return_to=<encoded>
  → flujo Didit (DNI + selfie)
  → vuelve a /cliente/portal?verificacion=pendiente&return_to=...
  → el portal hace polling del webhook; al confirmar, redirige a return_to
  → "/?pedido=retomar" reabre el carrito (que persiste en localStorage) → Confirmar
```

Para el estudio, `return_to` lleva las fechas en la query (`/estudio?d=...&h=...&dur=...&pack=...`), que el
form ya sabe restaurar.

## Cambios, archivo por archivo

### Backend (la pared, no salteable)
1. `backend/routes/cliente_portal/core.py` — helper único `require_cliente_verificado` + `cliente_verificado`
   (fuente única del criterio "está verificado"; mensaje único `IDENTIDAD_NO_VERIFICADA_MSG`).
2. `backend/routes/cliente_portal/__init__.py` — re-exporta el helper.
3. `backend/routes/cliente_portal/pedidos.py` — `POST /api/cliente/pedidos` usa el gate.
4. `backend/routes/estudio.py` — `POST /api/estudio/reservas` usa el gate.
5. `backend/routes/didit.py` — `POST /api/cliente/verificacion/sesion` acepta `return_to` (con allowlist)
   y lo mete en la URL de retorno de Didit. Helper `_es_path_interno_seguro`.

### Frontend (la experiencia, DRY)
6. `src/lib/verificacion.ts` (nuevo) — `chequearEstadoCuenta()` + `iniciarVerificacionIdentidad(returnTo)`.
   Un solo lugar para clasificar la cuenta y disparar Didit.
7. `src/components/rental/VerificacionRequeridaPanel.tsx` (nuevo) — el panel del paso de verificación,
   **reusado** por las tres bocas (no recrear variantes).
8. `src/lib/cart-store.ts` — hook `useRetomarPedido(cb)` que lee/limpia el flag `?pedido=retomar` y reabre
   el carrito al volver verificado.
9. `src/components/rental/CartDrawer.tsx` (desktop) — gate en el submit + panel.
10. `src/components/rental/mobile/CatalogoMovil.tsx` (mobile) — gate en el submit del `CartSheet` + panel
    + reabrir el sheet al volver.
11. `src/components/studio/StudioBookingForm.tsx` — gate antes de reservar + volver con las fechas cargadas.
12. `src/routes/cliente.portal.tsx` — acepta `return_to` y redirige ahí cuando se confirma; refactorea el
    `iniciarVerificacion` interno para usar el helper compartido (saca el duplicado).

### Tests + docs
13. Tests backend del gate (sin verificar → 403; verificado → 201) + del allowlist de `return_to`
    (rechaza open-redirect).
14. Corregir la línea desactualizada del `design-brief` (decía que el gate "ya estaba").

## Plan de prueba para el dueño (en staging)

1. Con una cuenta **sin verificar**, armá un carrito y tocá "Confirmar solicitud" → tiene que aparecer el
   paso de verificación, **no** mandarse el pedido.
2. Hacé la verificación → al volver, el carrito se reabre con todo cargado y podés confirmar.
3. Repetí en **mobile** y en **/estudio**.
4. Con una cuenta **ya verificada**, pedir tiene que andar igual que antes (sin fricción).

## Fuera de alcance de PR1 (van en PR2/PR3)
- Fusionar Identidad en Perfil y mostrar ahí los datos de RENAPER.
- Estados nuevos del webhook (rechazado / en revisión) y la columna de estado.
- Vista admin.
