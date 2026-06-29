# Decisiones — Rambla Rental (log ADR completo, on-demand)

> **El _por qué_ completo de cada decisión de criterio + preferencia.** Este es el **log de
> rationale** (Contexto / Decisión / Why / Consecuencias / gotchas), de lectura **on-demand** — NO se
> auto-carga en cada sesión. El **digest enforceable** (la regla de cada entrada en 1-3 líneas) vive en
> [`MEMORIA.md`](MEMORIA.md), que sí se auto-carga. **Misma fecha-título** en ambos archivos → cuando
> algo cita _2026-06-03 — X_, la regla está en el digest y el desarrollo está acá. Ver decisión
> _2026-06-08 — Memoria en dos sub-capas_.
>
> **Quién lo lee:** el **supervisor** lo abre en su ventana aislada para juzgar drift fino y para
> **curar** (proponer retirar/fusionar/actualizar); la sesión lo lee solo cuando necesita el *por qué*
> de una entrada puntual.
>
> **Curado (no exhaustivo), fechado.** Es la **verdad curada del presente, NO un append-only**: se
> **edita y poda** para que quede vigente. El "nada se pierde" lo cumple el **historial de git**
> (inmutable); una decisión reemplazada se **actualiza o retira en el lugar** (no se apilan
> contradicciones). Ver decisión _2026-05-26 — Curación de la memoria_.
>
> Las **decisiones de arquitectura fundacionales** viven en [`MANIFIESTO.md`](../MANIFIESTO.md) §6
> (baseline congelado). Acá van las **nuevas**. El **trabajo pendiente** vive en GitHub Issues;
> el **registro de cambios**, en el commit history.
>
> **Cómo se escribe acá:** la sesión agrega, **edita o poda** entradas **solo con aprobación
> explícita del dueño** (toda escritura acá tiene su reflejo en el digest `MEMORIA.md`). El supervisor
> **propone** (agregar, retirar, fusionar) pero no escribe. Cuando una decisión tiene fecha de
> vencimiento, anotar el **disparador** que obliga a revisarla.

---

## Decisiones (ADR-lite)

### 2026-06-08 — Workflow de cambios (fuente única): dev = staging, push directo siempre, PR solo para prod

> **Fuente única del workflow.** Consolida y reemplaza las 6 decisiones de flujo previas. Refinado
> 2026-06-25: se elimina el "routing por riesgo" (rama+PR antes de dev para cambios grandes) — el
> dueño prefiere push directo a dev siempre, PR solo para dev→main. No restatear en otros docs.

- **Ambientes:** `dev` (rama `dev`) = **staging** en Railway (auto-deploy en cada push; copia de prod,
  sin clientes reales); `main` = **prod** (sagrado, no se prueba ahí).
- **Flujo único: push directo a `dev` siempre.** No hay ramas intermedias ni PR antes de staging.
  Si algo se rompe en staging se pushea el fix — no hay clientes ahí, el costo es bajo. `main` nunca
  recibe push directo.
- **PR solo para `dev → main`** (la puerta a prod). Ese PR es donde el supervisor revisa, el CI corre
  como gate, y el dueño aprueba antes de que llegue a producción.
- **Red de seguridad:** el **CI corre en cada push** a `dev` y `main`. No pushear con CI en rojo.
- **Quién mueve qué:** la sesión pushea a `dev` sola y avisa al dueño con plan de prueba — no pide
  permiso. El dueño prueba en staging y aprueba el PR `dev → main`.
- **Gates del dueño:** (1) probar en staging; (2) aprobar `dev → main`. Helper: `scripts/pre-promote.sh`
  (corrélo antes de promover — lista el scope dev→main, corre check-docs y recuerda el checklist supervisor/app/CI).
- **Merge `dev → main`** = merge commit (NO squash → revert quirúrgico por PR si hace falta en prod).
  Commits atómicos, Conventional Commits en español.
- **Why:** `dev` es seguro (sin clientes) → el PR antes de staging era overhead sin beneficio real.
  El único gate que importa es `dev → main`: ahí está el supervisor, el CI en modo gate, y el dueño.
  Menos fricción, misma red de seguridad para prod.

### 2026-06-08 — Issues: la cola espeja el código (Closes #N → auto-cierre en dev→main; diferido aparte)

> Refina _Memoria en capas (2026-05-25)_: "Issues = cola" se precisa en cómo se abren, cierran e
> integran con el _Workflow de cambios (2026-06-08)_.

- **Contexto:** 36 issues abiertas, ~la mitad sin tocar desde mayo; sensación de catarata. Causa real
  del "no se cierran": los commits citan el **PR** (`#843`) pero **no la issue**, así que GitHub nunca
  las auto-cierra aunque el trabajo ya shippeó. Y lo diferido (features grandes "para algún día")
  mezclado con lo accionable hace sentir todo como una pila.
- **Qué merece issue (anti-catarata):** trabajo **diferido** (no ahora), **multi-sesión**, o un
  **brain-dump / idea** del dueño que no se hace en el momento. Lo que se **hace y mergea en la misma
  sesión NO lleva issue** — el commit history es su registro; crear una para cerrarla al toque es
  burocracia.
- **Cierre = shippeó a prod.** Toda issue que se trabaja lleva **`Closes #N`** en el commit (directo a
  `dev`) o en el PR (lo grande). Como la **branch default es `main`**, GitHub la **auto-cierra cuando
  el trabajo llega a `main`** (en la promoción `dev → main`) → la issue se cierra cuando el dueño puede
  usar la cosa en prod, no antes. Citar la **issue**, no solo el `#PR`.
- **La promoción `dev → main` es el checkpoint de reconciliación:** el PR de promoción lista en su
  cuerpo las issues que cierra el lote (`Closes #N` c/u) → se cierran **en bloque, con evidencia**, al
  ritmo de prod. Nunca más cerrar a mano de a una.
- **Diferido aparte:** las features grandes diferidas llevan label **`someday`** (definido en
  `docs/ISSUE_LABELS.md`) → se filtran de la vista "qué hago ahora". La cola accionable queda chica; lo
  diferido queda **asentado pero separado** — no es deuda sin cerrar, es backlog. El brain-dump del
  dueño va a issue igual (no se pierde), con `someday` si es "algún día".
- **Triage liviano y seguido**, no masivo: el método es el skill `pendientes` — **verificar
  que shippeó antes de cerrar** (las tools y la intuición mienten), con evidencia. Hacerlo en cada
  promoción, no dejar acumular meses.
- **Una iniciativa multi-sesión = un issue de tracking** (decisión _Modus operandi durable_), que
  cierra cuando la iniciativa shippea a prod. **No** un issue por fase.

### 2026-05-25 — Modus operandi durable, sesión efímera

- **Contexto:** las sesiones son efímeras; el plan de una iniciativa larga no puede vivir solo en
  la conversación o se pierde.
- **Decisión:** el cómo-se-trabaja vive en docs durables (MANIFIESTO + esta memoria + `CLAUDE.md`),
  no se re-discute por sesión. Plan de tarea: si cabe en una sesión → plan en sesión; iniciativa
  multi-sesión → **un issue de tracking por iniciativa** (checklist de fases adentro, NO un issue
  por fase), auto-mantenido por la sesión que ejecuta.
- **Consecuencias:** una sesión nueva retoma una iniciativa larga sin contexto perdido.

### 2026-05-25 — Memoria en capas

- **Contexto:** "todo en GitHub Issues" enterraba el _por qué_ en issues cerrados, imposible de
  hacer cumplir por un agente.
- **Decisión:** Issues = cola de trabajo; commits/PRs = registro de cambios; `docs/MEMORIA.md` =
  decisiones de criterio + preferencias (curado, enforceable por el supervisor).
- **Consecuencias:** el criterio del proyecto queda cargado en cada sesión y revisable.

### 2026-05-25 — Gate de estilo en CI: formato + lógica de React bloquean

- **Contexto:** el repo tenía `eslint.config.js` pero el tooling nunca se instaló ni corría; al
  medir, ~98% de la deuda era formato auto-arreglable (prettier), no bugs.
- **Decisión:** el CI bloquea por **formato (prettier)** — automático y sin criterio, mantiene el
  código parejo. Las **reglas de lógica de React** (`exhaustive-deps`, `react-refresh`) arrancaron
  como **aviso** (para no frenar por deuda preexistente) y se **promovieron a bloqueante** una vez
  saldada esa deuda: hoy van en `"error"` + `reportUnusedDisableDirectives: "error"`.
- **Consecuencias:** los cambios nuevos deben pasar `npm run lint` sin errores (formato **y** lógica
  de React). Cada `eslint-disable` que sobreviva tiene que estar **justificado** — un disable que ya
  no silencia nada es error, así no se acumula deuda muerta.
- **Resuelto (#476, 2026-06-06):** triage completo de los avisos suprimidos — los 10 `exhaustive-deps`
  restantes son patrones intencionales (autosave con debounce, efectos mount-once, memos capturados
  una vez, exclusión de método/store estable), documentados en el código; **cero bugs reales**.

### 2026-05-26 — Convención de alias `e` para `equipos` en queries SQL

- **Contexto:** la migración `d5a8f2c4b6e9` dropeó `equipos.marca` (TEXT). El nombre se resuelve
  por subquery contra `marcas.nombre` vía `e.brand_id`. La subquery estaba copiada literal en >15
  lugares; algunas quedaron sin migrar → 500s en producción (#499). Se extrajo a un helper único
  (`database.MARCA_SUBQUERY`) que usa el alias `e`.
- **Decisión:** **todas las queries SQL nuevas que toquen `equipos` usan el alias `e`**
  (`FROM equipos e ...`, `e.brand_id`, etc.). Eso permite usar el helper canónico
  `MARCA_SUBQUERY` (que ya está escrito con `e.brand_id`) sin reescribir la subquery a mano.
- **Consecuencias:** una sola forma de resolver `marca` en queries de equipos → modularidad a
  prueba de balas (no se repite el olvido). Las queries viejas sin alias siguen funcionando (no
  son bug), pero al reescribirse migran a la convención.
- **Quién hace cumplir:** el supervisor lo marca como hallazgo en PRs nuevas que escriban queries
  sin alias.

### 2026-05-26 — Curación de la memoria (no es append-only puro)

- **Contexto:** el doc era "append-only", pero eso lo hace crecer indefinidamente y deja entradas
  obsoletas escritas como si fueran ciertas. Caso testigo: la entrada de "minutos de Actions" quedó
  falsa en horas (el repo volvió a público) y hubo que editarla en el lugar para no mentirle a una
  sesión futura.
- **Decisión:** `MEMORIA.md` es la **verdad curada del presente**, no un log. Se **edita y poda**
  para que quede chico y vigente. El "nada se pierde" lo garantiza el **historial de git**
  (inmutable) — ahí queda toda versión vieja. Una decisión reemplazada se **actualiza o retira en el
  lugar** (con nota "reemplazada por X" si ayuda), en vez de apilar contradicciones.
- **Quién cura:** el **supervisor** — además de cazar drift, en cada PR **propone** retirar entradas
  cuyo disparador ⏰ ya se cumplió, fusionar redundantes, o podar lo que perdió consecuencia. El
  supervisor **propone**; el dueño aprueba (la regla de "solo el dueño aprueba escrituras en
  MEMORIA" no cambia, ahora cubre también editar y podar).
- **Consecuencias:** la memoria se mantiene chica y verdadera; el log completo vive en git.

### 2026-05-27 — El Estudio: producto aparte que reusa el motor de reservas

- **Contexto:** el **Estudio** es un espacio físico que se alquila — parte del inventario pero **fuera
  de categorías/specs**. Se reserva **por horas** (no por día, mín 2h, tarifa plana), con un **pack
  opcional curado** (lista de equipos elegida en el back-office, tabla `estudio_pack_equipos`; los
  que estén ocupados en la franja no se ofrecen pero **no bloquean** la reserva — best-effort) y
  **slots fijos recurrentes mensuales** (ej. "miércoles 8-20 Filmar"). No es un equipo más.
- **Decisión:** modelarlo **reusando el motor de reservas existente, sin tocarlo ni duplicarlo**. La
  reserva vive en `alquileres`/`alquiler_items` con una columna `tipo` (`DEFAULT 'diaria'` → cero
  impacto en lo existente); un **equipo "centinela"** invisible (stock=1, sin categorías/specs)
  representa el espacio para que el overlap + buffer salgan de `_check_stock` (el gate vive en
  `backend/reservas/gate.py` — ver decisión 2026-05-30; ya es hora-granular). El pack se materializa
  como `alquiler_items`; los slots fijos generan **pedidos
  mensuales** que fluyen por estadísticas/pagos como cualquier alquiler. **El core de reservas es
  sagrado → no se modifica** (el buffer propio del estudio se aplica expandiendo el rango antes de
  llamar, nunca adentro del motor).
- **Consecuencias:** no se abre un segundo sistema de reservas paralelo. Plan v1 + etapas (E1-E4,
  multi-foto, slots) viven en GitHub **#548**; la v2 (rediseño UI mobile-first, login obligatorio,
  pack curado, features/FAQ editables) en **#555**. Follow-ups habilitados: multi-foto en equipos (el
  componente `PhotoGallery` se construyó genérico), pago online, **revenue separado estudio≠rental**
  (distribución proporcional del pack → rental; espacio/slot → estudio — es contabilidad, iniciativa aparte).

### 2026-05-27 — Notificaciones canal-agnósticas; mail construido-no-activado; confirmación = redirect al portal

- **Contexto:** al solicitar un pedido (carrito o estudio) el feedback era pobre; y la infra de mails
  ya estaba **construida pero apagada** (caía al backend `test`), no inexistente.
- **Decisión:** (1) el feedback de "pedido solicitado" es un **redirect al portal del cliente** con la
  card nueva resaltada (no un cartel en el lugar) — mismo flujo para carrito y estudio. (2) Las
  **notificaciones son canal-agnósticas**: hoy el canal es mail; **WhatsApp es follow-up** que se
  enchufa al mismo punto de despacho (generalizándolo a un notificador multi-canal), no un segundo
  sistema. (3) El envío de mails se **activa por configuración, no por código** (setear
  `RESEND_API_KEY`/`SMTP_*` + `EMAIL_FROM`/`EMAIL_ADMIN_TO` en prod) → es tarea de ops, iniciativa
  aparte. (4) Regla de **documentos**: el remito/contrato no existen en `presupuesto`, recién desde
  `confirmado` → el mail de creación no los promete, el de confirmación sí.
- **Consecuencias:** el recorrido del pedido queda documentado en `docs/FLUJO_PEDIDOS.md` (enlazado
  desde CLAUDE.md + MANIFIESTO). WhatsApp requiere proveedor (Meta/Twilio), verificación y plantillas
  pre-aprobadas → cuando se encare, va como iniciativa propia.

### 2026-05-29 — Módulo `equipment/shared/` = librería canónica de assets visuales (reusar, no recrear)

- **Contexto:** el design handoff de las vistas de equipos introdujo `StepperPill`, `PriceBlock` y
  `FavButton` como componentes compartidos. El handoff ya los define como tokens usados en las tres
  vistas del catálogo **y** en el CartDrawer.
- **Decisión:** viven en `src/components/rental/equipment/shared/` (exportados desde
  `equipment/index.ts`) y son la **única** fuente de esos patrones (stepper de cantidad, bloque de
  precio, botón favorito). Todo lugar que necesite uno **importa de ahí** — no se crea una variante
  "parecida pero distinta". Se irán incorporando a más pantallas con el tiempo (ese es el objetivo).
  `PriceBlock` calcula con `priceBreakdown()` (`@/lib/pricing`); `FavButton` se cablea a `useFavoritos`.
- **Consecuencias:** refuerza la barra de calidad (§ "modularidad a prueba de balas"). El supervisor
  marca como hallazgo cualquier stepper/precio/favorito ad-hoc que duplique estos componentes.

### 2026-05-29 — `RentalDateModal` = base única de selección de fechas (desktop + mobile)

- **Contexto:** el catálogo mobile (`CatalogoMovil`) tenía su propio `DateSheet` (bottom-sheet con
  `<input type=date>` nativo + `<select>` de horas) y un **estado de fechas local paralelo** al
  carrito, mientras desktop usaba `RentalDateModal`. Dos UIs y dos estados para la misma decisión.
- **Decisión:** hay **un solo selector de fechas** — `RentalDateModal` (responsive: calendario de
  2 meses en desktop, 1 mes full-screen en mobile) — usado en todos lados. Se **retiró** el
  `DateSheet` mobile. Las fechas del alquiler viven **solo en el cart-store** (`useCart`:
  `startDate/endDate/startTime/endTime`, jornadas vía `days()`); el modal las lee y escribe, y toda
  pantalla que las muestre las **deriva del store** (no estado local). La lógica de fechas se comparte
  desde `src/lib/rental-dates.ts` (incluido el helper `ymd`); el core de reservas no se toca.
- **Consecuencias:** no recrear un selector/sheet de fechas aparte ni un estado de fechas paralelo —
  reusar `RentalDateModal` y `useCart`. El supervisor marca como hallazgo cualquier UI de fechas
  ad-hoc o estado de fechas local que duplique la fuente única.

### 2026-05-30 — `backend/reservas/` = motor único de reservas (fuente única; el core sagrado tiene dirección física)

- **Contexto:** la lógica de disponibilidad y el gate `_check_stock` vivían dispersos y duplicados en
  `routes/alquileres.py`. La iniciativa #501 (PR #623) los unificó en el paquete `backend/reservas/`
  (`estados.py`, `semantics.py`, `disponibilidad.py`, `gate.py`).
- **Decisión:** todo cálculo de disponibilidad / chequeo de stock / overlap pasa por
  `backend/reservas/`. No se recrea ni se duplica lógica de reservas en los routes. Esto
  **materializa** el principio "el core de reservas es sagrado" (barra de calidad, punto 6): ahora ese
  core tiene **una dirección física única**.
- **Consecuencias:** el supervisor marca como hallazgo cualquier chequeo de stock/overlap/disponibilidad
  ad-hoc en un route que debería llamar al paquete. Cambios al paquete son de **alto radio de
  explosión** → Opus (ver _Eficiencia de sesión: modelo según tarea_). El test de concurrencia con
  Postgres real (`test_reservas_concurrency_db.py`, opt-in) es la prueba definitiva del `FOR UPDATE`.

### 2026-05-31 — Expansión recursiva del motor de reservas (C4 #635)

- **Contexto:** la lectura y el gate expandían la composición a **1 nivel**. Un combo **anidado**
  (combo→kit→hoja) se contaba de menos en AMBAS direcciones → overbooking (reproducido contra
  Postgres real antes de tocar nada). El conteo _backward_ (`reservado_via_kit`, 1 nivel) era tan
  culpable como el _forward_: no alcanzaba con recursar solo la expansión del pedido.
- **Decisión:** toda expansión de composición del motor —demanda hacia abajo y consumo hacia
  arriba— es **recursiva hasta las hojas**, vía una pieza ÚNICA `_expandir_mult` en
  `backend/reservas/semantics.py` (agnóstica de dirección: `componentes_de` baja, `parientes_de`
  sube). `reservado_total` reemplazó al par `reservado_directo + reservado_via_kit`. El gate
  (`validar_stock`) expande forward + backward recursivo y lockea en **`ORDER BY id`**
  (determinístico, sin deadlock). El `FOR UPDATE`/transacción/commit quedaron **byte-idénticos**
  (núcleo sagrado intacto). `esencial` propaga **conjuntivo** (una arista best-effort corta su
  subrama): lectura con `solo_esenciales=True`, gate estricto con `False` (lógica blanda afuera).
- **Consecuencias:** lectura y gate **no pueden divergir** (misma pieza recursiva). No re-introducir
  expansión inline de 1 nivel en routes ni "otra función parecida" — todo pasa por `_expandir_mult`.
  El supervisor marca como hallazgo cualquier conteo de stock/expansión/overlap ad-hoc. El **batch
  O(N)→1** (perf, no correctitud) queda **diferido** a #626. Materializa y extiende la decisión
  _2026-05-30_ (`backend/reservas/` = motor único). Red de seguridad: caracterización diferencial
  (`test_gate_caracterizacion_c4.py`) + correctitud/concurrencia anidada real
  (`test_reservas_nested_db.py`, opt-in).

### 2026-06-01 — Gotcha de Railway: fork de ambiente desincroniza la contraseña del Postgres

- **Contexto:** el backend de staging (`dev`) tiraba 500 en cascada con
  `psycopg2.OperationalError: FATAL: password authentication failed for user "postgres"`.
  No era bug de código: al **forkear** el ambiente `dev` desde prod, el **volumen** del Postgres
  quedó con una contraseña, pero la variable `POSTGRES_PASSWORD` se **regeneró sin correr el
  `ALTER USER`** correspondiente → la variable mentía. Ni la variable de staging, ni la de prod,
  abrían la BD (la contraseña real del volumen no coincidía con ninguna).
- **Decisión / cómo arreglar:** la contraseña real vive **dentro del Postgres** (en disco), no en
  una variable de entorno → **ninguna** edición de variables (ni Shared Variables) lo arregla. Hay
  que **resetear la contraseña en la BD** para que matchee la variable, entrando por el socket local
  (auth `peer`, sin contraseña) vía SSH al contenedor:
  ```
  railway ssh --service Postgres --environment dev \
    "psql -U postgres -d railway -h /var/run/postgresql \
     -c \"ALTER USER postgres WITH PASSWORD '<POSTGRES_PASSWORD de ese ambiente>';\""
  ```
  Después, alinear `DATABASE_URL` del backend a esa misma contraseña y redeploy.
- **How to apply:** ante `password authentication failed` en un ambiente recién forkeado, es **esto**
  — no perseguir variables. Reset por SSH + socket local. **Prod es sagrado**: no se leen sus
  credenciales ni se prueba contra su BD para diagnosticar staging.
- **Consecuencias:** receta directa para la próxima sesión que forkee un ambiente con DB.

### 2026-06-02 — Google Analytics: sin consent, solo catálogo público, ID administrado desde el back-office

- **Contexto:** se integró GA4 al front. Decisiones del dueño: sin banner de consentimiento (GA
  carga directo), medir páginas vistas + 3 eventos de negocio (`add_to_cart`, `solicitar_pedido`,
  `reservar_estudio`), cobertura **solo catálogo público** (`/admin` y `/cliente` quedan fuera del
  conteo), y el Measurement ID se administra **desde el back-office** (`/admin/settings`), no por
  variable de entorno.
- **Decisión:** el tracking vive en un módulo único `src/lib/analytics.ts` (sin React); cada evento
  se dispara en **un solo punto canónico** (carrito → `cart-store.ts`, pedido → `orders.createOrder`,
  estudio → `api.apiCrearReservaEstudio`). El ID se guarda en `app_settings.ga4_measurement_id` y el
  front lo lee en runtime de `GET /api/analytics-config`. `VITE_GA4_ID` queda como **override opcional
  de ops** (gana, cualquier ambiente).
- **Gate por entorno (clave):** ese endpoint **solo expone el ID en producción** (`settings.is_production`
  en `backend/config.py`). Como staging (`dev`) corre con **BD copiada de prod** (decisión 2026-06-01),
  sin el gate compartiría el ID y ensuciaría las métricas reales con tráfico de prueba. `is_production`
  usa una **lista negra** de nombres no-prod (`dev/staging/development/preview/test/local`) y falla hacia
  "sí es prod" ante un nombre desconocido (mejor medir de más que apagar prod en silencio).
- **⚠️ Gotcha operativo:** la lista negra es fija. **Al crear un ambiente Railway nuevo que no sea
  producción** (ej. `qa`, `sandbox`, `dev2`), agregar su nombre a `is_production` **o** dejar
  `VITE_GA4_ID` vacío ahí — si no, ese ambiente trackearía contra la propiedad de prod. Disparador ⏰:
  cada vez que se cree un ambiente nuevo.
- **Consecuencias:** no recrear tracking ad-hoc ni un segundo punto de disparo por evento — todo pasa
  por `analytics.ts` y los puntos canónicos. WhatsApp/otros canales y la cobertura del portal `/cliente`
  (con rutas sanitizadas) quedan como follow-ups si se piden.

### 2026-06-03 — Esquema en dos capas: `init_db()` (bootstrap) + Alembic; toda tabla nueva va TAMBIÉN en `init_db()`

- **Contexto:** el 500 de "Qué busca la gente" (#687) destapó que las migraciones de prod no llegaban
  al head: la tabla `search_queries` vivía solo en una migración Alembic y nunca se creó. Causa raíz
  (#690): el arranque corre `alembic upgrade head` y, si una migración **aborta por los datos** (ej.
  `f5b8d2e4a9c1` corta si hay slugs duplicados en `equipos`), el error se loguea y la app sigue → la BD
  queda **trabada en una revisión vieja en silencio**. No se reproduce en local (sin esos datos).
- **Decisión:** el esquema vive en **dos capas**: (1) `backend/database.py::init_db()` —bootstrap
  idempotente (`CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`), corre en cada arranque, es
  el que **garantiza que las tablas existan**— y (2) Alembic, para cambios incrementales (sobre todo
  migraciones de datos). **Toda tabla/columna nueva va TAMBIÉN en `init_db()`**, no solo en una
  migración. La visibilidad del estado de migraciones es **fuente única** en
  `backend/migration_state.py` (no recrear el chequeo ad-hoc), expuesta en `GET /health/migrations`.
- **Why:** si las migraciones se traban, una tabla creada solo en una migración no existe en prod;
  `init_db()` es la red. La cadena de migraciones **no se basta sola desde una BD vacía** (una
  migración de datos hace `UPDATE equipos`) → el único bootstrap soportado es `init_db()` + upgrade.
- **How to apply:** el supervisor marca como hallazgo cualquier tabla/columna nueva que aparezca solo
  en una migración Alembic sin su equivalente idempotente en `init_db()`, o cualquier chequeo de
  estado de migraciones reimplementado fuera de `migration_state.py`. El test
  `backend/tests/test_alembic_upgrade_db.py` (opt-in + job CI `db-migrations`) corre init_db + upgrade
  contra Postgres real y exige llegar al head. Modelo + runbook de reparación de prod en
  [`docs/RUNBOOK_MIGRACIONES.md`](RUNBOOK_MIGRACIONES.md). La **Parte B** (destrabar prod) sigue
  pendiente en #690.

### 2026-06-03 — `backend/reportes/` = motor único de reportes financieros (espeja `backend/reservas/`)

- **Contexto:** el generador de reportes (#88) introdujo la liquidación por dueño: atribución por
  fecha de pago (solo pedidos 100% pagados), prorrateo del total entre los equipos del pedido y
  reparto entre beneficiarios según un modelo de comisiones editable (`app_settings.comisiones_modelo`).
  Es lógica de **plata** con alto costo si se duplica o diverge.
- **Decisión:** todo cálculo de reportes financieros (atribución, prorrateo, reparto de comisiones,
  agregación) vive en el paquete **`backend/reportes/`** (`comisiones.py` = modelo + reparto +
  validación; `liquidacion.py` = SQL de pedidos saldados + prorrateo + `agregar` pura). El route
  (`routes/reportes.py`) es **solo transporte HTTP + CSV**. Materializa el mismo principio que
  _2026-05-30_ (`backend/reservas/` = motor único): el dinero tiene una **dirección física única**.
- **Cómo aplica / quién hace cumplir:** el supervisor marca como hallazgo cualquier cálculo de
  reporte/reparto/atribución ad-hoc en un route en vez de pasar por `backend/reportes/`. El pipeline
  se parte SQL→filas→`agregar` para que la matemática (prorrateo + comisiones + buckets mes/día) se
  teste sin DB.
- **Consecuencias:** no re-implementar lógica de plata en routes ni "otra función parecida". El
  modelo de comisiones es **editable desde el back-office** (no hardcode); su default vive en
  `comisiones.DEFAULT_MODELO`. Caveat conocido (follow-up): un endpoint legacy puede setear
  `monto_pagado` sin registrar el pago en `alquiler_pagos` → ese cobro no aparecería en el reporte
  (el front actual cobra por la vía que sí registra).

### 2026-06-03 — Cierre de mes + clean start de la liquidación (junio 2026)

- **Contexto:** la liquidación (#88) se calcula en vivo → editar el modelo de comisiones o un pedido
  viejo reescribe el pasado. Y al arrancar el reparto formal entre dueños no se quiere arrastrar el
  histórico previo.
- **Decisión — Cerrar mes (foto inmutable, #721):** cerrar un mes guarda una **foto inmutable** del
  reporte de ese mes (números **+** modelo de comisiones con que se calculó) en `liquidacion_cierres`;
  mientras está cerrado el reporte se sirve de la foto, inmune a cambios posteriores. **Reabrir** la
  borra y vuelve a vivo. Editar un pedido de un mes cerrado **se permite**, pero el semáforo de
  reconciliación **avisa** que la foto quedó vieja (chequeo `mes_cerrado_desactualizado`). Motor en
  `backend/reportes/cierres.py`; tabla en `init_db()` **+** migración (esquema en dos capas).
- **Decisión — Clean start (junio 2026):** los pedidos cuyo **alquiler (`fecha_desde`) es anterior al
  `2026-06-01` no cuentan** para la liquidación, aunque se paguen después. El corte es por **fecha del
  alquiler** (NO de pago — la atribución temporal sigue siendo por fecha de saldado; esto es un filtro
  de elegibilidad, ortogonal). Aplica **solo a la liquidación** (Reportes + sus chequeos de
  reconciliación); el **Resumen general de estadísticas sigue mostrando el histórico completo**. Es una
  constante única **`LIQUIDACION_INICIO`** en `backend/reportes/liquidacion.py`, embebida en el CTE
  compartido `SALDADO_CTE` y derivada en la reconciliación (`_CLEAN_START`) — **fija en el código a
  propósito, NO administrable** (decisión de una sola vez).
- **Quién hace cumplir:** el supervisor marca como hallazgo (1) cualquier tabla/columna de cierres sin
  su espejo en `init_db()`; (2) duplicar el valor de corte fuera de `LIQUIDACION_INICIO`; (3) filtrar
  el Resumen general con el clean start; (4) reintroducir expansión/atribución de plata ad-hoc fuera de
  `backend/reportes/`. Extiende la decisión _2026-06-03 — `backend/reportes/` = motor único_.

### 2026-06-06 — El Presupuesto (PDF) muestra el IVA aparte, no sumado al total

- **Contexto:** al alinear los 5 documentos PDF al mockup de Claude Design, el Presupuesto
  pasó a mostrar el **total como el neto** (con descuento) y un sufijo **"+ IVA"** al lado,
  en vez de sumar el IVA dentro del número grande (como hacía antes, con filas "Neto" e
  "IVA 21%").
- **Decisión:** en el **Presupuesto**, para un cliente **responsable inscripto**, el total
  grande es el **neto** y el IVA se anota como **"+ IVA"** (no se suma ni se discrimina el monto
  acá). Para no-RI, total = neto sin sufijo. Es **decisión del dueño**, puramente de presentación.
- **Why:** el presupuesto es un documento **previo**, no la factura. El cliente RI ve el precio
  sin IVA con la aclaración de que se agrega; la **Factura A** real sigue discriminando el IVA por
  el motor de precios (`services/precios.py`, intacto). Mostrar el neto grande es más limpio y es
  lo que pidió el dueño.
- **How to apply / quién hace cumplir:** **no "arreglar" esto** pensando que es un bug — el
  Presupuesto NO suma el IVA al total a propósito. Vive en `pdf_templates._pedido_html`
  (sufijo `.iva-suffix`). El **remito/contrato/reportes y la Factura A** no cambian. El supervisor
  marca como hallazgo cualquier cambio que vuelva a sumar el IVA al total del presupuesto sin
  aprobación del dueño.

### 2026-06-06 — Datos del pedido: contacto en vivo, plata congelada

- **Contexto:** un pedido (`alquileres`) guarda una **foto** de los datos del cliente al crearse
  (`cliente_nombre/email/telefono` + `descuento_pct`). El dueño editó el descuento y el contacto de
  un cliente y esperaba verlos reflejados en sus pedidos; no pasaba. Además había **inconsistencia**:
  el back-office mostraba la foto vieja del contacto mientras el portal del cliente ya lo leía en
  vivo (el mismo documento mostraba datos distintos según quién lo abría).
- **Decisión — dos tipos de dato, dos comportamientos:**
  - **Contacto / identidad (nombre, email, teléfono) → SIEMPRE en vivo** desde la ficha del cliente,
    en **todos los estados** (presupuesto/confirmado/finalizado) y **todas las superficies**
    (back-office: detalle + listado + los 4 PDFs; portal). Corregir un apellido o teléfono se ve en
    todos los pedidos de esa persona. No hay nada que "congelar" en un dato de contacto.
  - **Plata (precio, descuento, ítems, totales) → snapshot con lock por estado.** El descuento del
    cliente se propaga a sus **presupuestos** (no confirmados), que se **recotizan**; los
    **confirmados/cerrados conservan su snapshot** (un pedido ya confirmado/facturado no debe cambiar
    de importe porque después se editó el perfil). El **perfil fiscal** (razón social/CUIT) sí se lee
    en vivo, porque la Factura A debe salir correcta.
- **Why:** el contacto es *cómo/quién es* la persona → se quiere lo último. La plata es lo *cobrado/
  a cobrar* → trazabilidad: lo confirmado no muta. Son ejes ortogonales y por eso se tratan distinto.
- **How to apply / quién hace cumplir:** el contacto pasa por un **helper único**
  `_enriquecer_pedido_con_cliente` (+ su versión batch para listados, sin N+1) en
  `routes/alquileres.py`, que sobrescribe **solo** nombre/email/teléfono (nunca montos); fallback a la
  foto si el pedido no tiene cliente vinculado o el cliente no existe. La plata vive en
  `_recalcular_total_pedido` + `propagar_descuento_a_presupuestos` (misma transacción que el update
  del cliente). El supervisor marca como hallazgo: (1) cualquier superficie de pedido que muestre
  contacto sin pasar por el helper; (2) congelar el contacto o, al revés, descongelar la plata de un
  confirmado/finalizado; (3) propagar el descuento a estados que no sean `presupuesto`.

### 2026-06-06 — `backend/services/branding/` = motor único de assets de marca (SVG master → derivados)

- **Contexto:** el logo de marca convivía en ~4 fuentes distintas (webp en `Logo.tsx`, webp suelto en
  el footer, SVG huérfano del DS, PNGs estáticos de favicon/og) y el logo del mail era un PNG
  transparente sobredimensionado que se ensuciaba en dark mode. Se unificó todo: el dueño sube
  **dos SVG master** (wordmark + isologo) en `/admin/diseño → "Marca (SVG)"` y el sistema **deriva**
  el resto.
- **Decisión:** todo asset de marca sale de un **motor único** `backend/services/branding/`
  (`rasterize.render_svg_png` reusa el **Chromium headless de los PDFs** — `pdf._get_browser`, cero
  deps nuevas; `derive_from_wordmark`/`derive_from_isologo` arman la matriz). El recoloreo usa los
  **tokens del DS** y el par sancionado **ink ↔ amber** (blanco-sobre-amber NO está sancionado).
  Los SVG master + sus derivados se guardan en `app_settings` (incluido `wordmark_svg`, el SVG
  saneado como texto). **Consumidores (una sola fuente):**
  - **web:** `Logo.tsx` inyecta el wordmark **inline** (themable vía `currentColor`) desde
    `wordmark_svg` → fallback al SVG canónico bundleado. Topbar + footer + logins.
  - **mail:** header = celda amber + wordmark blanco (`email_logo_url`, derivado).
  - **PDFs (5 docs):** `pdf_templates._active_wordmark()` lee `wordmark_svg` con fallback al constante.
  - **favicon / apple-touch / icon:** derivados del isologo (tile amber + ink), swap en runtime
    (`FaviconSync`). El **og:image** para crawlers se inyecta server-side en la home (`main.root()`).
- **Materializa** el mismo principio que _2026-05-30_ (`backend/reservas/`) y _2026-06-03_
  (`backend/reportes/`): el dominio tiene una **dirección física única**. Se **retiró** la subida
  vieja "Logo del sitio" (`logo_url` / `upload-logo`) — unificada en el wordmark SVG master.
- **Quién hace cumplir:** el supervisor marca como hallazgo (1) cualquier rasterización/recoloreo de
  marca ad-hoc fuera de `services/branding/`; (2) un `<img>` de wordmark nuevo en la web en vez del
  `Logo` inline; (3) resucitar la subida `logo_url`/`upload-logo`; (4) un derivado de logo/favicon
  hecho a mano en vez de generado por el motor. El diseño del header de documentos/mail (barra amber
  full-bleed + wordmark blanco) es decisión visual del dueño — no "arreglar" el full-bleed ni sumar
  un tagline bajo el wordmark sin pedido.

### 2026-06-06 — `backend/busqueda/` = motor único de búsqueda textual (fuzzy + ranking)

- **Contexto:** la búsqueda de clientes (`LIKE` alfabético, sensible a tildes, sin entender "nombre
  apellido" en campos separados) y de equipos (`ILIKE` plano, sensible a tildes/guiones) estaba
  copiada ad-hoc en los routes, y el front tenía ~3 normalizadores de texto distintos. El dueño no
  encontraba clientes ("escribo Santiago y a veces trae uno, a veces otro") ni equipos con tilde o
  guion en el nombre.
- **Decisión:** toda búsqueda de texto (clientes, equipos, catálogo) pasa por el paquete único
  **`backend/busqueda/`** (`normalizar.py` + `motor.py`), espejando el patrón de `reservas/` y
  `reportes/`. Normalización canónica (minúsculas, sin acentos, no-alfanumérico→espacio, espacios
  colapsados) **espejada en el front** (`src/lib/search/normalize.ts`) contra un corpus compartido
  (`backend/tests/data/normalizacion_corpus.json`). Matching + ranking con **`pg_trgm` + `unaccent`**:
  substring sin tildes/guiones, multi-palabra cruzando campos, tolerancia a typos y **ranking por
  relevancia** (el mejor match primero, consistente). Los índices GIN trigram usan la **misma
  expresión canónica** que arma el motor (`CAMPO_PLANTILLA` / `busqueda.campo_sql`). El catálogo
  público sigue filtrando **client-side** (instantáneo, mobile-first) pero con esas mismas reglas.
- **Nombre del cliente:** se compone "Nombre Apellido" (nombre primero) en TODAS las superficies, vía
  un helper único por lado (`routes/clientes.nombre_completo_cliente` / `src/lib/cliente-nombre.ts`).
  Ortogonal al motor de búsqueda, pero salió en la misma iniciativa.
- **Aprendizaje (todavía no):** el click-through (`search_clicks`) registra qué resultado abre la
  gente del catálogo público — es señal **cruda para el futuro**, NO toca el ranking todavía. Cuando
  se active la capa de aprendizaje (sinónimos curados desde búsquedas con cero resultados + boost por
  popularidad/click-through), **actualizar esta entrada**.
- **Quién hace cumplir:** el supervisor marca como hallazgo cualquier `ILIKE`/`LIKE` o normalizador de
  búsqueda ad-hoc en un route o en el front que no pase por el motor; cualquier índice de búsqueda
  cuya expresión no sea la canónica; o componer el nombre del cliente sin el helper único. **Caveat
  honesto:** el contrato corpus↔front NO está enforzado por un test mientras el repo no tenga runner
  de tests JS (hoy solo lo verifica el test de Python). Extiende _2026-05-30 (`reservas/`)_,
  _2026-06-03 (`reportes/`)_ y el esquema en dos capas _2026-06-03_ (extensiones + `f_unaccent` +
  índices + `search_clicks` viven en `init_db()` Y migración).

### 2026-06-06 — Design system consolidado en la app; `design-system` gobierna, `pulido-frontend` aplica

- **Contexto:** convivían DOS implementaciones del DS: el paquete workspace
  `@rambla/design-system` (tokens/CSS/fuentes — consumidos vía `@import` — **+** copias paralelas de
  componentes que **driftearon** de la app, ej. EquipmentCard 317 líneas distintas) y los componentes
  reales de la app en `src/components` (los que usó el rediseño de Pedidos v2 = lo último/canónico). El
  paquete no se consumía para componentes (0 imports JS), solo para CSS. Además había dos skills de
  diseño (`design-system` para el paquete, `importar-diseno` para implementar handoffs).
- **Decisión original (2026-06-06):** todo el DS en la app; un solo skill (`importar-diseno`). El
  paquete workspace `@rambla/design-system` retirado. Cierra #662.
- **Refinamiento (2026-06-23):** `importar-diseno` archivado — el diseño se refina directamente en
  Claude Code, ya no vienen handoffs de Adobe/PDF externos. El rol de gobernanza del DS lo toma el
  skill **`design-system`** (`model: opus`): audita sistémicamente (tokens, adopción,
  reimplementaciones, 11 principios, drift del doc `DESIGN_SYSTEM.md`), proporciona el dashboard `/ds`,
  y propone issues. **`pulido-frontend`** aplica los fixes en pantalla. Cuadro de roles: `design-system`
  gobierna · `pulido-frontend` ejecuta UI · `mantenimiento` ejecuta código.
- **Cómo aplica / quién hace cumplir:** un token/utility se edita en `src/design-system/styles/`,
  una pieza de DS en `src/design-system/{ui,kit}` o de negocio en `src/components/{rental,admin}`;
  **no se recrea un paquete workspace** ni se duplica una pieza que ya existe. El
  supervisor marca un skill en disco que no esté listado en `CLAUDE.md`; `check-docs.mjs` lo caza.
  Los trackers de migración por pantalla (#612) siguen vigentes sobre `src/`.

### 2026-06-07 — `backend/contabilidad/` = motor único de la plata "de adentro" (cierra #809)

- **Contexto:** la iniciativa #809 construyó el módulo contable del back-office (sección Finanzas):
  cuentas/cajas con saldo, libro de movimientos (gasto/transferencia/retiro/aporte/ajuste),
  rendición mensual entre socios, ganancia neta (P&L), cierre contable y reconciliación. Es lógica
  de **plata** con alto costo si se duplica o diverge.
- **Decisión:** toda la plata "de adentro" del negocio (cajas, movimientos, saldos, rendición,
  ganancia, cierre contable, reconciliación) vive en el paquete **`backend/contabilidad/`**; los
  routes son solo transporte HTTP. Materializa el mismo principio que `backend/reservas/`
  (_2026-05-30_) y `backend/reportes/` (_2026-06-03_): el dominio tiene una **dirección física
  única**. Invariantes:
  - **Los ingresos por alquiler DERIVAN de `alquiler_pagos`** (única fuente del cobro, #722): el
    saldo de la caja de un socio se calcula sumando sus pagos por `destinatario`; **nunca** se
    re-carga un movimiento por un cobro de cliente → cero doble-contabilización por construcción.
  - **La plata no se borra:** anular un movimiento es soft-delete con motivo (deja de contar para
    los saldos pero queda trazable). Auditoría `created_by/updated_by/anulado_por`.
  - **Enteros ARS** en todo el cálculo (como el resto del sistema), no `NUMERIC`.
  - **Multi-moneda por caja (2026-06-07):** cada caja tiene `moneda` (ARS default / USD). Los saldos
    **NO se mezclan** entre monedas (`saldos.totales` por moneda; `total_disponible` = ARS, campo de
    compat); transferencia/ajuste exigen **misma moneda** (sin conversión automática); los cobros de
    clientes son **ARS** y solo alimentan cajas ARS; el **P&L es en ARS** (los gastos pagados desde
    una caja USD no suman al P&L en pesos). La **moneda es inmutable tras crear** (cambiarla
    reinterpretaría saldos pasados — NO "arreglar" eso pensando que es un bug). Una conversión real
    entre cajas, si hace falta, va como flujo aparte y explícito, no como edición de campo.
  - **Devengado vs percibido, a propósito:** la **ganancia/P&L** se mide por **ingreso devengado**
    (= total del reporte de liquidación del mes); el **saldo de caja** se mueve por **plata
    entrante** (incluidas señas). Pueden no coincidir mes a mes — no es un bug.
  - **Vista unificada de Movimientos (2026-06-07):** la pantalla Movimientos muestra, junto a los
    movimientos manuales, los **cobros de pedidos agregados por mes** (una línea read-only "Cobro
    alquileres &lt;mes&gt;", derivada de `alquiler_pagos`, NUNCA una fila en `movimientos` → cero doble
    conteo). El monto lleva **guía debe/haber**: entra (haber) en `text-verde`, sale (debe) en
    `text-destructive`, interno (transferencia/ajuste 2 cajas) neutro — el verde "éxito" se usa como
    semáforo de plata **a propósito** (decisión del dueño), aunque el DS lo reserve a status/charts.
    Cada movimiento puede llevar un **`beneficiario`** (a quién/para qué, ej. "Jimena"): etiqueta de
    texto reutilizable (autocompletado de los usados + filtrable para ver su historial), **NO un
    sistema de empleados**. "Pagos" se renombró a "Cobros de pedidos".
  - **Rendición** atada al MISMO universo de pedidos saldados que el reporte (reusa `SALDADO_CTE`)
    → cierra en cero; un saldado se registra como **transferencia `es_rendicion`** en el mismo
    libro (no un sistema paralelo). **Los tres cobran** (Pablo/Tincho/Rambla; **Rambla es el
    cobrador por defecto** desde 2026-06-07): la plata cobrada se atribuye a la caja del cobrador
    (Pablo/Tincho → su caja de socio; Rambla → Fondo Rambla) vía la columna `cuentas.socio` (= a qué
    cobrador representa la caja). La **parte de Rambla NO se reparte** entre Pablo y Tincho. Los
    cobradores válidos viven en la constante única `COBRADORES` (los tres) + `SOCIOS_HUMANOS`
    (Pablo/Tincho, los únicos válidos para una caja de tipo `socio`).
  - **Socios = cuenta corriente, no caja (2026-06-09):** Pablo/Tincho dejaron de modelarse como
    "caja de plata" (un saldo de socio crecía al cobrar, lo cual confundía: cobrar ≠ ganar su parte)
    y pasaron a **cuenta corriente** deudor/acreedor: `deuda = arranque + cobró − su parte ±
    rendiciones`, donde **arranque** = `saldo_inicial` del socio (lo que cobró ANTES del sistema),
    **cobró** = sus `alquiler_pagos`, **su parte** = su comisión devengada (de `reportes/liquidacion`,
    `por_beneficiario`). **>0 → DEUDOR** (el socio le debe a Rambla), **<0 → ACREEDOR** (Rambla le
    debe), **0 → saldado**. Las cuentas corrientes **NO suman al total disponible** (esa plata la
    tiene el socio en mano, no es caja del negocio) y una **negativa (acreedor) NO es error** de
    reconciliación — el chequeo de saldos negativos corre solo sobre cajas. **Rambla/Fondo Rambla
    sigue siendo caja de plata real** (su parte NO se resta; lo que cobra es cash del negocio). La
    dualidad devengado/percibido sigue valiendo (a un socio se le resta lo devengado de lo percibido);
    lo que cambió es que la *caja de socio* del modelo viejo ahora se lee como cuenta corriente. La
    pantalla Cuentas y el tablero separan "Socios · Cuenta corriente" de "Cajas · Plata del negocio".
    La **rendición mensual** (foto del mes) y la **cuenta corriente** (saldo acumulado) son dos vistas
    del mismo motor.
  - **Cierre contable DISTINTO del de liquidación (#721):** aquel congela el reparto del reporte;
    este congela el estado de cajas/movimientos y **traba la edición de movimientos del mes por la
    fecha del movimiento** (`_exigir_mes_abierto` en crear/editar/anular). Esquema en dos capas
    (`init_db()` + migración) para toda tabla nueva.
- **Quién hace cumplir:** el supervisor marca como hallazgo cualquier cálculo de plata interna
  ad-hoc fuera del paquete; un endpoint que escriba `movimientos` sin pasar por el motor (se
  saltearía el candado de mes cerrado); recargar ingresos de alquiler a mano; o duplicar el valor
  de los cobradores fuera de `COBRADORES`. Extiende _2026-05-30_ (`reservas/`) y _2026-06-03_ (`reportes/`).
- **Pendiente conocido:** las partes de la rendición son fijas (Pablo/Tincho/Rambla). Si alguna vez
  el modelo de comisiones reparte a un **cuarto beneficiario**, esa parte quedaría fuera del cuadro
  y el total no cuadraría → habría que generalizar las partes. Hoy no es un caso real.

### 2026-06-08 — Memoria en dos sub-capas: digest enforceable + log de decisiones

- **Contexto:** `MEMORIA.md` había crecido a 711 líneas (37 entradas de prosa ADR) y se **auto-carga
  entera en cada sesión** (vía `@docs/MEMORIA.md` en `CLAUDE.md`). El costo dominante del plan es la
  re-lectura de contexto en caché (decisión _2026-05-26 — Eficiencia de sesión_); pagar 711 líneas por
  turno, la mayoría relato del *por qué*, era el mayor desperdicio evitable. Las **reglas enforceables**
  estaban mezcladas con el **rationale**.
- **Decisión:** la memoria se parte en dos sub-capas, sin perder nada:
  - **`docs/MEMORIA.md` = digest enforceable, auto-cargado.** Cada entrada conserva su header
    `### YYYY-MM-DD — Título` + **1-3 líneas con la regla/invariante** y un link al log. ~150 líneas.
    Es la línea base que el supervisor hace cumplir y la que la sesión tiene siempre en contexto.
  - **`docs/DECISIONES.md` = log ADR completo, on-demand.** La prosa entera (Contexto/Why/
    Consecuencias/gotchas). NO se auto-carga; lo abre el supervisor (ventana aislada) para juzgar drift
    fino y curar, y la sesión cuando necesita el *por qué* puntual.
- **Why / cómo es seguro:** **refina** —no reemplaza— la decisión _2026-05-25 — Memoria en capas_
  (Issues=cola, commits=changelog, memoria=criterio): solo sub-divide la capa "criterio" en
  regla+rationale. **Nada se pierde:** el log recibe la prosa **verbatim**; el digest se **deriva**.
  La **misma fecha-título** vive en ambos archivos → toda cita "_ver MEMORIA AAAA-MM-DD_" sigue
  resolviendo. El gate de escritura no cambia: **solo el dueño aprueba**, toda escritura toca ambos.
- **How to apply / quién hace cumplir:** una decisión nueva se escribe en **los dos** (regla al digest,
  desarrollo al log) bajo el mismo header de fecha. El script `scripts/check-docs.mjs` (job CI
  `docs-lint`) verifica la **paridad de headers** digest↔log y que `@docs/MEMORIA.md` siga presente. El
  supervisor marca como hallazgo una entrada que exista en uno y no en el otro, o una regla en el digest
  sin su rationale en el log.

### 2026-06-19 — Staging-login: la sesión auto-prueba el back-office logueado

- **Contexto:** el back-office (`/admin/*`) y sus endpoints `require_admin` solo se podían verificar a
  ciegas. La sesión podía confirmar que rechazan al anónimo (401/403), pero no el **comportamiento logueado**
  (que un GET admin devuelve datos reales, que un handler refactorizado sirve igual). La auth es **Google
  OAuth**, así que no hay forma práctica de pasarle una cookie a la sesión, y el dueño no quería clickear el
  back-office a mano para cada cambio. Disparador: el split de `equipos.py` (#501 fase a) — había que probar en
  vivo que los submódulos (dashboard/mantenimiento/ficha/kit) servían bien **autenticados**, no solo que las
  rutas existían.
- **Decisión:** un login programático **solo de staging**, `POST /auth/staging-login`, que mintea la **misma
  cookie de sesión firmada** que el OAuth real para una cuenta de servicio (`STAGING_LOGIN_EMAIL`, default
  `staging-bot@rambla.local`). A diferencia de `/auth/dev-login` (apagado en CUALQUIER entorno Railway), este
  corre en el `dev` de Railway. Con eso la sesión se loguea por `curl` y **smoke-testea flujos autenticados del
  back-office en staging por sí misma**; de paso desbloquea los tests HTTP autenticados (antes solo cubrían el
  401/403).
- **Gate de doble llave (defensa en profundidad):** (1) **no-prod** vía `settings.is_production`, que **falla
  hacia "sí prod"** ante un nombre de entorno desconocido → un ambiente nuevo mal nombrado queda con el login
  APAGADO, no abierto; (2) **secreto configurado** (`STAGING_LOGIN_SECRET`): sin él el endpoint responde 404 ni
  siquiera en dev. 404 cuando está deshabilitado (parece inexistente en prod), secreto comparado en **tiempo
  constante** (`secrets.compare_digest`), rate-limit por IP compartido con el OAuth, cada intento logueado.
- **Why / cómo es seguro:** el secreto es **obligatorio, no opcional**, porque la BD de `dev` es **copia de
  prod → tiene PII real** (MEMORIA 2026-06-02); un login abierto en una URL pública de dev sería una fuga. La
  **admin-ness NO se saltea**: la sesión se mintea pero el rol lo sigue resolviendo `is_admin_email` (fuente
  única) → la cuenta debe estar en `ADMIN_EMAILS` de dev. **Refina —no reemplaza—** _El dueño testea, no revisa
  código (2026-05-25)_: el gate humano sigue siendo el dueño probando en staging; esto solo deja que la sesión
  cierre el loop de verificación logueada antes de pasárselo.
- **How to apply / gotchas:** vars **solo en el entorno `dev`** de Railway: `STAGING_LOGIN_SECRET` (rotable) +
  el mail del bot en `ADMIN_EMAILS` (o `STAGING_LOGIN_EMAIL` = un mail que ya sea admin). **Nunca** en prod (el
  handler responde 404 igual, pero el secreto no debe existir fuera de dev). Para no mutar staging (que es copia
  de prod), las escrituras de prueba van con **IDs inexistentes** (404 "no encontrado" = la auth pasó y el
  handler corre, sin crear datos). Probado en vivo: login 200, `/auth/me` `is_admin: true`, lecturas admin 200,
  escrituras a id falso 404. Setup detallado en `docs/DEPLOY_RAILWAY.md`.

### 2026-06-20 — Gate de "frontend servible" + paths de assets a la raíz (no __file__ del paquete)

- **Contexto.** `ramblarental.com.ar` sirvió `{"error":"Frontend not built"}` (503) en vez del catálogo. El
  backend (Railway) sirve el SPA desde `FRONT_NEW/index.html`; el split `database.py` → paquete `database/`
  (#501) bajó `core.py` un nivel y `FRONT_NEW = BASE.parent / "dist"` (con `BASE = Path(__file__).parent`)
  pasó a apuntar a `backend/dist` en vez de la raíz `/app/dist` (donde el Dockerfile copia el build) →
  `_serve_frontend` no encontraba el index → 503.
- **Por qué no se cazó antes.** En ese momento el backend Railway de dev no servía el SPA (lo hacía un front
  aparte) → la regresión quedó **dormida** y solo fue fatal en prod. Y el healthcheck de Railway apuntaba
  a `/health` (siempre 200, a propósito, para tolerar fallos de migración) → el deploy roto pasó como sano.
- **Decisión / gate.** (1) `GET /health/frontend` → 503 si `FRONT_NEW/index.html` no existe; `railway.json`
  apunta el healthcheck ahí → un deploy que no puede servir el SPA **falla el healthcheck y no se promueve**
  (staging Y prod). **Debe** estar en `middleware.PUBLIC_EXACT`: el healthcheck va **sin auth** → si no fuera
  público daría 401 y **ningún** deploy pasaría (lo cazó un test). (2) Las paths a assets de la **raíz** del
  repo (`FRONT`/`FRONT_NEW`) se anclan a la raíz, no con `__file__` relativo al paquete.
- **Consecuencia / gotcha durable.** Un **split de paquete** (`x.py` → `x/`) **corre un nivel** todo
  `Path(__file__).parent…` → en un move-verbatim hay que revisar las **paths relativas** (a assets, .env,
  templates), no solo el código. Staging ahora sirve el SPA por Railway igual que prod → el gate
  `/health/frontend` cubre **staging y prod** (la vieja asimetría del front de dev por un servicio aparte ya
  no existe). Recordar la otra asimetría: `/health` es liveness-siempre-200 (no readiness). Regresión:
  `test_front_paths.py` (FRONT_NEW hermano de `backend/`) + `test_health_frontend_gate.py` (503/200 del gate).

### 2026-06-20 — Iteración local con datos reales (clon de staging) + verificar sin mocks

- **Contexto.** Iterar el portal cliente —y cualquier flujo con sesión o datos reales— con fixtures no
  alcanza: los bugs de theming/datos no se ven con mocks. El wordmark custom del admin (color hardcodeado
  en un `<style>`) se veía **amber** sobre los topbars de color en staging/prod, pero con el SVG bundleado
  local (currentColor) **nunca** aparecía. Solo cargando el portal logueado con el SVG real saltó.
- **Decisión.** Para iterar flujos autenticados / con datos reales se monta un **entorno local con datos
  reales**: (1) **backend local** (`uvicorn`, `.env` gitignored); (2) **BD de staging clonada a Postgres
  local** vía `pg_dump` **read-only** de la remota → restore local (cuidar versiones: pg 18↔18); (3)
  **staging-login** para impersonar (`POST /auth/staging-login {secret, target:"cliente"|"admin"}`; el
  cliente se resuelve por `STAGING_CLIENTE_EMAIL` o un `cliente_id`). **Nunca** apuntar el backend local a
  la BD remota: `init_db()` corre al startup y le haría `ALTER/CREATE` al esquema (escritura), además de que
  es PII real. Corolario enforceable: el **loop render-compare se valida con datos/assets reales, no solo
  mocks**, antes de pasar el cambio al dueño.
- **Why.** Ver el producto "como es de verdad" (logueado, con los SVG/datos reales) caza una clase de bugs
  que el entorno mockeado oculta. Extiende _Staging-login (2026-06-19)_ —que ya auto-probaba el back-office—
  al **portal cliente** y al **loop local**, manteniendo el gate del dueño (él prueba en staging; la sesión
  verifica antes).
- **Consecuencias.** El staging-login de cliente vive en `auth.py` (`STAGING_CLIENTE_EMAIL`,
  `_resolve_staging_cliente`, `target`), #961. El clon es **solo lectura** sobre la remota (cero escritura a
  staging/prod). Setup en `DEPLOY_RAILWAY.md` / `MANIFIESTO`. Cazó el wordmark no themeable (arreglado:
  `Logo` normaliza los fills —atributo y `<style>`— a `currentColor`).

### 2026-06-20 — TopBar modular por área: shell único, color de marca, logo themeable

- **Contexto.** La web tiene varias áreas (rental/estudio/workshops + portal cliente) y el hub. Cada una
  arrastraba un topbar ad-hoc (alturas, paddings, logos y comportamientos distintos): inconsistente y
  duplicado.
- **Decisión.** Un **shell único** —`TopBarShell` en `components/rental/TopBar.tsx`— del que salen TODAS las
  variantes con el **mismo alto/padding/logo**. Cada área tiene su **color de marca de fondo** y el **logo
  en blanco themeable**: el wordmark normaliza sus fills (atributo `fill=` y `<style> fill:`) a
  `currentColor`, y el isologo mobile es un **isologo mono** (`LogoMark`, silueta `currentColor` + R
  recortada) que funciona sobre cualquier color. La lista de áreas es **fuente única** en
  `src/data/areas.ts` (label/desc/href/color), consumida por el topbar Y el menú. La **navegación entre
  áreas** vive en un **menú hamburguesa** (sheet con la identidad del hub: áreas + acceso/portal + links).
  **Mobile simplifica**: el label del área aparece solo si hay lugar (se oculta cuando hay date pill
  central), las acciones redundantes (CTA de sección, perfil/salir del portal) se mueven al menú, el logo va
  a la izquierda; la landing (`/`) no lleva topbar; el login del portal usa el mismo topbar que el portal.
- **Why.** Una sola estructura → consistencia automática y un único lugar para cambiar alto/padding/color.
  La fuente única de áreas evita duplicar color/ruta/label. Es la materialización en la navegación de la
  _Filosofía de diseño del DS (2026-06-20)_ (una sola forma de hacer cada cosa, reusar no recrear) y de la
  _Barra de calidad de ingeniería (2026-05-25)_ (modularidad a prueba de balas, mobile-first).
- **Consecuencias.** Documentado en `DESIGN_SYSTEM.md` (sistema TopBar). Piezas: `TopBarShell`,
  `SectionLogo`, `AreaMenu`, `LogoMark`, `Logo` (themeable), `src/data/areas.ts`. El supervisor marca un
  topbar nuevo que no salga del shell, una lista de áreas duplicada, o un logo/asset de marca con color
  hardcodeado donde deba ser themeable.

---

## Preferencias (cómo quiero que se hagan las cosas)

### 2026-05-25 — El dueño testea, no revisa código

- **What:** el gate humano del dueño es **probar la conducta**, no leer diffs (no es programador).
- **Why:** la corrección del código la cubren el supervisor + tests automáticos + CI; el dueño
  aporta lo que esos no pueden: ¿hace lo que quería?
- **How to apply:** todo cambio testeable se acompaña de un **plan de prueba en lenguaje claro**
  ("andá a /X, hacé Y, tenés que ver Z"). El supervisor y los PRs hablan sin jerga.

### 2026-05-25 — La conversación es para decisiones, no para el ruido de commits

- **What:** la sesión con el dueño gira en torno a decisiones y a la forma de hacer las cosas, no
  al detalle mecánico de cada diff/commit.
- **Why:** mantener la atención del dueño en lo que aporta valor (criterio), no en mecánica.
- **How to apply:** el trabajo pesado de revisión va al subagente `supervisor` (contexto aislado);
  a la conversación llega el veredicto en claro + el plan de prueba.

### 2026-05-25 — Barra de calidad de ingeniería (cómo construimos)

- **What:** el estándar de calidad del código del proyecto. El supervisor lo hace cumplir en cada PR.
  1. **Modularidad a prueba de balas.** Lógica que se repite (caso testigo: las fechas de reserva
     estaban implementadas distinto en ~5 lugares) se extrae a un módulo/función único y robusto.
     Nada de copiar-pegar variantes "parecidas pero distintas". Modularizar cuando sea coherente.
  2. **Nada de hotfixes.** Implementaciones pensadas y a prueba de errores, no parches. Vale más
     tardar y hacerlo robusto que parchar.
  3. **Mobile-first + performance + sin bugs.** La UX (y especialmente la mobile) es prioridad:
     que cargue rápido y funcione. (Refuerza el mobile gate de §3 del MANIFIESTO.)
  4. **Consistencia visual / design system.** Estilos y componentes centralizados y reusables,
     no estilo ad-hoc por pantalla. (La inconsistencia actual es en parte falta de modularización.)
  5. **Código prolijo aunque el dueño no lo lea.** Legibilidad y orden son requisito, no opcional.
  6. **El core de reservas es sagrado.** Cero overlap de pedidos; la disponibilidad tiene que ser
     correcta siempre. (El core vive en `backend/reservas/` — ver decisión 2026-05-30.)
- **Why:** el dueño está seteando las bases para un sistema robusto y de largo plazo, no un MVP
  descartable. La deuda y la inconsistencia se pagan caro después.
- **How to apply:** el supervisor marca como hallazgo (no bloqueante salvo que sea grave) cuando un
  cambio viola estos principios — ej. duplica lógica en vez de reusar, mete un hotfix, agrega
  estilo ad-hoc, o toca reservas sin cuidar el overlap.

### 2026-05-25 — Protocolo de brain-dumps del dueño

- **What:** el dueño tira ideas en lotes grandes y desordenados (varias cosas mezcladas, a mitad de
  otra tarea, sin terminar el plan de la anterior). Eso está bien — la sesión lo ordena.
- **Why:** que nada se pierda y que el desorden al pedir no se traduzca en desorden en el proyecto.
- **How to apply:** la sesión **triagea cada ítem en el acto** y devuelve un mapa corto de dónde fue
  cada cosa. Cada ítem cae en: **principio durable** → propuesta a esta memoria (con aprobación del
  dueño); **trabajo** (bug/feature/iniciativa) → GitHub Issue (lo que no es para ahora queda
  `priority:low`; la cola _es_ el backlog); **pregunta** → respuesta; **idea cruda / "más adelante"**
  → igual va a issue. **Nada se borra.** Si la sesión nota algo y no lo arregla en el momento, lo
  deja como issue, no lo descarta.

### 2026-05-25 — Minutos de GitHub Actions: cuota a cuidar SOLO si el repo vuelve a privado ⏰

- **Estado:** en **público** (hoy) Actions es **ilimitado** — regla **dormida**. Buena higiene que
  vale siempre igual: batch de commits (cada push = corrida completa), y los cambios solo-docs ya no
  disparan CI (`paths-ignore` de `*.md`/`docs/**`) — afinado mayor pendiente en #487. `concurrency:
cancel-in-progress` ya cancela corridas viejas.
- **⏰ Disparador:** si el repo vuelve a privado, el plan Free da 2.000 min/mes y el CI corre 6 jobs
  por push → ahí sí hay que cuidar la cuota (sacar `compileall`, cachear `npm ci`, terminar #487).

### 2026-05-26 — Sesión local para trabajo visual/testeable _(reemplazada 2026-06-08)_

- _(Reemplazada por la decisión 2026-06-08 — Workflow de cambios. El staging de Railway cubre
  la necesidad de ver cambios en vivo. Ya no hace falta arrancar local para validar UX/flujos;
  se pushea a `dev` y se ve en staging. La sesión local sigue siendo válida para debugging
  muy específico sin acceso a Railway, pero no es el flujo default.)_

### 2026-05-26 — Al actualizar gobernanza, barrer todo el sistema de supervisión

- **What:** cada vez que se edita un doc de gobernanza (`MEMORIA.md`, `CLAUDE.md`, `MANIFIESTO.md`,
  `PROTOCOLO.md`, el agente `supervisor`, demás docs de `docs/`), hacer una **lectura comprensiva
  del sistema de supervisión completo** en la misma pasada, para mantenerlo consistente — cazar
  referencias cruzadas viejas: conteos, punteros a archivos/secciones que ya no existen, o
  decisiones que una nueva contradice.
- **Why:** los docs se cruzan entre sí y se desincronizan en silencio. Casos testigo: `CLAUDE.md`
  decía "MANIFIESTO 671 líneas" cuando tiene 287 (#516); `SISTEMA_SPECS.md` citaba `registry.py`
  que ya no existe. Una edición aislada deja mentiras escritas como ciertas.
- **How to apply:** quien toca un doc de gobernanza revisa el resto en la misma pasada; el
  **supervisor** lo verifica en su revisión. Extiende la decisión _2026-05-26 — Curación de la
  memoria_ (que cura _dentro_ de MEMORIA) a la **consistencia ENTRE docs**.

### 2026-05-26 — Eficiencia de sesión: modelo según tarea + limpiar contexto

- **What:**
  - **Auditar / planificar / decidir / arquitectura** → Opus (effort alto).
  - **Ejecutar** (implementar un prompt bien especificado, bug fixes con tests, trabajo mecánico) →
    **Sonnet** (effort medio). **Excepción — Opus aunque sea ejecución:** cuando el cambio es
    **delicado / de alto radio de explosión** (ej. tocar el **core de reservas**, que es sagrado),
    conviene Opus, porque un bug sutil ahí es caro y el costo extra se justifica. La barra es el
    riesgo del cambio, no la etapa. No usar la variante de ventana **1M** salvo que la tarea necesite
    contexto gigante (la ventana grande deja crecer el contexto → más cache-reads).
  - **`/clear`** entre PRs/tareas independientes; **`/compact`** a mitad de una iniciativa larga
    cuando el contexto ya está pesado.
- **Why:** el consumo del plan lo domina la **re-lectura de contexto en caché**. Caso testigo: una
  sesión local de ~8 PRs gastó **306M tokens, 99% cache-reads** (contexto grande releído en cada
  turno). Opus-en-todo + maratones de muchos PRs en un solo contexto = quema rápido; baja mucho
  usando Sonnet para ejecutar y reseteando el contexto entre tareas, sin perder calidad donde
  importa (Opus para pensar).
- **How to apply:** la sesión sugiere bajar a Sonnet cuando la tarea es de ejecución, y propone
  `/compact`/`/clear` al cambiar de PR/tarea. El contexto durable vive en `CLAUDE.md` + `MEMORIA` +
  issues + PRs, así que limpiar es de bajo riesgo (una sesión nueva retoma sola).

### 2026-06-05 — Apple HIG como guía de UX mobile/táctil (enforceable)

- **What:** la referencia por default para las decisiones de **UX mobile/táctil** que el design system
  no resuelve ya es **Apple Human Interface Guidelines (HIG)** — el estándar de usabilidad táctil que
  seguimos al decidir un tamaño, gesto o espaciado de interacción. Es una **guía general**, no la regla
  de un componente puntual.
- **Materialización concreta (lo que disparó esto):** **tap target mínimo 44×44px** (`h-11 w-11`) en
  todo elemento interactivo — el número de HIG. El valor vive en los specs (`DESIGN_SYSTEM.md`,
  `PROTOCOLO.md`, `MOBILE_AUDIT.md`, `MOBILE.md`), **no acá**; los componentes legacy en 40px migran
  vía **#745**. Otros casos bajo la misma guía: inputs ≥ 16px (no zoom iOS), áreas de gesto cómodas,
  `.safe-*` cerca de notch/home-bar.
- **Why:** la mayoría del tráfico entra desde el celular (label `mobile` = trato prioritario); apoyarse
  en un estándar táctil reconocido y estable evita discutir cada número caso por caso y mantiene
  coherencia. Nombra y refuerza el punto 3 de la _Barra de calidad_ (mobile-first).
- **How to apply / quién hace cumplir:** ante una decisión de UX táctil sin resolver, se sigue HIG y el
  valor concreto se documenta en el design system (acá vive el **criterio**, no la tabla de números). El
  **supervisor lo hace cumplir**: marca como hallazgo un tap target nuevo < 44px, o una decisión táctil
  que contradiga HIG sin justificación.

### 2026-06-20 — Filosofía de diseño del DS: enforceable, la esencia del front

- **Contexto.** El rediseño de Pedidos (jun 2026) no fue una lista de fixes sino la aplicación de un
  criterio repetible. El dueño pidió capturar **la esencia** —el _por qué_— para reproducirla en toda la
  web, no solo los componentes sueltos (avatar, badges).
- **Decisión.** La **Filosofía de diseño** vive como **primera sección** de `DESIGN_SYSTEM.md` (11
  principios) y es **enforceable**: el supervisor mide toda UI nueva o rediseñada contra ella antes que
  contra cualquier detalle. Los principios: (1) la info se tiene que ver (contraste/peso reales, WCAG de
  piso); (2) mostrá el estado y la plata, no los escondas (`Debe $X`, no "sin seña" gris; el estado se
  **deriva** del backend); (3) un foco por pantalla; (4) **una sola forma de hacer cada cosa** (sin tres
  controles para una acción ni botones duplicados); (5) lo más usado, a mano; (6) reconocimiento >
  lectura (avatares, pills, selección obvia); (7) densidad útil sin aire muerto; (8) decí lo que hace
  (copy/labels/empty states, voz "vos"); (9) **reusar no recrear** (la forma del pill vive en `kit/Pill`;
  `EstadoBadge`/`PagoBadge` derivan; cero clases copiadas a mano); (10) mobile/a11y no son extra (HIG,
  ≥44px, foco visible); (11) el core es sagrado, el diseño es presentación.
- **Why.** Sin el _por qué_ escrito, cada pantalla re-discute el mismo criterio y el front deriva. La
  esencia documentada + enforceable es lo que hace que el rollout a toda la web sea consistente y no una
  colección de one-offs.
- **Consecuencias.** Materializado en código: `kit/Pill` (forma + tonos semánticos única), `kit/PagoBadge`
  (estado de pago con monto), `kit/ClienteAvatar` (avatar determinístico). El **contraste de los tints de
  `EstadoBadge`** queda como decisión visual aparte (pendiente, afecta también el portal del cliente).
  Refina —no reemplaza— _Apple HIG (2026-06-05)_ y es la contraparte visual de la _Barra de calidad de
  ingeniería (2026-05-25)_: les da el marco de diseño unificado.

### 2026-06-20 — Fijarse en el repo antes de implementar (sobre todo tras mergear dev)

- **Contexto.** Se iba a implementar un staging-login de cliente que **ya existía en `dev`** (#961). El
  dueño frenó —"fijate en el repo antes de seguir"— y efectivamente estaba hecho: bastó traer `dev`.
- **Decisión.** Antes de implementar algo, **verificar si ya existe** en el repo, con prioridad **después de
  mergear `dev`**: lo que avanzó allá puede ya cubrir el pedido entero o en parte. Aplica a features,
  helpers, endpoints, migraciones y patrones; ante la duda, `git grep` / revisar `dev` antes de codear.
- **Why.** Reimplementar algo existente genera duplicación, deuda y conflictos de merge, y viola la _fuente
  única_. Chequear es barato; deshacer una reimplementación es caro. El dueño no debería tener que frenar la
  sesión para señalarlo.
- **Consecuencias.** Refuerza la _Barra de calidad de ingeniería (2026-05-25)_ (modularidad, no duplicar) y
  la _Memoria en capas (2026-05-25)_ (los Issues/commits/`dev` son la verdad del estado). El supervisor marca
  una reimplementación de algo ya presente en el repo o en `dev`.

### 2026-06-22 — Creación de pedidos concurrente: serializar por equipo con advisory lock (no tocar el gate)

- **Contexto.** Reservas concurrentes del **mismo equipo** daban **500 intermitente**. Root cause (traceback
  real, no de los logs block-buffered): `psycopg2.errors.DeadlockDetected` — el `INSERT` de `alquiler_items`
  toma un FK **KEY-SHARE** sobre la fila de `equipos`, y el gate de stock pide luego `SELECT … FOR UPDATE`
  (exclusivo) sobre la **misma fila** → dos transacciones se bloquean en el _upgrade_ de lock y PG aborta una.
- **Decisión.** `create_pedido` (`backend/routes/alquileres/core.py`) toma
  `pg_advisory_xact_lock(_ADVISORY_NS_PEDIDO, equipo_id)` por cada equipo del pedido, **en orden de id**,
  ANTES de insertar los ítems → serializa las creaciones concurrentes del mismo equipo (cola, no deadlock; se
  libera al commit/rollback). `create_pedido_retry` es la **puerta única** de creación (cliente + admin):
  reintenta ante `DeadlockDetected` como backstop y, agotados los intentos, devuelve **503** (carga puntual),
  **nunca 500**. **NO se toca el `FOR UPDATE` del gate** (`reservas/gate.py`).
- **Why.** El motor de reservas es **sagrado** (cero overbooking). El advisory lock vive **afuera** del gate
  (no cambia su lógica), elimina el deadlock **en origen** (no solo lo sobrevive), y el orden por id evita
  auto-deadlock entre transacciones. El retry queda de red por si aparece un deadlock residual (ej. composites
  que comparten componentes). 503 (no 500) le dice al cliente "reintentá", no "se rompió".
- **Consecuencias.** Refina _backend/reservas = motor único (2026-05-30)_ y _expansión recursiva (2026-05-31)_
  **sin tocarlas**. Regresión: `test_crear_pedidos_concurrentes_sin_deadlock_ni_overbooking` (opt-in
  `RESERVAS_DB_TEST=1`, Postgres real). Verificado en vivo: 15 reservas paralelas → 6×201 + 9×409, **0×500**,
  en la DB 6 pedidos / 6 unidades = sin sobreventa ni huérfanos. PR #969.

### 2026-06-22 — Los hallazgos de una auditoría son hipótesis: confirmar (código + en vivo) antes de arreglar

- **Contexto.** Tras una auditoría profunda (skill `auditoria-profunda`) se fueron a corregir sus hallazgos.
  Al confirmarlos uno por uno, **varios eran falsos o stale**: el bug del mini-bar estaba en `CatalogoMovil`
  (no en el `CartMiniBar` que señalaba el audit); el "catálogo en blanco" era un artefacto del harness
  (`ui-edge.mjs` con un glob `**/api/equipos**` que en dev matcheaba el **módulo fuente**
  `/src/.../equipos.ts` → al interceptarlo con JSON rompía el import y dejaba la página en blanco, cosa que
  NO pasa en prod); los overflows de admin estaban stale (páginas ya redirect / read-only / 0-overflow); los
  contrastes "1.66/1.73" venían del parser de color, no eran reales; y los "datos rotos" (DESTACADA,
  `nombre_publico` duplicado) estaban bien en la DB.
- **Decisión.** Un hallazgo de auditoría —de un agente o de un harness— es una **hipótesis**, no un hecho.
  Antes de **arreglarlo** se re-confirma **en el código + en vivo** (la extensión **Chrome MCP**: clickear de
  verdad, medir computed styles por JS, inspeccionar la red). El contraste sobre `oklch` se **recalcula del
  token** (OKLab→sRGB→WCAG, sobre el color compuesto para tints), no se reporta el número del parser. Quien
  arregla **no hereda el hallazgo como verdad**.
- **Why.** Las herramientas y los agentes exageran, se quedan cortos o miran un estado viejo; arreglar un
  no-bug genera churn, puede romper diseño intencional (ej. las variaciones a propósito del `EstadoBadge`) y
  erosiona la confianza en la auditoría. Confirmar es barato; deshacer un fix equivocado es caro. _Honestidad
  > actividad._
- **Consecuencias.** Extiende la _Regla de oro_ del skill `auditoria-profunda` ("verificar antes de reportar")
  al que **arregla**, y _Fijarse en el repo antes de implementar (2026-06-20)_. Materializado: gotchas del
  glob (dev sirve módulos fuente) y del parser de contraste documentados en el skill; varios "bugs" de la
  pasada cerrados **sin código** por ser falsas alarmas (PR #976 fijó el glob del harness).

### 2026-06-22 — CTA primario = ink + texto hueso (no dorado); el dorado es la jugada del hover

- **Contexto.** Al migrar ~14 CTAs crudos al primitivo `Button` (auditoría fina del DS, #988 N3), apareció
  que el CTA principal vivía en **dos formas**: la mayoría del catálogo/reserva con `bg-ink text-amber`
  (texto **dorado** en reposo), y el `variant="primary"` del DS con `bg-ink text-background` (texto
  **hueso**). Unificar a "una sola forma" exigía elegir el canon. El dueño pidió ver el botón antes de decidir.
- **Decisión.** El dueño comparó ambas en vivo (render real, fuentes y colores de marca, reposo + hover) y
  eligió **hueso**: `variant="primary"` = **fondo ink + texto hueso/bone** en reposo, invierte a
  **`--area-accent` + ink** en hover (`hover:bg-[var(--area-accent)] hover:text-ink`): amber en rental,
  naranja en estudio, rosa en workshops. El texto hueso en reposo es **decisión de marca, NO un bug**:
  no "corregir" a dorado. El accent del hover (la _reverse signature_ ink↔área) es la jugada de identidad.
- **Why.** Dos formas del mismo CTA violan "una sola forma de hacer cada cosa" (_Filosofía de diseño del DS,
  2026-06-20_). Hueso da más contraste sobre ink (19:1 vs 11:1 del dorado — ambos AA holgado) y un look más
  limpio; el accent queda reservado al gesto del hover, más fuerte que un simple aclarado. Usar `--area-accent`
  (no amber fijo) extiende la decisión a todas las áreas sin necesitar un override por área en el botón.
- **Consecuencias.** Los ~14 CTAs migraron a `variant="primary"` (texto dorado → hueso) en PR #990.
  Hover actualizado a `--area-accent` en #1063 (theming por área). El supervisor marca un CTA primario
  cuyo hover invierta a un color fijo en vez de `--area-accent`, o un `<button>` crudo que reimplemente
  el gesto. Documentado en `DESIGN_SYSTEM.md` (sección Button).

### 2026-06-23 — Capa de skills auto-gobernada y portable: registro verificado + routing de modelo + loop de aprendizaje

> Aplica al meta-nivel (la capa de skills) los mismos patrones que el repo ya usa para código y memoria.
> Por etapas: **1A** (registro correcto y enforced — esta entrada describe toda la visión, incl. 1B),
> **1B** (el loop de aprendizaje), **2** (propagación + meta-skill `gobernanza`).

- **Contexto.** El dueño sentía que los issues se desfasan y que **perdió la noción de qué skills existen**, y
  pidió un sistema que **se vaya optimizando y aprendiendo de cómo el repo evoluciona**, recursivo y portable
  a otros repos suyos. Diagnóstico verificado en el repo: (1) el mapa de skills ya driftaba sin que nada lo
  cazara — `auditoria-profunda` estaba en disco y citado en la memoria pero **faltaba en `CLAUDE.md`**;
  (2) la administración de issues vivía enterrada como "Frente D" de `mantenimiento` (skill de ~490 líneas que
  solo corre al "auditar el repo"); (3) los skills decían "expandir con el tiempo" pero ningún ritual lo
  forzaba ni había dónde acumular las mejoras propuestas; (4) el routing de modelo (_2026-05-26_) vivía solo en
  la memoria, no en los skills.
- **Dato técnico (verificado con la guía de Claude Code).** El frontmatter `model:` de un `SKILL.md` **cambia
  el modelo de verdad** al invocar el skill (turn-scoped, revierte solo); el `model:` de un subagente lo cambia
  para su vida. Por eso "el sistema elige el modelo según el task" es **enforceable**, no advisory.
- **Decisión.**
  - **Mapa canónico** = la tabla "Skills — cuál uso para qué" de `CLAUDE.md`: una fila por skill con su
    **disparador** (árbol de decisión, no por tema) + columna **Modelo**. Es el registro único; cura el
    "perdí la noción".
  - **Guardrail mecánico** = `scripts/check-docs.mjs` gana dos bloques: **Bloque 4** (todo `skillsDir/*/SKILL.md`
    tiene que estar listado en `CLAUDE.md`) y **Bloque 5** (linter estructural: frontmatter `name`/`description`/
    `model`/`last-reviewed`/`version` bien formado; `model` válido; `last-reviewed` viejo = **warning**, no error).
    Corre ya en `docs-lint.yml` + hook SessionStart.
  - **Portable** = lo repo-específico (rutas de memoria/front door/skills) se extrae a
    `.claude/governance.config.mjs`; el motor (`check-docs.mjs` + los skills) es genérico. Adoptar en otro repo
    = copiar `.claude/skills/` + `check-docs.mjs` y editar ~10 líneas de config. Si la config falta, el script
    cae a defaults.
  - **Routing de modelo** = materializa _Eficiencia de sesión (2026-05-26)_ en el `model:` de cada skill:
    `mantenimiento`/`auditoria-profunda`/`pulido-frontend` → **opus** (su corazón es criterio/diagnóstico);
    `pendientes`/`importar-diseno`/`gear-compatibility` → **sonnet** (ejecución / loop frecuente). Los de criterio
    **delegan la ejecución mecánica a subagentes `model: sonnet`**.
  - **Blueprint = el Curator de Hermes Agent, nativo.** Se copia el *mecanismo* (reportar sin mutar, archivar
    sin borrar, curación gateada) **sin** adoptar Hermes como segundo agente — sería un segundo store de
    skills+memoria ciego a la gobernanza = más desfasaje, justo la enfermedad que curamos.
  - **Loop de aprendizaje (Etapa 1B).** Buzón durable `docs/PROPUESTAS_SKILLS.md` (append-only, curado por el
    dueño como la memoria) donde la **Auto-mejora** de cada skill deposita propuestas (propone, no aplica);
    **telemetría de uso** vía hook PostToolUse(`Skill`) → `.claude/skill-ledger.jsonl` (gitignored); **check-in
    proactivo** de la cola (SessionStart avisa si `pendientes-state.json` está stale).
  - **Plantilla** `.claude/skill-template.md` (skeleton canónico) — vive **fuera de `skillsDir`** a propósito,
    así Claude Code no la descubre y los Bloques 4/5 no la cuentan.
- **Modo: propone y el dueño aprueba.** El loop de auto-mejora NO reescribe skills/memoria solo — redacta la
  propuesta y el dueño la aprueba (igual que la curación de memoria; el supervisor puede validar). Es el
  `curator --dry-run` de Hermes.
- **Consecuencias.** Etapa 1A implementada en este PR: skill `pendientes`, `mantenimiento` Frente D → puntero,
  `gear-compatibility` normalizado a dir+`SKILL.md`, tabla de skills + columna Modelo, `model:`/metadata en los
  6 skills, `governance.config.mjs` + `check-docs.mjs` config-driven con Bloques 4/5, plantilla. Etapa 1B (buzón
  + auto-mejora + telemetría + check-in) y Etapa 2 (propagar Auto-mejora a todos + meta-skill `gobernanza` que
  **consume** ledger y buzón, audita drift/overlap/staleness/routing de modelo, propone consolidar con
  archiva-no-borra, y suma el dashboard `/skills` + un **cierre de gobernanza periódico** que espeja el cierre
  de mes de la plata) quedan para PRs siguientes. El supervisor marca un skill en disco sin fila en `CLAUDE.md`,
  un frontmatter mal formado, o un `model:` que no pegue con el task.

### 2026-06-23 — pendientes (ex-`cola`) = skill único de administración de la cola (issues/feature-requests); Frente D apunta acá

> **Nota 2026-06-25 — rename.** El skill se renombró de `cola` a **`pendientes`** (nombre poco descriptivo y
> colisión conceptual con "GitHub Issues"). El método y el rol no cambian; solo el nombre, el dir
> (`.claude/skills/pendientes/`), el hook (`check-pendientes.sh`), el state file (`pendientes-state.json`) y el
> slash-command (`/pendientes`). Abajo se conserva la narración original con el nombre nuevo.

- **Contexto.** La administración de issues era el "Frente D" de `mantenimiento` — enterrado en un skill de
  ~490 líneas que solo se invoca al "auditar el repo". Pero la cola necesita atención **continua y liviana**
  (reconciliar seguido es lo que evita que se desfase), no una pasada esporádica. Por eso el dueño sentía que
  "los issues se desfasan y se pierde el hilo".
- **Decisión.** Se extrae a un skill propio, **`pendientes`** (`.claude/skills/pendientes/SKILL.md`), **fuente única** de
  toda la administración de la cola: (1) **reconciliar** —la cola espeja el código (_2026-06-08_): cruzar issues
  abiertos contra commits/PRs shippeados para cazar **hecho-pero-abierto**—; (2) **triage con evidencia**
  (cerrar solo con PR/commit + comentario + `state_reason`; parciales = abiertos); (3) **deduplicar/consolidar**
  trackers (rescatar únicos primero); (4) **etiquetar** (3 dimensiones obligatorias + cross-cutting de
  `ISSUE_LABELS.md`); (5) **intake de brain-dumps** (_2026-05-25_); (6) reporte **"¿cómo está la cola?"** (el
  loop liviano y frecuente). El método del Frente D se movió **verbatim** y se amplió.
- **Why.** Un skill liviano de uso frecuente mata el desfasaje mejor que un método sepultado en un mega-skill.
  Fuente única → el `mantenimiento` Frente D **apunta acá** en vez de duplicar (mismo principio que el workflow
  es fuente única). El modelo del skill es **sonnet** (es ejecución/loop frecuente, no diagnóstico arquitectónico).
- **Consecuencias.** `pendientes` es descubrible por sus disparadores ("ordená los issues", "¿cómo están los pendientes?",
  "cerrá lo hecho", brain-dumps); está en la tabla de skills de `CLAUDE.md`; el Frente D de `mantenimiento` quedó
  como puntero. Refina _Issues: la cola espeja el código (2026-06-08)_ y _Protocolo de brain-dumps (2026-05-25)_.
  La Auto-mejora del skill (Etapa 1B) lo hace recursivo. Regla de oro heredada: **cerrar es afirmar "esto está
  hecho"** → nunca sin evidencia o sin la orden del dueño.

---

### 2026-06-23 — Gobernanza Etapa 2: Auto-mejora universal + meta-skill gobernanza (dashboard, auditoría, dry-run)

- **Contexto.** Etapa 1A + 1B establecieron el registro verificado y el loop de aprendizaje en el skill
  `pendientes`. Etapa 2 propaga el ritual de auto-mejora a todos los skills y crea el meta-skill que cierra el
  ciclo: el sistema puede auditarse a sí mismo.
- **Decisión.**
  1. **Auto-mejora universal** — la sección `## Auto-mejora` se propagó a los 5 skills que existían
     entonces (`mantenimiento`, `auditoria-profunda`, `pulido-frontend`, `importar-diseno`,
     `gear-compatibility`); `importar-diseno` fue archivado en 2026-06-23.
     El Bloque 5 del linter (`check-docs.mjs`) ahora **exige** la sección en todo `SKILL.md` (error, no
     warning) — el CI la caza automáticamente si se crea un skill sin ella.
  2. **Meta-skill `gobernanza`** (`.claude/skills/gobernanza/SKILL.md`, `model: opus`) implementa el loop
     completo de curación: dashboard `/skills` (qué hay, uso real del ledger, staleness, buzón); auditoría
     profunda (drift de `model:`, overlap, staleness de contenido, bloat, cross-refs); consumo del buzón
     (`PROPUESTAS_SKILLS.md`) y el ledger (`.claude/skill-ledger.jsonl`); consolidación dry-run (propone
     archivar a `.claude/skills/.archive/`, no borra); cierre periódico con digest (cadencia por volumen
     del buzón desde _2026-06-29_). Blueprint:
     Curator de Hermes, nativo. Modo propone-aprobás en todos los pasos.
- **Why.** El sistema aprende de su propio uso (ledger → qué se invoca de verdad) y de las mejoras
  detectadas durante el uso (buzón → propuestas acumuladas). Sin el meta-skill, la telemetría y el buzón
  son datos sin consumidor. El ritual periódico convierte "tengo datos" en "el sistema evoluciona con
  criterio, no al azar". La sección Auto-mejora universal cierra el loop recursivo: cualquier skill puede
  proponer su propia mejora, independientemente de quién lo corra.
- **Consecuencias.** 7 skills registrados y bien formados (`check-docs.mjs` verde). El linter exige
  `## Auto-mejora` → un skill mal formado falla el CI desde ahora. La tabla de `CLAUDE.md` incluye
  `gobernanza` con sus disparadores y `model: opus`. El supervisor marca skills sin `## Auto-mejora` o
  un `gobernanza` que aplique cambios sin aprobación explícita del dueño.

### 2026-06-23 — design-system = gobernador del DS; importar-diseno archivado

- **Contexto.** El DS de Rambla tiene estructura sólida (tokens OKLCH modulares, 4 piezas `kit/` con
  fuente única, guardrails ESLint) pero **adopción incompleta** que acumula drift en cada PR: ~19 CTAs
  crudos, ~52 `text-[Nrem]` escapados, ~7 pills manuales, tokens de motion sin adoptar (~0%), N1/N8
  (contrastes WCAG bajo AA). No existía un skill que auditara el DS sistémicamente — `pulido-frontend`
  lo hace pantalla por pantalla y `auditoria-profunda` va por flujo de negocio, no por DS. Por otra
  parte, `importar-diseno` dejó de tener uso real: el diseño ya no viene de handoffs de Adobe/PDF
  externos sino que se refina directamente en Claude Code.
- **Decisión.**
  1. **Archivar `importar-diseno`** → `.claude/skills/.archive/importar-diseno/` (reversible vía git;
     no se borra). El rol de implementar cambios al DS lo toma `pulido-frontend` cuando corresponda.
  2. **Crear el skill `design-system`** (`.claude/skills/design-system/SKILL.md`, `model: opus`) como
     **gobernador del DS**: audita sistémicamente (Fase 1: grep mecánico de colores/sizes/componentes/
     a11y; Fase 2: contraste WCAG + 11 principios + adopción de tokens; Fase 3: drift entre
     `docs/DESIGN_SYSTEM.md` y el código), dashboard `/ds` (estado rápido sin auditoría completa),
     y propone issues con drafts — el dueño aprueba, la sesión los crea. **Read-only: nunca edita
     código.** `pulido-frontend` aplica los fixes en pantalla.
  3. **Actualizar `CLAUDE.md`** y la entrada de MEMORIA 2026-06-06 para reflejar el nuevo cuadro.
- **Why.** El mismo ciclo propone-aprobás que `gobernanza` y `pendientes` — detecta antes de que acumule
  deuda. La separación gobernador/ejecutor evita que el skill de auditoría mezcle diagnosis con
  escritura (honestidad > movimiento). `importar-diseno` era un skill sin uso: archivarlo limpia el
  mapa y el linter.
- **Consecuencias.** 7 skills en disco (idem, `importar-diseno` en `.archive/` ignorado por el
  linter). `CLAUDE.md` reemplaza la fila de `importar-diseno` por `design-system`. El supervisor
  marca un skill en disco sin fila en la tabla. Cadencia sugerida: mensual o tras merge que toque
  `src/design-system/` o `docs/DESIGN_SYSTEM.md`.

### 2026-06-23 — 6 skills nuevos: calidad-codigo, auditoria-seguridad, performance, specs, catalogo, calidad-tests

- **Contexto.** La capa de skills cubría ejecución (pulido-frontend, gear-compatibility) y auditoría
  de negocio (auditoria-profunda, mantenimiento) pero tenía vacíos sistemáticos: calidad del código en
  sí, seguridad, performance, taxonomía de specs y completitud del catálogo. El dueño pidió estos skills
  explícitamente; `calidad-tests` se propuso como fundamental faltante.
- **Decisión.** 6 skills nuevos, todos `model: opus` (criterio/diagnóstico), todos read-only
  (proponen-no-aplican), todos con el patrón propone-aprobás y `## Auto-mejora`:
  1. **`calidad-codigo`** — TypeScript preciso, patterns React, duplicación lógica, naming, complejidad.
     Distinto de `mantenimiento` (que busca código muerto/god-modules) y de `calidad-tests`.
  2. **`auditoria-seguridad`** — OWASP Top 10, auth/cookies, CORS, headers HTTP, SQL injection/IDOR,
     secretos hardcodeados, deps vulnerables (npm audit + pip-audit), rate limiting.
  3. **`performance`** — bundle size, code splitting, re-renders React, N+1 en DB, caching React Query,
     HTTP cache, fuentes/CLS.
  4. **`specs`** — taxonomía de especificaciones técnicas: duplicados con nombres distintos, gaps por
     categoría, specs informales que deberían ser estructuradas, motor de specs.
  5. **`catalogo`** — completitud de datos de equipos: fotos, nombre_publico, descripción, precio > $0,
     specs mínimas por categoría. Propone borradores de descripción para aprobación.
  6. **`calidad-tests`** — cobertura de módulos críticos (reservas, contabilidad, auth, reportes),
     calidad de assertions (comportamiento vs implementación), edge cases sin tests.
- **Why.** La gobernanza sin cobertura de seguridad y performance es incompleta — son los dos ejes que
  generan incidentes en producción. La calidad de código y tests son la deuda técnica silenciosa. Specs
  y catálogo son la calidad del producto (lo que el cliente ve). Todos siguen el mismo blueprint
  propone-aprobás para mantener la consistencia de la capa.
- **Consecuencias.** 13 skills en disco (6 activos previos + 6 nuevos + `pendientes` = 13 total).
  `CLAUDE.md` tiene 13 filas en la tabla de skills. `scripts/check-docs.mjs` los verifica todos.
  El supervisor marca cualquier skill en disco sin fila, o un skill que aplique sin aprobación.
- **Consolidación a 2 medida y RECHAZADA (2026-06-27, Exp 2 del roadmap de gobernanza empírico).** Se probó
  fusionar los 4 de código en `auditoria-codigo` (4 lentes) y `specs`+`catalogo` en `auditoria-datos`, con
  medición before/after (`scripts/evals/`): **routing** 12/12 → 12/12 (no mejoró — ya era perfecto separado);
  **costo por invocación** señal A: el merged carga TODOS los lentes por invocación → **3.1×** (`auditoria-codigo`)
  y **1.9×** (`auditoria-datos`) el costo del skill puntual, contra un ahorro de tabla auto-cargada de solo
  −192 tok/sesión. El caso común es 1 lente → el merge penaliza ~3× lo común para un beneficio marginal +
  diluye el foco (4 checklists cuando se quiere 1). **Veredicto: revert, se mantienen los 6 separados.** No
  re-mergear salvo con un diseño de **carga on-demand por lente** (progressive disclosure), no inline. Es el
  primer caso del principio _2026-06-27 — empirismo proporcional_ matando un cambio que la intuición aprobaba.

### 2026-06-23 — docs/MARCA.md = hub de marca; skill `marca` gobierna el inventario de features

- **Contexto.** El contenido de marca/marketing de Rambla estaba disperso: en slides de Instagram, en la
  cabeza del dueño y parcialmente en `docs/CAMPAÑA_FEATURES.md` (inventario de features, fechado
  2026-06-08, curado para una campaña puntual). No había fuente canónica para "qué es Rambla, qué
  representa y por qué alguien debería usarla". El dueño quería un lugar donde viviera esa info — tanto
  como doc en el repo como posible sección del back-office (segunda etapa).
- **Decisión.**
  1. **`docs/MARCA.md`** — hub de identidad: quiénes somos, tagline canónico, selling points por área
     (rental completo desde las placas de Instagram; estudio y workshops con `[TODO]` para que el dueño
     complete), voz/tono (referencia a `DESIGN_SYSTEM.md`, sin duplicar), assets canónicos (URL, handle
     Instagram, rutas de logo en el repo). El inventario detallado de features queda en
     `docs/CAMPAÑA_FEATURES.md` — `MARCA.md` no lo duplica, lo referencia.
  2. **Skill `marca`** (`model: opus`, read-only) — gobernador de marca: audita que las features reales
     de la app estén en `docs/MARCA.md` y `docs/CAMPAÑA_FEATURES.md`, detecta features nuevas sin
     comunicar y selling points stale, propone borradores de copy para aprobación del dueño. Nunca edita
     los docs sin aprobación explícita.
- **Why.** La marca no es un artefacto estático — la app crece y los selling points pueden quedar
  desactualizados. El skill `marca` cierra ese loop: cada vez que se agrega una feature importante, el
  skill lo detecta y propone actualizar el doc. Separar identidad (`MARCA.md`) de inventario
  (`CAMPAÑA_FEATURES.md`) mantiene ambos docs manejables.
- **Consecuencias.** 14 skills en disco. `CLAUDE.md` tiene 14 filas. El supervisor marca drift entre
  features en código y `docs/MARCA.md` o `docs/CAMPAÑA_FEATURES.md` como hallazgo de marca. Los TODOs
  de Estudio/Workshops en `MARCA.md` son intencionales — el dueño los completa cuando tenga el copy.

---

### 2026-06-25 — Guardrail con prefijo ⏰ LEGACY: coexistencia temporal en migraciones por fases

- **Contexto.** La iniciativa #1029 (Sistema unificado de media) migró las fotos del estudio a R2 en
  fases: F0 construyó el motor, las fases intermedias migraron datos, F7 eliminó los archivos estáticos
  del repo. Entre F0 y F7, el guardrail CI `check-no-content-images.mjs` tenía que permitir los archivos
  viejos temporalmente sin perder la capacidad de bloquear fotos nuevas. Se usó un prefijo de allowlist
  con comentario `⏰ LEGACY: remover cuando F7 mergee a dev`.
- **Decisión.** Cuando una feature y su cleanup viven en fases distintas: el guardrail incluye el estado
  legado con el comentario explícito `⏰ LEGACY: remover cuando <fase> mergee a dev`. La fase de cleanup
  quita el prefijo y borra el estado legado en el mismo commit, con referencia explícita al comentario.
- **Why.** Permite coexistencia temporal sin romper nada. La señal `⏰ LEGACY` es visible (no se pierde
  en comentarios ambiguos) y la recoge el supervisor en cada revisión: si el disparador ya se cumplió,
  lo propone como candidato a retirar. Refuerza la entrada existente de `⏰` en `MEMORIA.md`
  (_Minutos de GitHub Actions, 2026-05-25_) que ya establece el patrón de disparador temporal.
- **Consecuencias.** El supervisor tiene instrucción explícita de buscar prefijos `⏰ LEGACY` con
  disparador cumplido y proponerlos. El commit de cleanup referencia el comentario (`"remover el prefijo
  ⏰ LEGACY de F7"`), lo que hace la historia de git más legible.

### 2026-06-25 — El supervisor atrapa bugs de implementación, no solo drift de scope/forma

- **Contexto.** Durante la iniciativa #1029 (Sistema unificado de media), el supervisor encontró en las
  revisiones de F5, F6, F7, F8 los siguientes bugs reales: (a) `import pytest` sin usar en
  `test_f5_og_estudio_talleres.py` — causa rechazado; (b) `_add_componentes()` en `documentos.py` sin
  las columnas `foto_url_sm`/`foto_url_thumb` — bug de incomplete change; (c) `ESTUDIO_IMG` en
  `estudio.tsx` apuntando a un archivo recién borrado; (d) `test_auth_guards.py` parametrizado con
  paths de fotos que ya no existen en el repo. Ninguno de estos bugs los habría atrapado CI (compilación,
  lint, tests no ejercitaban esos paths en ese contexto).
- **Decisión.** El supervisor es una segunda revisión de código, no solo un gate de scope/drift.
  **No skippearlo aunque el cambio parezca mecánico.** La instrucción "Antes de abrir/mergear una PR:
  despachar el agente supervisor" (CLAUDE.md) se refuerza con esta evidencia: el valor concreto es que
  caza bugs en la intersección de cambio nuevo + código existente que CI no ejercita.
- **Why.** CI verifica: tipos, lint, tests que ya existían. El supervisor verifica: coherencia semántica
  del cambio (¿todos los lugares que debían cambiar cambiaron?, ¿no quedaron referencias rotas?). Son
  capas complementarias, no redundantes. El costo de skippearlo es bajo en energía pero puede hacer
  llegar a staging un bug que no tira error pero sí comportamiento silenciosamente roto.
- **Consecuencias.** No hay cambio procedimental — el supervisor ya era obligatorio. El cambio es de
  framing: es una segunda revisión de código, no burocracia. Los bugs que encuentra son de la categoría
  "incomplete change" (cambié A pero no B que depende de A) e "import muerto" (residuos de iteración).

### 2026-06-25 — Hero (LCP) = AVIF-directo + preload AVIF; el resto usa `picture`; SSR descartado

- **Contexto.** Sesión de optimización de PageSpeed mobile de `rambla.house/rental` (partió en 67, terminó
  en **80 mobile / 91 desktop**). El elemento LCP en mobile es la foto del hero (`HeroBanner` en
  `CatalogoMovilHelpers.tsx`). Se intentó preloadear el AVIF del hero, pero el hero mobile era un `<img>`
  crudo webp sin AVIF → el preload `type=image/avif` no matcheaba el elemento LCP → "Request not
  discoverable" + el AVIF se descargaba dos veces → LCP saltó de 4.4s a 6.6s (score 80 → 60). Diagnóstico de
  raíz: un preload AVIF solo matchea de forma determinista contra un `<img src=avif>` **directo**, no contra
  un `<source type=image/avif>` dentro de `<picture>` (matching frágil en Chromium; la regresión a 6.6s fue
  la evidencia empírica). En paralelo el dueño preguntó por ir AVIF-only / consistencia con el pipeline.
- **Decisión.** (1) El **elemento LCP** (hero, mobile + desktop) se sirve con `<img src=avif>` **directo**
  (sin `<picture>`) + `onError`→webp, centralizado en el helper único `heroImgProps(photo,{eager})` de
  `frontend/src/lib/studio/hero-photos.ts`; el backend `_inject_hero_preload` (`backend/main.py`) preloadea
  el AVIF con `type=image/avif` + `imagesizes=100vw` cuando la principal lo tiene, y cae a webp si es NULL.
  (2) **Toda otra imagen** (catálogo, cards, fichas) sigue con el `<picture><source avif><img webp>`
  canónico — fallback nativo del browser, sin JS, y no se preloadea (no lo necesita). (3) **webp NO se
  elimina** del pipeline: es el fallback del `onError` (hero) y del `<picture>` (resto); el JPEG sigue
  generándose para OG/crawlers de redes. (4) **SSR descartado** como vía a 90+ mobile.
- **Why — la asimetría hero vs. resto.** El hero es la ÚNICA superficie que se preloadea (es el LCP, tiene
  que ser descubrible en el HTML inicial). El preload exige `<img>` directo. El catálogo no se preloadea →
  ahí el `<picture>` es estrictamente mejor (fallback nativo). No es inconsistencia arbitraria: la regla es
  "todos usan el pipeline AVIF; el LCP usa `<img>` directo porque se preloadea, el resto `<picture>`".
- **Why — SSR descartado.** (a) SSR completo (TanStack Start) requiere runtime Node para renderizar React
  server-side; el backend es Python/FastAPI → implicaría reescribir el serving o mantener dos servidores en
  paralelo. No se paga por un número de laboratorio. (b) SSG/prerender estático: el catálogo es dinámico
  (equipos cambian), rutas paramétricas costosas → ROI bajo. (c) SSR parcial del hero (inyectar el markup en
  el HTML servido): la app monta con `createRoot()` (no `hydrateRoot`), que **borra `#root` al montar** →
  coordinar un overlay sin flash/CLS es intrincado y en la cara más visible del sitio, y **duplica el markup
  del hero** (Python + React → drift, contra "fuente única"). Decisión del dueño: NO meter el hack; el LCP
  mobile de una SPA con CPU 4× + Slow 4G emulado tiene techo ~80, y los usuarios reales (mejor red/CPU) ya
  ven el sitio rápido. **80 mobile / 91 desktop es un techo sano para una SPA.**
- **Gotcha.** El preload (backend, `_inject_hero_preload` + las queries en `root()`/`rental_page()`) y el
  `<img>` (front, `useHeroPhotos`) deben elegir la MISMA foto principal, o vuelve la doble descarga. Ambos
  ordenan **`es_principal DESC, orden ASC, id ASC`** (el `id` como desempate se agregó explícitamente en el
  front para espejar el backend). Si se cambia el orden de fotos en el endpoint de estudio, revisar que sigan
  coincidiendo.
- **Consecuencias.** El supervisor marca: un `<picture>` en el elemento LCP (rompe el match del preload), o
  un `<img src=avif>` sin `onError`→webp fuera del LCP (pierde el fallback de compatibilidad). Esta decisión
  cierra la evaluación de SSR para no re-litigarla cada sesión. Sigue pendiente como ROI real (operacional,
  no código) migrar las ~9 fotos externas (Tier C, incl. una de 437 KB) al motor de media vía
  `backfill_ingest_legacy.py --solo-tier=c` — baja peso real, no un número de lab. Refina _Filosofía de
  diseño del DS (2026-06-20)_ y la _Barra de calidad de ingeniería (2026-05-25)_ (fuente única / reusar no
  recrear).

### 2026-06-25 — Manuales técnicos por sistema (`SISTEMA_X.md`): fuente única del "cómo", linkea a MEMORIA el "porqué"

- **Contexto.** El dueño preguntó dónde está la "fuente de la verdad" de cómo funciona cada sistema (fotos,
  reservas, specs), para poder responder "cómo funciona X" con autoridad. Relevamiento: specs tiene su manual
  (`SISTEMA_SPECS.md`), pedidos tiene `FLUJO_PEDIDOS.md`, diseño `DESIGN_SYSTEM.md`, reservas/plata están bien
  cubiertos en MEMORIA + MANIFIESTO §6. Pero **fotos estaba disperso** en varias decisiones de MEMORIA, sin un
  manual único — justo el sistema más tocado en la sesión (procesar + mostrar) y el más difícil de explicar.
- **Decisión.** Convención de gobernanza: cada motor/sistema importante tiene un manual técnico
  **`docs/SISTEMA_<X>.md`** (molde: `SISTEMA_SPECS.md`), **fuente única del cómo funciona** (arquitectura +
  flujo + paths de entrada). El manual **describe, no decide**: las reglas de criterio y el porqué viven en
  `MEMORIA.md`/`DECISIONES.md` y se **linkean**, no se copian. Índice maestro en **MANIFIESTO §8**. Piloto:
  `SISTEMA_FOTOS.md`.
- **Why — separar "cómo" de "porqué".** Si el manual copiara las reglas, habría dos verdades que se desfasan
  (el manual envejece, MEMORIA cambia). Linkear mantiene una sola fuente de cada cosa: MEMORIA = decisión
  enforceable (la hace cumplir el supervisor); el manual = el mapa técnico vivo. Extiende _Memoria en capas
  (2026-05-25)_ con una capa más: el manual de sistema (el "cómo", on-demand), debajo de MANIFIESTO (arquitectura)
  y MEMORIA (criterio).
- **Why — NO un skill.** Un manual es un **documento** (fuente de verdad estática), no un **proceso** (lo que un
  skill codifica). La capa de skills tiene su propia gobernanza anti-bloat (_Gobernanza Etapa 2 (2026-06-23)_);
  meter un skill por cada manual la inflaría sin razón. El mantenimiento cae en el supervisor (marca un manual
  stale cuando revisa un cambio a ese motor) + `check-docs.mjs` (verifica que los manuales referenciados existan,
  links vivos).
- **Consecuencias.** El manual se actualiza en el **mismo cambio** que toca su motor (como el código y los tests).
  El supervisor marca: un manual desactualizado, o una regla de criterio copiada en el manual que debería ser un
  link a MEMORIA. Próximos candidatos a manual propio: reservas (el core sagrado, hoy en MEMORIA + MANIFIESTO §6)

### 2026-06-26 — skill `consejo`: juicio crítico de propuestas como fuente única, rigor escalable, memoria separada

- **Contexto.** El proceso de trabajo no tenía un gate deliberativo aguas arriba: las propuestas se evaluaban
  ad-hoc en la sesión, con el sesgo de complacencia no estructurado. El supervisor juzga lo ya hecho; faltaba
  el equivalente para lo que se va a hacer. En conversación, preguntar "¿qué te parece?" activa la cooperación,
  no la crítica — el análisis queda distorsionado hacia el acuerdo.
- **Decisión.** El juicio crítico de propuestas/ideas/planes antes de construir vive en el skill **`consejo`**
  (`.claude/skills/consejo/SKILL.md`) — fuente única, no ad-hoc en la sesión. El valor no es "más cabezas" (mismo
  modelo, mismos sesgos) sino el **mandato adversarial** y el **rigor escalable**: default pase crítico eficiente
  (~10-15k, sin subagentes); escala a voces aisladas paralelas (Contrario + Investigador, ~120k) o consejo completo
  de 5 lentes (~300k) solo si la decisión lo justifica. El consejo **no escribe** en `MEMORIA.md`/`DECISIONES.md`
  — tiene su propia `BITACORA.md` con autoridad separada (lo que juzgó el consejo ≠ lo que decidió el dueño).
- **Why.** Un mandato de matar la idea sobre una proposición encuadrada en neutral suelta la crítica que el modo-charla
  reprime. La separación de memorias es necesaria por la independencia crítica: si el consejo obedeciera `MEMORIA.md`
  como autoridad, pierde su razón de existir (validaría lo ya decidido en vez de juzgarlo). La escalabilidad de
  rigor materializa _Eficiencia de sesión (2026-05-26)_: los recursos son finitos, el rigor se asigna donde rinde.
- **Consecuencias.** El supervisor marca: (a) propuesta mediana/grande juzgada sin invocar el skill; (b) veredicto
  del consejo promovido a `MEMORIA.md` sin autorización explícita del dueño. El consejo calibra su propio acierto
  via `BITACORA.md` (registra qué juzgó vs. qué decidió el dueño — campo "¿coincidieron?"). Condición de retiro
  (anti-bloat): si el ledger de `gobernanza` lo muestra con uso <1/mes y veredictos tibios, se retira.
  y contabilidad/plata. No todo sistema necesita uno: si MEMORIA + MANIFIESTO ya lo cubren claro, no se fuerza.

### 2026-06-26 — Theming por área: `--area-accent` cascade + `--color-estudio` token propio

- **Contexto.** La página del Estudio (`/estudio`) tiene identidad visual propia (naranja cálido `#E9552F`)
  pero todos sus componentes usaban `bg-amber`/`text-amber` hardcodeados. Dos problemas: (1) `--color-naranja`
  existía como status Warning con la misma hex — reutilizarlo en marketing crea confusión semántica; (2) sin
  mecanismo de cascade, cada componente del estudio necesitaría conocer su contexto de área.
- **Decisión.** CSS cascade `[data-area]` con tokens semánticos de área:
  1. `PublicLayout.tsx` inyecta `data-area="<area>"` en el div raíz según el `variant` del topbar.
  2. `tokens/colors.css` define `--area-accent` / `--area-accent-soft` / `--area-accent-hot` en `:root`
     (default → `--color-amber`) y los sobreescribe en `[data-area="estudio"]` (→ `--color-estudio`).
  3. Los componentes consumen `var(--area-accent)` via Tailwind arbitrary values (`bg-[var(--area-accent)]`)
     sin saber en qué área están.
  4. `EstudioBand` (componente de la landing rental) usa `data-area="estudio"` en su `<section>` para
     activar el cascade local (nested override), sin que el layout padre lo necesite saber.
- **`--color-estudio` vs `--color-naranja`:** mismo hex `#E9552F`, tokens separados. `--naranja` = status
  Warning (paleta semántica de pedidos); `--color-estudio` = accent de marketing del área. No mezclar —
  son paralelos como `--color-amber` (marca) vs `--amber` (token de Tailwind en `@theme`).
- **Límites del theming (fijos, no se tematizan por área):** focus rings (`border-amber/60`), estados de
  UI cross-app, badges del kit (`EstadoBadge`/`PagoBadge`), back-office, paleta de status.
- **WCAG sobre `#E9552F`:** `text-ink` puro (4.88:1) es el único opaco viable para texto normal sobre
  el fondo naranja — ink/90 = 3.80:1 (falla AA), ink/65 = 3.00:1 (falla). Naranja sobre ink: ≥ 80%
  de opacidad para pasar AA normal (80% → 4.60:1, 70% → 4.15:1 falla). La sección "Reservar" de
  `estudio.lazy.tsx` bumpeó todos los `text-ink/55,/65,/50` a `text-ink` opaco por este motivo.
- **Guard:** `frontend/e2e/area-accent-cascade.spec.ts` verifica `data-area` correcto por ruta y que
  `--area-accent` resuelva distinto en estudio vs rental. Iniciativa #1063; Fase 2 (rental + workshops)
  en el mismo PR.
- **Why.** El cascade CSS es la solución elegante: zero runtime JS, composición natural del cascade,
  ningún componente necesita prop de área. El token semántico `--area-accent` es más robusto que
  `--color-estudio` directo porque desacopla la elección de color de la semántica de uso — agregar
  workshops u otras áreas es un bloque CSS adicional, no un barrido de componentes.

### 2026-06-27 — Medir lo barato-e-incierto; juicio + reversibilidad para el resto (empirismo proporcional)

- **Contexto.** Tras la auditoría externa del sistema de gobernanza (comparado contra Hermes Agent,
  MemGPT/Letta, Voyager, ADR/Zettelkasten), el dueño aprobó el roadmap de mejoras con una condición que
  cambia su forma: _"todo lo que rinde, pero **empíricamente** — medilo, compará antes/después, y lo que no
  demuestra que mejora se revierte. Incluso esta filosofía puede quedar grabada."_ Riesgo real en un repo con
  ethos anti-bloat: el **aparato de medición puede volverse él mismo el bloat**.
- **Decisión — la regla de proporcionalidad.** El 2×2 de (barato vs caro de medir) × (resultado cierto vs
  incierto): **se mide SOLO el cuadrante barato-Y-incierto**. Caro-de-medir u obvio-y-reversible → **juicio +
  git revert**, no eval. La medición nunca cuesta más que lo medido.
- **Qué SÍ se mide (cheap + uncertain):** (a) ¿el digest se sigue haciendo cumplir tras un trim? → dispatch
  del `supervisor` contra `scripts/evals/fixtures/*.diff` que violan la decisión trimeada, catch-rate
  antes/después; (b) ¿el routing sobrevive a un merge de skills? → LLM-as-judge sobre las descripciones
  (`routing-cases.jsonl`); (c) el tamaño del prefijo auto-cargado → `context-size.mjs` (lado valor del trim,
  lado costo del merge).
- **Qué NO se mide (judgment + reversibility):** "¿es bueno este manual/doc?", un 1-liner del digest — son
  reversibles (un archivo, git, auto-cargado fresco cada sesión); el gate es leerlo + el link-check de
  `check-docs`. Un judge automático de "paridad de hallazgos" sería más ruidoso que lo que chequea → se hace
  con un fixture smoke + ojo del dueño, una vez.
- **Foundation.** `scripts/evals/` (único hogar net-new; ~80 líneas de código real, el resto data/runbook).
  Reusa lo existente: pytest `-m golden` (tests decisivos ya escritos, sólo marcados), `ui-audit.mjs`
  (`LABEL=before/after`), y el dispatch de subagentes (precedente: `consejo` despacha voces aisladas). Las
  señales B/C/D corren **solo cuando su target cambia** (digest → B; capa de skills → C/D), **no en cada
  push**: B necesita dispatch de agente y C una llamada a modelo (caro + no determinista en CI; un gate flaky
  de gobernanza va contra el ethos). Los `-m golden` sí gatean en CI (jobs `python-tests`/`db-migrations`).
- **Cláusula de retiro (auto-referencial).** Cada eval lleva fecha: si gatea 0 regresiones reales en N meses
  → se retira vía `gobernanza` (igual que el self-revert de `consejo`). El golden set es **curado, no
  append-only** (misma disciplina que la memoria). Esta misma filosofía queda grabada como principio —
  satisfaciendo el _"incluso esto puede quedar"_.
- **Why.** La reversibilidad es una red más barata que la medición para la mayoría de los cambios de
  gobernanza (un archivo bajo git). El empirismo se reserva para donde genuinamente no se puede predecir el
  efecto (fuerza de enforcement tras un trim; routing tras un merge). Materializa y **acota** _Los hallazgos
  de una auditoría son hipótesis (2026-06-22)_: ahora la confirmación tiene método y techo de costo.

### 2026-06-27 — Filosofía de trabajo derivada del corpus, mantenida como hipótesis (defaults, no leyes)

- **Contexto.** El dueño quería que la sesión entendiera "cómo quiere desarrollar y mantener el repo" sin un
  ensayo de personalidad ni una lista declarada de mandamientos: que se **derivara por análisis** del cuerpo de
  decisiones y preferencias ya tomadas, que **no quedara congelada**, y —clave— que se **aplicara sola**, sin
  que él tenga que pedirlo ni estar atento ("como verificar que los skills tengan algo para aprender").
- **Qué se decidió.** (1) Los principios se **derivan del corpus** (clusters de evidencia en las propias
  decisiones), no se declaran. (2) Viven **auto-cargados en `CLAUDE.md`** (sección "Filosofía de trabajo") →
  están en contexto en toda sesión y superficie, y son la base desde la que la sesión propone. (3) Se mantienen
  como **hipótesis**: se ponen a prueba, mutan o aparece uno nuevo contra cada decisión. (4) **Son defaults, no
  leyes** — el dueño puede ir en contra; la sesión **nota la desviación, nombra el principio y explica el
  porqué** (porque el dueño también se puede confundir), y si confirma, **procede**. Una **excepción puntual no
  deroga** el principio; solo un **patrón repetido** o un **cambio de criterio explícito** lo muta, y la
  mutación se **propone** a la memoria (aprobación del dueño). (5) **Aplicar esto es default de la sesión** —
  no requiere pedido ni vigilancia: mismo loop que el `## Auto-mejora` de los skills (el sistema detecta y
  propone; el dueño aprueba).
- **Cómo se mantiene (mecanismo).** Auto-load nativo (CLAUDE.md se lee en cada sesión, todas las superficies) =
  los principios siempre en contexto. El **supervisor** (ya despachado antes de cada PR) suma a su checklist:
  ¿el lote confirma/tensiona/suma un principio? → distingue **excepción puntual** (no propone) de **drift
  recurrente / cambio de criterio** (propone mutar). `gobernanza` los **re-deriva del corpus** cada 2 cierres
  de gobernanza (anti-congelamiento). El hook `check-governance-review.sh` los **surfacea** como backstop cuando la
  rama toca el digest (local: terminal/desktop; no en celu/web).
- **Por qué así (reusar, no recrear).** Es el mecanismo que el dueño ya confía para los skills (`## Auto-mejora`:
  detectar-proponer sin pedido), aplicado a los principios — no se inventa uno nuevo (principio #1). Límite
  honesto: el auto-load corre en todas las superficies; el hook solo local. Aplicarlos **no es más débil** que
  el resto del modus operandi: es el **mismo** mecanismo de regla auto-cargada que ya gobierna todo lo que la
  sesión hace sin que se lo pidan. _(Primera aplicación en vivo, antes de estar grabada: el dueño pidió mandar
  esto directo a prod; la sesión lo marcó como desviación del gate `dev→main`, el dueño confirmó con razón
  válida —son docs sin comportamiento que probar en staging— y se procedió. La excepción no derogó el gate.)_
- **Los 5 (derivados; evidencia entre paréntesis).**
  1. **Una sola forma de cada cosa** (motores únicos: reservas/reportes/contabilidad/búsqueda/branding;
     `equipment/shared/`; _Fijarse en el repo antes de implementar (2026-06-20)_).
  2. **El core que anda no se toca; lo nuevo se acopla** (El Estudio reusa el motor sin tocarlo; advisory lock
     sin tocar el `FOR UPDATE`; reservas = Opus por radio de explosión).
  3. **Lo vivo se mantiene chico y curado — se poda lo que no rinde, no lo que cuesta** (curación no
     append-only; cláusula de retiro de evals; anti-bloat con **techo de valor**, no de costo — corrección
     explícita del dueño: lo valioso se hace aunque sea difícil).
  4. **Lo que paga se mide barato; lo reversible se decide con juicio + git** (empirismo proporcional 2026-06-27;
     _Los hallazgos son hipótesis (2026-06-22)_).
  5. **El sistema propone, el dueño decide — y dice la verdad** (propone-no-escribe en supervisor/gobernanza/
     buzón; "no fabriques churn"; el dueño es el gate).

### 2026-06-27 — PR como hoja de ruta: rama aislada → PR scoped del tema → issue de tracking → batch a prod

- **Contexto.** En una misma sesión se abrieron 3 PR para lo que era un solo tema; el dueño ("ya vamos por el PR
  mil") pidió **menos PR, no redundantes**, y a la vez quería **encapsular** los cambios grandes "por si las
  dudas" y poder **ver qué se hizo** sin leer código.
- **Qué se decidió.** Para trabajo grande/encapsulado (lo chico sigue por push-directo-a-`dev`, _Workflow de
  cambios 2026-06-08_): (1) **una rama aislada por tema**; (2) **un PR scoped del tema** (no uno por commit ni
  varios por fase) que funciona como **hoja de ruta + historial** legible; (3) los PR del tema se **dejan sin
  mergear** — el dueño es el gate que mergea; (4) la **issue de tracking** es la **historia** que apunta a los PR
  (un issue por iniciativa, no por fase — espeja _Modus operandi (2026-05-25)_); (5) a prod, **batch `dev →
  main`**: un PR de promoción que reconcilia el lote (espeja _Issues (2026-06-08)_).
- **Tensión resuelta (git).** Un mismo PR no puede apuntar a `dev` y a `main` a la vez; por eso el modelo es
  **PR-del-tema → `dev`** + **PR-batch `dev→main`**, atados por la **issue de tracking** como hoja de ruta, en
  vez de un único PR imposible. Menos PR sueltos, trazabilidad por issue. **Excepción reconocida:** un cambio
  **solo-docs/gobernanza** (sin comportamiento que probar en staging) puede ir en **un PR aislado directo a
  `main`** — el "probalo en `dev` primero" aplica a código, no a docs (decisión del dueño, 2026-06-27).
- **Why.** Espeja lo que ya estaba (_Workflow 2026-06-08_, _Issues espeja el código 2026-06-08_, _Modus operandi
  2026-05-25_): un issue de tracking por iniciativa; el commit/PR como registro. No introduce mecanismo nuevo;
  ordena el existente para que no proliferen PR/issues.

### 2026-06-27 — DAL = wrapper fino `database/core.py` (NO ORM); guardas SQL mecánicas; sync + psycopg3

- **Contexto.** El dueño encontró el comentario "nervioso" del wrapper (`database/core.py`) que documentaba
  la traducción `?`→`%s` con una advertencia + un puntero stale a `routes/equipos.py:1817` (archivo partido
  en paquete, #946) → dudó si la DB estaba "parcheada". El wrapper nació como shim de migración SQLite→
  PostgreSQL: traduce placeholders `?` (sqlite3) a `%s` (psycopg) y emula `lastrowid` con `SELECT lastval()`.
  La raíz de la inquietud (bien olida por el dueño): parte del wrapper EMULA formas peores cuando hay nativas
  mejores (`?`, `lastrowid` vía `lastval()` — inferior a `RETURNING`, session-scoped) → residuo legacy de la
  migración, no diseño superior. Su seguridad además dependía de una convención NO enforced, vigilada por prosa.
- **Decisión.** Distinguir DOS cosas en el wrapper: (i) **muletas de compat (disfraz sqlite3)** → se sacan;
  (ii) **infraestructura real** (pool, rollback-al-devolver, chokepoint de guardas) → se queda (no emula nada;
  toda app la tiene en alguna forma). Concretamente: (a) **Endurecer** con guardas `_assert_pct_safe` (único
  `%` válido = `%s`/`%(name)s`/`%%`) + `_assert_params_present` (agnóstica `?`/`%s`), en execute + executemany.
  (b) **Migrar** lo legacy a nativo por fases bajo la red: `?`→`%s` (go-forward), `lastrowid` (7 usos)→
  `RETURNING`, pool propio→`psycopg_pool`; core sagrado último. (c) **Driver psycopg3 sync** (3 archivos, el
  wrapper lo aísla) — override informado del "diferir" del consejo (el dueño lo quiere al día, costo bajo).
  (d) **El wrapper SE QUEDA** como DAL único — NO ORM, NO "psycopg crudo por todos lados". (e) **NO async.**
- **Why.** Se evaluaron a fondo (evidencia web + consejo, lentes Contrario/Principista/Investigador/Cliente)
  CUATRO alternativas más pesadas, y todas convergen al wrapper fino: **paramstyle nativo** = cosmético
  (idiomático, no más seguro); **psycopg3** = beneficios no aterrizan (async no se hace; el 3-4x server-side
  lo neutraliza PgBouncer) — pero barato, se hace por estar al día; **SQLAlchemy Core** = NO (SQL crudo por
  elección, el core complejo no entra en el ORM, pool/dialect/migraciones ya están vía wrapper + Alembic; con
  `text()` cargás su peso sin su valor — lo dice su creador); **SQLModel** = NO (ORM+Pydantic sobre SA → hereda
  el "no"; su valor de unificar API/DB no aplica: no hay modelos de DB); **async** = NO (app DB-bound, conc.
  moderada, DB same-datacenter, pool tuneado → sync bien pooleado es el fit; async = reescritura viral con
  riesgo en el core sagrado por un techo que no se toca). Patrón: cuanto más pesado/famoso el tool, PEOR
  encaja — raw SQL + wrapper fino es legítimo y a escala (Stripe/PostHog/Zapier). Clave: el plan saca CADA
  pieza que emula una forma nativa mejor; lo que queda no disfraza nada.
- **Consecuencias.** Guardas **seguras por construcción** (el wrapper siempre pasa una tupla → psycopg ya
  pyformatea → un `%` desnudo ya fallaba; la guarda solo lo hace antes y claro; verificado 0 `%` literales en
  SQL activo). Migración por fases con `⏰ LEGACY` en la traducción + el split; al no quedar ningún `?` se
  borra el `replace` (Fase 6). Workflow especial (pedido del dueño, por tocar el spine): **rama aislada** →
  testear/supervisor/simular → recién seguro a `dev` → PR a prod mucho después. El supervisor marca: `?` nuevo
  en código nuevo, `%` literal en SQL, reimplementación/bypass del DAL, o un CTA de adoptar ORM/async sin que
  cambien las condiciones de revisita (equipo >10 / multi-DB / tiempo-real). Implementación en el plan.
- **Estado (2026-06-27):** Fases 0-6 (`?`→`%s` + shim retirado) + `lastrowid`→`RETURNING` (7 usos) completadas en PR #1075.

### 2026-06-28 — La ganancia de Rambla descuenta la comisión de los dueños (es costo, no ganancia)

- **Contexto.** El Reporte mensual (P&L, `backend/contabilidad/pyl.py`) calculaba `ganancia_neta = ingresos −
  gastos` con `ingresos = resumen["total"]` de la liquidación = el **total facturado bruto**. El reparto de
  comisiones se calculaba en paralelo (`por_beneficiario`) pero **no se restaba** de la ganancia.
- **Problema.** La comisión que se llevan los dueños de los equipos (Pablo/Tincho/terceros) se contaba como
  ganancia de Rambla. Ejemplo (modelo default): equipo de Pablo factura $100k → Pablo 50% / Rambla 45% / Tincho
  5%. La ganancia tomaba los $100k enteros, inflándola en $55k (la plata que Rambla les debe a los dueños).
- **Decisión (dueño, 2026-06-28).** La **ganancia de Rambla = parte de Rambla − gastos**. La comisión de los
  dueños es un **costo**, no ganancia. El P&L muestra la cascada completa: **facturado − comisiones a dueños −
  gastos = ganancia**. `comisiones_duenos = facturado − parte_rambla` (= todo lo facturado que no es de Rambla;
  robusto a cualquier beneficiario, incl. terceros). La parte de Rambla ya la calcula el reparto
  (`reportes/comisiones`); `pyl.py` solo la usa en lugar del total. Reemplaza el criterio viejo del docstring de
  `pyl.py` (ingreso = total devengado "para que coincida con la liquidación").
- **Consecuencias.** Cambian `pyl.py::ganancia_neta` (nuevo desglose `facturado`/`comisiones_duenos`) y
  `reporte_mensual.py` (expone `comisiones_duenos`); el front muestra los 4 KPIs de la cascada. Funciona igual
  para meses cerrados (la foto guarda `por_beneficiario`). Solo afecta cuando hay equipos de dueños ≠ Rambla
  (equipo propio = 100% de Rambla, sin diferencia). NO toca el reparto de la liquidación ni la rendición (ya
  estaban bien). Regresión: `test_reporte_ganancia_descuenta_comision_de_duenos` (Pablo $100k → ganancia $45k,
  no $100k). Los tests existentes (delta de gasto/cargo) siguen pasando.

### 2026-06-29 — Retro de iniciativa: el cierre de algo importante dispara un retro que reparte aprendizajes

- **Contexto.** Tras una sesión de implementación el dueño quiere saber **qué sirvió y qué no**, y que el
  aprendizaje no se evapore. Auditoría con evidencia: el ledger (`.claude/skill-ledger.jsonl`) registra
  **frecuencia, no eficacia**; el buzón (`docs/PROPUESTAS_SKILLS.md`) no recibió propuestas de la sesión; el loop
  `## Auto-mejora` es **por-skill** → no cubre el ~90% del trabajo que es **código de producto** (no toca ningún
  skill). No existía un "retro de iniciativa".
- **Pedido del dueño (verbatim).** "algo que detecte que fue una implementación, o un bug arreglado o algo
  importante, un hook que manda a claude a analizar lo que sirvió y lo que no, algo que aprender, y reparta donde
  tenga que repartir, si al skill, o al sistema de gobernanza" + "no con cosas triviales".
- **Frontera honesta (lo dejo explícito, no lo disimulo).** Un hook **no puede despachar un agente** ni
  preguntar-y-esperar una respuesta — solo **surfacea un recordatorio**. Por eso el "manda a claude a analizar" es
  **semi-automático** con **dos OK del dueño**: (1) el hook detecta y recuerda al cierre del turno → la sesión
  pregunta "¿corro el retro?" (sí/no) → con el OK analiza; (2) la sesión trae el reparto **ítem por ítem** y el
  dueño aprueba cada destino. Nada a memoria/SISTEMA/principios sin OK; lo único que escribe sola es el buzón (que
  ya es el inbox de proponer) y los issues.
- **Decisión.** Tres piezas, **reusando lo que ya existe** (anti-bloat _2026-06-23_; no un skill nuevo): (a) **Hook
  `.claude/hooks/check-retro.sh`** = **gemelo** de `check-governance-review.sh` (misma mecánica: merge-base vs
  `origin/dev`, `git diff` de rama+working+staged `| sort -u`, dedupe por firma `cksum` en `.claude/.retro-state`
  gitignored, `exit 0` siempre), con dos diferencias: filtro **disjunto** = código de producto
  `^(backend/|frontend/src/)` (excluye naturalmente skills/digest → cero overlap con el de gobernanza) y umbral
  "no trivial" (≥4 archivos **o** ≥150 líneas vs `origin/dev`, en constantes arriba del script). (b) **Método** en
  el skill `gobernanza` (§7 "Retro de iniciativa", hermana del cierre de gobernanza §6, pero per-iniciativa y extendida
  a aprendizajes de **producto**, no solo de skills). (c) **Reparto**: método de skill → buzón (**autónomo**);
  criterio/arquitectura → `MEMORIA`+`DECISIONES` (OK); gotcha cómo-funciona-X → `SISTEMA_*` (OK); principio →
  `CLAUDE.md` Filosofía (OK); trabajo diferido → issue vía `pendientes` (autónomo); nada → decirlo (no fabricar
  churn).
- **Consecuencias.** Roles claros: **hook = disparador · `gobernanza` = método · dueño = gate**. El recordatorio
  es **conveniencia, no gate**: corre donde corren los hooks de Claude Code (terminal/desktop, no en el chat de
  Mac/iPhone ni en la web/nube); donde no corra, el retro es invocable a demanda (`/gobernanza` → §7). Aplica la
  **cláusula de retiro** del harness de evals (si gatea 0 retros útiles en N meses → se retira). Archivos:
  `.claude/hooks/check-retro.sh` (nuevo), `.claude/settings.json` (2ª entrada `Stop`, no toca la existente),
  `.claude/.gitignore` (+`.retro-state`), `.claude/skills/gobernanza/SKILL.md` (§7 + cheatsheet + anti-objetivo +
  nota de scope), `CLAUDE.md` (fila de `gobernanza` con el disparador del retro), `scripts/evals/README.md` (2º
  auto-disparador en "Auto-disparo (Nivel 1)"). **Dogfooded** sobre la iniciativa de contenido (entrada gemela
  2026-06-29): produjo la corroboración gh-CLI al buzón (autónomo) + la entrada de memoria de la puerta.

### 2026-06-29 — `backend/services/contenido/` = puerta única de "qué incluye un producto" (display derivado de la receta real)

- **Contexto.** Varias features client-facing necesitan mostrar "qué incluye" un kit/combo: la vista de contenido
  en el carrito, el packing list/checklist, buscar kits por contenido, repetir un pedido, listas personales del
  cliente y compartir una composición (gaffer → productor). Todas leen la **misma receta** que el motor de reservas
  usa para expandir y chequear stock (la tabla `kit_componentes`).
- **Problema.** Sin una puerta única, cada feature reimplementaría el "qué incluye" con su propia query → el
  display podría **desincronizarse** de lo que realmente se reserva. Además se arrastraba un **drift de
  soft-delete**: `attach_kit` filtraba `eliminado_at IS NULL` pero `get_kit` no.
- **Decisión.** **`backend/services/contenido/`** es la **puerta única del display** de "qué incluye", **derivada
  de la receta real** (el mismo `kit_componentes` del motor). Nuevo miembro de la familia **motor-único** (espeja
  `reservas`/`reportes`/`busqueda`/`contabilidad`/`branding`). Invariantes: (a) devuelve los componentes
  **directos (1 nivel)** —es display, no la demanda de stock; la **expansión recursiva** sigue siendo del gate vía
  `reservas.semantics`—; (b) **no toca el motor de reservas** (solo SELECTs de lectura, sin `FOR UPDATE`/
  transacción — core sagrado intacto); (c) **expone el soft-delete vía `solo_activos` por superficie** (no lo
  unifica incondicionalmente — ver gotcha abajo); (d) reusa
  alias `e` + `MARCA_SUBQUERY` (_2026-05-26_) y psycopg3 `%s` (_2026-06-27_). API: `contenido_de_batch(conn,
  equipo_ids, solo_activos=True) -> dict[int, list[dict]]` + `contenido_de(conn, equipo_id, solo_activos=True) ->
  list[dict]`.
- **`solo_activos` no es universal (gotcha).** `True` (default) para **catálogo/ficha/carrito** (oculta los
  componentes soft-deleted: el cliente no debe ver lo retirado); `False` para **documentos / detalle de un pedido
  ya hecho** (debe mostrar lo que de verdad se entregó, incluso piezas hoy retiradas). Elegir el flag **por
  superficie**, no por reflejo: vuelve **explícita** la diferencia que antes era drift accidental (`attach_kit`
  filtraba `eliminado_at`, `get_kit` no). El **cómo** (consumidores, tabla por superficie, fronteras, los tres
  conceptos de "qué incluye") vive en el manual [`docs/SISTEMA_CONTENIDO.md`](SISTEMA_CONTENIDO.md); el
  **criterio/porqué** acá — split _2026-06-25 — Manuales técnicos por sistema_.
- **Consecuencias.** El supervisor marca display de "qué incluye un producto" reimplementado fuera de la puerta.
  Dos candados: `test_contenido_puerta_db.py` (integración Postgres: misma fuente que el gate, granularidad 1
  nivel, el flag `solo_activos`) + `test_contenido_sql_safety.py` (unit: falla si un consumidor migrado vuelve a
  armar SQL inline contra `kit_componentes`). **Adopción no total (honesto):** el detalle de pedido para mails/
  cotización (`_get_alquiler_items`/`_batch_get_alquiler_items`, superficie de plata) todavía devuelve `kc.*`
  crudo — consolidación follow-up, documentada en el manual. Módulo:
  `backend/services/contenido/{__init__.py, contenido.py, modelos.py}`. Iniciativa de tracking **#1087**;
  shippeada en el lote de contenido client-facing (repetir pedido + listas + compartir + las tres "casi gratis":
  vista en carrito, packing list, buscar por contenido). Repetir/listas/compartir reusan `rearmarCarrito`, que
  **re-cotiza el catálogo actual** respetando la decisión snapshot _2026-06-06_ (presupuestos se recotizan;
  confirmados conservan su snapshot). Features #3 «armá tu kit» y #5 «faltantes inteligentes» quedaron diferidas
  (#1092).

### 2026-06-29 — Cierre de gobernanza disparado por volumen del buzón (no por calendario)

- **Contexto.** El cierre de gobernanza (skill `gobernanza` §6) nació **mensual** (_2026-06-23 — Etapa 2_).
  Al ritmo real de la sesión, un mes deja apilar demasiado drift antes de triagear el buzón, podar lo que no
  rinde y re-derivar principios. El dueño lo notó: _"1 mes me parece mucho al ritmo que vamos"_.
- **Decisión.** El cierre se dispara **por volumen, no por almanaque**: cuando el buzón
  `docs/PROPUESTAS_SKILLS.md` junta **≥ 5 propuestas pendientes** (las que no llevan `✅ aplicada`). Constante
  `THRESHOLD` tuneable arriba del hook; **N=5** de arranque, se afina con el ritmo real observado (empirismo
  proporcional, _2026-06-27_). Lo **surfacea solo** un hook nuevo `check-buzon.sh` (SessionStart, **gemelo de
  `check-pendientes.sh`**: cuenta un backlog y nudgea; **sin state file** → recomputa en cada arranque, así el
  aviso **persiste** hasta que el cierre baje el buzón). Como todo hook de Claude Code: terminal/desktop, no
  web/celu; `exit 0` siempre.
- **Why volumen y no tiempo.** El cierre hace varias cosas, pero casi todas **ya tienen su propia red**: la
  staleness de manuales la caza el supervisor por-cambio (+ el check de staleness propuesto en el buzón), y los
  skills sin revisar > 120 días son un warning de `check-docs`. **Lo único que necesita de verdad un ritual
  periódico de juicio humano es el triage del buzón** — y eso **es** volumen. Por eso el buzón es la señal
  correcta para gatillar; un calendario quedaría siempre mal calibrado cuando el ritmo varía (mismo criterio
  que `check-retro.sh`, que dispara por tamaño de diff, no por fecha).
- **Sin piso de tiempo (el borde honesto).** Si el buzón queda quieto, el cierre no corre — y eso es
  **correcto** (buzón vacío = nada que triagear). Cualquier otra cosa la cubren el supervisor (por cambio) y el
  `/gobernanza` a demanda. No hace falta un "dead-man switch" de calendario.
- **Principios cada 2 cierres.** La re-derivación de la Filosofía de trabajo (anti-congelamiento) va en un beat
  más lento —cada segundo cierre— porque re-derivar sobre poco corpus agrega ruido en vez de señal.
- **Consecuencias.** Refina —no reemplaza— la cadencia "mensual" de _2026-06-23 (Etapa 2)_ y _2026-06-27
  (Filosofía de trabajo derivada)_; el skill §6 + cheatsheet, la fila de `CLAUDE.md` y los punteros de memoria
  se actualizaron a "por volumen". El supervisor marca un cierre gateado por calendario en vez de por volumen, o
  un `THRESHOLD` cambiado en el hook sin reflejarlo en la memoria. Salida de la conversación de cierre de la
  iniciativa del retro (misma sesión que _2026-06-29 — Retro de iniciativa_).

### 2026-06-29 — `backend/auth/` = motor único de autenticación (multi-método sobre una sesión única, aditiva)

- **Contexto.** La auth estaba **desperdigada** en ~5 lugares: `routes/auth.py` (631 líneas, god-module: sesión
  + OAuth + staging + rate-limit), `admin_guard.py`, los guards de cliente en `routes/cliente_portal/core.py`, y
  `services/passkeys/`. Tras sumar passkey (PR #1095), era el único concern transversal sin paquete propio.
  Insight: Google OAuth y passkey **ya convergían** en una sola sesión (la cookie que mintea
  `_make_session_response`); faltaba juntar los *archivos*, no rediseñar.
- **Decisión.** Toda la auth en el **paquete-motor `backend/auth/`** (espeja `reservas/`/`contabilidad/`):
  `session` (núcleo: signer único + cookie + `_make_session_response` + `get_session`), `ratelimit`, `guards`
  (admin + cliente), `google` (OAuth + el router compartido), `staging`, `sessions_store`/`sessions_routes`
  (revocación), `passkey/`. **Una sola sesión, varios métodos:** todo login (Google admin/cliente, passkey,
  staging) pasa por el **punto único `_make_session_response`** → la misma cookie firmada `session`. Los guards
  **solo la leen** (agnósticos del método). Passkey es **aditivo** a Google: no lo reemplaza; Google sigue siendo
  el anchor de identidad + la recuperación (perdés el dispositivo → entrás por Google y re-registrás).
- **Why.** "Una sola forma de cada cosa" + "el core que anda no se toca; lo nuevo se acopla alrededor". La
  consolidación fue **move-verbatim** (sin shims; git detectó renames byte-idénticos), con imports y tests
  re-apuntados — no un rediseño. Tener un punto único de minteo es lo que después habilitó la revocación (un solo
  lugar donde crear el `jti`).
- **Consecuencias.** El supervisor marca: un `set_cookie("session", …)` crudo por fuera de
  `_make_session_response` (no heredaría jti/revocación), o lógica de auth (un guard, un mint de sesión) recreada
  fuera del paquete. Setup de prueba logueada: _Staging-login (2026-06-19)_. El "cómo funciona" vive en
  [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); la historia, en PR #1095 (passkey) + #1100 (consolidación).

### 2026-06-29 — Revocación de sesión: allowlist `auth_sessions` + `jti` obligatorio (corte limpio, anti-IDOR)

- **Contexto.** La sesión era una cookie firmada **stateless** (itsdangerous, TTL 30 días): el logout solo
  borraba la cookie del navegador → un token robado valía 30 días, sin forma de matarlo ni de "cerrar mis otras
  sesiones". Era el gap #1 de la auditoría de seguridad. El dueño priorizó seguridad ("la web tiene que ser
  segura") y no le molesta el re-login.
- **Decisión.** Un **id opaco de sesión (`jti`)** viaja firmado en la cookie + una **allowlist server-side**
  (tabla `auth_sessions`). `get_session` valida la firma **y** que el `jti` siga vivo (`is_active`: no revocada,
  no vencida). **`jti` OBLIGATORIO (corte limpio):** una cookie sin jti (las viejas pre-deploy, las hand-minted de
  tests) se **rechaza** → re-login; **ninguna sesión válida queda fuera de la tabla** (todo revocable desde el
  minuto uno). Logout (`GET`/`POST /auth/logout`) y "cerrar mis otras sesiones" son **reales**: revocan el `jti`
  en la tabla; `revoke_all_for_owner` preserva el dispositivo que la pide con `except_jti`. El `jti` se crea en el
  punto único `_make_session_response` y viaja **solo en la cookie** (no en el body JSON).
- **Why.** El corte limpio (vs. tolerar cookies viejas) lo eligió el dueño: cierra el (chico) hueco de transición
  al instante a cambio de un re-login único; el invariante "toda sesión es revocable" es más simple que dos clases
  de cookie. La forma (allowlist + jti) reusa lo existente: esquema en dos capas (_2026-06-03_), DAL `%s` + bound
  params (_2026-06-27_), y el patrón owner-scoped de `passkey/store`. Sin infra nueva (sin Redis). El chequeo va
  dentro de `get_session` (fuente única: middleware/guards/handlers lo heredan); memoizado en `request.state`.
- **Consecuencias.** **Anti-IDOR:** toda revocación incluye al dueño en el `WHERE` (`owner_type` +
  `cliente_id`/`owner_email`), no solo el `jti`. Tiempos en wall-clock de AR (`now_ar()`) en ambos lados de la
  comparación de vencimiento. Al promover a prod, las sesiones abiertas de antes se cierran (re-login una vez):
  es el corte limpio funcionando, no un bug. El supervisor marca una sesión minteada sin pasar por
  `_make_session_response` (quedaría sin jti) o una revocación que no scopee al dueño. Cómo →
  [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md) §2; historia → PR #1102 (revocación) + #1103 (quick wins de seguridad).
