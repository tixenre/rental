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

### 2026-06-08 — Workflow de cambios (fuente única): dev = staging, push directo siempre, PR solo para prod

**Fuente única del workflow** (consolida 6 decisiones de flujo previas; refinado 2026-06-25).
`dev` (rama `dev`) = **staging** en Railway (auto-deploy en cada push; base copiada de prod, sin
clientes); `main` = **prod** (sagrado, no se prueba ahí). **Todo cambio va en push directo a `dev`** —
si algo se rompe en staging se pushea el fix, no hay clientes ahí. **PR solo para `dev → main`** (la
puerta a prod). **Nunca a `main` directo; no pushear con CI en rojo.** El **CI corre en cada push** a
`dev`/`main`. **La sesión pushea a `dev` sola y avisa con plan de prueba — no pide permiso.**
**Gates del dueño:** probar en staging + aprobar `dev → main` (helper: `scripts/pre-promote.sh` lista el
scope + checklist antes de promover). Merge `dev→main` = merge commit
(revert por PR). Commits atómicos, Conventional Commits en español.

### 2026-06-08 — Issues: la cola espeja el código (Closes #N → auto-cierre en dev→main; diferido aparte)

Refina _Memoria en capas_ ("Issues = cola"). **Issue solo para trabajo diferido / multi-sesión /
brain-dump del dueño**; lo hecho-y-mergeado en la misma sesión **no lleva issue** (el commit es el
registro). Toda issue trabajada lleva **`Closes #N`** en el commit (directo a `dev`) o el PR; como la
branch default es **`main`**, se **auto-cierra al promover `dev → main`** (cuando shippea a prod) —
citar la issue, no solo el `#PR`. La **promoción `dev → main` reconcilia**: su PR lista las issues que
cierra el lote → cierre en bloque con evidencia. Features grandes diferidas con label **`someday`**
(separa lo diferido de la cola activa; no es deuda sin cerrar). Triage **liviano y seguido** vía skill
`pendientes`: verificar que shippeó antes de cerrar. Iniciativa multi-sesión = **un** issue de
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

Toda expansión de composición es **recursiva hasta las hojas** vía la pieza única `_expandir_mult`. **No
reintroducir expansión inline de 1 nivel ni "otra función parecida"**; el `FOR UPDATE`/transacción del gate
son byte-idénticos (no se tocan). Cómo → [`backend/reservas/CLAUDE.md`](../backend/reservas/CLAUDE.md); porqué → `DECISIONES.md`.

### 2026-06-01 — Gotcha de Railway: fork de ambiente desincroniza la contraseña del Postgres

Ante `password authentication failed` en un ambiente forkeado: **resetear la contraseña en la BD** (`ALTER
USER` por SSH), no perseguir env vars. Receta → [`DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md) §Troubleshooting.

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

### 2026-06-06 — Design system consolidado en la app; `design-system` gobierna, `pulido-frontend` aplica

El DS canónico es la app: primitivos en `src/design-system/{ui,composites}`, componentes de negocio en
`src/components/{rental,admin}`, tokens/fuentes en `src/design-system/styles/` (entry
`src/design-system/ds-styles.css`). **El skill `design-system` (opus) gobierna** (audita sistémicamente,
dashboard `/ds`, propone issues); **`pulido-frontend` aplica** los fixes en pantalla. `importar-diseno`
archivado — el diseño se refina directamente en Claude Code, no desde handoffs externos. No reintroducir el
paquete workspace `@rambla/design-system`; no duplicar una pieza que ya existe.
_(Paths actualizados post-PR #981 — reorg a `src/design-system/`.)_

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

El healthcheck `/health/frontend` (`railway.json`, en `middleware.PUBLIC_EXACT` porque es **sin auth**) → un
deploy que no sirve el SPA **no se promueve** (cazó la caída de prod **#930**). Regla durable: las paths a
assets de la **raíz** (`FRONT`/`FRONT_NEW`) se anclan a la raíz, **no** con `Path(__file__).parent` del
paquete (un split las corre un nivel). Cubre staging y prod. Cómo + runbook →
[`DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md); regresión: `test_front_paths.py` + `test_health_frontend_gate.py`.

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

### 2026-06-22 — Creación de pedidos concurrente: serializar por equipo con advisory lock (no tocar el gate)

Reservas concurrentes del mismo equipo se deadlockeaban → **500 intermitente**. Fix: `create_pedido` toma
`pg_advisory_xact_lock` por equipo **en orden de id** ANTES de insertar; `create_pedido_retry`
(`routes/alquileres/core.py`) es la **puerta única** de creación y reintenta → **503** si persiste, **nunca
500**. **NO toca el `FOR UPDATE`** (motor sagrado). Refina _motor único de reservas (2026-05-30)_;
verificación (15 paralelas → 0×500) + PR #969 → `DECISIONES.md`.

### 2026-06-22 — Los hallazgos de una auditoría son hipótesis: confirmar (código + en vivo) antes de arreglar

Un hallazgo de auditoría —de un agente o un harness— es **hipótesis, no hecho**: se re-confirma en el
código + **en vivo** (Chrome MCP: clickear, medir computed styles por JS, ver la red) antes de
arreglarlo. En una pasada real varios eran falsos: el bug del mini-bar estaba en otro componente, el
"catálogo en blanco" era artefacto del harness (glob que matcheaba un módulo fuente en dev), los
overflows de admin estaban stale, los contrastes "1.66/1.73" eran del parser, y los datos "rotos"
(DESTACADA, `nombre_publico`) estaban bien. Contraste oklch → **recalcular del token**
(OKLab→sRGB→WCAG), no creerle al parser. Refuerza _honestidad > actividad_ y _fijarse en el repo antes
de implementar (2026-06-20)_; el detalle de método vive en el skill `auditoria-profunda`.

### 2026-06-22 — CTA primario = ink + texto hueso (no dorado); el dorado es la jugada del hover

El `variant="primary"` del `Button` es **fondo ink + texto hueso/bone** en reposo (`bg-ink text-background`) e
invierte a **`--area-accent` + ink** en hover (`hover:bg-[var(--area-accent)] hover:text-ink`): amber en rental,
naranja en estudio, rosa en workshops. El texto hueso en reposo es **decisión de marca del dueño, NO un bug**:
no "corregir" a dorado — el accent del hover es la jugada de la _reverse signature_ ink↔área. Materializa la
_Filosofía de diseño del DS (2026-06-20)_ (una sola forma del CTA). El supervisor marca un CTA primario cuyo
hover invierta a un color fijo en vez de `--area-accent`, o un `<button>` crudo que reimplemente el gesto.

### 2026-06-23 — Capa de skills auto-gobernada y portable: registro verificado + routing de modelo + loop de aprendizaje

La capa de skills se gobierna como el código y la memoria (**fuente única + guardrail mecánico +
propone-no-escribe**). El **mapa canónico** es la tabla "Skills — cuál uso para qué" de `CLAUDE.md` (árbol
de decisión por disparador + columna **Modelo**); `scripts/check-docs.mjs` —config-driven vía
`.claude/governance.config.mjs`, **portable a otros repos**— verifica que todo skill en disco esté listado
ahí (Bloque 4) y bien formado (Bloque 5: frontmatter `name`/`description`/`model`/`last-reviewed`/`version`;
staleness = warning). El **routing de modelo** materializa _Eficiencia de sesión (2026-05-26)_ en el `model:`
de cada skill (criterio/diagnóstico→**opus**, ejecución→**sonnet**; los de criterio delegan la ejecución a
subagentes `sonnet`). Blueprint del Curator de Hermes Agent, **nativo** (no un segundo agente). El **loop de
aprendizaje** (Etapa 1B): buzón `docs/PROPUESTAS_SKILLS.md` (auto-mejora **propone**, el dueño aprueba),
telemetría de uso por hook y check-in proactivo de la cola. Plantilla `.claude/skill-template.md` (fuera de
`skillsDir`). El supervisor marca un skill en disco sin fila en `CLAUDE.md` o un `model:` que no pegue con el task.

### 2026-06-23 — Gobernanza Etapa 2: Auto-mejora universal + meta-skill gobernanza (dashboard, auditoría, dry-run)

**Auto-mejora propagada a todos los skills activos** (`mantenimiento`, `auditoria-profunda`, `pulido-frontend`,
`gear-compatibility`; `importar-diseno` recibió la sección pero fue archivado en 2026-06-23). El linter (Bloque 5 de `check-docs.mjs`) ahora **exige**
`## Auto-mejora` en todo `SKILL.md` — skills sin ella fallan el CI. El **meta-skill `gobernanza`**
(`.claude/skills/gobernanza/SKILL.md`, `model: opus`) implementa el loop completo: dashboard `/skills`
(qué hay, último uso del ledger, staleness, propuestas pendientes), auditoría profunda de drift/overlap/
bloat/routing de modelo, consumo del buzón + ledger, consolidación en modo **dry-run** (propone-no-borra,
archiva a `.claude/skills/.archive/`), y cierre de gobernanza por volumen del buzón (≥5 propuestas, _2026-06-29_). Modo propone-aprobás en todos los pasos.
El supervisor marca skills sin `## Auto-mejora` o un `gobernanza` que aplique cambios sin aprobación.

### 2026-06-23 — pendientes (ex-`cola`) = skill único de administración de la cola (issues/feature-requests); Frente D apunta acá

Toda administración de la cola (reconciliar issues abiertos contra commits/PRs shippeados para cazar
**hecho-pero-abierto**, triagear con evidencia, deduplicar trackers, etiquetar, intake de brain-dumps, reporte
"¿cómo están los pendientes?") vive en el skill **`pendientes`** (`.claude/skills/pendientes/SKILL.md`; renombrado
2026-06-25 desde `cola` por nombre poco descriptivo + colisión con "GitHub Issues"), **fuente única**, para que
tenga la atención continua y liviana que necesita. El **Frente D de `mantenimiento` apunta acá** (ya no duplica
el método). Refina _Issues: la cola espeja el código (2026-06-08)_ y _Protocolo de brain-dumps (2026-05-25)_.
Regla de oro: **cerrar es afirmar** → solo con evidencia (PR/commit) o la orden del dueño; el dueño dirige, la
sesión recomienda.

### 2026-06-23 — design-system = gobernador del DS; importar-diseno archivado

El skill **`design-system`** (`model: opus`) gobierna el Design System: audita sistémicamente (tokens, adopción,
reimplementaciones, 11 principios, drift del doc), dashboard `/ds` (estado rápido sin auditoría completa), propone
issues — `pulido-frontend` los aplica. Es **read-only**: nunca edita código. **`importar-diseno` archivado** — el
diseño se refina directamente en Claude Code, no desde handoffs externos; su rol de implementar lo toma
`pulido-frontend` cuando aplique. El cuadro completo: `design-system` gobierna · `pulido-frontend` ejecuta UI ·
`mantenimiento` ejecuta código. Refina _Design system consolidado (2026-06-06)_.

### 2026-06-23 — 6 skills nuevos: calidad-codigo, auditoria-seguridad, performance, specs, catalogo, calidad-tests

Capa de skills ampliada con 6 skills de auditoría y gobernanza (todos `model: opus`, proponen-no-aplican):
**`calidad-codigo`** (TypeScript, React patterns, duplicación lógica, complejidad); **`auditoria-seguridad`**
(OWASP, auth, CORS, headers, secretos, deps vulnerables); **`performance`** (bundle, code splitting, N+1, caching,
Core Web Vitals); **`specs`** (taxonomía de specs de equipos: consistencia, gaps, specs informales); **`catalogo`**
(completitud de datos: fotos, descripciones, precios, specs mínimas por categoría); **`calidad-tests`** (cobertura
de módulos críticos, calidad de assertions, edge cases sin tests). Todos son read-only y siguen el patrón
propone-aprobás. `scripts/check-docs.mjs` los verifica como al resto.
**Consolidación a 2 (`auditoria-codigo`+`auditoria-datos`) medida y RECHAZADA (2026-06-27, Exp 2):** mergear
los 4 de código en uno carga los 4 lentes por invocación (**3.1× el costo** del skill puntual; el caso común
es 1 lente) y el routing ya era **12/12 separado** → no aporta. Se mantienen los 6. **No re-mergear** sin un
diseño de carga on-demand por lente.

### 2026-06-23 — docs/MARCA.md = hub de marca; skill `marca` gobierna el inventario de features

**`docs/MARCA.md`** es la fuente canónica de identidad de marca: quiénes somos, selling points por área
(rental completo; estudio y workshops con `[TODO]` para que el dueño complete), voz/tono (referencia a
`DESIGN_SYSTEM.md`), assets canónicos (URL, handle Instagram, rutas de logo). El inventario detallado de
features de cara al usuario vive en **`docs/CAMPAÑA_FEATURES.md`** (no se duplica). El skill **`marca`**
(`model: opus`, read-only) audita que las features reales de la app estén reflejadas en ambos docs, detecta
features nuevas sin comunicar y selling points stale, y propone borradores de copy para aprobación del dueño.

### 2026-06-25 — Hero (LCP) = AVIF-directo + preload AVIF; el resto usa `picture`; SSR descartado

El **elemento LCP** (hero) se sirve con `<img src=avif>` **directo** (NO `<picture>`) + `onError`→webp vía el
helper único `heroImgProps`; el backend preloadea el AVIF (un preload AVIF no matchea un `<source>` de
`<picture>`). **Toda otra imagen** usa el `<picture><source avif><img webp>` canónico; **webp NO se elimina**
(es el fallback). **SSR descartado** (techo SPA ~80 mobile / ~91 desktop es sano — no re-evaluar). **El
supervisor marca un `<picture>` en el LCP, o un `<img src=avif>` sin `onError`→webp fuera del LCP.** Cómo
(preload, orden de foto principal, gotchas) → [`SISTEMA_FOTOS.md`](SISTEMA_FOTOS.md).

### 2026-06-25 — Manuales técnicos por sistema (`SISTEMA_X.md`): fuente única del "cómo", linkea a MEMORIA el "porqué"

Cada motor/sistema importante tiene un manual técnico **`docs/SISTEMA_<X>.md`** (molde: `SISTEMA_SPECS.md`) =
**fuente única del cómo funciona** (arquitectura + flujo + los paths como puntos de entrada). **Describe, no
decide**: las reglas de criterio y el _porqué_ viven en `MEMORIA.md`/`DECISIONES.md` y se **linkean**, no se
copian (dos verdades = drift). Índice maestro en **MANIFIESTO §8 "Dónde encontrar cosas"**. El manual se
actualiza en el **mismo cambio** que toca su motor; el supervisor marca un manual stale o una regla duplicada
que debería ser un link. `check-docs.mjs` verifica que los manuales referenciados existan (links vivos). **NO
se crea un skill por esto** — un manual es un doc (fuente de verdad), no un proceso; su mantenimiento cae en el
supervisor + `check-docs`, no en la capa de skills (que tiene su propia gobernanza anti-bloat). Piloto:
**`SISTEMA_FOTOS.md`** (fotos = procesar + mostrar). Ya existen `SISTEMA_SPECS.md`, `FLUJO_PEDIDOS.md`,
`DESIGN_SYSTEM.md`.

### 2026-06-26 — skill `consejo`: juicio crítico de propuestas como fuente única, rigor escalable, memoria separada

El juicio de propuestas/ideas/planes antes de construir vive en el skill **`consejo`** (fuente única — no
ad-hoc en la sesión general). El consejo **no escribe** en `MEMORIA.md`/`DECISIONES.md` del repo: tiene su
propia `BITACORA.md` con autoridad separada (lo que juzgó el consejo ≠ lo que decidió el dueño). Default:
pase crítico eficiente (~10-15k, sin subagentes); escala a voces aisladas solo si la decisión justifica el
gasto. El supervisor marca: (a) propuesta mediana/grande juzgada sin invocar el skill; (b) veredicto del
consejo promovido a `MEMORIA.md` sin autorización del dueño.

### 2026-06-26 — Theming por área: `--area-accent` cascade + `--color-estudio` token propio

El accent de marketing de cada sección pública resuelve por `[data-area]` CSS cascade: `--area-accent` /
`--area-accent-soft` / `--area-accent-hot` en `:root` (default → amber); `[data-area="estudio"]` →
`--color-estudio` (`#E9552F`). `PublicLayout` inyecta el `data-area` por área. Los componentes consumen
`var(--area-accent)` sin saber el contexto. **`--color-estudio` es token propio** — no reusar
`--color-naranja` (es status Warning, misma hex, semántica distinta). **Focus rings, estados de UI
cross-app, badges del kit, back-office y paleta de status → amber/status fijos, nunca por área.**
El supervisor marca: `bg-naranja` donde debería ir `var(--area-accent)` en marketing del estudio;
o `--color-naranja` en contexto de marketing de área.

### 2026-06-27 — Medir lo barato-e-incierto; juicio + reversibilidad para el resto (empirismo proporcional)

Todo cambio que "paga" se valida empíricamente, pero **PROPORCIONAL**: se mide solo lo _barato-de-medir Y
incierto-en-resultado_ (¿el digest se sigue haciendo cumplir tras un trim? ¿el routing sobrevive a un merge de
skills?), con la **señal más barata** que conteste "¿ayudó o perjudicó?". Lo reversible-y-obvio (un doc, un
1-liner del digest) se decide con **juicio + git**, no con un eval. La medición **nunca cuesta más que lo
medido**; un eval que gatea 0 regresiones reales se retira (como `consejo`). Foundation en `scripts/evals/`
(reusa pytest `-m golden` + `ui-audit.mjs` `LABEL=before/after` + dispatch del `supervisor`); detalle en el log.
Acota _Los hallazgos de una auditoría son hipótesis (2026-06-22)_: la confirmación ahora tiene método y techo de costo.

### 2026-06-27 — Filosofía de trabajo derivada del corpus, mantenida como hipótesis (defaults, no leyes)

Los principios de cómo se desarrolla/mantiene el repo **se derivan del corpus** (no se declaran) y viven
**auto-cargados en `CLAUDE.md`** (sección "Filosofía de trabajo"). Son **defaults, no leyes**: ante un
pedido que va en contra, la sesión lo **nota, nombra el principio y explica el porqué** (red contra la
confusión del dueño) y, si el dueño confirma, **procede** — la **excepción no deroga** el principio; solo
un **patrón repetido** o un **cambio de criterio explícito** lo muta. **Aplicarlos es default de la sesión,
no se pide** (mismo loop que el `## Auto-mejora` de los skills: el sistema detecta y propone, el dueño
aprueba). Los **mantiene** el supervisor (testea cada lote: _excepción puntual_ vs. _drift recurrente_ →
propone mutar) + `gobernanza` (re-deriva cada 2 cierres de gobernanza). El supervisor marca un principio aplicado
como ley rígida (sin permitir excepción confirmada por el dueño) o una mutación grabada sin su aprobación.

### 2026-06-27 — PR como hoja de ruta: rama aislada → PR scoped del tema → issue de tracking → batch a prod

Refina _Workflow de cambios (2026-06-08)_ para el trabajo **grande/encapsulado** (el push-directo-a-`dev`
sigue para lo chico). Un tema = **una rama aislada** → se trabaja y commitea → **un PR scoped del tema** (no
uno por commit, no varios por fase), que queda como **hoja de ruta + historial** legible de qué se hizo; los
PR del tema se dejan **sin mergear** (el dueño es el gate que clickea). La **issue de tracking** es la
**historia** que apunta a esos PR (un issue por iniciativa, espeja _Modus operandi (2026-05-25)_). A prod va
en **batch `dev → main`** (un PR de promoción que reconcilia el lote, espeja _Issues (2026-06-08)_). Tensión
de git resuelta: un PR no puede apuntar a `dev` y `main` a la vez → PR-del-tema→`dev` + PR-batch `dev→main`,
atados por la issue. El supervisor marca un PR por-commit, un tema partido en varios PR sin razón, o issues
duplicadas por fase.

### 2026-06-27 — DAL = wrapper fino `database/core.py` (NO ORM); guardas SQL mecánicas; sync + psycopg3

El acceso a datos vive en el **DAL único** `PGConnection`/`PGCursor` (`backend/database/core.py`) — **no
ORM**. Guardas mecánicas (`_assert_pct_safe` + `_assert_params_present`) enforcan lo que era convención en
prosa: todo VALOR como bound param; el único `%` válido es placeholder (`%s`/`%(name)s`) o `%%` — un `%`
literal en SQL es bug (el comodín de `LIKE` va en params); placeholders sin params falla fuerte. **Código
nuevo usa `%s` nativo**; el `?` legado (herencia sqlite3) migra a `%s` por fases bajo la red, **core sagrado
último**; `lastrowid` (7 usos) → `RETURNING` vía helper `insert_returning()`. Driver: **psycopg3 sync**.
**NO adoptar SQLAlchemy/SQLModel ni async** — evaluados a fondo (evidencia + consejo, 4 alternativas): no
encajan en app **DB-bound, SQL-crudo-por-elección, con core de reservas complejo + Alembic ya presente** (SA
aportaría algo solo en CRUD simple aislado, que ya está hecho). Revisita solo si: equipo >10 / multi-DB /
necesidad de ORM o tiempo-real. El supervisor marca: `?` nuevo en código nuevo, `%` literal en SQL, y
reimplementación o bypass del DAL.

### 2026-06-28 — La ganancia de Rambla descuenta la comisión de los dueños (es costo, no ganancia)

La **ganancia neta** del Reporte mensual es **la parte de Rambla − gastos**, NO el total facturado − gastos. La
comisión que se llevan los dueños de los equipos (Pablo/Tincho/terceros, del reparto de la liquidación) es un
**costo**, no ganancia de Rambla. El P&L muestra la cascada: **facturado − comisiones a dueños − gastos =
ganancia**, con `comisiones_duenos = facturado − parte_rambla` (robusto a cualquier beneficiario). Corrige el
criterio viejo (ingreso = total devengado, en `pyl.py`) que inflaba la ganancia con plata que Rambla les debe a
los dueños. Solo afecta cuando hay equipos de dueños ≠ Rambla. No toca el reparto/rendición (ya estaban bien).
Regresión: `test_reporte_ganancia_descuenta_comision_de_duenos`.

### 2026-06-29 — Retro de iniciativa: el cierre de algo importante dispara un retro que reparte aprendizajes

El cierre de un cambio sustancial de producto (iniciativa o bug grande, por **tamaño de diff vs `origin/dev`**:
≥4 archivos **o** ≥150 líneas) dispara un **retro** que analiza qué rindió/qué no (**honestidad > actividad**) y
**reparte** cada aprendizaje a su destino: método de skill → buzón `PROPUESTAS_SKILLS.md` (autónomo); criterio/
arquitectura → `MEMORIA`+`DECISIONES` (OK del dueño); gotcha cómo-funciona-X → `SISTEMA_*` (OK); principio →
`CLAUDE.md` Filosofía (OK); diferido → issue vía `pendientes` (autónomo); nada → decirlo. **Hook `check-retro.sh`
= disparador** (gemelo de `check-governance-review.sh`, filtro disjunto = código de producto; corre en terminal/
desktop; surfacea, no despacha ni reemplaza al de gobernanza) · **skill `gobernanza` §7 = método** · **dueño =
gate** (dos OK: ¿corro el retro? → reparto ítem por ítem). Semi-automático: el hook recuerda, la sesión juzga, el
dueño aprueba. Propone-no-aplica salvo buzón e issues. Aplica la cláusula de retiro del harness de evals.
**El disparador mide TAMAÑO (proxy barato); el rinde lo da la NOVEDAD** (criterio/arquitectura/principio nuevo, no
líneas) → al primer OK la sesión **estima el rinde por novedad** ("rutinaria, reusó X → flaca" vs. "terreno nuevo en
Y → vale") para que el dueño gatee informado y temprano, no tras gastar el análisis (refinado 2026-06-30).

### 2026-06-29 — `backend/services/contenido/` = puerta única de "qué incluye un producto" (display derivado de la receta real)

Todo el **display** de "qué incluye un producto/kit" (vista en carrito/ficha, packing list, buscar por contenido,
repetir pedido, listas, compartir) pasa por la **puerta única** `backend/services/contenido/`, que **deriva del
mismo `kit_componentes`** que usa el motor de reservas → el display **no puede desincronizarse** de lo que se
reserva. Nuevo miembro de la familia motor-único. Devuelve los componentes **directos (1 nivel)** para mostrar; el
**gate expande recursivo** (`reservas.semantics`). **No toca el motor** (solo SELECTs de lectura, sin locks ni
transacción — core sagrado intacto). El soft-delete lo decide el flag **`solo_activos` por superficie** (no
incondicional): `True` catálogo/ficha (oculta retirados, default) · `False` documentos/detalle de un pedido ya
hecho (muestra todo lo que la receta referencia) — vuelve **explícita** la diferencia que antes era drift
accidental (`attach_kit` filtraba, `get_kit` no). La garantía no es "lista idéntica" sino **misma fuente** (puerta
directa == `reservas.semantics`, a equipos no retirados). Candados: `test_contenido_puerta_db.py` (misma fuente
que el gate) + `test_contenido_sql_safety.py` (prohíbe SQL inline de `kit_componentes`). El supervisor marca
display de "qué incluye" ad-hoc fuera de la puerta. Cómo → [`SISTEMA_CONTENIDO.md`](SISTEMA_CONTENIDO.md);
tracking #1087.

### 2026-06-29 — Cierre de gobernanza disparado por volumen del buzón (no por calendario)

El **cierre de gobernanza** (§6 del skill) deja de ser **mensual** y se dispara **por volumen**: cuando el
buzón `PROPUESTAS_SKILLS.md` junta **≥ 5 propuestas pendientes** (constante `THRESHOLD` tuneable en el hook;
**N=5** de arranque, se afina con el ritmo real — empirismo proporcional _2026-06-27_). Lo **surfacea solo**
el hook `check-buzon.sh` (SessionStart, gemelo de `check-pendientes.sh`; terminal/desktop, no web/celu) → la
sesión le pregunta al dueño si corre el cierre; el dueño es el gate. **Sin piso de tiempo:** buzón quieto =
nada que triagear = correcto; el resto del cierre (staleness de manuales, skills > 120 días) ya tiene su
propia red (supervisor + `check-docs`), así que el **buzón es la señal correcta** para gatillar (mismo
criterio que `check-retro.sh`: por volumen/diff, no por fecha). La **re-derivación de principios**
(anti-congelamiento) va **cada 2 cierres**, no en cada uno (re-derivar sobre poco corpus agrega ruido).
Refina —no reemplaza— la cadencia "mensual" de _2026-06-23 (Etapa 2)_ y _2026-06-27 (Filosofía derivada)_.
El supervisor marca un cierre gateado por calendario en vez de por volumen.

### 2026-06-29 — `backend/auth/` = motor único de autenticación (multi-método sobre una sesión única, aditiva)

Toda la auth vive en el paquete-motor **`backend/auth/`** (sesión, guards, OAuth Google, passkey, staging,
revocación) — como `reservas/`/`contabilidad/`. **Todos los métodos de login convergen en UNA cookie firmada**
(`session`), que mintea el **punto único `_make_session_response`**; los guards (`require_admin`/`require_cliente`)
solo la **leen** (agnósticos del método). Passkey es **aditivo** a Google (no lo reemplaza; Google = anchor de
identidad + recuperación). El supervisor marca un `set_cookie("session")` crudo fuera de `_make_session_response`
(no heredaría jti/revocación) o lógica de auth (guard/mint de sesión) recreada fuera del paquete. Cómo →
[`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); historia → PR #1095 (passkey) + #1100 (consolidación).

### 2026-06-29 — Revocación de sesión: allowlist `auth_sessions` + `jti` obligatorio (corte limpio, anti-IDOR)

La sesión es **revocable server-side**: la cookie firmada lleva un `jti` opaco y la allowlist **`auth_sessions`**
decide si vive (`get_session` valida firma **Y** `is_active`: no revocada, no vencida). **`jti` OBLIGATORIO
(corte limpio):** una cookie sin jti (las viejas pre-deploy, las hand-minted de tests) se **rechaza** → re-login;
**ninguna sesión válida queda fuera de la tabla**. Logout y "cerrar mis otras sesiones" son **reales** (revocan
el jti; `revoke_all` preserva la actual con `except_jti`). Revocaciones **owner-scoped** (el `WHERE` incluye el
dueño, no solo el jti → anti-IDOR), espejando `passkey/store`. Tabla en 2 capas (_2026-06-03_), DAL `%s`
(_2026-06-27_), tiempos en `now_ar()`. El supervisor marca una sesión sin pasar por `_make_session_response` (sin
jti) o una revocación no scopeada al dueño. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); historia → PR #1102/#1103.

### 2026-06-29 — `backend/services/carrito/` = módulo único de la lógica del carrito (intención; el gate es la verdad)

Toda la **lógica del carrito** —la intención "esto quiero reservar"— vive en la puerta única
`backend/services/carrito/`: **selección** canónica (`SeleccionItem` + `normalizar_seleccion` único:
dedup/clamp/filtro/cap, antes duplicado byte-por-byte en compartir/listas), **activos/abandonados**
(heartbeat/funnel/`marcar_confirmado`) y **readiness** (`precios_catalogo_para_reserva`: gate `visible_catalogo`
+ el cliente no decide el precio, y **handoff** a `create_pedido_retry` — NO crea la reserva). **Referencia, no
reimplementa** los motores: stock→`reservas` (sagrado, solo lee), plata→`services/precios`, qué-incluye→
`services/contenido`, creación→`create_pedido_retry`. Invariante de plata **cotizado == cobrado**: el precio
efectivo por jornada lo resuelve UNA función, `precios.precio_jornada_efectivo` (combo→`precio_combo`;
kit/simple→propio), consumida por los 3 caminos que persisten plata (cotizar/crear/modificar) — cierra el drift de
combos por construcción. **Las 3 tablas NO se unifican** (ciclos de vida distintos); sí la forma del ítem. El
supervisor marca lógica de carrito ad-hoc fuera de la puerta o un precio de combo resuelto inline. Nuevo miembro de
la familia motor-único (espeja contenido 2026-06-29). El **split de `routes/alquileres/core.py`** queda fuera: es
lógica de **alquileres**, no del carrito (se tocan, pero es otro motor) → su propio PR. Cómo →
[`SISTEMA_CARRITO.md`](SISTEMA_CARRITO.md); tracking #1110.

### 2026-06-29 — El front no calcula plata: la pide al backend y la muestra

**Ningún número de plata se calcula en el front.** El backend lo resuelve (el total vía
`services/precios.calcular_total`; el precio por ítem vía el resolutor único `precio_jornada_efectivo`) y lo
devuelve ya hecho; el front **solo renderiza** —a lo sumo **suma** valores que el backend ya le dio para mostrar—,
nunca aplica reglas de precio/descuento/IVA/combo. **Generaliza** _cotizar = fuente única (#617)_ de "el total" a
**todo** número de plata, incluido el estimado/teaser del carrito (era la raíz del drift de combos cotizado≠cobrado:
el front multiplicaba el precio crudo). El **cómo se muestra** (lo visual) es decisión aparte. **FASE 3 del carrito
se implementa así:** el service devuelve los precios resueltos, el front los muestra (para mantenerlo instantáneo,
cada equipo puede traer su precio efectivo desde el catálogo → el front suma, no calcula). El supervisor marca una
regla de precio/descuento/IVA/combo recalculada en el front.

### 2026-06-29 — Cuentas livianas: alta passwordless con passkey (cuenta vacía hasta Didit, inerte + anti-spam)

El alta con passkey (`POST /auth/passkey/signup/{begin,complete}`, motor `auth/passkey/`) crea una **cuenta
liviana**: nace solo con `id` + passkey, SIN datos —los `NOT NULL` base de `clientes` (nombre/apellido/telefono/
email/direccion/cuit) se relajaron, `cuenta_estado='liviana'`, `owner_email=''` en la passkey—. La
**identidad/contacto los completa Didit al primer pedido** y van a las columnas `*_renaper` (con COALESCE),
**NUNCA** a los campos base por el usuario; la cuenta queda **inerte** (`require_cliente_verificado` la bloquea
hasta `dni_validado_at`). Cuenta+passkey se insertan en **una transacción atómica** (sin huérfanos) y mintea por
`_make_session_response` (email/nombre NULL → `""`, hereda jti). **Higiene anti-spam (invisible al usuario, las 3
patas):** rate-limit por-IP que cuenta también las altas **exitosas** (`_record_event`, no solo fallos) +
inertidad-hasta-Didit + **cleanup diario** de livianas abandonadas (`jobs/cleanup_livianas.py` en el scheduler
único: liviana + sin verificar + sin email + sin pedidos + > 30d → borrar; cascade limpia passkey/sesiones).
Google sigue **co-primario**; el **admin NO se auto-crea** (allowlist — su passkey se agrega desde el perfil tras
Google). En el front, el login del cliente lidera con "Crear cuenta con passkey" (CTA `Button variant=primary`).
El supervisor marca un alta que escriba identidad en los campos base en vez de esperar a Didit, o un signup fuera
de la transacción atómica / del punto único de minteo. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); tracking #1098 (Fase 4).

### 2026-06-29 — Merge de cuentas por link autenticado (unir cuando es la misma persona + una es absorbible)

Cuando un cliente logueado en la cuenta A vincula una llave (hoy Google) que ya es de la cuenta B, el sistema
**une las dos** en vez de rechazar: estar logueado en A (probó una llave de A) **+** completar el OAuth de B (probó
una llave de B) **es prueba de que A y B son la misma persona** → se mergean. **Guardrail:** solo si una de las dos
es **absorbible** (`account_is_absorbable`: liviana + sin verificar + sin pedidos → no tiene datos que perder); se
mueven sus llaves a la otra y se borra (`auth/account_merge.merge_accounts`, transaccional; todas las FKs a
`clientes` son CASCADE/SET NULL → borrar es seguro). Si **ambas tienen datos**, NO se auto-mergea (→ "taken"): el
merge general con reasignación de pedidos/contabilidad + dedup por CUIL es **Fase 2** (`identity/merge`). Cuando se
absorbe la cuenta donde estabas, se re-mintea sesión en la sobreviviente por el punto único. **Sin prueba de ambas
llaves no se une** (crear passkey → desloguear → volver por Google ≠ misma persona _conocida_ → quedan separadas
hasta Didit; de cualquier forma, al primer pedido Didit ancla por CUIL y unifica). El supervisor marca un merge sin
el guard de absorbible, o un auto-merge de dos cuentas con datos. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); #1098 Fase 1B.

### 2026-06-29 — Step-up con passkey ("confirmá que sos vos") para operaciones sensibles del cliente

Antes de una **operación sensible** del cliente (hoy: **quitar un método de acceso**; reusable a futuro: confirmar
un pedido) se exige un **step-up**: una assertion WebAuthn **fresca** (passkey de ESTA cuenta) que deja la cookie
firmada **`stepup`** (~5 min), que el guard **`require_recent_auth`** (`auth/stepup.py` = `require_cliente` +
`stepup` fresca y owner-scopeada) exige. **No es un login** (no mintea sesión; reusa la ceremonia de
`auth/passkey/`, scopeada: la passkey tiene que ser de la cuenta). El front dispara `stepUpWithPasskey()` antes de
la acción y reintenta. **Primitivo único** — no recrear un "confirmá con passkey" ad-hoc por endpoint. El supervisor
marca una operación sensible del cliente sin `require_recent_auth`, o un step-up que acepte una passkey de otra
cuenta. Base del step-up de **Fase 3** (operaciones sensibles) y se conecta con la **firma con passkey (Fase 5)**.
Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); #1098 Fase 1B.

### 2026-06-29 — `backend/services/checkout/` = portero único del checkout (fail-not-fast; devuelve {listo, faltan})

Toda validación previa a crear un pedido pasa por la **puerta única** `backend/services/checkout/validar.py::validar_checkout(conn, cliente_id, session_id, firma_ok)`. Corre **10 checks fail-not-fast** (sin parar en el primero) y devuelve `{listo: bool, faltan: [{check, mensaje}]}` para que la UI muestre exactamente qué resolver. **No crea pedidos** — el gate de creación sigue siendo `create_pedido_retry` (`routes/alquileres/core.py`; core sagrado intacto). **2 checks cableado-apagado** (`_check_bloqueo` #1125, `_check_antelacion` #1126) retornan siempre OK hasta activarse. La **firma** admite passkey step-up (`has_recent_stepup`, ~5 min) O fallback `session_confirmed=true` ("Confirmo") para clientes sin passkey. HTTP: `POST /api/checkout/validar` + `POST /api/checkout/aceptar-tyc` (idempotente). El supervisor marca validación de checkout ad-hoc fuera de la puerta, o un check nuevo no cableado-apagado sumado fuera de `validar_checkout`.

### 2026-06-30 — Firma con passkey: presencia de un toque (on-the-fly) + gate del checkout reusa el portero; presencia ≠ firma legal

La firma con passkey del cliente es **presencia fresca de un toque**: registrar una passkey de cliente deja la marca
`stepup` (`_register_complete`→`mark_stepup`; registrar exige el mismo gesto biométrico que una assertion) → es un
**modo más de auth fresca** (junto a login/step-up) y **crear la llave ya firma**. Helper **único**
`firmarConPasskey(tienePasskey)` en `lib/passkey.ts` (no un módulo aparte — `lib/firma.ts` se borró). El **gate de
firma+T&C en la creación del pedido reusa** los checks cliente-scoped del portero (`faltan_firma_tyc` =
`_check_tyc`+`_check_firma`), **no re-implementa** ni usa el portero completo (depende de `carritos_activos`);
stock/precio los sigue enforzando `create_pedido_retry`. **Cableado-apagado** (`FIRMA_CHECKOUT_OBLIGATORIA=False`)
hasta que la UI del checkout mande la señal (patrón #1125/#1126). **Presencia ≠ firma legal:** la marca prueba "hay
un humano con el dispositivo ahora" (checkout = acepto T&C + confirmo); la **firma legal del contrato** (no-repudio
**atada al hash**, Ley 25.506) extiende la **misma** ceremonia de `auth/passkey/` firmando el `doc_hash` — **no un
sistema paralelo** (contratos/ARCA, aparte). El supervisor marca: firma de presencia recreada fuera de
`auth/stepup`+`firmarConPasskey`; el gate del checkout re-implementando los checks; o una firma de contrato con
ceremonia paralela. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md) §3; historia → #1131.

### 2026-06-30 — `staging-verify`: fakear la verificación Didit en dev SIN tocar `dni_validado_at` a mano

Didit (KYC) no corre en dev/staging → una cuenta nunca llega a `dni_validado_at` y el portero del checkout la
bloquea, impidiendo probar el flujo de pedido. `POST /auth/staging-verify` la marca como verificada **reusando la
pluma única `identity.kyc`** (`aprobar`/`actualizar_estado`): setea un `didit_session_id` fresco y delega — **nunca
un UPDATE manual de `dni_validado_at`**. **Mismo gate de doble llave** que staging-login (`is_production` falla-a-prod
+ `STAGING_LOGIN_SECRET`): **404 en prod**. Soporta `estado` approved/rejected/en_revision y siembra contacto para
cuentas livianas; CUIL fake válido (mod-11) único por id. **No mintea sesión** (combinar con `staging-login
target=cliente`). Extiende _Staging-login (2026-06-19)_ al gate de identidad. El supervisor marca un fake de KYC vía
UPDATE de `dni_validado_at`/`*_renaper` a mano en vez de la puerta. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md) +
[`DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md).

### 2026-06-30 — `backend/services/fechas.py` = puerta única de la lógica de fechas/horas; lead-time configurable (#1126)

Toda **decisión** sobre fechas/horas vive en `services/fechas.py`: formato (`validar_fecha_iso`), criterio de
rango (`validar_rango_fechas`: orden/no-pasado/tope de días), lead-time (`antelacion_*`), ventana/corte de
modificación (`setting_horas` + el predicado puro `dentro_de_ventana_horas`), horarios de retiro
(`validar_horarios_habilitados`, devuelve `str|None`; el route es adapter que levanta el 400) y mes actual
(`mes_actual_ar`). Se construye sobre las **primitivas** `now_ar()`/`to_datetime()` del DAL (fuente única de bajo
nivel, _2026-06-27_): el módulo es dueño de las **reglas**, el DAL de las primitivas. El **dominio de cada motor NO
se mueve** (reservas: buffer/overlap; precios: jornadas; reportes/contabilidad: ventanas de mes; auth: TTLs;
ical/pdf/email: display). El **lead-time** (#1126) es configurable (`app_settings.antelacion_minima_horas`,
0 = apagado) con **defensa en profundidad** (portero UX `_check_antelacion` + backstop server-side en
`cliente_crear_pedido`, **solo-cliente** — el admin carga urgencias a mano; no toca el `FOR UPDATE`) y un disclaimer
con CTA de WhatsApp en el carrito; **fail-open** (setting corrupto/ausente → 0). El supervisor marca: una regla o
validación de fecha/hora genérica recreada o duplicada fuera del módulo, o `date.today()` donde debería ir
`now_ar()`. Cómo → el propio docstring de `services/fechas.py`; tracking #1126.

### 2026-07-02 — El editor de pedidos admin cotiza con el precio de línea congelado, no con el de catálogo

El editor de pedidos (`pedidos.$id.lazy.tsx`) mostraba el total "en vivo" recotizando contra `/api/cotizar`,
que para ítems de catálogo siempre re-busca el precio **actual** de `equipos` — ignorando el `precio_jornada`
ya persistido/editado del pedido. Eso podía divergir del `monto_total` que efectivamente se guarda
(`_recalcular_total_pedido`, que sí usa el precio de línea congelado), mostrando "100% pagado" en la pantalla
del pedido mientras la reconciliación mensual (que lee `monto_total`/`monto_pagado` directo de la base) lo
marcaba como sobrepagado — dos totales del mismo pedido. `/api/cotizar` ahora acepta `respetar_precio_item`
(solo lo honra una sesión admin): usa el precio de línea que manda el front en vez de recotizar contra
`equipos`; el editor de pedidos lo activa siempre. La pantalla de Cobranza además deja de esconder un
excedente cobrado (antes clampeaba a 0): si se cobró de más se muestra explícito, en vez de descubrirse
recién en la reconciliación. El supervisor marca una pantalla que recotice un pedido YA EXISTENTE contra el
precio de catálogo en vez del precio de línea persistido. PR #1181.

### 2026-07-02 — `backend/contabilidad/` reorganizado CQRS-lite (`queries/`+`commands/`), espejo de `services/specs/`

El motor de contabilidad (_2026-06-07_) se reorganizó en `queries/` (lectura, nunca muta) + `commands/` (única
puerta de mutación) + `constants.py` (lo que ambos lados necesitan: cobradores, tipos de cuenta/movimiento,
partes de la rendición) — mismo patrón CQRS-lite que `services/specs/`/`services/specs_ingesta/`. **Move
verbatim, no rewrite**: cero cambio de lógica/SQL, confirmado por los 51 tests puros + 29 tests de integración
(Postgres real) en verde byte-a-byte. Invariante dura: `commands/` puede importar de `queries/`; `queries/`
**nunca** de `commands/` — confirmado al hacer el split que ningún query del paquete necesitaba nada de
`commands/` (es un motor mayormente de lectura, 10 puntos de mutación reales). De paso se consolidó `PARTES`
(estaba duplicada byte-idéntica en `rendicion.py` y `reporte_mensual.py`) en `constants.py` — una sola forma.
El supervisor marca lógica de escritura nueva agregada a `queries/`, o un query importando de `commands/`.
Estructura completa → `backend/contabilidad/CLAUDE.md`; tracking #1184.

### 2026-07-02 — Auditoría de `backend/contabilidad/`: bordes reforzados (edición, locking, auditoría de pagos)

A pedido del dueño tras el split CQRS-lite, 3 auditorías en paralelo (corrección/concurrencia, seguridad HTTP,
duplicación/gaps de tests) sobre `backend/contabilidad/` completo: **el núcleo (fórmulas de saldo, derivación,
soft-delete, multi-moneda en creación) estaba bien hecho y bien testeado — los problemas reales estaban en los
bordes.** Se implementaron los 19 hallazgos. Los 3 bugs reales: (1) `editar_movimiento` no repetía las
validaciones de `crear_movimiento` (existencia/actividad de cuenta, misma moneda, categoría activa) — se podía
editar una transferencia para que apunte a una cuenta de OTRA moneda sin error, violando ARS≠USD; extraído a
`_validar_cuentas_y_categoria`, reusado por ambas. (2) `alquiler_pagos` (la tabla que alimenta todo el motor)
no tenía actor ni soft-delete — `eliminar_pago` hacía `DELETE` real, sin motivo; ahora tiene
`created_by`/`anulado`/`anulado_por`/`anulado_at`/`anulado_motivo` (mismo patrón que `movimientos`),
`DELETE→POST .../anular` con motivo obligatorio, y los 7 SELECT que suman `alquiler_pagos` (incluido el
`SALDADO_CTE` de `reportes/liquidacion.py`, compartido por 3 consumidores) filtran `NOT anulado`. (3)
`subir_comprobante` escribía SQL directo saltándose el motor (sin candado de mes cerrado, sin chequear
`anulado`, sin actor) — exactamente el escenario que el propio `CLAUDE.md` del paquete advertía; ahora pasa por
`commands.movimientos.actualizar_comprobante`.

Robustez agregada: `pg_advisory_xact_lock` (mismo patrón que `services/facturacion/engine.py`/
`routes/talleres.py`) entre `cerrar_mes`/`reabrir_mes` y crear/editar/anular movimiento del mismo mes —
**verificado con un test de concurrencia real de dos conexiones** (no solo en teoría): sin el lock, un gasto
podía colarse en un mes "recién cerrado" fuera de la foto; con el lock, B espera a que A commitee y después es
rechazado correctamente. `desactivar_cuenta` toma `FOR UPDATE` (mismo método de verificación, B esperó los 5s
reales del lock). Rate limiting (`ADMIN_WRITE_LIMIT`/`ADMIN_UPLOAD_LIMIT` en `rate_limit.py`) en los 13
endpoints de escritura de `contabilidad.py`/`pagos.py` (ninguno lo tenía). Cotas `Field(...)` en los 8 modelos
Pydantic — el `lt=2_147_483_647` en ids es lo que de verdad cierra la puerta a `NumericValueOutOfRange` crudo
de Postgres — más el decorator `@map_pg_errors` (nuevo, en `routes/contabilidad.py`, reusado por `pagos.py`)
que traduce `UniqueViolation`/`NumericValueOutOfRange` a 400 limpio en vez de filtrar el mensaje interno de
Postgres vía el handler global. `idx_cuentas_socio` ahora único solo entre cuentas activas (simétrico con
`cuentas_nombre_activa_uq` — antes dar de baja una cuenta de socio bloqueaba para siempre crear una nueva
activa con ese socio). 8 tests nuevos candado (`editar_cuenta` no tenía ninguno pese a usarse en producción;
`ajuste` con origen+destino; fallback de `saldo_de_cuenta`; anular un saldado de rendición ya registrado —
documenta que `ya_transferido` excluye el anulado pero `_movimientos_rendicion` lo sigue mostrando, intencional).
Ambigüedad dejada sin resolver a propósito en esta pasada (retiro/aporte/gasto/ajuste contra una cuenta
CORRIENTE de socio) — **resuelta después, ver _2026-07-02 — Tipo de movimiento vs tipo de cuenta_ más abajo**.
El supervisor marca: un `UPDATE`
directo a `movimientos`/`alquiler_pagos` fuera de `commands/`, un endpoint de escritura de contabilidad/pagos
sin `@limiter.limit`, o un `except Exception` nuevo en esos routes sin pasar por `map_pg_errors`. Rama aislada
`fix/contabilidad-auditoria` (PR sin mergear, hoja de ruta), sobre `feature/contabilidad-cqrs`; tracking #1184.

### 2026-07-02 — Tipo de movimiento vs tipo de cuenta: retiro/aporte bloqueados contra un socio, gasto permitido a propósito

Resuelve la ambigüedad que la auditoría anterior dejó documentada-sin-bloquear. Confirmado con el dueño: un
socio humano (Pablo/Tincho) tiene su plata real en un banco propio, **fuera del sistema** — su cuenta acá
(`SOCIOS_HUMANOS`) es **puro balance de deuda**, nunca plata física. Con eso claro: **`retiro`/`aporte`
quedan BLOQUEADOS contra una cuenta de socio** (`_validar_cuentas_y_categoria`, `commands/movimientos.py`) —
representan plata física entrando/saliendo de una caja real, sin sentido contra un balance de deuda.
**`transferencia`/`ajuste` siguen permitidos sin cambios** (`saldar()` necesita tocar cuentas de socio).
**`gasto` queda PERMITIDO a propósito** contra una cuenta de socio como origen — es el caso real "el socio
pagó un gasto de Rambla con su propia plata": ni `gastos_por_categoria` ni `ganancia_neta` filtran por tipo
de cuenta origen (solo por moneda), así que un solo movimiento **cuenta en el P&L categorizado Y baja la
deuda del socio** (`egresos` resta en la fórmula de cuenta corriente) — sin necesitar un tipo de movimiento
nuevo. El caso inverso ("Rambla pagó algo de Pablo") ya se resolvía con 2 movimientos: `gasto` desde una caja
real + `ajuste` con destino=socio (sin cambios). Mismo commit/rama que la auditoría de bordes
(`fix/contabilidad-auditoria` → PR #1195, sin mergear); tests:
`test_retiro_aporte_bloqueados_contra_cuenta_socio`, `test_gasto_contra_cuenta_socio_cuenta_en_pyl_y_baja_deuda`.
El supervisor marca un `retiro`/`aporte` nuevo que se le vuelva a permitir a una cuenta de socio, o un tipo de
movimiento nuevo inventado para el caso "el socio pagó un gasto de Rambla" en vez de reusar `gasto`.

### 2026-07-02 — Auditoría cruzada de plata: `docs/SISTEMA_PLATA.md` + el fix de #405 (#1181) nunca se mergeó

A pedido del dueño, tras la auditoría de `contabilidad/`, ante el miedo de "drift de plata" con muchos
motores tocando dinero sin un mapa único. 6 auditorías paralelas sobre `services/precios`,
`reportes/liquidacion`+`comisiones`+`cierres`+`reconciliacion`, `services/facturacion`, el camino de
congelamiento de precio en pedidos, y un trace end-to-end + estado del semáforo de reconciliación.
**Hallazgo crítico de proceso:** el PR #1181 (fix original del bug #405 — editor de pedidos admin
cotizando con precio de catálogo en vez del precio de línea congelado) **nunca se mergeó** a `dev`/`main`
— `respetar_precio_item` no existe en ningún branch real, solo en la rama del PR sin mergear. La sesión
anterior lo había registrado como shippeado por error. **El bug #405 sigue potencialmente activo hoy.**
Nuevo manual **`docs/SISTEMA_PLATA.md`** (fuente única de cada número de plata + el semáforo de
reconciliación, cruzado entre motores) — no repite invariantes de cada `CLAUDE.md`/`SISTEMA_*.md` local,
los referencia. Hallazgos priorizados (14 ítems + el PR sin mergear) documentados ahí, no acá — evita
duplicar y que se desactualice. Reconciliación confirmada **100% manual**: ni `reportes/reconciliacion.py`
ni `contabilidad/queries/reconciliacion.py::reconciliar` corren en `jobs/scheduler.py`; sin badge/alerta
en el dashboard admin — es el gap de gobernanza más directo detrás del miedo original del dueño. El
supervisor marca un motor de plata nuevo sin entrada en la tabla "fuente única" de `SISTEMA_PLATA.md`, o
un PR de fix de plata reportado como shippeado sin confirmar merge real a `dev`/`main`.

### 2026-07-02 — `backend/services/finanzas_flujo/` = módulo orquestador de plata (Fase 1: desglose de pedido)

El dueño pidió que el mapa de `SISTEMA_PLATA.md` (renombrado **`docs/SISTEMA_FINANZAS_FLUJO.md`**, mismo
patrón 1:1 manual↔módulo que `SISTEMA_CARRITO.md`↔`services/carrito/`) fuera **código real, no solo
prosa** — un módulo que sea el único punto de entrada para preguntar un número de plata, para que un
consumidor nuevo no tenga que saber a cuál motor llamar. Nace **`backend/services/finanzas_flujo/`**:
facade de **solo lectura** (nunca escribe — las mutaciones siguen en cada motor directo), cada función
delega 1:1 al motor dueño (`services.precios`, `reportes.liquidacion`, `contabilidad.queries`,
`services.facturacion`), sin reimplementar. **Fase 1 (primera pieza, implementada):**
`finanzas_flujo/pedido.py::desglose_de_pedido` fixea el bug de `cobro_modo` (una línea personalizada
`cobro_modo='fijo'`, ej. flete #805, se multiplicaba igual por jornadas) en los 6 consumidores reales:
`_enriquecer_pedido_con_total` (`routes/alquileres/core.py`) ahora es un wrapper que delega en la
fachada; `services/facturacion/engine.py` migró a importarla directo (antes importaba de
`routes.alquileres` — un service dependiendo de un route). Mismo bug arreglado en `pdf_templates.py`
(`_bruto_item_pdf`, nuevo helper cobro_modo-aware, reemplaza la reimplementación inline en
`_pedido_html`/`_sum_bruto`). Frontend: `PedidoPageCards.tsx`/`PedidoPageHelpers.tsx` (que habían
divergido — Cards ignoraba `cobro_modo`) ahora importan `subtotalDraftItem` desde `usePedidoDraft.ts` —
misma función, no pueden volver a divergir. **Candado:** `test_finanzas_flujo_source_scan.py` verifica
que `pdf_templates.py` usa el helper y que `services/facturacion/engine.py` importa la fachada, no
`routes.alquileres`. El resto de las fases (liquidación, contabilidad, facturación, reconciliación) del
módulo quedan para PRs siguientes, mismo patrón. El supervisor marca un consumidor nuevo que reimplemente
el desglose de un pedido en vez de llamar a `finanzas_flujo.pedido.desglose_de_pedido`, o un `service` que
importe de un `route`.

### 2026-07-03 — `routes/estadisticas.py`: las agregaciones leen `monto_total`, no reconstruyen el descuento (#1209)

Las queries del dashboard de Estadísticas (totales/por_mes/top_equipos/por_dueno/mejor_peor_mes)
reconstruían el ingreso con `subtotal * (1 - descuento_pct/100)` — que solo mira el descuento de
CLIENTE, ignorando el de JORNADAS cuando era el GANADOR (`descuento_aplicable = max()`, el caso común en
alquileres multi-día): sobreestimaba el ingreso y no cuadraba con "Top clientes"/"Clientes recurrentes"
de la MISMA pantalla (que ya usaban `monto_total` bien). Fix: a nivel PEDIDO (totales/por_mes/mejor_peor)
lee `monto_total` directo, sin join a `alquiler_items` (evita multiplicarlo por línea); a nivel ÍTEM
(top_equipos/por_dueno) lo prorratea por participación en `subtotal` — mismo patrón que
`reportes/liquidacion.py::filas_atribucion` (fragmento SQL compartido `_PRORRATEO_CTE`). **NO se
reconstruye el descuento en ningún caso** — `monto_total` es la fuente única del neto. El supervisor
marca cualquier query nueva de estadísticas/reportes que recalcule `descuento_pct * subtotal` en vez de
leer `monto_total`. Regresión: `test_estadisticas_db.py` (Postgres real; pedido con descuento por
jornadas ganador y descuento de cliente en 0%).

### 2026-07-03 — Factura y mail de "pedido creado": línea de bonificación/descuento visible (M5+L1, #1209)

Con descuento (el caso común: cualquier alquiler de varios días tiene descuento automático por jornadas),
la **Factura** (`services/facturacion/pdf.py::_conceptos`) mostraba el BRUTO por línea con un `% Bonif.`
hardcodeado en `0,00`, y el **mail de "pedido creado"** (`routes/alquileres/core.py::_pedido_email_context`)
mostraba el bruto por ítem sin ningún renglón que explicara la diferencia con el "Total" (ya neto) — el
comprobante/mail no cerraba consigo mismo. Mismo criterio bruto→descuento→neto que ya usaba el
**Presupuesto** (`pdf_templates._pedido_html`, decisión 2026-06-06 sobre el IVA aparte — **no se toca**).
La Factura reparte la bonificación proporcionalmente entre las líneas (remanente de redondeo en la
última) contra el bruto de las LÍNEAS vs. el `imp_neto` YA DECLARADO/congelado en la factura — no el
pedido en vivo — para que también cierre en una Nota de Crédito. El mail suma una fila de "Descuento"
visible en la tabla de ítems vía el helper único `services/email/branding.py::discount_row`. El
supervisor marca una línea de factura o de mail que muestre el bruto sin reconciliar contra el total
declarado, o un `bonif`/`% Bonif.` hardcodeado reintroducido. Iniciativa: #1209 (2 de 9 hallazgos).

### 2026-07-03 — `routes/facturacion.py`: rate limit + mapeo de errores en las escrituras (gap de la auditoría de #1184, #1209)

Las escrituras de `backend/routes/facturacion.py` (facturar pedido, nota de crédito, enviar mail, CRUD de
emisores ARCA) ahora llevan `@limiter.limit(ADMIN_WRITE_LIMIT)` + `@map_pg_errors` — **reusados tal cual**
de `routes/contabilidad.py` (mismo import, mismo patrón), no reimplementados. Cierra el hueco que dejó la
auditoría de plata 2026-07-02 (#1184): esa pasada blindó contabilidad/pagos/reportes pero no tocó
facturación, pese a que también pega a ARCA y a Postgres sin freno. Única excepción: el endpoint async
`enviar_mail_factura` NO lleva `@map_pg_errors` (el decorator hace `fn(*args, **kwargs)` sin `await`, no
detecta excepciones de una corrutina — mismo motivo por el que `subir_comprobante`, también async, en
`contabilidad.py` tampoco lo lleva). El supervisor marca un endpoint de escritura de facturación nuevo sin
`@limiter.limit`, o un `except Exception` ad-hoc en esos routes en vez de `map_pg_errors`.

### 2026-07-03 — La vista multi-mes/anual de reportes ahora respeta los meses cerrados (`liquidar_rango`)

Uno de los 14 hallazgos de la auditoría cruzada de plata (severidad media): la vista "Mes a mes"/el total
anual (`_data_liquidacion` en `routes/reportes.py`) recalculaba TODO el rango en vivo con `liquidar()`,
ignorando que un mes individual dentro del rango podía estar **cerrado** — solo la tarjeta de un mes exacto
usaba `snapshot_de`. Resultado: la fila de junio dentro del año y el total anual podían mostrar un reparto
de comisiones distinto al de la tarjeta de junio, para el MISMO mes cerrado. Fix: `reportes/cierres.py`
suma `liquidar_rango(conn, desde, hasta)` — para cada mes calendario que el rango cubre COMPLETO, usa la
foto (`snapshot_de`) si está cerrado o `liquidar()` en vivo si no, y combina los N reportes por-mes con la
función pura nueva `liquidacion.combinar_meses` (sumar es seguro: un pedido pertenece a un único mes de
saldado, nunca se solapan). Los fragmentos de mes en los bordes (rango no alineado a mes calendario) siguen
en vivo, como antes. `_data_liquidacion` delega en `liquidar_rango` cuando el rango NO es un único mes
exacto; la vista de un mes puntual no cambió. El supervisor marca un cálculo de reporte multi-mes que
recalcule en vivo sin chequear `cierre_de`/`snapshot_de` por mes, o lógica de "está cerrado" reimplementada
fuera de `reportes/cierres.py`. Tests: `test_liquidar_rango_multimes_respeta_mes_cerrado` (Postgres real,
reproduce el escenario exacto) + `TestCombinarMeses` (puros). Tracking #1209.

### 2026-07-03 — dataio export/import perdía `anulado` de `alquiler_pagos`: un pago anulado revivía activo tras backup/restore

El exportador/importador de `dataio` (`exporters.py`/`importers.py`, distinto del `pg_dump` que se usa
para clonar staging) no incluía `anulado`/`anulado_por`/`anulado_at`/`anulado_motivo` del pago —
un pago **anulado** (soft-delete, auditoría de `contabilidad` 2026-07-02) **revivía activo** tras un
ciclo `dataio export`→`dataio import` (backup/restore o clonado de ambiente): el `INSERT` del import lo
reinsertaba con el default de la columna (`anulado=FALSE`), inflando `monto_pagado`/cajas/liquidación sin
dejar rastro. Fix: las 4 columnas viajan tal cual en `AlquilerPagoRef` (`dataio/schema.py`); el `SELECT`
del export las trae y el `INSERT` del import ya no las defaultea. Regresión (Postgres real, opt-in):
`test_dataio_pagos_anulado_roundtrip_db.py` — verificado que falla contra el código viejo y pasa con el
fix. `movimientos` (contabilidad, también tiene `anulado`) no está exportado por `dataio` hoy — no hay
nada más que arreglar en este alcance. El supervisor marca una entidad nueva de `dataio` que toque una
tabla con soft-delete (`anulado`/`eliminado_at`) sin exportar/importar esas columnas.

### 2026-07-03 — El pipeline de carritos activos (dashboard admin) incluye el precio derivado de un combo

`_enrich_items` (`services/carrito/activos.py`, alimenta `monto_estimado`/`pipeline_ars` de
`GET /admin/carritos`) leía `equipos.precio_jornada` **crudo** por ítem — NULL para un `tipo='combo'` (el
precio de un combo se deriva de sus componentes) — así que el combo quedaba en 0 y el filtro `if precio > 0`
lo descartaba del estimado. Ahora resuelve cada ítem con la fuente única `precios.precio_jornada_efectivo`
(_2026-06-29 — módulo único del carrito_), igual que `readiness.py`. Solo afecta la **métrica interna** del
dashboard admin — no toca cotizado==cobrado ni nada que vea el cliente. Fetch por-ítem, no batch: mismo
criterio que el batch `IN (...)` revertido en `/api/cotizar` (#643, devolvió precios vacíos en prod); el
carrito de un heartbeat es chico, no hot-path. Test: `test_carritos_activos_precio_combo.py`. El supervisor
marca un ítem de carrito/dashboard cuyo precio salga de `equipos.precio_jornada` crudo en vez del resolutor.

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
**reusar no recrear** (la forma del pill vive en `ui/Pill`; `EstadoBadge`/`PagoBadge` derivan, cero clases
copiadas), mobile/a11y no son extra, el core es presentación. El supervisor la hace cumplir; el detalle
vive en el doc. Es la contraparte visual de la _Barra de calidad de ingeniería (2026-05-25)_.

### 2026-06-20 — Fijarse en el repo antes de implementar (sobre todo tras mergear dev)

Antes de codear algo, **verificar si ya existe** en el repo —con prioridad tras mergear `dev`, porque lo que
avanzó allá puede ya cubrir el pedido (caso: el staging-login de cliente ya estaba hecho, #961). Vale para
features, helpers, endpoints y patrones. Refuerza la _Barra de calidad de ingeniería (2026-05-25)_ (no
duplicar, fuente única); el supervisor marca reimplementaciones de algo ya presente.

### 2026-06-25 — Guardrail con prefijo ⏰ LEGACY: coexistencia temporal en migraciones por fases

Cuando una feature nueva y el cleanup del estado viejo se hacen en fases distintas, el guardrail (CI,
allowlist, o cualquier regla de calidad) incluye el estado legado con un comentario explícito `⏰ LEGACY:
remover cuando <fase> mergee a dev`. El paso de limpieza lo quita en el mismo commit que borra el estado
viejo. Permite coexistencia temporal sin romper nada y deja una señal visible de la deuda pendiente (no
se pierde en un comentario ambiguo). El supervisor busca activamente prefijos `⏰ LEGACY` cuyo disparador
ya se cumplió y los propone como candidatos a retirar.

### 2026-06-25 — El supervisor atrapa bugs de implementación, no solo drift de scope/forma

En la práctica (iniciativa #1029, F5–F7): `import pytest` sin usar, columnas faltantes en queries SQL,
URL apuntando a un archivo borrado, test con paths eliminados — todos encontrados por el supervisor.
**No skippearlo aunque el cambio parezca mecánico**: es una segunda revisión de código, no solo un gate
de scope. Los bugs concretos que encuentra son distintos a los que caza CI (tipos, lint, tests unitarios).
