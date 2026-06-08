# Auditoría de flujos — 2026-06-08

> Recorrido de la app real (catálogo público + portal cliente + back-office) con
> el skill nuevo `auditar-flujos`: se levantó el stack local con datos de ejemplo
> y se caminó cada superficie como un agente de navegación (browser real),
> capturando screenshots, errores de consola, 4xx y tap targets. Acá va **lo que
> se aplicó** y **lo que se propone** (con su evidencia). El dueño prueba conducta
> en staging.

## TL;DR

- **1 bug real de impacto, ARREGLADO + test:** el catálogo público recibía **401**
  en endpoints **públicos por diseño** (`/api/settings/*`, `/api/marcas`,
  `/api/analytics-config`). Consecuencia silenciosa: **las settings que el dueño
  edita en el back-office (logo, taglines del hero, FAQ, contacto, horarios de
  retiro, y el `usd_rate` que afecta el precio público) nunca llegaban al
  visitante anónimo** — caían al default bundleado.
- **Infra nueva** para poder auditar (y para mañana mostrarle pantallas a v0):
  seed de datos ficticios + dev-login de cliente + el walker + el skill.
- **El resto de los flujos funcionan.** La app está madura: portal, ficha de
  equipo, estudio, back-office cargan y se comportan bien. El resto de hallazgos
  son menores o ya están trackeados (mobile tap targets #745, editor cliente #750).

---

## Lo que se APLICÓ (en este PR)

### 1. Fix de seguridad/UX: lecturas públicas del catálogo (bug real)

**Qué pasaba:** el `auth_middleware` no eximía a `/api/settings/{key}`,
`/api/settings` (lista), `/api/marcas` ni `/api/analytics-config`, pero esos
endpoints son **públicos por diseño** (el handler de settings dice literalmente
_"Lectura pública"_ y existe un allowlist `ALLOWED_SETTINGS_KEYS`). Un visitante
anónimo recibía **401** en todos → el front caía a valores hardcodeados. El dueño
podía cambiar el logo / los horarios / la FAQ / el contacto / el tipo de cambio en
`/admin`, y **el público nunca lo veía**. Además sumaba ~6-8 requests fallidos por
carga de página (ruido + latencia).

**Qué se hizo (modular y seguro):**
- `backend/middleware.py` — `/api/marcas`, `/api/settings`, `/api/analytics-config`
  pasan a ser **GET públicos** (solo lectura; las escrituras siguen gateadas).
- `backend/routes/settings.py` — se definió `PUBLIC_SETTINGS_KEYS`, el
  **subconjunto** de settings que el catálogo necesita (precio, branding,
  contacto, horarios, FAQ, taglines). El handler sirve esas sin sesión y **sigue
  exigiendo sesión para las sensibles** (`email_admin_to`, `comisiones_modelo`,
  recordatorios, márgenes internos). La lista devuelve el subconjunto público a
  anónimos y todo a admin.
- `backend/tests/test_public_settings.py` — **test de regresión** (24 casos) que
  fija los dos invariantes: esos GET son públicos **y** ninguna key sensible se
  filtra. Corre sin DB (CI-safe).

**Verificado:** anónimo ahora recibe 200/404 (no 401) en públicas, **401 en las
sensibles** (email_admin_to, comisiones), y la lista filtra por sesión. Suite
backend completo: **1611 passed, 52 skipped**.

> ⚠️ **Ojo en prod:** en el seed demo las settings públicas no tienen valor → dan
> 404 (fallback correcto). En prod, donde el dueño SÍ cargó logo/horarios/etc.,
> ahora **se servirán de verdad al público** (antes 401 → fallback). Es el
> comportamiento que se quería.

### 2. Infraestructura de auditoría (additiva, gateada a no-prod)

- `backend/seeds/demo_data.py` — seed idempotente de datos ficticios (15 equipos
  con marcas/categorías, 4 clientes, 6 pedidos en estados variados + pagos +
  reserva de estudio). **No corre en Railway** (`settings.is_railway`). Doble uso:
  base para mostrarle pantallas a v0 más adelante.
- `backend/routes/auth.py` — `/auth/dev-login-cliente`, espeja el dev-login de
  admin (sesión `role=cliente`) para recorrer el portal en local. **Mismo gate
  anti-prod** que el bypass de admin.
- `.claude/skills/auditar-flujos/` — el **skill** (método de auditoría de flujos)
  + `walk.mjs` (el agente de navegación: recorre, captura screenshots + consola +
  4xx + tap targets <44px).

---

## Lo que se PROPONE (no se tocó — para tu visto bueno)

No se ramearon de prepo: son visuales/trackeados o necesitan tu criterio.

1. **Tap targets mobile < 44px** (HIG). En portal/catálogo varios controles están
   en 30-36px: chips de filtro ("Todos/Activos/Historial" ~30px), "Ver pedido"
   (~32px), botón "Salir"/avatar (~34-36px). Encaja con el tracker **#745** (migrar
   legacy 40px→44px). Propongo abordarlo ahí, con las reglas del DS (`importar-diseno`),
   no suelto acá (cambio transversal = mejor en su iniciativa).
2. **Ruido de consola en páginas públicas:** `/api/cliente/me` devuelve 401 a
   anónimos (correcto: "¿hay cliente logueado?") pero el front lo logea como error
   en cada página pública. Menor; se puede silenciar el 401 esperado en ese fetch.
3. **Editor de pedido del cliente pausado (#750):** `/cliente/pedidos/$id/editar`
   rebota al portal (feature pausada a propósito, ver comentario en
   `PedidoPage.tsx`). **Confirmar que el portal no exponga un link muerto** a esa
   ruta mientras esté pausada.
4. **Warning React "empty string passed to attribute"** en home: un atributo
   (`src`/`href`) recibe `""` → el browser puede re-pedir la página. Cleanup menor;
   ubicar el componente y darle `undefined` en vez de `""`.

### No-hallazgos (verificados, están bien)

- `/admin/email-templates` → `/admin/settings`: **redirect de compat intencional**, no bug.
- `/admin/pedidos/nuevo`: crea un borrador y abre su editor — comportamiento por diseño.
- Portal, ficha de equipo, estudio, listado de pedidos, back-office: cargan y se
  comportan bien (auth, estados, documentos del confirmado, stats).

---

## Plan de prueba (en staging, cuando el fix llegue)

1. **Lo importante — settings públicas llegan al visitante:** en `/admin/settings`
   (o "Diseño y marca") cambiá los **horarios de retiro**, el **teléfono de
   contacto** o un **tagline del hero**. Abrí el sitio público **sin loguearte**
   (ventana incógnito) → **tenés que ver el cambio** (antes mostraba el default
   viejo siempre). Igual con el **logo** (favicon/wordmark) si subiste uno.
2. **Marcas en el catálogo:** entrá al catálogo público anónimo → el filtro/datos
   de marcas tiene que cargar sin errores.
3. **Nada se rompió en el back-office:** entrá a `/admin/settings` logueado → todas
   las settings (incluidas email/comisiones) siguen visibles y editables.
4. **Privacidad:** la config sensible (email del admin, modelo de comisiones) **no**
   debe ser visible sin sesión (es el test de regresión, pero confirmalo si querés).

---

## Sobre el skill nuevo (decisión de gobernanza)

Se dejó **standalone** (`auditar-flujos`), hermano de `limpieza`: es un **método
de auditoría**, no un skill de diseño. Cuando un hallazgo se arregla con piezas
visuales, **consume la librería del DS por las reglas de `importar-diseno`** (no
recrea). Para que el supervisor no lo marque como "segundo skill de UI"
(MEMORIA *2026-06-06*), **propongo** sumar esta entrada a `docs/MEMORIA.md` —
**pendiente de tu aprobación explícita** (no la escribí, las escrituras a MEMORIA
las aprobás vos):

> **2026-06-08 — `auditar-flujos` = método de auditoría de flujos (no es un 2º skill de UI).**
> Recorre la app real (browser vía Playwright + seed local) para descubrir qué
> falla en los recorridos; complementa `importar-diseno` (que implementa diseños).
> No posee patrones de UI: las correcciones visuales pasan por la librería del DS
> y las reglas de `importar-diseno`. La regla "un solo skill de UI" se mantiene
> (este es de auditoría, como `limpieza`). El supervisor no lo marca como drift.
