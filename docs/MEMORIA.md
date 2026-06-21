# Memoria viva — Rambla Rental (digest enforceable)

> **Reglas vivas de criterio + preferencias, en 1-3 líneas cada una.** Este es el **digest
> auto-cargado** (vía `@` desde `CLAUDE.md`): la línea base que el **supervisor hace cumplir** y que la
> sesión tiene siempre en contexto. El **_por qué_ completo** de cada entrada (Contexto / Why /
> Consecuencias / gotchas) vive en el log on-demand [`DECISIONES.md`](DECISIONES.md), **bajo el mismo
> `### fecha — título`** → si necesitás el desarrollo de una regla, buscá su título ahí.
>
> **Curado, no append-only.** Es la verdad del presente: se **edita y poda** para que quede chico y
> vigente (el "nada se pierde" lo cumple git). **Solo el dueño aprueba** agregar/editar/podar; el
> supervisor **propone** (retirar/fusionar/actualizar) pero no escribe. Toda escritura acá tiene su
> reflejo en `DECISIONES.md` (misma fecha-título) — lo verifica `scripts/check-docs.mjs`.
>
> Las **decisiones de arquitectura fundacionales** viven en [`MANIFIESTO.md`](../MANIFIESTO.md) §6
> (baseline congelado). El **trabajo pendiente** → GitHub Issues; el **registro de cambios** → commits.

---

## Decisiones (ADR-lite)

### 2026-06-08 — Workflow de cambios (fuente única): dev = staging, routing por riesgo, gates del dueño

**Fuente única del workflow** (consolida 6 decisiones de flujo previas; no se restatea en otros docs).
`dev` (rama `dev`) = **staging** en Railway (auto-deploy en cada push; base copiada de prod, sin
clientes); `main` = **prod** (sagrado, no se prueba ahí). **Lo que muestra algo en staging es el push a
`dev`, no el PR.** **Routing por riesgo:** trivial/normal → **push directo a `dev`** (la sesión verifica
local antes para no romper staging); grande/sensible/core de reservas o plata/lo que ve el cliente →
**rama (`claude/<desc>`) + PR** (CI + supervisor gatean antes de tocar `dev`); **ante la duda, PR**. El
**CI corre en cada push** a `dev`/`main` (red incluso sin PR); **nunca a `main` directo**; **no mergear
con CI en rojo**. **La sesión mergea/pushea a `dev` sola** (supervisor OK + verde) y **avisa con plan de
prueba — no pide permiso**. **Gates del dueño:** probar en staging + aprobar `dev → main`. Merge:
`rama→dev` = squash (`tipo: desc (#PR)`); `dev→main` = merge commit (revert por PR); directos a `dev`
sin squash. Commits atómicos, Conventional Commits en español.

### 2026-06-08 — Issues: la cola espeja el código (Closes #N → auto-cierre en dev→main; diferido aparte)

Refina _Memoria en capas_ ("Issues = cola"). **Issue solo para trabajo diferido / multi-sesión /
brain-dump del dueño**; lo hecho-y-mergeado en la misma sesión **no lleva issue** (el commit es el
registro). Toda issue trabajada lleva **`Closes #N`** en el commit (directo a `dev`) o el PR; como la
branch default es **`main`**, se **auto-cierra al promover `dev → main`** (cuando shippea a prod) —
citar la issue, no solo el `#PR`. La **promoción `dev → main` reconcilia**: su PR lista las issues que
cierra el lote → cierre en bloque con evidencia. Features grandes diferidas con label **`someday`**
(separa lo diferido de la cola activa; no es deuda sin cerrar). Triage **liviano y seguido** vía skill
`mantenimiento` (frente D): verificar que shippeó antes de cerrar. Iniciativa multi-sesión = **un** issue de
tracking (no uno por fase).

### 2026-05-25 — Modus operandi durable, sesión efímera

El cómo-se-trabaja vive en docs durables (CLAUDE/MEMORIA/MANIFIESTO), no se re-discute por sesión.
Iniciativa multi-sesión = **un issue de tracking** (checklist de fases adentro, NO un issue por fase).

### 2026-05-25 — Memoria en capas

Issues = cola de trabajo; commits/PRs = registro de cambios; memoria (digest `MEMORIA.md` + log
`DECISIONES.md`) = decisiones de criterio + preferencias, curada y enforceable por el supervisor.

### 2026-05-25 — Gate de estilo en CI: formato + lógica de React bloquean

CI bloquea por **formato (prettier)** Y **lógica de React** (`exhaustive-deps`, `react-refresh` en
`"error"` + `reportUnusedDisableDirectives`). Cada `eslint-disable` que sobreviva debe estar justificado.

### 2026-05-26 — Convención de alias `e` para `equipos` en queries SQL

Toda query SQL nueva que toque `equipos` usa el alias `e` (`FROM equipos e`, `e.brand_id`) para reusar
el helper canónico `database.MARCA_SUBQUERY`. El supervisor marca queries de equipos sin alias.

### 2026-05-26 — Curación de la memoria (no es append-only puro)

La memoria es la **verdad curada del presente**, no un log: se **edita y poda** (git guarda lo viejo).
Una decisión reemplazada se actualiza/retira en el lugar. El supervisor cura (propone); el dueño aprueba.

### 2026-05-27 — El Estudio: producto aparte que reusa el motor de reservas

El Estudio se modela **reusando el motor de reservas sin tocarlo** (columna `tipo DEFAULT 'diaria'`,
equipo "centinela" invisible, buffer aplicado expandiendo el rango **afuera** del motor). Core intacto.

### 2026-05-27 — Notificaciones canal-agnósticas; mail construido-no-activado; confirmación = redirect al portal

Feedback de "pedido solicitado" = **redirect al portal** con la card resaltada. Notificaciones
multi-canal a un punto único (mail hoy, WhatsApp follow-up); se activan por **config, no código**. El
remito/contrato no existen en `presupuesto`, recién desde `confirmado`.

### 2026-05-29 — Módulo `equipment/shared/` = librería canónica de assets visuales (reusar, no recrear)

`StepperPill`, `PriceBlock`, `FavButton` (en `src/components/rental/equipment/shared/`) son la **única**
fuente de stepper/precio/favorito. Importar de ahí, no recrear variantes. El supervisor marca duplicados.

### 2026-05-29 — `RentalDateModal` = base única de selección de fechas (desktop + mobile)

Un solo selector de fechas (`RentalDateModal`, responsive). Las fechas viven **solo en el cart-store**
(`useCart`); lógica compartida en `src/lib/rental-dates.ts`. No recrear selector/estado de fechas paralelo.

### 2026-05-30 — `backend/reservas/` = motor único de reservas (fuente única; el core sagrado tiene dirección física)

Todo cálculo de disponibilidad / chequeo de stock / overlap pasa por `backend/reservas/`. No duplicar
lógica de reservas en routes. Cambios al paquete = alto radio de explosión → **Opus**.

### 2026-05-31 — Expansión recursiva del motor de reservas (C4 #635)

Toda expansión de composición (forward + backward) es **recursiva hasta las hojas** vía la pieza única
`_expandir_mult` (`reservas/semantics.py`); gate lockea en `ORDER BY id`; `FOR UPDATE`/transacción
**byte-idénticos**. No reintroducir expansión inline de 1 nivel ni "otra función parecida".

### 2026-06-01 — Gotcha de Railway: fork de ambiente desincroniza la contraseña del Postgres

Ante `password authentication failed` en un ambiente recién forkeado: **resetear la contraseña en la BD**
por SSH + socket local (`ALTER USER`), no perseguir variables de entorno. Receta completa en el log.

### 2026-06-02 — Google Analytics: sin consent, solo catálogo público, ID administrado desde el back-office

Tracking en módulo único `src/lib/analytics.ts`, **un punto canónico por evento**; ID en
`app_settings.ga4_measurement_id`, expuesto **solo en prod** (`is_production`). ⏰ **Al crear un ambiente
no-prod nuevo**: agregar su nombre a `is_production` o dejar `VITE_GA4_ID` vacío (si no, trackea contra prod).

### 2026-06-03 — Esquema en dos capas: `init_db()` (bootstrap) + Alembic; toda tabla nueva va TAMBIÉN en `init_db()`

**Toda tabla/columna nueva va TAMBIÉN en `backend/database.py::init_db()`** (idempotente), no solo en una
migración Alembic. La visibilidad del estado de migraciones es fuente única en `migration_state.py`. El
supervisor marca tablas/columnas solo-en-migración o chequeos de estado reimplementados.

### 2026-06-03 — `backend/reportes/` = motor único de reportes financieros (espeja `backend/reservas/`)

Todo cálculo de reporte financiero (atribución/prorrateo/reparto de comisiones/agregación) vive en
`backend/reportes/`; el route es solo transporte HTTP + CSV. Modelo de comisiones **editable** desde el
back-office (default en `comisiones.DEFAULT_MODELO`). El supervisor marca cálculos de plata ad-hoc en routes.

### 2026-06-03 — Cierre de mes + clean start de la liquidación (junio 2026)

**Cerrar mes** = foto inmutable del reporte (`liquidacion_cierres`, motor `reportes/cierres.py`).
**Clean start:** pedidos con `fecha_desde < 2026-06-01` no cuentan para la liquidación — constante única
`LIQUIDACION_INICIO`, NO administrable. El **Resumen general de estadísticas sigue mostrando el histórico completo**.

### 2026-06-06 — El Presupuesto (PDF) muestra el IVA aparte, no sumado al total

En el **Presupuesto**, para un RI el total grande es el **neto** + sufijo **"+ IVA"** (no se suma el IVA).
**NO "arreglar" como bug** — es decisión del dueño. La **Factura A** sigue discriminando el IVA (motor intacto).

### 2026-06-06 — Datos del pedido: contacto en vivo, plata congelada

**Contacto (nombre/email/tel) → SIEMPRE en vivo** vía el helper único `_enriquecer_pedido_con_cliente`
(+ batch), en toda superficie. **Plata (precio/desc/ítems) → snapshot con lock por estado**: presupuestos
se recotizan, confirmados/cerrados conservan su snapshot. Perfil fiscal (razón social/CUIT) sí en vivo.

### 2026-06-06 — `backend/services/branding/` = motor único de assets de marca (SVG master → derivados)

Todo asset de marca sale del motor único (SVG master → derivados; `Logo.tsx` inyecta el wordmark inline).
No rasterizar/recolorear marca ad-hoc, no un `<img>` de wordmark nuevo, no resucitar `logo_url`/`upload-logo`.

### 2026-06-06 — `backend/busqueda/` = motor único de búsqueda textual (fuzzy + ranking)

Toda búsqueda de texto (clientes/equipos/catálogo) pasa por `backend/busqueda/` (`pg_trgm` + `unaccent`),
con normalización espejada en `src/lib/search/normalize.ts`. Nombre del cliente vía helper único. El
supervisor marca `ILIKE`/`LIKE` o normalizadores ad-hoc, e índices cuya expresión no sea la canónica.

### 2026-06-06 — Design system consolidado en la app; un solo skill de UI

El DS canónico es la app: componentes en `src/components/{ui,kit,rental}`, tokens/fuentes en `src/styles/`
(entry `src/ds-styles.css`). **Un solo skill: `importar-diseno`.** No reintroducir el paquete workspace
`@rambla/design-system` ni un segundo skill de DS; no duplicar una pieza que ya existe.

### 2026-06-07 — `backend/contabilidad/` = motor único de la plata "de adentro" (cierra #809)

Toda la plata interna (cajas/movimientos/saldos/rendición/P&L/cierre/reconciliación) vive en
`backend/contabilidad/`; los routes son transporte. Invariantes: ingresos de alquiler **derivan de
`alquiler_pagos`** (nunca recargados); la plata no se borra (**soft-delete** con motivo); **enteros ARS**;
**multi-moneda no se mezcla** (moneda inmutable tras crear); cobradores en la constante única `COBRADORES`
(+ `SOCIOS_HUMANOS`). **Socios (Pablo/Tincho) = cuenta corriente** (deudor/acreedor: `arranque + cobró −
su parte ± rendiciones`), NO cajas de plata: **no** suman al total disponible (esa plata la tiene el socio
en mano) y una cuenta corriente **negativa (acreedor) NO es error** de reconciliación; solo **Rambla/Fondo
Rambla** es caja de plata real (su parte no se resta). El supervisor marca cálculos de plata interna ad-hoc
fuera del paquete.

### 2026-06-08 — Memoria en dos sub-capas: digest enforceable + log de decisiones

La memoria se parte en **`MEMORIA.md` (digest enforceable, auto-cargado)** + **`DECISIONES.md` (log ADR
completo, on-demand)**, misma `### fecha — título` en ambos. Refina —no reemplaza— _Memoria en capas
(2026-05-25)_. Toda decisión nueva se escribe en los dos; `scripts/check-docs.mjs` verifica la paridad.

### 2026-06-19 — Staging-login: la sesión auto-prueba el back-office logueado

`POST /auth/staging-login` (doble llave **solo-dev**: `is_production` que falla-a-prod + secreto
`STAGING_LOGIN_SECRET`) mintea la cookie firmada para una cuenta de servicio en `ADMIN_EMAILS` de dev → la
sesión **smoke-testea flujos autenticados del back-office en staging vía `curl`**, no solo el camino 401/403.
**Refina —no reemplaza—** _El dueño testea, no revisa código (2026-05-25)_: el dueño sigue siendo el gate que
prueba en staging; la sesión verifica lo logueado antes de pasárselo. La admin-ness la sigue resolviendo
`is_admin_email` (el login no la saltea); en prod responde **404**. Setup solo-dev en `DEPLOY_RAILWAY.md`;
escrituras de prueba con IDs inexistentes para no mutar staging.

### 2026-06-20 — Gate de "frontend servible" + paths de assets a la raíz (no __file__ del paquete)

El healthcheck de Railway (`railway.json`) apunta a **`/health/frontend`** (503 si falta
`FRONT_NEW/index.html`; va en `middleware.PUBLIC_EXACT` porque el healthcheck es **sin auth**, si no 401 y
ningún deploy pasa) → un deploy que no sirve el SPA **no se promueve**. Cazó la caída de prod **#930**
(servía `"Frontend not built"`). Regla durable: las paths a assets de la **raíz** del repo
(`FRONT`/`FRONT_NEW` → `frontend/public`/`dist`) se anclan a la raíz, **no** con `Path(__file__).parent`
relativo al paquete — un **split** (`database.py` → paquete `database/`) las corre un nivel y quedan en
`backend/…`. Staging sirve el SPA por Railway igual que prod → el gate `/health/frontend` cubre **staging y
prod**. Regresión: `test_front_paths.py` + `test_health_frontend_gate.py`.

### 2026-06-20 — Iteración local con datos reales (clon de staging) + verificar sin mocks

Para iterar flujos autenticados / con datos reales: **backend local + BD de staging clonada a Postgres
local** (`pg_dump` read-only de la remota → restore local) + **staging-login** para impersonar
(`POST /auth/staging-login {target:"cliente"|"admin"}`; cliente por `STAGING_CLIENTE_EMAIL` o `cliente_id`).
**Nunca** apuntar el backend local a la BD remota: `init_db()` corre al startup y le escribiría el esquema +
expone PII (clon = solo lectura sobre la remota). `.env` local gitignored. El loop render-compare se valida
con **datos/assets reales, no solo mocks** (así apareció el wordmark custom no themeable). Extiende
_Staging-login (2026-06-19)_ al portal cliente y al loop local; setup en `DEPLOY_RAILWAY.md`.

### 2026-06-20 — TopBar modular por área: shell único, color de marca, logo themeable

Un **shell único** (`TopBarShell`, `components/rental/TopBar.tsx`) → TODAS las variantes
(rental/estudio/workshops/cliente): mismo alto/padding/logo, **color de marca por área** y **logo blanco
themeable** (el wordmark normaliza sus fills a `currentColor`; isologo mono vía `LogoMark`). **Fuente única**
de las áreas en `src/data/areas.ts` (label/desc/href/color), consumida por el topbar Y el menú. La
navegación entre áreas vive en un **menú hamburguesa** (sheet con identidad del hub). **Mobile simplifica**:
label del área solo si hay lugar (no con date pill central), acciones redundantes (CTA de sección,
perfil/salir del portal) al menú, logo a la izquierda; la landing (`/`) no lleva topbar. Materializa la
_Filosofía de diseño del DS (2026-06-20)_ en la navegación; detalle en `DESIGN_SYSTEM.md`. El supervisor
marca un topbar fuera del shell o una lista de áreas duplicada.

---

## Preferencias (cómo quiero que se hagan las cosas)

### 2026-05-25 — El dueño testea, no revisa código

El gate humano del dueño es **probar la conducta**, no leer diffs. Todo cambio testeable se acompaña de un
**plan de prueba en lenguaje claro** ("andá a /X, hacé Y, tenés que ver Z").

### 2026-05-25 — La conversación es para decisiones, no para el ruido de commits

La sesión gira en torno a decisiones y a la forma de hacer las cosas, no al detalle de cada diff/commit.
El trabajo pesado de revisión va al subagente `supervisor` (contexto aislado) → a la conversación, el veredicto.

### 2026-05-25 — Barra de calidad de ingeniería (cómo construimos)

(1) **Modularidad a prueba de balas** (no copiar-pegar variantes; extraer a módulo único). (2) **Nada de
hotfixes** (robusto > parche). (3) **Mobile-first + performance + sin bugs**. (4) **Consistencia visual /
design system** (nada ad-hoc por pantalla). (5) **Código prolijo** aunque el dueño no lo lea. (6) **El core
de reservas es sagrado** (cero overlap). El supervisor marca como hallazgo cuando un cambio los viola.

### 2026-05-25 — Protocolo de brain-dumps del dueño

Triagear **cada ítem en el acto** y devolver un mapa corto: **principio durable** → propuesta a la memoria
(con aprobación); **trabajo** → GitHub Issue; **pregunta** → respuesta; **idea cruda** → igual va a issue.
**Nada se borra.**

### 2026-05-25 — Minutos de GitHub Actions: cuota a cuidar SOLO si el repo vuelve a privado ⏰

Regla **dormida** mientras el repo es público (Actions ilimitado). Higiene que vale siempre: batch de
commits, `paths-ignore` de docs, `concurrency: cancel-in-progress`. ⏰ Si vuelve a privado, cuidar la cuota.

### 2026-05-26 — Sesión local para trabajo visual/testeable _(reemplazada 2026-06-08)_

Reemplazada por _Workflow de cambios (2026-06-08)_: se pushea a `dev` y se ve en staging. La sesión local queda
solo para debugging muy específico sin acceso a Railway, no es el flujo default.

### 2026-05-26 — Al actualizar gobernanza, barrer todo el sistema de supervisión

Al editar un doc de gobernanza (`MEMORIA`/`DECISIONES`/`CLAUDE`/`MANIFIESTO`/`PROTOCOLO`/`supervisor`/docs),
hacer en la misma pasada una **lectura comprensiva del sistema completo** para cazar cross-refs viejas
(conteos, punteros a archivos/secciones que ya no existen, decisiones que una nueva contradice).

### 2026-05-26 — Eficiencia de sesión: modelo según tarea + limpiar contexto

**Auditar/planificar/decidir/arquitectura o cambio delicado (core de reservas)** → Opus. **Ejecutar**
(prompt bien especificado, fixes con tests, mecánico) → Sonnet. No usar ventana 1M salvo necesidad real.
`/clear` entre tareas independientes; `/compact` a mitad de una iniciativa larga.

### 2026-06-05 — Apple HIG como guía de UX mobile/táctil (enforceable)

La referencia default para UX mobile/táctil es **Apple HIG**. Materialización: **tap target mínimo 44×44px**
(`h-11 w-11`); inputs ≥ 16px; `.safe-*` cerca de notch/home-bar. El valor vive en los specs del DS (no acá).
El supervisor marca un tap target nuevo < 44px o una decisión táctil que contradiga HIG sin justificación.

### 2026-06-20 — Filosofía de diseño del DS: enforceable, la esencia del front

Toda UI nueva o rediseñada sigue la **Filosofía de diseño** del DS (`DESIGN_SYSTEM.md`, primera sección,
11 principios): la info se tiene que ver (contraste/peso reales), **estado + plata visibles** (`Debe $X`,
no "sin seña" gris), un foco por pantalla, **una sola forma de hacer cada cosa** (sin controles/botones
duplicados), lo más usado a mano, reconocimiento > lectura (avatares/pills), densidad sin aire muerto,
**reusar no recrear** (la forma del pill vive en `kit/Pill`; `EstadoBadge`/`PagoBadge` derivan, cero clases
copiadas), mobile/a11y no son extra, el core es presentación. El supervisor la hace cumplir; el detalle
vive en el doc. Es la contraparte visual de la _Barra de calidad de ingeniería (2026-05-25)_.

### 2026-06-20 — Fijarse en el repo antes de implementar (sobre todo tras mergear dev)

Antes de codear algo, **verificar si ya existe** en el repo —con prioridad tras mergear `dev`, porque lo que
avanzó allá puede ya cubrir el pedido (caso: el staging-login de cliente ya estaba hecho, #961). Vale para
features, helpers, endpoints y patrones. Refuerza la _Barra de calidad de ingeniería (2026-05-25)_ (no
duplicar, fuente única); el supervisor marca reimplementaciones de algo ya presente.
