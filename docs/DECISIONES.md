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
  una pieza de DS en `src/design-system/{ui,composites}` o de negocio en `src/components/{rental,admin}`;
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
  (copy/labels/empty states, voz "vos"); (9) **reusar no recrear** (la forma del pill vive en `ui/Pill`;
  `EstadoBadge`/`PagoBadge` derivan; cero clases copiadas a mano); (10) mobile/a11y no son extra (HIG,
  ≥44px, foco visible); (11) el core es sagrado, el diseño es presentación.
- **Why.** Sin el _por qué_ escrito, cada pantalla re-discute el mismo criterio y el front deriva. La
  esencia documentada + enforceable es lo que hace que el rollout a toda la web sea consistente y no una
  colección de one-offs.
- **Consecuencias.** Materializado en código: `ui/Pill` (forma + tonos semánticos única), `ui/PagoBadge`
  (estado de pago con monto), `ui/ClienteAvatar` (avatar determinístico). El **contraste de los tints de
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

- **Contexto.** El DS de Rambla tiene estructura sólida (tokens OKLCH modulares, primitivos en `ui/` con
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
- **Refinamiento 2026-06-30 — tamaño ≠ novedad; rinde estimado al gate.** El disparador por **tamaño de diff**
  (≥4 archivos/≥150 líneas) es un **proxy barato**, pero lo que el retro **paga** es la **novedad**: una iniciativa
  grande-pero-rutinaria (reusa patrones/guards ya establecidos) rinde poco; una chica-pero-novedosa rinde mucho.
  Por eso, al dispararse, la sesión **estima el rinde esperado por novedad ANTES de analizar** y lo trae al primer
  OK ("rutinaria, reusó X → va a salir flaca" vs. "rompió terreno en Y → vale"), para que el dueño **gatee informado
  y temprano**, no después de gastar el análisis. **Caso testigo (dogfood):** el retro de la *vitrina de organismos
  del DS* (7 archivos / ~1.100 líneas → calificaba por tamaño) salió **flaco** porque fue rutinario (reusó el patrón
  de vitrina + el guard Bloque 6b de la iniciativa anterior): rinde neto = **1 gotcha al buzón**, todo lo demás
  confirmó decisiones existentes. El dueño lo notó al final (_"¿hay que hacer el retro?"_) → de ahí el refinamiento.
  El skill `gobernanza` §7 paso 1 + cheatsheet se actualizaron. El supervisor marca un retro que reporte solo el
  tamaño al gate sin estimar la novedad.

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

### 2026-06-29 — `backend/services/carrito/` = módulo único de la lógica del carrito (intención; el gate es la verdad)

- **Contexto.** Auditoría profunda del carrito (#1110, 32 hallazgos verificados). El stock ya tenía motor único
  (`reservas/` + candado AST) y el "qué incluye" su puerta (`contenido/`), pero la LÓGICA del carrito estaba
  dispersa: el `_normalizar_items` vivía byte-por-byte en `routes/compartir.py` y `routes/cliente_portal/listas.py`
  (caps copiados), el estado de carritos activos/abandonados mezclado en `routes/carritos.py`, y —la raíz— el precio
  de un combo se **cotizaba** con `precio_combo()` pero se **persistía** con `equipos.precio_jornada` crudo: el total
  mostrado podía no coincidir con el cobrado. Con cada feature nueva (compartir, abandonados, listas) crecía el
  riesgo de repetir el drift del kit.
- **Decisión.** Módulo de dominio backend `services/carrito/` (patrón route=transporte, service=lógica) que **owna**
  la lógica propia del carrito y **referencia** (no reimplementa) los motores. Owna: (1) la **selección canónica**
  (`SeleccionItem` + caps únicos + `normalizar_seleccion`: dedup última-cantidad-gana / clamp 1..99 / filtro a
  equipos existentes / cap 200 / preserva orden + proyecciones items_json/tuplas); (2) **activos/abandonados**
  (heartbeat upsert por session_id, enrichment, abandono 24h, funnel admin, `marcar_confirmado`); (3) **readiness**
  (`precios_catalogo_para_reserva`: gate `visible_catalogo` + el cliente no decide el precio, resolviendo con el
  resolutor único, y **handoff** a `create_pedido_retry`). Referencia: `reservas/` (stock/overlap/locks, SAGRADO,
  solo lee — candado AST intacto), `services/precios` (toda la plata), `services/contenido/` (qué-incluye),
  `create_pedido_retry` (creación real con advisory-lock — NO se reimplementa).
- **Invariante de plata: cotizado == cobrado.** El precio efectivo por jornada lo resuelve UNA función,
  `precios.precio_jornada_efectivo(conn, equipo_id) -> Optional[int]` (combo → `precio_combo` derivado de
  componentes C3 #635; kit/simple → `equipos.precio_jornada`; `None` si no existe / soft-deleted). La consumen los
  **tres** caminos que persisten plata: `cotizar` (cotizacion.py), `crear` (vía `readiness`), `modificar`
  (`solicitudes._equipo_precio_catalogo`). Cada uno mantiene su **propio gate** (cotizar ignora inexistentes; crear
  exige `visible_catalogo` y tira 404; modificar cae a 0). La paridad queda **por construcción** (un solo
  resolutor), reforzada por source-scan — no hace falta un test de DB que compare "la misma función con sí misma".
- **Why.** El dueño pidió **una sola fuente de verdad de la lógica del carrito** y no repetir el drift del kit. Se
  aplica el patrón ya probado (motor único + puerta + candados + manual). El front queda separado (el módulo es
  backend-only); el dueño lo confirmó ("el front no se mezcla").
- **Consecuencias / fronteras.** Las 3 tablas (`carritos_activos`/`carritos_compartidos`/`cliente_listas`) **NO se
  unifican** (ciclos de vida distintos); sí la **forma del ítem** y su validación. La línea personalizada del admin
  (#805, `equipo_id=None`) queda fuera de la selección canónica (es del builder admin). No se toca el motor de
  reservas, ni `create_pedido`/advisory-lock, ni el TOTAL canónico de `cotizacion.py`. **El split del god-module
  `routes/alquileres/core.py`** (move-verbatim de emails/enriquecer) NO es parte de este módulo: es lógica de
  **alquileres**, no del carrito (se tocan, pero es otro motor; aclaración del dueño 2026-06-29) → su propio PR, sin
  tocar `create_pedido`.
- **Candados.** `test_carrito_seleccion.py` (dedup/clamp/filtro/cap/orden), `test_carrito_normalizar_safety.py`
  (compartir/listas no redefinen el normalizador ni el SQL del filtro), `test_carrito_precio_efectivo.py` (resolutor
  unit + source-scan: los 3 caminos usan `precio_jornada_efectivo`, ninguno inlinea `precio_combo()` ni el SELECT de
  la rama de combo, y crear delega en la puerta).
- **Gotchas.** `marcar_confirmado` conserva su firma `(session_id, conn)` y se re-exporta desde `routes/carritos.py`
  (lo importa `pedidos.py`). `readiness` puede lanzar `HTTPException(404)` — convención aceptada en services del
  repo (spec_persist/media). El manual del cómo-funciona vive en [`SISTEMA_CARRITO.md`](SISTEMA_CARRITO.md); este
  log guarda el porqué. Supervisor: APROBADO (PR #1112), sin drift.
- **Pendiente** (fuera del lote, documentado en `SISTEMA_CARRITO.md` §Pendiente): FASE 3 (display de plata: el
  front no calcula, el service devuelve los precios — ver decisión siguiente), el split de `alquileres/core.py`
  (alquileres, su propio PR), y FASE 6 (features: recuperación #1111, agregar-vs-reemplazar #1108 — definir alcance).

### 2026-06-29 — El front no calcula plata: la pide al backend y la muestra

- **Contexto.** El total del carrito ya salía 100% del backend (`/api/cotizar`, #617): el front no lo calcula. Pero
  el **estimado** ("≈ $X/jornada" sin fechas) y los subtotales por línea se recalculaban a mano en 5 superficies del
  front (CartDrawer, `c/$token`, ClientePortalListas, CartMiniBar, CatalogoMovilHelpers), con redondeo propio y
  usando el `pricePerDay` crudo (mal en combos). Al pensar FASE 3 del carrito, el dueño fijó el principio general:
  "el front no decide nada, solo muestra lo que le dan; pero no calcula".
- **Decisión.** **Ningún número de plata se calcula en el front.** El backend lo resuelve (el total vía
  `calcular_total`; el precio por ítem vía el resolutor único `precio_jornada_efectivo`) y lo devuelve ya hecho; el
  front **solo renderiza**. A lo sumo **suma** valores que el backend ya le dio para mostrar; nunca aplica reglas de
  precio/descuento/IVA/combo. El "cómo se muestra" (lo visual) es decisión aparte.
- **Why.** Una sola fuente de la plata, de punta a punta: si el front calcula, hay una segunda verdad que driftea
  (fue exactamente la raíz del drift de combos cotizado≠cobrado). **Generaliza #617** ("cotizar = fuente única, el
  front no calcula el total") de *el total* a *todo* número de plata, incluido el teaser.
- **Consecuencias.** Para no pegarle al backend en cada cambio del carrito por un estimado, cada equipo puede traer
  su **precio efectivo** desde el catálogo → el front suma lo que le dieron (no aplica reglas) y sigue instantáneo.
  **FASE 3 del carrito se implementa así** (el service devuelve los precios, el front los muestra), NO con un helper
  de cálculo en el front. El supervisor marca una regla de precio/descuento/IVA/combo recalculada en el front.
- **Gotcha.** "Sumar para mostrar subtotales que el backend ya calculó" no es calcular plata; "multiplicar
  precio×cantidad×jornadas×(1−desc)" sí lo es y va al backend.

### 2026-06-29 — Cuentas livianas: alta passwordless con passkey (cuenta vacía hasta Didit, inerte + anti-spam)

- **Contexto.** Hoy la cuenta de un cliente **nace por Google** (el registro arranca con el login de Google;
  la búsqueda es por email). El dueño quiere el norte "modelo banco": el cliente **no tipea nada** (ni mail, ni
  contraseña, ni sus datos), los trae Didit. La experiencia faro la describió él: "entré a Vercel, elegí passkey
  y me creó la cuenta directamente". Además, al probar passkey en staging apareció una **trampa**: el único botón
  "Entrar con passkey" mandaba a un QR sin salida a quien no tenía una. Se juzgó con el `consejo` (Nivel 1): el
  riesgo era la cuenta **huérfana pre-Didit** (sin contacto para avisar/recuperar); lo desinfla que las passkeys
  **sincronizan** (iCloud/Google) + Didit devuelve mail/tel al primer pedido. El consejo recomendó **A** (mail
  skippeable); el dueño eligió **C** (passkey-pura, cero contacto en el alta) — override consciente: "la cuenta
  vacía no vale nada hasta que pide → no me importa el huérfano pre-pedido".
- **Decisión.** Alta passwordless **opción C**: `POST /auth/passkey/signup/{begin,complete}` (motor
  `auth/passkey/`, aditivo a Google) crea una **cuenta liviana** — nace solo con `id` + passkey, sin datos. Para
  eso se **relajan los `NOT NULL`** de los campos base de `clientes` (nombre/apellido/telefono/email/direccion/
  cuit) y se agrega `cuenta_estado TEXT NOT NULL DEFAULT 'completa'` (las existentes quedan `'completa'`; las
  nuevas, `'liviana'`); la passkey lleva `owner_email=''` (la cuenta no tiene mail). Cuenta + passkey se insertan
  en **una transacción atómica** (si falla la passkey, no queda cuenta huérfana) y la sesión mintea por el punto
  único `_make_session_response` (que ahora tolera email/nombre NULL → `""`, heredando jti + revocación). La
  **identidad/contacto los completa Didit al primer pedido**, en las columnas `*_renaper` (con COALESCE) —**el
  usuario nunca escribe los campos base de identidad**—; la cuenta queda **inerte** hasta verificar
  (`require_cliente_verificado` mira `dni_validado_at`). El **admin no tiene signup** (es allowlist; su passkey se
  agrega desde el perfil tras entrar por Google). En el front, el login del cliente lidera con "Crear cuenta con
  passkey" (CTA `Button variant=primary`, gesto ink→accent) separado de "Entrar con passkey" → cierra la trampa;
  se saca el bloque "¿no tenés cuenta? WhatsApp".
- **Why.** Reusa los tres motores sin tocarlos: `auth/` (mismo `_make_session_response` + cookie + jti),
  `reservas/` (intacto), Didit (el gate de verificación ya existía). El esquema va en **dos capas**
  (_2026-06-03_): `init_db()` **y** la migración `a7f3e1c9d2b4` hacen lo mismo (idempotente, convergen — lo clava
  `test_alembic_upgrade_db`). El blast-radius de relajar los `NOT NULL` es seguro porque la arquitectura ya lee la
  identidad validada de `*_renaper` (con COALESCE), no de los campos base. Anclar el CUIL recién al verificar (no
  forzar KYC en el alta) no mata conversión y respeta la separación identidad(locked)↔contacto/login(editable).
- **Consecuencias.** **Higiene anti-spam, invisible al usuario (las 3 patas):** (1) rate-limit por-IP que cuenta
  también las altas **exitosas** (`_record_event`, no solo los fallos — si no, frenaría fuerza bruta pero no spam
  de cuentas; lo cazó el supervisor); (2) inertidad-hasta-Didit (una liviana no puede pedir ni mandar mails); (3)
  **cleanup diario** de livianas abandonadas (`jobs/cleanup_livianas.py`, colgado del scheduler in-process único
  _2026-06-04_: borra liviana + sin verificar + sin email + sin pedidos + > 30d; el `ON DELETE CASCADE` limpia
  passkey/sesiones/identidades; el predicado además evita orfanar pedidos, cuya FK es `SET NULL`). El daño máximo
  pre-cleanup es filas vacías inertes, no abuso real. Candados: `test_clientes_livianas_db` (alta + cleanup contra
  Postgres real: `NOT NULL` relajados, `UNIQUE(email)` con múltiples NULL, `owner_email=''`, inerte, el barrido
  borra solo lo abandonado) + unit en `test_passkey` (signup begin/complete, 409 passkey duplicada, flag `signup`
  del challenge, ráfaga de altas → 429). El supervisor marca un alta que escriba identidad en los campos base en
  vez de esperar a Didit, o un signup fuera de la transacción atómica / del punto único de minteo. Es la **Fase 4**
  de la iniciativa de identidad (#1098); quedan dentro de la fase la invitación white-glove del admin. Cómo →
  [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); juicio → `consejo/BITACORA.md` (2026-06-29); historia → commits del lote en `dev`.

### 2026-06-29 — Merge de cuentas por link autenticado (unir cuando es la misma persona + una es absorbible)

- **Contexto.** Probando en staging, el dueño hizo el alta con passkey (cuenta liviana nueva) y desde el perfil
  quiso **Vincular Google** con su Google de siempre → chocó con "ese Google ya está en uso por otra cuenta" (su
  cuenta real). Quedó con **dos cuentas** y un dead-end. **Insight del dueño:** "si se crea una con passkey y
  después quiere vincular Google desde su perfil, deberían vincularse o mergear, porque sabemos que las dos cuentas
  son la misma persona". Y la contraparte, que él mismo marcó: si crea la passkey, se desloguea y vuelve por Google
  **sin esa prueba**, no hay forma de saber que es la misma → quedan separadas (entiende la diferencia).
- **Decisión.** **Merge-on-link.** Al vincular una llave (Google) que ya es de otra cuenta B estando logueado en A,
  se **unen** A y B en vez de rechazar — porque estar logueado en A prueba control de una llave de A, y completar el
  OAuth prueba control de una llave de B → **misma persona**. **Guardrail:** se mergea solo si una de las dos es
  **absorbible** (`auth/account_merge.account_is_absorbable`: liviana + `dni_validado_at` NULL + sin pedidos). Se
  mueven sus llaves (passkeys + `login_identities`, respetando el `UNIQUE`) a la otra y se borra (`merge_accounts`,
  transaccional). Si la absorbida es la cuenta donde estabas, se re-mintea sesión en la sobreviviente por
  `_make_session_response`. Si **ninguna** es absorbible (ambas con datos) → no se auto-mergea, vuelve "taken". Va
  por la URL `?keys=merged|taken|...` que el perfil convierte en toast.
- **Why.** El **link autenticado es la prueba** de control de ambas cuentas — más fuerte que matchear por mail
  (SIM-swappeable) y disponible sin Didit. Absorber **solo lo vacío** mantiene el merge trivial y seguro (no hay
  datos que reasignar; todas las FKs a `clientes` son CASCADE/SET NULL → el DELETE nunca falla por una referencia
  colgada). El merge **general** de dos cuentas con datos (reasignar pedidos/contabilidad, diagnóstico de duplicados,
  dedup por CUIL verificado) es la parte delicada → se difiere a **Fase 2** (`identity/merge`), como pide el plan
  ("nunca auto-merge de datos sin cuidado"). La red última sigue siendo Didit: al primer pedido el CUIL ancla y
  unifica aunque el merge-on-link no haya disparado.
- **Consecuencias.** Saca el dead-end que encontró el dueño: un usuario que ya tiene Google y prueba el alta-passkey
  termina con **una** cuenta (su real + la passkey nueva), no dos. La sesión vieja de la cuenta absorbida muere con
  el `DELETE` (cascade de `auth_sessions`) y se re-mintea en la sobreviviente. Candados:
  `test_clientes_livianas_db::test_merge_absorbe_*` (DB real: mueve llaves, borra el source, respeta el guard) +
  `test_linking::TestMergePorGoogle` (las 3 ramas: actual absorbible → entra a la real; otra absorbible → la
  absorbe; ninguna → "taken"). El supervisor marca un merge sin el guard de absorbible o un auto-merge de dos
  cuentas con datos. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); historia → commits del lote en `dev`; #1098 Fase 1B.

### 2026-06-29 — Step-up con passkey ("confirmá que sos vos") para operaciones sensibles del cliente

- **Contexto.** El dueño, probando, pidió poder **usar la passkey para confirmar cosas sensibles** — "como borrar
  algo, o hacer un pedido". Borrar un método de acceso es sensible: alguien con una sesión robada podría quitarte
  tus otras llaves y dejarte afuera. Confirmar con una prueba fresca de identidad lo frena.
- **Decisión.** Un **primitivo de step-up** reusable: `POST /cliente/auth/passkey/stepup/{begin,complete}` corre
  una assertion WebAuthn (la misma del login, pero **scopeada**: la passkey TIENE que ser de esta cuenta) y, si
  pasa, deja una cookie firmada `stepup` de corta vida (~5 min, owner-scopeada). El guard **`require_recent_auth`**
  (`auth/stepup.py`) = `require_cliente` + `stepup` fresca; lo usa el `DELETE /cliente/auth/keys/...`. **No es un
  login** (no mintea sesión). El front (`stepUpWithPasskey()`) dispara la confirmación antes de la acción.
- **Why.** El **link/assertion autenticado es prueba fresca** de control — más fuerte que un simple confirm. Se
  hace **un primitivo** (no un "confirmá con passkey" ad-hoc por endpoint) para reusarlo: hoy el borrado de llaves;
  mañana, **confirmar un pedido** (mismo guard al confirmar) y la base de la **firma con passkey (Fase 5)**. Reusa
  la ceremonia de `auth/passkey/` (cero motor nuevo) + `itsdangerous` para la marca (sin Redis ni tabla). Es el
  `require_recent_auth` que el plan tenía para la **Fase 3** (step-up transversal), aterrizado en su primer uso.
- **Consecuencias.** Quitar un método de acceso ahora exige confirmar con passkey (el front lo dispara y reintenta;
  si cancelás, no borra). **Pendiente:** aplicarlo a **confirmar un pedido** (toca el flujo de pedidos + decidir el
  fallback para quien no tiene passkey — Google-only) y la firma criptográfica del contrato (Fase 5). Candados:
  `test_passkey::TestStepup` (la passkey tiene que ser de la cuenta → 401 si es de otra) + `test_linking`
  (el borrado sin `stepup` da 401; con `stepup` fresco procede). El supervisor marca una operación sensible del
  cliente sin `require_recent_auth`, o un step-up que acepte una passkey de otra cuenta. Cómo →
  [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md); historia → commits del lote en `dev`; #1098 Fase 1B.

### 2026-06-29 — `backend/services/checkout/` = portero único del checkout (fail-not-fast; devuelve {listo, faltan})

- **Contexto.** `create_pedido_retry` mezclaba validación + creación: la UI no podía mostrar "qué te falta" sin intentar crear el pedido y fallar en el primer check. El flujo tiene 9 precondiciones activas (logueado, identidad, carrito, fechas, stock-preflight, precio, contacto, T&C, firma) + 2 diferidas (bloqueo #1125, antelación #1126).
- **Decisión.** Módulo validador puro `backend/services/checkout/` que corre todos los checks **fail-not-fast** y devuelve `{listo, faltan}`. Wired a `POST /api/checkout/validar` (body: `session_id` UUID v4 + `session_confirmed` bool; el route computa `firma_ok = has_recent_stepup OR session_confirmed`). T&C separado en `POST /api/checkout/aceptar-tyc` (idempotente; tabla `aceptaciones_tyc` `UNIQUE(cliente_id, version)`). Los 2 checks cableado-apagado retornan siempre OK hasta que el issue los active.
- **Why.** Separa concerns: validar ANTES, crear después — el `FOR UPDATE` + advisory lock de `create_pedido_retry` sigue intacto. El fail-not-fast es el corazón: la UI necesita la lista completa de problemas para que el cliente los resuelva de una. La firma con passkey es más fuerte pero no bloquea a clientes sin passkey: el `session_confirmed` es un fallback consciente y documentado (weaker, no una laguna — el cliente declaró intención en la misma sesión). El stock-preflight no tiene lock (solo lectura): puede dar verde y que el gate falle después, documentado como "preflight" para no confundir. El contacto viene de `*_renaper` (no del usuario): si Didit no terminó, el check falla — correcto y explícito.
- **Consecuencias.** `aceptaciones_tyc` en `init_db()` + migración Alembic `b1a2c3d4e5f6` (convención _2026-06-03_); clasificada en `identity/merge.py::TABLAS_REASIGNADAS` con dedup-on-reassign por el `UNIQUE`. 31 tests unitarios sin DB real (fake conn configurable). El check `logueado` lo hace el route vía `require_cliente` — el servicio recibe `cliente_id` y asume cliente válido. El supervisor marca validación de checkout ad-hoc fuera de la puerta, un fail-fast en el medio de `validar_checkout`, o `session_confirmed` aceptado sin documentar como fallback de firma. PR #1128 (servicio) + #1129 (routes).

### 2026-06-30 — Firma con passkey: presencia de un toque (on-the-fly) + gate del checkout reusa el portero; presencia ≠ firma legal

- **Contexto.** El dueño pidió poder **firmar/confirmar el pedido con passkey** sin fricción — "como cuando desbloqueás
  el celular, que cree la passkey de un saque, simple". La base ya existía (step-up _2026-06-29_: cookie `stepup` +
  `require_recent_auth`), pero (a) el cliente **sin** passkey caía a un fallback débil, y (b) la firma vivía solo en el
  pre-flight advisory `/checkout/validar`, **no** en el gate real de creación (`POST /api/cliente/pedidos`, que solo
  exigía identidad). Aparte, el dueño aclaró que la firma **legal** (no-repudio del contrato) la construye en **otra
  sesión** — esto es "más un acepto los términos y condiciones".
- **Decisión.** Tres piezas. **(1) On-the-fly de un toque:** registrar una passkey de cliente **deja la marca `stepup`**
  (`_register_complete`→`mark_stepup` cuando `owner_type=="cliente"`) — registrar exige el mismo gesto biométrico que
  una assertion, así que **vale como presencia fresca**; es un **modo más de auth** (junto a login/step-up) y **crear
  la llave ya firma**. Helper **único** `firmarConPasskey(tienePasskey)` en `lib/passkey.ts` (step-up si tiene llave,
  register on-the-fly si no — un toque en ambos); se borró el island `lib/firma.ts`. **(2) Gate en la creación
  reusando el portero:** `faltan_firma_tyc(conn, cliente_id, firma_ok)` corre los **mismos** `_check_tyc`+`_check_firma`
  del portero (no re-implementa); el route computa `firma_ok = has_recent_stepup OR session_confirmed`. **No** usa el
  portero completo (lee `carritos_activos`, no siempre sincronizado → 422-earía pedidos válidos); el stock/precio los
  enforza `create_pedido_retry` (motor sagrado intacto). **Cableado-apagado** (`FIRMA_CHECKOUT_OBLIGATORIA=False`) hasta
  que la UI del checkout mande la señal. **(3) Presencia ≠ firma legal:** frontera explícita.
- **Why.** "Reusar no recrear": el gate reusa los checks del portero, el helper se pliega al cliente de auth, y
  registrar-como-firma evita un segundo prompt → un toque siempre. El cableado-apagado (patrón #1125/#1126 + _⏰ LEGACY
  2026-06-25_) deja la firma lista sin romper el flujo vivo (que aún no manda la señal). La distinción **presencia ≠
  firma legal** es la que más valió: la marca `stepup` prueba "hay un humano con el dispositivo ahora" (alcanza para el
  checkout = acepto T&C + confirmo, liviano); la **firma legal del contrato** (no-repudio **atada al hash**, Ley
  25.506) se logra **extendiendo la misma ceremonia** de `auth/passkey/` para firmar el `doc_hash` — **no un sistema
  paralelo**. Se difirió a contratos/ARCA (su lugar natural: ahí existe el documento que se hashea) y la construye otra
  sesión que **reusa** estos primitivos (nota de handoff en #1098 + `SISTEMA_AUTH.md` §3).
- **Consecuencias.** La firma del checkout queda en `services/checkout` (gate liviano), separada de la firma legal. El
  supervisor marca: una firma de presencia recreada fuera de `auth/stepup`+`firmarConPasskey`; el gate del checkout
  re-implementando los checks en vez de reusar el portero; o una firma de contrato con ceremonia paralela en vez de
  firmar el `doc_hash` sobre la ceremonia existente. **Pendiente:** prender `FIRMA_CHECKOUT_OBLIGATORIA` con la UI del
  checkout (otra sesión); la firma legal atada al hash (contratos/ARCA). Candados: `test_passkey` (registrar cliente
  deja `stepup`, admin no) + `test_checkout_portero::faltan_firma_tyc`. En el retro salió como caso testigo un flake de
  timezone (`test_check_fechas_pasada_cliente` usaba `date.today()` UTC vs `now_ar()` del código) → buzón de
  `calidad-tests`. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md) §3; historia → #1131 (on-the-fly + gate), #1132 (handoff).

### 2026-06-30 — `staging-verify`: fakear la verificación Didit en dev SIN tocar `dni_validado_at` a mano

- **Contexto.** El dueño quiso **probar el checkout y el passkey end-to-end en dev**, pero su cuenta no estaba
  verificada y **Didit no corre en dev/staging** (la API de KYC no está cableada ahí). Sin verificación, el portero
  del checkout (`_check_identidad` → `cliente_verificado` → `dni_validado_at`) bloquea para siempre y no se puede
  llegar al pago. Pidió explícitamente "fakear la autorización, es para chequear y validar, estamos en dev".
- **Decisión.** Endpoint dev-only **`POST /auth/staging-verify`** (`auth/staging.py`), gemelo de `staging-login`:
  **misma doble llave** (`is_production` falla-a-prod + secreto `STAGING_LOGIN_SECRET`) → **404 en prod**, secreto en
  tiempo constante, rate-limit por IP. Marca una cuenta como verificada **reusando la pluma única `identity.kyc`**
  (`aprobar` / `actualizar_estado`): setea un `didit_session_id` fresco (único por llamada → sin colisión de
  idempotencia en `kyc_events`) y delega — **nunca un UPDATE manual de `dni_validado_at`/`*_renaper`**. Body:
  `{secret, cliente_id?, estado?, email?}`; `estado` ∈ approved(default)/rejected/en_revision (los 3 caminos del
  KYC); siembra un contacto verificado para cuentas livianas (que el portero exige email); CUIL fake válido (mod-11)
  único por id (no colisiona con el índice único). **No mintea sesión** (se combina con `staging-login
  target=cliente`).
- **Why.** "Una sola forma + reusar no recrear": un UPDATE a mano de `dni_validado_at` duplicaría la escritura de
  identidad que el supervisor marca como prohibida fuera de `identity/kyc` (la pluma única). Reusar `aprobar` hace
  que el fake recorra **exactamente** el mismo camino que el webhook real (COALESCE, ancla CUIL mod-11, contactos,
  evento de auditoría) → lo que se prueba en dev es lo que pasa en prod. La doble llave heredada de staging-login es
  la red ya probada (staging tiene PII real; 404 en prod). Extiende _Staging-login (2026-06-19)_ del login al **gate
  de identidad**; mismo patrón que _Iteración local con datos reales (2026-06-20)_.
- **Consecuencias.** La sesión puede smoke-testear el flujo de pedido logueado+verificado en local y en staging
  Railway sin Didit. **Verificado en vivo:** `/api/checkout/validar` pasa a `listo:true` tras fakear identidad +
  aceptar T&C + firma "Confirmo"; el front (login → carrito → passkey) anda. Candados: `test_staging_verify.py`
  (gate 404/401, approved/rejected, CUIL fake válido y único). En la misma sesión salieron, como cruft del clon
  local (no del código), dos gaps de config dev que rompían el passkey en `localhost` y se arreglaron: deps
  faltantes (`webauthn`, `@simplewebauthn/browser`) y el **default de `FRONTEND_ORIGINS`** que no incluía el puerto
  `:3000` del `vite dev` (el origin que el navegador reporta en la assertion) → fix de 1 línea en `config.py`. El
  supervisor marca un fake de KYC vía UPDATE a mano en vez de la puerta. Cómo → [`SISTEMA_AUTH.md`](SISTEMA_AUTH.md) +
  [`DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md).

### 2026-06-30 — `backend/services/fechas.py` = puerta única de la lógica de fechas/horas; lead-time configurable (#1126)

- **Contexto.** El criterio de validación de fechas estaba **duplicado byte-por-byte en 4 lugares**
  (`create_pedido`, `_apply_pedido_datos`, `_validar_fechas_propuestas`, el cap de 120 días del portal), con
  mensajes y comparadores que iban divergiendo; la validación de **formato** (`_validar_fecha_iso`) vivía suelta en
  `routes/alquileres`; y el check de **antelación mínima** (#1126) estaba cableado-apagado. El dueño pidió, además,
  que "el módulo de fechas maneje **todo** lo de fechas y horas, así todos usan los mismos valores".
- **Decisión.** Crear `backend/services/fechas.py` como **puerta única de toda DECISIÓN sobre fechas/horas**:
  `validar_fecha_iso` (formato, borde→422), `validar_rango_fechas` (orden/no-pasado/tope), `setting_horas` (lector
  genérico de settings de horas) + `dentro_de_ventana_horas` (predicado puro), `antelacion_*` (lead-time),
  `inicio_desde_fecha_hora`, `mes_actual_ar`, `validar_horarios_habilitados`. Los 4 callsites + el portero +
  `_modificacion_ventana_horas`/`_ventana_cumple` + los horarios delegan ahí. Se **activa el lead-time** (#1126):
  setting `app_settings.antelacion_minima_horas` (0 = apagado) en `init_db()` + Alembic + whitelist; portero
  `_check_antelacion` (UX, lee fecha+hora del carrito) + **backstop** en `cliente_crear_pedido` (defensa en
  profundidad, solo-cliente); disclaimer + CTA de WhatsApp en el carrito (el front lee el setting y avisa, el back
  enforza).
- **Why.** "Una sola forma de cada cosa": el criterio de fechas no puede tener 4 copias que driftean. La frontera
  con el DAL: `now_ar()`/`to_datetime()` son **primitivas de bajo nivel** (reloj AR + coerción psycopg) y se quedan
  en `database/core.py` (_2026-06-27_) porque ya son fuente única y no son "decisiones"; el módulo de fechas es dueño
  de las **reglas** construidas sobre ellas (re-exportarlas crearía dos caminos → se evitó). El **dominio de cada
  motor NO se mueve** (reservas: buffer/overlap; precios: jornadas de facturación; reportes/contabilidad: ventanas de
  mes/cierre; auth: TTLs de sesión/step-up; ical/pdf/email: formateo de display) — una auditoría de todo el backend
  lo confirmó. El lead-time con **doble enforcement** (portero advisory + backstop en creación) cierra el agujero de
  saltear el pre-flight, sin tocar el `FOR UPDATE` del gate (core sagrado). **Fail-open**: un setting corrupto/ausente
  cae a 0 (no bloquea pedidos por mal-config). El backstop es **solo-cliente** (el admin carga urgencias a mano),
  espejando el cap de 120 días.
- **Consecuencias.** `validar_horarios_habilitados` se movió a `services/fechas` devolviendo `str|None`;
  `_validar_horarios_habilitados` quedó como **adapter** que levanta el 400 (preserva firma, re-export y el monkeypatch
  de tests). De paso se corrigió un **sesgo de timezone**: `mes_actual()` (tablero) y `_mes_de_fecha` (movimientos)
  usaban `date.today()` (UTC en CI) → ahora `mes_actual_ar()`; `pagos.py` usa `now_ar().date()`. El cambio de mensajes
  de error a lenguaje claro no rompe nada (ni tests ni front dependían del texto). Candados: `test_fechas.py`
  (32 tests) + `test_checkout_portero` (lead-time activo) + los de horarios/seguridad existentes. Dos consolidaciones
  más quedaron **descartadas a propósito** por la auditoría: `validar_mes`/`rango_mes` (reportes) ya tienen fuente
  única sana, y el buffer del motor de reservas es regla de overlap (no genérica). **Pendiente menor** (no es de
  fechas): `cuentas.py` hardcodea `'2026-06-01'` en vez de `LIQUIDACION_INICIO` (drift latente del clean-start). PR
  #1136; tracking #1126.

### 2026-07-02 — El editor de pedidos admin cotiza con el precio de línea congelado, no con el de catálogo

- **Contexto.** El dueño reportó el pedido #405 marcado como "sobrepagado" en la reconciliación mensual pese a
  que la pantalla del pedido mostraba "Cobranza $163.860 de $163.860 · pagado". Investigado: la reconciliación
  (`reportes/reconciliacion.py`, chequeo 3) compara `alquileres.monto_pagado` contra `alquileres.monto_total`
  — dos columnas persistidas de la base. La pantalla del pedido (`pedidos.$id.lazy.tsx`) NO lee esa columna: arma
  su propio total llamando en vivo a `POST /api/cotizar`, que para ítems de catálogo **siempre** recotiza contra
  el precio **actual** de `equipos` (`cotizacion.py`, comentario: "no se confía en lo que mande el front") — no
  contra el `precio_jornada` que ya está persistido/editado en `alquiler_items` del pedido. Dos cálculos
  independientes del mismo "total" para el mismo pedido, que pueden divergir en cualquier momento en que el
  precio de catálogo de algún ítem cambie desde que el pedido se armó.
- **Decisión.** `POST /api/cotizar` acepta un flag nuevo `respetar_precio_item` (solo lo honra una sesión
  admin, mismo patrón que `cliente_id`/`descuento_pct`): si viene en `true`, usa el `precio_jornada` que manda
  cada ítem de catálogo en vez de re-buscarlo en `equipos`. El editor de pedidos (`useCotizacion` con
  `respetarPrecioItem: true`) lo activa siempre — así el total que ve el admin mientras edita es el MISMO que
  persiste `_recalcular_total_pedido` al guardar, que es el mismo que lee la reconciliación. Además, la pantalla
  de Cobranza dejaba de mostrar un excedente cobrado (`restante = Math.max(0, total - pagadoMonto)` clampeaba a
  0 cualquier sobrepago): ahora un `excedente = Math.max(0, pagadoMonto - total)` se muestra explícito en rojo
  ("de más $X") con una nota sugiriendo devolución/crédito, en vez de esconderse detrás de un "pagado" falso.
- **Why.** Se evaluaron dos caminos: (a) bloquear la edición de precio/descuento en pedidos ya
  confirmados/cobrados (snapshot-lock estricto, matching la letra de la decisión 2026-06-06 "Datos del pedido:
  plata congelada"), o (b) mantener la edición permitida (uso real del dueño: dar un descuento retroactivo tras
  cobrar) pero eliminar la fuente de verdad duplicada. El dueño explícitamente pidió (b): "quiero poder editar
  las cosas y que estén todas bien, no sincronizadas" — la solución no es restringir el flujo de trabajo, es que
  no haya DOS cálculos del mismo número. El caso #405 en sí (dinero ya cobrado por encima del total actual tras
  un descuento retroactivo) sigue siendo una situación real de negocio que el dueño resuelve a mano (crédito o
  devolución) — no es un bug de datos, es información que antes estaba oculta.
- **Consecuencias.** Ningún cambio de contrato público: `respetar_precio_item` default `False` (el carrito
  público/`CartDrawer`/`CatalogoMovil` siguen cotizando contra catálogo, sin tocar). Regresión: verificado
  manualmente que `es_admin` se resuelve antes del loop de ítems (antes solo se calculaba dentro del bloque
  `if tiene_fechas:`, se hoisteó). PR #1181, sin tests nuevos (cambio de UI + flag de query ya cubierto por el
  test de contrato de `/api/cotizar`); plan de prueba manual en el PR.

### 2026-07-02 — `backend/contabilidad/` reorganizado CQRS-lite (`queries/`+`commands/`), espejo de `services/specs/`

- **Contexto.** A raíz de investigar el caso #405 (ver decisión anterior), el dueño pidió explícitamente aplicarle
  a `backend/contabilidad/` "el CQRS liviano que estamos implementando en el repo" (ya usado en
  `services/specs/` y `services/specs_ingesta/`) y auditar el módulo para que este tipo de bug no vuelva a pasar.
  El módulo (10 archivos, ~1400 líneas, `#809`) era plano: cada archivo mezclaba lectura y escritura sin
  frontera física.
- **Decisión.** Split **move-verbatim** (cero cambio de lógica/SQL) en `queries/` (lectura, nunca muta) +
  `commands/` (única puerta de mutación) + `constants.py` (top-level: `TIPOS_CUENTA`, `COBRADORES`,
  `SOCIOS_HUMANOS`, `MONEDAS`, `TIPOS_MOVIMIENTO`, `METODOS_MOVIMIENTO`, `PARTES` — viven fuera de `queries/`/
  `commands/` porque `queries/` los necesita y no puede importarlos del lado de escritura). Mapeo: de los 10
  archivos viejos salieron 10 `queries/*.py` + 5 `commands/*.py` (categorías, cuentas, movimientos, cierres,
  rendición). `PARTES` estaba duplicada byte-idéntica en `rendicion.py` y `reporte_mensual.py` — consolidada
  en `constants.py` (una sola forma). Actualizados los 2 callers (`routes/contabilidad.py`,
  `routes/alquileres/pagos.py`) y los 4 archivos de test que importaban rutas viejas.
- **Why.** El motor resultó ser mayormente de lectura: de ~35 funciones públicas, solo 10 mutan de verdad
  (`crear_categoria`, `crear_cuenta`/`editar_cuenta`/`desactivar_cuenta`, `crear_movimiento`/`editar_movimiento`/
  `anular_movimiento`, `cerrar_mes`/`reabrir_mes`, `saldar`). Confirmado al hacer el split: **ningún** query del
  paquete necesitaba nada de `commands/` — la invariante "`commands/` importa de `queries/`; `queries/` nunca de
  `commands/`" se cumple sin fricción, igual que en `specs`/`specs_ingesta`. Separar físicamente lectura de
  escritura hace más fácil auditar visualmente "¿esto puede mutar plata?" con solo mirar en qué carpeta vive —
  reduce la clase de bug de #405 (que fue un bug del LADO CLIENTE del total, no de este módulo, pero la misma
  disciplina de "una sola fuente, nunca dos caminos" es la que lo hubiera prevenido si hubiera vivido acá).
- **Consecuencias.** Candado: 51 tests puros (sin DB) + 29 tests de integración (Postgres real, todo el árbol
  `test_contabilidad_db.py`/`test_reportes_cierres_db.py`/`test_init_db_cuentas_seed_db.py`) pasan en verde
  byte-a-byte contra el comportamiento pre-split — confirma que fue mecánico, no una reescritura. `pyflakes`
  limpio sobre el paquete completo (sin imports muertos ni nombres indefinidos). Suite completa del backend:
  2684 passed (los 3 failed + 3 error de `test_catalogo_motor_shape.py` son preexistentes, no tocan
  `contabilidad` — sin datos de catálogo sembrados en la DB de prueba local). **Auditoría del patrón "dos
  cálculos del mismo número"** (lo que causó #405) sobre el módulo: no se encontró una segunda instancia dentro
  de `contabilidad/` — el propio `queries/reconciliacion.py::reconciliar` ya es el semáforo que cazaría ese
  patrón (hereda `reportes/reconciliacion.py`, que tiene 3 chequeos: pagados-sin-ledger, `monto_pagado`
  divergente del ledger real, y sobrepagados). Rama aislada `feature/contabilidad-cqrs`, PR sin mergear
  (convención "PR como hoja de ruta"); tracking #1184.

### 2026-07-02 — Auditoría de `backend/contabilidad/`: bordes reforzados (edición, locking, auditoría de pagos)

- **Contexto.** Tras cerrar el split CQRS-lite, el dueño pidió una segunda pasada: "¿qué está mal, flojo, poco
  seguro, bien, qué falta, qué sobra?". Se lanzaron 3 auditorías en paralelo (agentes `Explore` independientes,
  sin compartir contexto entre sí para evitar sesgo de confirmación): corrección contable/concurrencia,
  seguridad de la capa HTTP (`routes/contabilidad.py` + `routes/alquileres/pagos.py`), y duplicación/gaps de
  cobertura de tests. Encontraron 19 hallazgos, priorizados en 4 tiers. El dueño, tras ver el diagnóstico
  completo, pidió implementar los 19 en una rama aislada.
- **Decisión — Tier 1 (3 bugs reales):**
  1. `editar_movimiento` (`commands/movimientos.py`) no repetía las validaciones de `crear_movimiento`
     (existencia+actividad de cuenta, misma moneda entre origen/destino, categoría existente+activa) — extraídas
     a `_validar_cuentas_y_categoria(conn, origen, destino, categoria_id)`, llamada por ambas funciones. Antes,
     `PATCH .../movimientos/{id}` con `cuenta_destino_id` de otra moneda pasaba sin error — violación directa de
     "ARS y USD no se mezclan". Verificado: `grep` confirmó cero call-sites de `updateMovimiento` en el
     frontend hoy — el fix es de riesgo cero para flujos en producción, cierra un hueco de la API.
  2. `alquiler_pagos` (la tabla que alimenta `ingresos_derivados`/`saldos`/`rendicion`/`reporte_mensual`/
     liquidación) no tenía columna de actor y `eliminar_pago` hacía `DELETE` real sin motivo — contradecía "la
     plata no se borra" que `movimientos` sí respeta. Fix: migración `a3b4c5d6e7f8` agrega `created_by` +
     `anulado`/`anulado_por`/`anulado_at`/`anulado_motivo` (mismo patrón que `movimientos`, espejado en
     `schema.py`). `agregar_pago` captura `admin.get("email")`. `DELETE /pagos/{id}` → `POST .../{id}/anular`
     con `motivo` obligatorio (soft-delete). **7 queries** que sumaban `alquiler_pagos` sin filtrar ahora llevan
     `AND NOT anulado`: `ingresos_derivados`, `cobros_mensuales`, el chequeo `pagos_sin_socio` de
     `contabilidad/queries/reconciliacion.py`, `cobrado_por_socio` (rendición — hallazgo adicional, no estaba en
     la lista original de la auditoría, encontrado al mapear el fix), el `SALDADO_CTE` de
     `reportes/liquidacion.py` (compartido por 3 consumidores — el filtro va UNA vez ahí, no repetido), los 2
     chequeos de `reportes/reconciliacion.py` (`sin_ledger`/`divergentes`, que además ahora comparan contra la
     MISMA fuente que `monto_pagado` — sin esto, cada pago anulado marcaría un falso divergente), y los 2
     listados de pagos del portal cliente. De regalo: el chequeo "mes cerrado desactualizado" ahora también
     detecta un pago anulado DESPUÉS del cierre (`ap.anulado_at > c.cerrado_at`) — antes imposible de distinguir
     porque el hard-delete no dejaba rastro temporal. Frontend: `deletePago`→`anularPago` (pide motivo vía
     `window.prompt`, mismo patrón que `AnularMovimiento`); los pagos anulados quedan visibles tachados
     (`line-through`+`opacity-50`) en vez de desaparecer — mismo lenguaje visual que ya usa la pantalla de
     movimientos. `test_routes_contract.py` actualizado al nuevo contrato (sumado a `_VALIDA_ANTES_DEL_GUARD`,
     mismo patrón que los demás POST con body requerido).
  3. `subir_comprobante` (`routes/contabilidad.py`) escribía `UPDATE movimientos` directo, saltándose el motor
     — exactamente el escenario que el propio `contabilidad/CLAUDE.md` advertía textualmente ("un endpoint que
     escriba `movimientos` por fuera se saltearía el candado"). No llamaba `_exigir_mes_abierto`, no chequeaba
     `anulado`, no capturaba actor. Fix: nueva `commands.movimientos.actualizar_comprobante(conn, mov_id, *,
     key, por)` que sí pasa por las 3 validaciones; el route la llama en vez del `UPDATE` inline.
- **Decisión — Tier 2 (robustez, concurrencia):**
  - `pg_advisory_xact_lock` (mismo patrón exacto que `services/facturacion/engine.py` y `routes/talleres.py`/
    `routes/alquileres/core.py` ya usan) entre `cerrar_mes`/`reabrir_mes` y `crear_movimiento`/
    `editar_movimiento`/`anular_movimiento` (vía `_exigir_mes_abierto`) del mismo mes. Namespace
    `_ADVISORY_NS_CONTAB_MES = 5390420` (siguiente libre después de `_ADVISORY_NS_PEDIDO`/`_ADVISORY_NS_ESTUDIO`),
    key = `'YYYY-MM'` convertido a entero natural (`YYYYMM`). **Verificado con un test de concurrencia real de
    dos conexiones psycopg + threading** (no solo en teoría, siguiendo "los hallazgos de una auditoría son
    hipótesis hasta confirmarlos" — 2026-06-22): con un monkeypatch que demora `gastos_por_categoria` dentro de
    `cerrar_mes` para exponer la ventana entre tomar el lock y el commit interno, un `crear_movimiento`
    concurrente del mismo mes BLOQUEÓ 4 segundos reales (esperando el lock) y, al desbloquear, fue rechazado
    correctamente por "mes cerrado" — confirmando que la carrera (un gasto colándose en la foto de un cierre en
    curso) queda cerrada.
  - `desactivar_cuenta` (`commands/cuentas.py`) toma `SELECT ... FOR UPDATE` antes de leer el saldo — un
    `crear_movimiento` concurrente contra la misma cuenta toma un lock `FOR KEY SHARE` implícito por la FK, que
    conflictúa. **También verificado con dos conexiones reales**: el `crear_movimiento` concurrente esperó los
    5 segundos completos que la transacción de A mantuvo el lock abierto.
  - Rate limiting: `ADMIN_WRITE_LIMIT = "60/minute"` / `ADMIN_UPLOAD_LIMIT = "20/minute"` (nuevas constantes en
    `rate_limit.py`) aplicadas a los **13 endpoints de escritura reales** (10 en `contabilidad.py` + `pagos.py`
    tenía 2, más `subir_comprobante` con el límite de upload) — el patrón `@limiter.limit` ya existía en el
    repo mas solo para endpoints públicos.
  - Cotas `Field(...)` en los 8 modelos Pydantic de ambos routes: topes de longitud en texto libre, y
    `lt=2_147_483_647` en todo id de cuenta/categoría (el techo real de `INTEGER`/int4 de Postgres — sin esto,
    un id gigante pasaba Pydantic y reventaba en el bind de psycopg con `NumericValueOutOfRange`, no
    `ValueError`). El chequeo manual `monto<=0` de `agregar_pago` se eliminó (redundante con `Field(gt=0)`).
    Decorator nuevo `@map_pg_errors` (`routes/contabilidad.py`, reusado por `pagos.py` — sin ciclo de imports,
    verificado) que envuelve cada endpoint y traduce `psycopg.errors.UniqueViolation`/`NumericValueOutOfRange`
    a 400 limpio — antes, lo que las cotas de arriba no llegaban a prevenir subía crudo al handler global
    (`main.py`), que expone `f"{type(exc).__name__}: {exc}"` (mensaje interno de Postgres) al cliente.
- **Decisión — Tier 3 (limpieza barata, un commit):** `idx_cuentas_socio` pasa a único **solo entre activas**
  (migración `b4c5d6e7f8g9`, simétrica con `cuentas_nombre_activa_uq`) — antes dar de baja una cuenta de socio
  bloqueaba para siempre crear una nueva ACTIVA con ese mismo socio (verificado que el target-less
  `ON CONFLICT DO NOTHING` del seed, fix histórico de #932, sigue funcionando igual con el nuevo predicado).
  Comentario incorrecto corregido en `queries/saldos.py`. `ingresos_devengados` (0 usos confirmados) borrada.
  `SELECT socio FROM cuentas` crudo en el route reemplazado por `obtener_cuenta`. Ambigüedad tipo-cuenta-vs-
  tipo-movimiento (¿puede un `retiro`/`aporte`/`gasto`/`ajuste` tocar una cuenta CORRIENTE de socio, no una caja
  real?) **documentada en el docstring de `validar_estructura_movimiento`, NO bloqueada**: una validación dura
  ahí rompería `commands/rendicion.py::saldar`, que necesita crear `transferencia`s contra cuentas de socio por
  diseño — la regla de negocio no es obvia (un `ajuste` contra una cuenta de socio puede ser una corrección
  legítima), así que se fija el comportamiento actual con un test en vez de adivinar la regla correcta.
- **Decisión — Tier 4 (8 tests candado):** `editar_cuenta` (cero tests pese a usarse en producción para editar
  `saldo_inicial` de socios), `editar_movimiento` con cambio de moneda (el candado directo del bug #1), `ajuste`
  con origen y destino simultáneos (puro + DB — único hueco combinatorio real entre los 5 tipos), fallback de
  `saldo_de_cuenta` (cuenta inactiva/inexistente), anular un saldado de rendición ya registrado (documenta que
  `ya_transferido()` excluye el anulado —el pendiente reaparece, correcto— pero `_movimientos_rendicion` —el log
  de auditoría— lo sigue mostrando, intencional, no una divergencia accidental), `reabrir_mes` con assert
  explícito del retorno en sus 3 casos, y el test de la ambigüedad tipo-cuenta documentada arriba.
- **Why.** El patrón que emergió de las 3 auditorías independientes: **el núcleo (fórmulas, derivación,
  soft-delete, multi-moneda en creación) está sano y bien testeado — los problemas reales viven en los BORDES**
  (el camino de edición no repite las validaciones del camino de creación, un endpoint se salteaba el motor,
  faltaba locking donde el resto del repo ya lo usa, y una tabla vecina no respetaba el invariante de auditoría
  que el propio motor sí respeta). Dos hallazgos (`editar_movimiento` sin revalidar, `alquiler_pagos` sin
  actor/soft-delete) los marcaron DOS agentes de forma independiente sin verse entre sí — señal fuerte de que no
  eran ruido. Ningún hallazgo implica pérdida de plata YA OCURRIDA — son gaps que dejarían un descuadre si se
  daban las condiciones (una carrera real, o alguien editando vía API cruda en vez de la UI). Se prefirió
  verificar los dos locks con concurrencia REAL (dos conexiones, no solo leer el código y confiar) siguiendo el
  principio de que un hallazgo de auditoría es hipótesis hasta confirmarlo en vivo.
- **Consecuencias.** 2689 tests en verde (2681 + 8 nuevos), suite completa, sin regresiones. Dos migraciones
  Alembic nuevas (`a3b4c5d6e7f8`, `b4c5d6e7f8g9`), ambas con `upgrade`/`downgrade` verificados limpios contra
  Postgres real. `pyflakes` limpio en los ~18 archivos backend tocados; `eslint`/`tsc` limpios en los 4 archivos
  frontend tocados. Cambio de contrato HTTP: `DELETE /alquileres/{id}/pagos/{pago_id}` → `POST
  .../{pago_id}/anular` (body `{motivo}`) — sin otro consumidor confirmado por grep. Rama aislada
  `fix/contabilidad-auditoria` sobre `feature/contabilidad-cqrs` (convención "PR como hoja de ruta", PR sin
  mergear); tracking #1184.

### 2026-07-02 — Tipo de movimiento vs tipo de cuenta: retiro/aporte bloqueados contra un socio, gasto permitido a propósito

- **Contexto.** La auditoría de bordes (entrada anterior) dejó a propósito sin bloquear la ambigüedad de qué
  TIPO de cuenta puede tocar cada TIPO de movimiento — la regla de negocio no estaba clara desde el código
  solo. En la sesión siguiente, conversando con el dueño sobre casos reales ("Rambla pagó algo de Pablo",
  "Pablo pagó algo de Rambla"), confirmó el modelo: los socios (Pablo/Tincho) tienen sus bancos propios,
  **totalmente separados del sistema** — la cuenta que Rambla les lleva acá es **puro balance de deuda**
  (quién le debe a quién), nunca plata física que el sistema administre.
- **Decisión.**
  - **`retiro`/`aporte` quedan BLOQUEADOS contra una cuenta de socio** (`_validar_cuentas_y_categoria`,
    `commands/movimientos.py`, gana un parámetro `tipo`): representan plata física entrando/saliendo de una
    caja real — no tienen sentido de negocio contra un balance de deuda que no es caja.
  - **`transferencia`/`ajuste` siguen permitidos sin cambios** contra una cuenta de socio (`saldar()` los
    necesita; un `ajuste` puede ser una corrección legítima de arranque).
  - **`gasto` queda PERMITIDO a propósito** contra una cuenta de socio, como origen (nunca tuvo destino) —
    resuelve el caso real "el socio pagó un gasto de Rambla con su propia plata". Verificado en el código
    (`gastos_por_categoria` en `queries/movimientos.py`, `ganancia_neta` en `queries/pyl.py`): ninguno de los
    dos filtra por TIPO de cuenta origen, solo por `moneda = 'ARS'` — así que un `gasto` con origen una
    cuenta de socio **cuenta automáticamente en el P&L categorizado** Y **baja la deuda del socio en el mismo
    movimiento** (`egresos` resta en la fórmula de cuenta corriente de `queries/saldos.py` — Rambla ahora le
    debe eso). Un solo movimiento cubre el caso completo, sin inventar un tipo de movimiento nuevo.
  - El caso inverso ("Rambla pagó algo de Pablo") ya se resolvía sin cambios con 2 movimientos: `gasto` desde
    una caja real (categorizado, plata real que salió) + `ajuste` con destino=cuenta del socio (le sube la
    deuda) — patrón que ya funcionaba con las reglas existentes, no necesitó tocarse.
- **Why.** El check necesita leer `cuentas.socio` de la DB (`SOCIOS_HUMANOS`), así que no puede vivir en
  `validar_estructura_movimiento` (PURA, sin DB) — va en `_validar_cuentas_y_categoria`, el mismo punto único
  que ya cerró el bug de mayor impacto de la auditoría anterior (`editar_movimiento` sin revalidar). Se
  descartó bloquear `gasto` junto con `retiro`/`aporte` (opción más simple/uniforme) porque hubiera cerrado
  la única forma limpia de que un gasto pagado por un socio impacte el P&L sin necesitar un tipo de movimiento
  nuevo — el análisis del código (`gastos_por_categoria` sin filtro de tipo de cuenta) mostró que la regla
  "permitido" ya encajaba con la infraestructura existente, sin construir nada nuevo.
- **Consecuencias.** `test_movimiento_tipo_vs_tipo_cuenta_sin_restriccion` (fijaba el comportamiento viejo, sin
  restricción) reemplazado por `test_retiro_aporte_bloqueados_contra_cuenta_socio` (confirma el rechazo) +
  `test_gasto_contra_cuenta_socio_cuenta_en_pyl_y_baja_deuda` (confirma el permiso y el efecto doble: P&L +
  deuda). Docstring del módulo (`commands/movimientos.py`) reescrito de "ambigüedad sin resolver" a la regla
  resuelta. Suite completa en verde (2693 tests). Mismo commit/rama que la auditoría de bordes
  (`fix/contabilidad-auditoria` → PR #1195, sin mergear); tracking #1184. Frontend sin cambios — el gate es
  100% backend, el formulario de movimientos no filtra cuentas por tipo hoy y no hacía falta agregarlo para
  este alcance.

### 2026-07-02 — Auditoría cruzada de plata: `docs/SISTEMA_PLATA.md` + el fix de #405 (#1181) nunca se mergeó

- **Contexto.** Tras cerrar la auditoría de `contabilidad/` + el fix de socios, el dueño expresó un miedo
  concreto: "son muchos lugares donde se toca la plata, y no estoy tan seguro desde donde se gobierna cómo
  funciona". Pidió (1) un manual que mapee todos los motores de plata y (2) que no fuera solo un mapa de
  conexiones sino una verificación real de que cada uno funciona correcto — más seguridad/optimización.
- **Método.** 6 agentes de exploración en paralelo (sin compartir contexto entre sí), cada uno auditando un
  motor no cubierto por la auditoría de `contabilidad/`: `services/precios` (2 corridas independientes —
  la primera no delegó bien la tarea y devolvió un resumen genérico en vez del reporte, se reenganchó con
  una instrucción explícita de "no delegues, hacé el trabajo vos"), `reportes/` completo (liquidación +
  comisiones + cierres + reconciliación), `services/facturacion`, el camino de congelamiento de precio en
  la creación/edición de pedidos, y un trace end-to-end de un pedido + estado del semáforo de
  reconciliación. Se verificó cada hallazgo contra el código real antes de documentarlo (grep directo,
  no solo confiar en el reporte del agente) — así se descubrió el hallazgo crítico de abajo.
- **Descubrimiento crítico (de proceso, no de código nuevo).** El **PR #1181** — el fix ORIGINAL del bug
  #405 (el editor de pedidos admin recotizaba contra el precio de catálogo de hoy en vez del precio de
  línea ya persistido/congelado, mostrando "100% pagado" mientras la reconciliación mensual marcaba
  "sobrepagado") — **nunca se mergeó a `dev` ni a `main`**. Sigue abierto (`state: open, merged: false`,
  `mergeable_state: clean`). Confirmado con `git grep respetar_precio_item` sobre `origin/dev`/`origin/main`
  y el checkout actual: cero resultados en todos — el símbolo solo existe en la rama del PR sin mergear
  (`claude/payment-registration-issue-3mi8fk`). La entrada de `MEMORIA.md`/`DECISIONES.md` de la sesión
  anterior lo registraba como ya shippeado ("PR #1181 (merged branch history...)") — era un error de
  registro, no un revert; probablemente una confusión entre "el commit existe en una rama" y "esa rama está
  mergeada". **Consecuencia: el bug #405 está potencialmente activo en producción hoy.** Prioridad
  recomendada: mergear #1181 antes que cualquier otro hallazgo de esta auditoría.
- **Decisión — nuevo manual `docs/SISTEMA_PLATA.md`.** Cruza los ~6 motores de plata (precios, reservas,
  `alquiler_pagos`, `reportes/liquidacion`, `contabilidad`, `facturacion`) con una tabla "fuente única de
  cada número" + el estado del semáforo de reconciliación. **No repite** los invariantes de cada
  `CLAUDE.md`/`SISTEMA_*.md` local (`backend/contabilidad/CLAUDE.md`, `backend/reservas/CLAUDE.md`,
  `docs/SISTEMA_FACTURACION.md`, `docs/SISTEMA_CARRITO.md`) — los referencia. Indexado en `MANIFIESTO.md`
  §8. Responde directamente al miedo del dueño: antes no había un solo lugar para mirar "¿esto de dónde
  sale?", ahora sí.
- **Hallazgos priorizados (14 ítems, documentados con detalle en `SISTEMA_PLATA.md` — no duplicados acá):**
  el más severo es que `_enriquecer_pedido_con_total` (`routes/alquileres/core.py`) ignora `cobro_modo` en
  6 call-sites reales incluido el motor de facturación real (`services/facturacion/engine.py`) — una línea
  personalizada "fijo" (ej. flete) se multiplica igual por jornadas en el desglose mostrado/facturado,
  aunque `monto_total` persistido (lo que se cobra) sigue siendo correcto. Le siguen: mismo bug en el PDF
  de presupuesto; un `UndefinedColumn` real en `enviar_mail_factura` (`c.owner_email` no existe en
  `clientes`, debería ser `c.email`) que rompe siempre que se usa esa función; una división por cero en
  `reportes/liquidacion.py::filas_atribucion` que puede perder plata en silencio del reporte si todos los
  ítems de un pedido tienen subtotal 0; 3 lugares en el front que reimplementan cálculo de línea en vez de
  leer lo que ya devolvió el backend (2 de ellos ya divergidos entre sí); un bug dormido en el editor de
  pedido del portal cliente (mismo patrón que #405, inalcanzable hoy por un feature flag apagado); falta de
  lock de concurrencia en `reportes/cierres.py::cerrar_mes` (mismo patrón ya cerrado en `contabilidad`); y
  la **reconciliación confirmada 100% manual** — ni `reportes/reconciliacion.py` ni
  `contabilidad/queries/reconciliacion.py::reconciliar` corren en `jobs/scheduler.py` (el único scheduler
  in-process del repo, que solo corre recordatorios de retiro + cleanup de cuentas livianas), y no hay
  ningún badge/alerta en el dashboard admin — si nadie abre esa pantalla puntual, un desbalance puede
  persistir indefinidamente sin que nadie se entere. Es el gap de gobernanza más directo detrás del miedo
  original del dueño.
- **Lo que está confirmado BIEN hecho** (no solo ausencia de bug, para el panorama completo): comisiones
  con `validar_modelo` que fuerza sumar 100% con fallback seguro; `SALDADO_CTE` ya filtra pagos anulados;
  IVA en `Decimal` con `assert total==neto+iva`, calculado sobre el neto post-descuento; sin secretos
  hardcodeados en facturación; sin IDOR en la factura del cliente; `create_pedido_retry` persiste la plata
  de forma atómica; el cliente nunca decide su propio precio (2 caminos reales verificados); cotas de
  cantidad/descuento en múltiples capas espejadas; y `test_carrito_precio_efectivo.py` hace un source-scan
  real (no solo unit test) que blinda mecánicamente contra el drift de combos histórico (#635).
- **Consecuencias / próximos pasos.** Mergear #1181 con prioridad. El resto de los 14 hallazgos quedan
  priorizados en `SISTEMA_PLATA.md` a la espera de que el dueño decida el orden de implementación (no se
  arregló nada todavía en esta pasada — fue diagnóstico + manual, siguiendo el mismo patrón de la auditoría
  de `contabilidad/`: primero el mapa completo, después la rama de fixes). El supervisor marca un motor de
  plata nuevo sin entrada en la tabla "fuente única" de `SISTEMA_PLATA.md`, o un PR de fix de plata
  reportado como shippeado en `MEMORIA.md` sin verificar el merge real a `dev`/`main` primero.

### 2026-07-03 — `facturas.imp_neto/imp_iva/imp_total`: INTEGER → NUMERIC(12,2), dejan de truncar al centavo (#1209)

- **Contexto.** Bug de severidad media encontrado al auditar `services/facturacion` (línea de la auditoría
  cruzada de plata, decisión anterior). `services/facturacion/engine.py` calcula el neto/IVA/total EXACTOS
  al centavo en `Decimal` vía `arca_fe.comprobante.calcular_importes` (`neto = req.importe_neto.quantize(...)`;
  `iva = (neto * alicuota.pct / 100).quantize(...)`; `assert total == neto + iva`) — y esos son los valores
  que se le mandan a ARCA en `armar_fecae` (`emitir_factura`/`emitir_nota_credito`, ambas llaman
  `wsfe.solicitar_cae(fecae_payload)` con `_fmt(neto)`/`_fmt(iva)`/`_fmt(total)`, string con 2 decimales) y
  se codifican en el QR fiscal vía `armar_qr(..., importe_total=importes["total"], ...)` (RG4892) para
  obtener el CAE. Pero al armar el dict que se persiste en `facturas` (`imp_neto=neto_int, imp_iva=iva_int,
  imp_total=total_int`, con `neto_int = int(round(float(importes["neto"])))` y análogos), esos Decimal
  exactos se truncaban a peso entero — la tabla `facturas` seguía, por error, la convención de "enteros ARS"
  de `backend/contabilidad/` (2026-06-07), que es la convención correcta para la plata **interna** pero NO
  para un documento fiscal cuyo importe legal ya quedó fijado al centavo en ARCA.
- **Escenario de falla concreto (verificado con un test, no solo teórico).** Un pedido Factura A (RI) con
  `monto_total` (neto) = $1001 — un entero de pesos, pero NO múltiplo de 100. IVA 21% de 1001 = 210,21 (con
  centavos, aunque el neto no los tenga). ARCA autoriza y el QR codifica: neto 1001.00, IVA 210.21, TOTAL
  1211.21. La fila en `facturas` guardaba `imp_iva=210`, `imp_total=1211` (truncados) y el PDF impreso decía
  "IVA 21%: $210,00" / "Importe Total: $1.211,00" — **$0,21 por debajo** de lo que el CAE/QR realmente
  autorizaron. Pasa en cualquier factura cuyo neto no sea múltiplo de 100 (común con descuentos o precios no
  redondos) — no es un caso de borde raro.
- **Efecto secundario descubierto al leer `comprobante_pedido.py`.** `construir_comprobante_nc` (usada para
  anular con Nota de Crédito) reconstruye el importe de la NC leyendo el SNAPSHOT ya persistido de la factura
  original (`importe_neto = Decimal(original.imp_neto)`) — a propósito, para que la NC cancele exactamente lo
  facturado y no lo que el pedido diga "en vivo" (decisión 2026-06-29, test
  `test_construir_comprobante_nc_usa_snapshot_no_pedido_en_vivo`). Con `imp_neto` truncado, ese snapshot
  YA VENÍA MAL — la NC hubiera heredado el mismo redondeo. El fix de la columna corrige este camino gratis,
  sin tocar `comprobante_pedido.py`.
- **Decisión — fix mínimo, sin tocar el core de ARCA.** (1) `facturas.imp_neto`/`imp_iva`/`imp_total` pasan
  de INTEGER a NUMERIC(12,2) — en `database/schema.py::init_db()` (`CREATE TABLE` con el tipo nuevo para
  instalaciones frescas + un bloque `DO $$ ... ALTER COLUMN ... TYPE NUMERIC(12,2) USING ...::NUMERIC(12,2)`
  idempotente, guardado tras chequear `information_schema.columns.data_type = 'integer'`, para DBs
  existentes que corran `init_db()` sin pasar por Alembic) y en la migración nueva `h3i4j5k6l7m8` (mismo
  `ALTER COLUMN ... TYPE` sin guard — Alembic ya trackea si se aplicó; `downgrade()` sí usa `ROUND(...)` antes
  de volver a INTEGER, por si para entonces hay filas con centavos reales que perderían precisión al bajar).
  (2) `engine.py` deja de truncar: `neto_dec/iva_dec/total_dec = importes["neto"|"iva"|"total"]` directo,
  sin `int(round(float(...)))`, en los 2 call-sites (`emitir_factura` e `emitir_nota_credito`). (3) `repo.py`:
  el dataclass `Factura` y la firma de `insert_factura` cambian el type hint de `int` a `Decimal` en los tres
  campos (cosmético para type-checking; en runtime Python no lo exige, pero documenta el contrato real).
  (4) `pdf.py` **NO necesitó ningún cambio** — `_money`/`_plain` ya formatean con `f"{float(n):,.2f}"`, así
  que ya mostraban 2 decimales; solo mostraban "00" de centavos porque el valor guardado venía sin ellos.
  Verificado manualmente (`factura_html` con `imp_iva=Decimal("210.21")` → el HTML contiene literalmente
  "210,21", no "210,00") antes de descartar tocar ese archivo.
- **Por qué NUMERIC(12,2) y no cambiar el `int(round(...))` por otra cosa.** Se consideró dejar la columna
  INTEGER y solo redondear "mejor" en algún otro punto — descartado: el problema no es CÓMO se redondea, es
  QUE se redondea un documento fiscal cuyo importe legal ya es fraccionario por diseño (IVA discriminado).
  NUMERIC(12,2) (no NUMERIC sin precisión, no FLOAT — mismo criterio que `g1a2b3c4d5e6` para `descuento_pct`:
  FLOAT introduce error de punto flotante en plata) replica exactamente la precisión de 2 decimales que ARCA
  exige en `ImpNeto`/`ImpIVA`/`ImpTotal`. El `USING ...::NUMERIC(12,2)` (sin `ROUND`) en el `upgrade()` es
  seguro porque el valor de origen es INTEGER — no hay parte fraccionaria que perder al ampliar precisión (a
  diferencia de la migración inversa `g1a2b3c4d5e6`, que sí necesitaba `ROUND` porque iba de más a menos
  precisión). Precedente seguido para el patrón de dos capas: `g1a2b3c4d5e6_descuentos_float_a_numeric.py`
  (mismo tipo de bug — plata perdiendo precisión por el tipo de columna equivocado).
- **Verificación.** Test nuevo `tests/test_facturacion_centavos.py`: (a)
  `test_emitir_factura_persiste_centavos_exactos_no_trunca` arma un pedido RI con neto=$1001, mockea
  WSFE/DB (mismo patrón que `test_facturacion_engine.py`, sin red ni Postgres real), y verifica que lo
  persistido en `insert_factura` (`imp_neto`/`imp_iva`/`imp_total`) coincide EXACTO —
  `Decimal("1001.00")`/`Decimal("210.21")`/`Decimal("1211.21")`— con lo que el mismo test capturó en el
  payload `FECAESolicitar` mandado a ARCA (`det["ImpIVA"] == "210.21"`); (b)
  `test_pdf_muestra_centavos_no_redondea_a_peso_entero` renderiza `factura_html` con esos mismos valores y
  confirma que el HTML contiene "210,21"/"1.211,21" y NO contiene "210,00"/"1.211,00". Suite completa
  (2550 unit + 2457 con Postgres real vía `RESERVAS_DB_TEST=1`, excluyendo `test_catalogo_motor_shape.py`
  que ya falla igual en `origin/dev` sin este cambio — verificado clonando el repo limpio) y
  `test_alembic_upgrade_db.py` (`ALEMBIC_DB_TEST=1`, que corre `init_db()+upgrade head` contra una BD
  descartable) en verde; confirmado además a mano que re-correr `init_db()` sobre una tabla `facturas` ya
  existente con columnas INTEGER (simulando una BD vieja no migrada) las deja en NUMERIC(12,2) — el guard
  `DO $$` idempotente funciona. pyflakes limpio en los 5 archivos tocados.
- **Consecuencias.** Sin cambios de contrato público más allá de más precisión (el JSON de
  `/api/admin/facturas` y `/facturas/{id}/pdf` sigue devolviendo los mismos campos, ahora con centavos
  reales en vez de siempre ".00"). No afecta `backend/contabilidad/` ni ningún reporte que sume plata
  interna — `facturas` no es consumida fuera del paquete `services/facturacion/` + su route (verificado con
  `grep -rl facturas backend/`). El supervisor marca un `int(round(...))` reintroducido sobre
  `imp_neto`/`imp_iva`/`imp_total`, o un cambio de esta tabla que la vuelva a alinear con "enteros ARS" sin
  entender que es la excepción fiscal. PR sin mergear (rama `fix/factura-centavos-arca` → `dev`); issue #1209.

### 2026-07-02 — `reportes/liquidacion.py::filas_atribucion` perdía plata en silencio con `suma_items = 0`

- **Contexto.** Fase 5 de la hoja de ruta de plata (#1184; hallazgo #4 de la auditoría cruzada,
  `docs/SISTEMA_PLATA.md`). El prorrateo del `monto_total` entre los equipos de un pedido se hacía
  `al.monto_total * pi.subtotal::numeric / NULLIF(t.suma_items, 0)`. Si **todos** los ítems de un pedido
  tenían `subtotal = 0` (ej. un descuento del 100% aplicado a nivel ítem, no al pedido completo) —
  `suma_items` daba 0, `NULLIF` lo convertía en `NULL`, y el `monto` resultante era `NULL` para cada
  ítem. En `agregar()` (la función pura que suma todo), `float(f["monto"] or 0)` trata `NULL` como 0 →
  esos pesos **desaparecían del reporte sin ningún error ni warning**. Ningún chequeo de reconciliación
  existente (ni `reportes/reconciliacion.py` ni `contabilidad/queries/reconciliacion.py`) lo detectaba,
  porque ambos comparan cosas distintas (pagado vs. total del pedido, no el reporte de liquidación
  agregado vs. la suma de `monto_total` de los pedidos incluidos).
- **Decisión — fallback de reparto parejo.** `tot` CTE suma también `COUNT(*) AS cant_items`. La query
  pasa a un `CASE`: si `suma_items = 0`, el monto de cada ítem es `monto_total / cant_items` (reparto
  **en partes iguales** entre los ítems del pedido); si no, sigue el prorrateo proporcional de siempre.
  Se descartó "atribuir todo a Rambla por default" (mencionado como opción en el plan original) porque
  no hay ninguna base real para decidir que la plata "sin subtotal" le pertenece a Rambla en vez de a
  los dueños de los equipos involucrados — repartir parejo entre los ítems reales del pedido es el
  fallback más neutral y defendible cuando no hay proporción real que usar.
- **Why.** La regla dura del sistema de plata es que ningún número puede desaparecer en silencio — un
  `NULLIF` que colapsa a 0 sin un camino alternativo viola eso. El fix es puramente técnico (garantizar
  que la suma siempre cuadre); no cambia el reparto en el caso común (`suma_items > 0`), que sigue
  siendo byte-idéntico.
- **Consecuencias.** `test_reportes_liquidacion_db.py::test_suma_items_cero_no_pierde_plata` (Postgres
  real, aislado de la fixture `setup` compartida para no alterar sus totales/aserciones existentes):
  un pedido con 2 ítems `subtotal=0` y `monto_total=30000` confirma que el reporte de junio sigue
  incluyendo esos 30000 (total agregado + suma de `por_beneficiario`). Suite completa 2548 passed / 183
  skipped (sin regresiones); `test_reportes_liquidacion.py` (28 tests puros/DB) también en verde. El
  supervisor marca cualquier prorrateo de plata con `NULLIF`/división que pueda colapsar a `NULL`/0 sin
  un fallback explícito que garantice que el total nunca se pierda. Rama `fix/liquidacion-division-cero`
  → PR scoped (sin mergear, hoja de ruta); tracking #1184.

### 2026-07-02 — Fase 3+6: lock de concurrencia en `reportes/cierres.py` + rate limit en `routes/reportes.py`

- **Contexto.** Últimas dos fases pendientes de la hoja de ruta de plata (#1184; hallazgos #8 y #10 de
  la auditoría cruzada en `docs/SISTEMA_PLATA.md`). `reportes/cierres.py::cerrar_mes`/`reabrir_mes` no
  tenían ningún candado de concurrencia — el mismo tipo de carrera que se cerró en `contabilidad`
  (2026-07-02, `_exigir_mes_abierto`/`_lock_mes`) seguía sin mitigar acá: un `cerrar_mes` podía leer el
  reporte de un mes en T0 y commitear su foto DESPUÉS de que un pago (`alquiler_pagos`) de ese mismo mes
  se insertara en otra transacción, dejando una foto que no incluye ese pago. Y `routes/reportes.py`
  tenía sus 3 endpoints de escritura (enviar mail, cerrar/reabrir mes) sin `@limiter.limit` — mismo gap
  ya cerrado en `contabilidad.py`/`pagos.py`.
- **Decisión — lock de concurrencia (Fase 3).** `reportes/cierres.py` gana `_lock_mes(conn, mes)`
  (`pg_advisory_xact_lock`, mismo parseo `'YYYY-MM'`→`YYYYMM` que
  `contabilidad/commands/movimientos.py::_lock_mes`), llamada al inicio de `cerrar_mes` y `reabrir_mes`.
  **Namespace nuevo y separado** — `_ADVISORY_NS_REPORTES_MES = 5390421` — NO reusa
  `_ADVISORY_NS_CONTAB_MES` (5390420): el cierre de liquidación (reparto/comisiones entre dueños) y el
  cierre contable (cajas/movimientos) son operaciones independientes sobre invariantes distintos;
  compartir namespace bloquearía sin necesidad un cierre por el otro (ej. cerrar el mes contable no
  debería esperar a que termine de cerrarse la liquidación de ese mismo mes).
- **Decisión — rate limit (Fase 6).** `routes/reportes.py` importa `limiter`/`ADMIN_WRITE_LIMIT` de
  `rate_limit.py` (ya existente) y agrega `@limiter.limit(ADMIN_WRITE_LIMIT)` a los 3 endpoints de
  escritura: `enviar_reporte_mail` (POST enviar-mail), `cerrar_mes_liquidacion` (POST cierres/{mes}),
  `reabrir_mes_liquidacion` (DELETE cierres/{mes}).
- **Why.** El lock de `reportes/cierres.py` no reemplaza el candado preventivo de `contabilidad` (ese
  protege movimientos internos; este protege el reporte de liquidación) — son dominios distintos que
  necesitan su propio candado, mismo patrón, sin compartir key space. El rate limit cierra el mismo gap
  de superficie de ataque que ya se había cerrado en el resto de los routes de escritura de plata.
- **Consecuencias.** Nuevo test de concurrencia real con Postgres (no solo en teoría, mismo criterio
  que la auditoría de `contabilidad`): `test_reportes_cierres_db.py::test_lock_serializa_cerrar_mes_concurrente`
  — dos conexiones reales + `threading.Event`, una toma el lock del mes y lo retiene, la otra intenta
  `cerrar_mes` del mismo mes y debe quedar bloqueada hasta que la primera libere (commit); se verifica
  el orden real de eventos, no solo ausencia de errores. Suite completa 2548 passed / 184 skipped (sin
  regresiones); `test_reportes_cierres_db.py` completo (4 tests) en verde. El supervisor marca: (1)
  cualquier escritura nueva en `reportes/cierres.py` que no pase por `_lock_mes`; (2) reusar
  `_ADVISORY_NS_CONTAB_MES` en vez de un namespace propio para un candado de otro dominio de plata; (3)
  un endpoint de escritura nuevo en `routes/reportes.py` sin `@limiter.limit`. Rama
  `fix/reportes-lock-rate-limit` → PR scoped (sin mergear, hoja de ruta); tracking #1184.

### 2026-07-02 — `enviar_mail_factura` roto por 2 bugs encadenados (columna inexistente + kwarg inexistente)

- **Contexto.** Fase 4 de la hoja de ruta de plata (`services/finanzas_flujo/`, ver entradas anteriores de
  esta misma fecha). El hallazgo #3 de la auditoría cruzada (`docs/SISTEMA_PLATA.md`) marcaba
  `routes/facturacion.py::enviar_mail_factura` con un `UndefinedColumn`: la query consultaba `c.owner_email`,
  columna que no existe en `clientes` (vive en otras tablas — `passkey_credentials`/`auth_sessions` tienen
  su propio `owner_email` para otro propósito). La función rompía **siempre** que se invocaba.
- **Decisión.** Fix directo: `SELECT c.owner_email, ...` → `SELECT c.email, ...` (+ las referencias
  derivadas de esa fila, `row["owner_email"]` → `row["email"]`).
- **Segundo bug encontrado al escribir el test de regresión.** Al ejercitar la función completa por primera
  vez (el test viejo de `test_facturacion_routes.py` nunca cubría este endpoint — gap de test real, no solo
  de código), apareció un **segundo bug** nunca antes ejecutado, escondido detrás del primero: la construcción
  del adjunto usaba `Attachment(filename=filename, content=pdf_bytes, content_type="application/pdf")`, pero
  el dataclass real (`services/email/base.py::Attachment`) tiene el campo `mimetype`, no `content_type` — un
  `TypeError` en cuanto se corregía el primer bug. Confirmado contra los otros 3 usos reales de `Attachment`
  en el repo (`routes/reportes.py`, `routes/alquileres/documentos.py`, `routes/alquileres/core.py`), los tres
  usan `mimetype`. Fix: `content_type=` → `mimetype=`.
- **Why.** Sin arreglar los dos, la función seguía completamente rota — el primer fix por sí solo no era
  suficiente para dejarla funcionando, solo movía el punto de falla más adelante. Refuerza con un corolario
  concreto la decisión _2026-06-22 — Los hallazgos de una auditoría son hipótesis_: confirmar un fix no es
  solo confirmar que la línea señalada compila, es ejecutar la función **completa** hasta el final — un bug
  puede estar tapado por otro que se ejecuta primero.
- **Consecuencias.** `test_facturacion_routes.py` suma `_FakeRow`/`_FakeConnConEmail` (fake de conexión con
  `execute().fetchone()` para simular la fila de `clientes`) + `test_enviar_mail_factura_no_rompe_con_undefined_column`
  (ejercita la función completa: SELECT → PDF → mail, confirma que no rompe y que el destinatario es el email
  real) + `test_enviar_mail_factura_400_si_sin_email` (cliente sin email → 400, no un crash). 22/22 tests de
  `test_facturacion_routes.py` en verde; suite completa 2720 (mismos 6 fallos preexistentes no relacionados
  de `test_catalogo_motor_shape.py`). El supervisor marca un fix de columna/kwarg que no ejercite el código
  que queda DESPUÉS de esa línea — un segundo bug latente puede estar escondido detrás del primero. Rama
  `fix/facturacion-owner-email` → PR scoped (sin mergear, hoja de ruta); tracking #1184.

### 2026-07-03 — El endpoint de modificación de pedido del cliente aplica el mismo gate de catálogo que la creación (M6, #1209)

- **Contexto.** Hallazgo M6 de la auditoría cruzada de plata (#1209, 52 agentes: 9 finders + verificación
  adversarial en 2 pasadas): `cliente_crear_pedido` (creación) resuelve el precio de cada ítem vía la
  puerta del carrito `services/carrito/readiness.py::precios_catalogo_para_reserva`, que además de
  resolver plata aplica un gate de seguridad — solo equipos `visible_catalogo=1` con precio definido.
  `cliente_modificar_pedido` (`routes/cliente_portal/solicitudes.py`, el endpoint de modificación de un
  pedido ya existente) resolvía el precio de un ítem nuevo con `_equipo_precio_catalogo` — que SOLO
  resuelve plata (`precio_jornada_efectivo`), sin ningún chequeo de visibilidad — así que un cliente podía,
  vía `POST /api/cliente/pedidos/{id}/modificacion` sobre un pedido en `presupuesto` o `confirmado`,
  agregar un equipo con `visible_catalogo=0` (oculto del catálogo público) o el recurso interno del Estudio
  (`es_recurso_interno=TRUE`, el "centinela" que modela el espacio físico — ver _El Estudio (2026-05-27)_)
  — reservando stock de un recurso que el negocio nunca ofreció públicamente. En `confirmado` el hueco era
  peor: la propuesta quedaba pendiente para que un admin la apruebe a ciegas, sin ver que el equipo nunca
  debió ofrecerse.
- **Decisión.** Se extrajo el gate a una función única, `services/carrito/readiness.py::equipo_visible_catalogo(conn,
  equipo_id)`, que valida: vivo (`eliminado_at IS NULL`), `visible_catalogo=1`, NO `es_recurso_interno`, y
  precio definido — lanza `HTTPException(404)` si falla cualquiera. `precios_catalogo_para_reserva`
  (creación) ahora llama a esta función en vez de tener su propio SELECT inline; `cliente_modificar_pedido`
  la llama ANTES de resolver el precio, pero SOLO para ítems que no estaban ya en el pedido
  (`it.equipo_id not in precios`) — un ítem ya reservado (frozen) no se re-gatea aunque se haya ocultado
  después, para no invalidar algo ya confirmado. El chequeo corre ANTES del branch `presupuesto`/
  `confirmado`, así que en `confirmado` rechaza la propuesta de una vez en vez de dejarla pendiente. El
  path admin (`admin_responder_solicitud`, que también llama `_equipo_precio_catalogo`) NO se tocó a
  propósito: el admin puede legítimamente agregar cualquier equipo — visible o no — igual que
  `PUT /alquileres/{id}/items`; documentado explícitamente en el docstring para que no se "arregle" por
  error en el futuro.
- **Why.** Extraer a una función única (en vez de solo copiar el chequeo dentro de `solicitudes.py`) sigue
  el patrón motor-único del repo (_`backend/services/carrito/` (2026-06-29)_): un solo lugar decide "qué es
  un producto real del catálogo", consumido por los dos caminos que persisten plata de cliente (crear +
  modificar). De paso se sumó `eliminado_at IS NULL` al gate — el SELECT viejo de la creación solo
  chequeaba `visible_catalogo=1 AND precio_jornada IS NOT NULL`, y el soft-delete de un equipo
  (`DELETE /equipos/{id}`) NO baja `visible_catalogo` a la vez (confirmado en `routes/equipos/core.py`) —
  así que un equipo soft-deleted con `visible_catalogo` sin bajar colaba en AMBOS caminos antes de este
  fix (no solo en la modificación). `es_recurso_interno=FALSE` es defensa en profundidad (hoy redundante
  en la práctica — el centinela nace con `visible_catalogo=0` — pero no depende de que ese dato nunca
  cambie).
- **Consecuencias.** Ningún cambio de contrato público para el uso legítimo (agregar un equipo visible
  nuevo al pedido sigue funcionando igual; un ítem ya frozen tampoco se ve afectado si se oculta después).
  Regresión contra Postgres real (`tests/test_cliente_modificar_pedido_gate_db.py`, 4 tests): rechaza un
  equipo oculto nuevo, rechaza el recurso interno, acepta un equipo visible nuevo (control), y no re-gatea
  un ítem ya frozen aunque se oculte después — confirmado manualmente que los 2 tests de rechazo fallan
  (200 en vez de 404) contra el código viejo (revertido temporalmente con `git stash` para verificar) antes
  de aplicar el fix. Hallazgo de la auditoría cruzada de plata (#1209); el resto de los hallazgos (M1-M5,
  L1-L3) quedan en ramas propias, sin mergear, mismo criterio "PR como hoja de ruta".

### 2026-07-02 — `backend/services/finanzas_flujo/` = módulo orquestador de plata (Fase 1: desglose de pedido)

- **Contexto.** Tras ver los 14 hallazgos + el descubrimiento de #1181, el dueño pidió una hoja de ruta
  en fases y, explícitamente, que "el proceso de la plata" fuera **una implementación real y
  reproducible** — no un documento que describa cómo se hace, sino un **módulo orquestador en el
  backend** que sea el único punto de entrada para "preguntar algo de plata", para que un consumidor
  nuevo no tenga que saber a cuál de los 6 motores llamar ("que no sean un montón de referencias
  cruzadas"). Se diseñó como facade de solo lectura, mismo patrón que `services/carrito/` (que ya
  orquesta lectura sobre reservas/precios/contenido). Nombre elegido con el dueño tras descartar
  "plata" (se quedaba corto — no capta que abarca liquidación/facturación) y "tesorería" (suena a solo
  caja): **`finanzas_flujo`**. El manual `docs/SISTEMA_PLATA.md` se renombró a
  `docs/SISTEMA_FINANZAS_FLUJO.md` (git mv, preserva historia) para mantener el patrón 1:1 manual↔módulo
  ya establecido (`SISTEMA_CARRITO.md`↔`services/carrito/`, `SISTEMA_CONTENIDO.md`↔`services/contenido/`).
- **Decisión — diseño del facade.** `backend/services/finanzas_flujo/` **nunca escribe** — las
  mutaciones siguen pasando por cada motor directo (`create_pedido_retry`, `contabilidad.commands.*`,
  rutas de `alquiler_pagos`), porque cada uno tiene su propia validación/candado/lock que no debe
  saltearse. Cada función del facade delega 1:1 al motor dueño (comentario explícito "OWNA: nada,
  delega en X" en cada una) — nunca reimplementa. Migración gradual: los consumidores existentes se
  migran de a uno, en el mismo PR en que ya se estaba tocando ese archivo por otra razón — no se abre
  un PR aparte solo para "migrar imports" sin otro motivo (sería refactor sin necesidad real).
- **Decisión — Fase 1 (primera pieza implementada, no solo diseñada).**
  `finanzas_flujo/pedido.py::desglose_de_pedido(conn, pedido)` es la nueva fuente única del desglose de
  plata de un pedido (bruto/descuento/neto/IVA por línea) — arregla el bug de `cobro_modo` encontrado en
  la auditoría: `_enriquecer_pedido_con_total` (`routes/alquileres/core.py`) armaba los ítems para
  `calcular_total` SIN pasarle `cobro_modo`, así que una línea personalizada `cobro_modo='fijo'` (ej.
  flete, #805) se multiplicaba igual por jornadas al mostrar/facturar (aunque `bruto_linea`, la función
  que `calcular_total` llama por ítem, ya sabía manejarlo bien — el bug era de "quién arma el input", no
  de la fórmula). El fix corrige de un solo punto los 6 call-sites reales: `_get_alquiler_detail`
  (detalle admin), `routes/alquileres/documentos.py` (PDF/mail), `routes/cliente_portal/documentos.py` +
  `pedidos.py` (portal cliente), y **`services/facturacion/engine.py`** (el motor de facturación real —
  el de mayor impacto, corrige lo que efectivamente se factura). `_enriquecer_pedido_con_total` se dejó
  como wrapper de compatibilidad (delega en la fachada) para no tocar los 6 call-sites en este PR —
  código nuevo debería importar `desglose_de_pedido` directo. De paso, `services/facturacion/engine.py`
  (un `service`) dejó de importar de `routes.alquileres` (un `route`) — dependencia arquitectónicamente
  invertida que ya no hace falta.
- **Fix espejo en el PDF.** `pdf_templates.py::_pedido_html`/`_sum_bruto` reimplementaban la
  multiplicación `precio_jornada × cantidad × jornadas` desde cero (sin `cobro_modo`) — no pasaban por
  `_enriquecer_pedido_con_total` para el detalle de línea. Nuevo helper `_bruto_item_pdf(it, j)` (espeja
  `bruto_linea` sin importar `services.precios` completo — el PDF agrega distinto por componente de
  combo, que `bruto_linea` no contempla tal cual) usado en ambos puntos.
- **Fix espejo en el front admin.** `PedidoPageCards.tsx` (ignoraba `cobro_modo`) y
  `PedidoPageHelpers.tsx` (correcto, comentario decía "espeja bruto_linea del backend") ya habían
  divergido sobre el mismo tipo `DraftItem`. Extraído `subtotalDraftItem(it, jornadas)` a
  `usePedidoDraft.ts` (hogar del tipo) — ambos componentes importan la misma función; no pueden volver a
  divergir porque ya no tienen cada uno su propia fórmula.
- **Fuera de esta fase, a propósito.** `CartDrawerView.tsx`/`CartMiniBarView.tsx` (carrito público)
  también recalculan localmente (`pricePerDay` cacheado) en vez de leer `lineaPorEquipo()` — pero el
  carrito público hoy NO tiene líneas `cobro_modo='fijo'` (feature exclusiva del builder admin, #805), y
  migrarlo requiere threadear el objeto `Cotizacion` completo por 3 call-sites (cambio de mayor alcance).
  Queda documentado como fase futura opcional en `SISTEMA_FINANZAS_FLUJO.md`, no en esta hoja de ruta.
- **Candados.** `test_finanzas_flujo_pedido.py` (unit, 5 casos: línea jornada, línea fija, mezcla,
  default sin `cobro_modo`, mutación in-place) + `test_finanzas_flujo_source_scan.py` (verifica que
  `pdf_templates.py` usa `_bruto_item_pdf` y que `services/facturacion/engine.py` importa la fachada, no
  `routes.alquileres`) + `test_pdf_helpers.py::TestBrutoItemPdf` (4 casos). No se agregó test de
  componente en frontend (sin infraestructura de Vitest en el repo hoy) — la garantía ahí es estructural
  por construcción (misma función compartida, no puede divergir).
- **Consecuencias.** Suite completa en verde (2717 tests, +26 nuevos). `pyflakes`/`eslint`/`tsc --noEmit`
  limpios en los archivos tocados. Rama aislada `feature/finanzas-flujo-fase1` (PR sin mergear, hoja de
  ruta); tracking #1184 (Fase 3, continúa tras la auditoría cruzada de plata).

### 2026-07-02 — Fase 2 (última): reconciliación proactiva — mail al dueño + chequeo `desglose_divergente`

- **Contexto.** Última fase de la hoja de ruta de plata (#1184). El semáforo de reconciliación era
  **100% manual**: `reportes/reconciliacion.py::reconciliar` y
  `contabilidad/queries/reconciliacion.py::reconciliar` solo se consultaban si alguien abría
  `/admin/reportes`/`/admin/contabilidad` a mirar — el gap de gobernanza más directo detrás del miedo
  original del dueño ("no sé desde dónde se gobierna cómo funciona la plata"). Antes de esta fase, la
  pregunta "¿un pedido confirmado puede desincronizarse de su propio desglose?" (el patrón general del
  bug #405) no tenía ningún chequeo automático — dependía de que alguien notara un reporte puntual raro.
- **Decisión — semáforo unificado.** `services/finanzas_flujo/reconciliacion.py::estado(conn)` (nuevo
  submódulo de la fachada, tercero tras `pedido.py`) une los dos `reconciliar()` existentes en un solo
  `{ok, reporte, contabilidad}` — `ok` es el AND de ambos. **No reimplementa ningún chequeo**: cada
  función delega 1:1, mismo patrón que `pedido.py` (Fase 1).
- **Decisión — job de alerta proactiva.** `jobs/reconciliacion.py::chequear_reconciliacion_y_alertar()`
  corre 1×/día desde el mismo thread in-process del scheduler (`jobs/scheduler.py`, junto a
  `enviar_recordatorios_retiro`/`purgar_cuentas_livianas_stale` — mismo mecanismo de "última fecha
  corrida" que ya acota a 1×/día, sin necesitar un rate-limit aparte): si `estado(conn)["ok"]` es
  `False`, arma un resumen legible del detalle y manda un mail a cada `settings.admin_emails` vía
  `send_raw_email` (mail transaccional one-off, mismo mecanismo que ya usa
  `routes/reportes.py::enviar_reporte_mail`). El job **solo avisa, nunca repara** — la corrección sigue
  siendo manual, vía el dashboard admin. Nunca propaga: un error en `estado()` o en el envío no debe
  tumbar el scheduler (mismo contrato que los otros dos jobs del thread).
- **Decisión — nuevo chequeo `desglose_divergente`.** Se agrega a `reportes/reconciliacion.py::reconciliar`
  (no a la fachada — vive donde viven los otros 4 chequeos del reporte). Para cada pedido activo (no
  cancelado, `monto_total > 0`, dentro del clean start), recalcula el desglose con el precio de línea
  YA PERSISTIDO de cada ítem (vía `finanzas_flujo.pedido.desglose_de_pedido` — NO el precio de catálogo,
  mismo criterio que el fix de #1181) y lo compara contra `monto_total`. Si divergen, el pedido se
  lista. **Se descartaron** los dos chequeos que el dueño propuso inicialmente en la conversación de
  diseño ("facturado == cobrado" y "ganancia del mes == suma recalculada"): el primero viola
  devengado≠percibido a propósito (`contabilidad/CLAUDE.md`); el segundo se calcula al vuelo sin
  persistirse dos veces, así que no tiene riesgo de drift por construcción — agregar un chequeo ahí
  sería ruido sin cazar nada real. El único chequeo con valor real era éste: es la red genérica que
  hubiera cazado el patrón de #405 sin depender de que el dueño notara un reporte puntual.
- **Why.** Un job que solo lee y notifica es de bajo riesgo (no toca ningún camino de escritura de
  plata) — la corrección la sigue haciendo un humano informado, no el sistema solo. El chequeo nuevo usa
  la MISMA fuente que ya usan los 6 consumidores reales del desglose (Fase 1), así que no puede
  divergir de lo que el dueño ve en pantalla.
- **Consecuencias.** `test_finanzas_flujo_reconciliacion.py` (3 tests: la fachada une bien los dos
  semáforos, cualquiera de los dos en `False` tumba el `ok` global). `test_jobs_reconciliacion.py`
  (5 tests: no manda mail si `ok=True`; manda uno a cada admin si `ok=False`; un envío fallido no
  propaga; el resumen HTML incluye los chequeos con cantidad positiva y no rompe sin ítems).
  `test_reportes_liquidacion_db.py::test_reconciliacion_caza_desglose_divergente_del_pedido` (Postgres
  real: un pedido con `monto_total` deliberadamente desincronizado de su desglose recalculado aparece
  en `desglose_divergente`). Suite completa 2565 passed / 177 skipped (sin regresiones). El supervisor
  marca: un chequeo de reconciliación nuevo fuera de la fachada `finanzas_flujo`, un job de este tipo
  que repare en vez de solo avisar, o un mail de alerta que no pase por `send_raw_email`. Rama
  `feature/finanzas-flujo-fase2-reconciliacion` (sobre `feature/finanzas-flujo-fase1`, que sigue sin
  mergear — PR scoped, sin mergear, hoja de ruta); tracking #1184 — **última fase de la iniciativa**.

### 2026-07-03 — `routes/estadisticas.py`: las agregaciones leen `monto_total`, no reconstruyen el descuento (#1209)

- **Contexto.** Uno de los 14 hallazgos de la auditoría cruzada de plata (2026-07-02, severidad media):
  `routes/estadisticas.py` tenía ~6 queries que, en vez de leer `alquileres.monto_total` (el neto ya
  correcto, persistido por `_recalcular_total_pedido` con el descuento GANADOR aplicado), reconstruían el
  ingreso a mano con `subtotal * (1 - COALESCE(descuento_pct, 0) / 100.0)`. `descuento_pct` en la tabla
  `alquileres` **solo guarda el descuento de CLIENTE** — nunca el de JORNADAS, aunque este último haya sido
  el ganador (`services/precios.descuento_aplicable = max(descuento_cliente_pct, descuento_jornadas_pct)`,
  no la suma). En un alquiler de varios días con 0% de descuento de cliente pero un % por jornadas (el caso
  común), la reconstrucción devolvía el BRUTO en vez del NETO realmente cobrado.
- **Escenario de falla concreto** (el que motivó el fix): 1 equipo a $10.000/día × 7 jornadas, cliente 0%
  propio + 10% por jornadas (ganador) → se cobra $63.000 real (en `monto_total`), pero
  `70.000 × (1 - 0/100) = $70.000` — **$7.000 de más**, que escala con cada alquiler multi-día del
  histórico. Y en la MISMA pantalla, "Top clientes"/"Clientes recurrentes" ya usaban `p.monto_total`
  directo (correcto) — dos números del mismo pedido no cuadraban entre sí.
- **Por qué no alcanza con leer `monto_total` en todos lados por igual.** Es una columna a nivel PEDIDO,
  no por ítem. Las agregaciones a nivel pedido (`totales`, `por_mes`, `mejor_peor_mes`) pueden leerlo
  directo — pero había que sacar el `JOIN alquiler_items` que tenían (si no, `monto_total` se multiplica
  por cada línea del pedido). Las agregaciones a nivel ÍTEM (`top_equipos`, agrupado por equipo; `por_dueno`,
  agrupado por `equipos.dueno`) necesitan saber "cuánto aportó cada línea" de un pedido con potencialmente
  varios equipos de dueños distintos — ahí no alcanza con el número del pedido entero. Solución: **prorratear**
  `monto_total` según la participación de cada línea en el `subtotal` (bruto) del pedido — el MISMO patrón ya
  usado y confiable en `reportes/liquidacion.py::filas_atribucion` (`SALDADO_CTE` + prorrateo por subtotal),
  ahora factorizado en un fragmento SQL compartido `_PRORRATEO_CTE` (misma técnica de composición por
  f-string que `SALDADO_CTE`) para no repetir la CTE en `top_equipos` y `por_dueno`.
- **`mejor_peor_mes` de paso simplificado.** Las 4 subqueries (mejor mes/total, peor mes/total) repetían la
  misma fórmula rota 4 veces; se consolidaron en una única CTE `por_mes_full` (con `monto_total`, sin join a
  ítems) referenciada 4 veces — menos código Y arregla el bug de una sola vez. Mismo universo que antes
  (todo el histórico, sin el `LIMIT 24` que sí tiene `por_mes`).
- **Universo de pedidos preservado.** Al sacar el `JOIN alquiler_items` de `totales`/`por_mes`/`mejor_peor`
  no cambia qué pedidos cuentan: todo pedido en estado `confirmado`/`finalizado`/`retirado` tiene ≥1 ítem
  por invariante de creación (`if not data.items and data.estado != "borrador"` en
  `routes/alquileres/core.py`), así que el join solo estaba ahí por la fórmula rota, no como filtro real.
- **NO se reconstruye el descuento en ningún camino** — ni con `descuento_pct` solo (el bug), ni con
  `GREATEST(descuento_pct, descuento_jornadas_pct)` (tentador pero redundante: `monto_total` YA tiene el
  número correcto, calcularlo de nuevo es la misma clase de bug con otra fórmula). `monto_total` es la
  fuente única del neto, se lee o se prorratea, nunca se recalcula.
  Consecuencia: cambio SQL-only en `backend/routes/estadisticas.py`, sin tocar el motor de precios ni el
  esquema.
- **Regresión:** `backend/tests/test_estadisticas_db.py` (Postgres real, opt-in `RESERVAS_DB_TEST=1`) —
  reproduce el escenario (descuento por jornadas ganador + descuento de cliente en 0%) y verifica que
  `totales`/`por_mes`/`top_equipos`/`por_dueno` devuelven el NETO (`monto_total`), no el bruto reconstruido;
  se confirmó que el test FALLA contra la fórmula vieja (revertido temporalmente) antes de mergear el fix.
  No había tests previos de `estadisticas.py` que asumieran la fórmula rota.
- El supervisor marca cualquier query nueva de estadísticas/reportes que reconstruya
  `subtotal * (1 - descuento_pct/100)` (o cualquier variante que recalcule el descuento) en vez de leer
  `alquileres.monto_total` directo o prorrateado.
- **Adenda 2026-07-04 — devengado, no cobrado.** El dueño preguntó si la sobreestimación podía venir de
  un descuento no contado (ya arreglado arriba) y, al revisar la pantalla completa, surgió una segunda
  pregunta: ¿"Facturado total" debería mostrar lo efectivamente cobrado en vez del valor del pedido? El
  dueño resolvió el criterio explícitamente: **"debería ser lo devengado todo lo de estadísticas"** — la
  misma línea "facturado" que ya usa la cascada del P&L de Reportes (_2026-06-28 — La ganancia de Rambla
  descuenta la comisión de los dueños_: `facturado − comisiones a dueños − gastos = ganancia`), no
  `monto_pagado`/cobros reales (`alquiler_pagos`), que Estadísticas no toca. Consecuencia: **ningún
  cambio de código** — las 7 agregaciones (`totales`/`por_mes`/`top_equipos`/`top_clientes`/`por_dueno`/
  `clientes_recurrentes`/`mejor_peor_mes`) ya eran consistentemente devengadas tras el fix de arriba; esto
  solo deja escrito el criterio para que no se re-litigue. Si a futuro se quisiera un "cobrado real"
  (`monto_pagado`), sería una tarjeta/métrica NUEVA y explícitamente rotulada, no un reemplazo de
  "Facturado total".
- **Refinado el mismo día — solo `finalizado`.** Tras la adenda de arriba, el dueño precisó más: "solo de
  finalizados, eso son las estadísticas, solo de pedidos finalizados y devengados" — Estadísticas no debe
  contar negocio `confirmado`/`retirado` (todavía puede cancelarse o modificarse), solo pedidos YA
  cerrados. **Esta vez sí hubo cambio de código:** las 7 queries de `compute_estadisticas`
  (`backend/routes/estadisticas.py`) pasan de `WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')`
  a `WHERE p.estado = 'finalizado'` — mismo criterio en las 7, sin excepciones (la función es fuente única
  compartida con la sección "Resumen general" del PDF de Reportes, `backend/pdf.py::_resumen_general_html`,
  que también ajustó sus 2 textos: "ingreso confirmado" → "ingreso finalizado"; "histórico de pedidos
  confirmados, retirados y finalizados" → "histórico de pedidos finalizados"). El invariante "todo pedido
  en este filtro tiene ≥1 ítem" se preserva (`finalizado` es subconjunto del set viejo). Regresión nueva:
  `test_estadisticas_excluye_confirmado_y_retirado` (Postgres real) — inserta un pedido `confirmado` y uno
  `retirado` con montos no-cero y verifica que NO mueven `totales`/`top_equipos`/`por_dueno`. Suite
  completa verde (2769 tests) tras el cambio.

### 2026-07-03 — Factura y mail de "pedido creado": línea de bonificación/descuento visible (M5+L1, #1209)

- **Contexto.** Issue #1209 ("Iniciativa: 9 hallazgos de la auditoría del régimen de plata") — auditoría
  multi-agente (52 agentes: 9 finders + verificación adversarial en 2 pasadas) sobre `dev` + los 5 PRs de
  fixes ya aplicados (#1203-1207), a pedido del dueño ("que no calcule mal, que sea seguro... no haber
  dobles sumas ni nada"). Veredicto general de esa auditoría: el núcleo (precio → cotización →
  `monto_total` congelado → pagos → liquidación → contabilidad) está bien construido —
  `cotizado == cobrado` blindado por construcción—; los 9 hallazgos están en superficies de
  **display/derivación** que recalculan en vez de leer la fuente única. Esta entrada cierra 2 de los 9
  (M5 + L1, agrupados porque comparten exactamente el mismo criterio de fix — "Convención" del issue: M5+L1
  van en un solo PR).
- **M5 (medio) — Factura.** `services/facturacion/pdf.py::_conceptos` mostraba, para cada línea, el
  BRUTO (`it["subtotal"]`, sin descuento) y un campo `bonif` (`% Bonif.` en la grilla clásica AFIP/ARCA)
  **hardcodeado en `"0,00"`**. El "Importe Neto Gravado"/"Importe Total" declarado (`factura.imp_neto`)
  sí tenía el descuento aplicado (viene de `pedido["monto_total"]`, neto persistido). Con 2 ítems de $500
  (=$1.000 bruto) + 10% de descuento → `imp_neto`=$900: la Factura mostraba dos líneas de $500 (suman
  $1.000) y un total de $900, sin ninguna línea de -$100 que explicara la diferencia — el comprobante no
  cerraba consigo mismo. Como el descuento por jornadas es automático en cualquier alquiler de varios
  días, esto afectaba al caso común, no a un edge case.
- **Investigación previa al fix — ¿el `%Bonif.` es un campo real de AFIP/ARCA?** Se revisó `arca_fe/`
  (el módulo que arma el `ComprobanteRequest` y llama al WSFE real): no hay ningún concepto de
  bonificación por línea en la llamada SOAP — `construir_comprobante` manda un `importe_neto` plano para
  todo el comprobante, sin desglose por ítem. La columna "% Bonif." es puramente del LAYOUT del PDF (una
  réplica visual del formato clásico impreso AFIP/ARCA, que sí trae esa columna en su grilla de 7
  columnas: Código · Producto · Cantidad · U. Medida · Precio Unit. · **% Bonif.** · Subtotal) — no
  restringe nada del lado fiscal real. Conclusión: repartir el descuento por línea (llenando esa columna
  ya presente en el layout, en vez de agregar una fila global aparte) es la opción MÁS fiel al formato
  real, porque el layout ya tiene el lugar pensado para eso — no una improvisación.
- **Fix.** `_conceptos` reparte el descuento total proporcionalmente al bruto de cada línea, con el
  remanente de redondeo absorbido en la ÚLTIMA línea (evita que la suma quede a centavos de distancia del
  total declarado por acumulación de redondeos independientes por línea). El total a repartir se calcula
  como `bruto_de_las_líneas − factura.imp_neto` (no `pedido["bruto"] − pedido["descuento_monto"]`, que son
  campos en VIVO) — así el desglose cierra también al mostrar una Nota de Crédito, cuyos importes vienen
  frozen del comprobante original y pueden no coincidir con el pedido si este cambió después de facturar
  (mismo principio que ya usa `construir_comprobante_nc`, que tampoco recalcula del pedido en vivo). Cada
  línea ahora expone: `bonif` = "% Bonif." real de esa línea, `subtotalFmt`/`importeStr` = el NETO
  post-bonif (antes era el bruto). Las 3 piezas de layout (clásica, celular, formal) comparten
  `_conceptos` → las 3 quedan arregladas con un solo cambio. El Presupuesto (que ya reconciliaba bien, y
  cuya decisión de IVA-aparte es intencional, 2026-06-06) **no se toca**.
- **L1 (bajo) — Mail de "pedido creado".** Mismo problema en
  `routes/alquileres/core.py::_pedido_email_context`: las filas de la tabla de ítems del mail (helper
  `services/email/branding.py::item_row`) mostraban `it["subtotal"]` (bruto), y el `{{ total }}` del
  template (`services/email/default_templates.py`) es `pedido["monto_total"]` (neto) — sin ningún
  renglón intermedio. Ejemplo real: 1 cámara a $10.000/día × 3 jornadas = $30.000 en la línea del ítem,
  "Total: $27.000" (10% de descuento) abajo, sin aclaración.
- **Fix.** Se agregó el helper único `discount_row()` a `services/email/branding.py` (mismo patrón visual
  que `item_row`/`items_table`, ya existentes — reusa `HAIRLINE`/`MUTED`, no inventa estilos nuevos).
  `_pedido_email_context` arma la fila con `pedido["descuento_monto"]`/`pedido["descuento_pct"]` (ya
  enriquecidos por `_enriquecer_pedido_con_total` antes de que se llame esta función, confirmado en
  `create_pedido`/`_get_alquiler_detail`) y la inserta en `items_html`, entre las líneas y donde el
  template imprime el `Total` — **sin tocar los 7 templates de mail sembrados en la DB** (el fix vive
  100% en el builder de contexto, ninguna migración de copy necesaria). Mismo signo "−" (U+2212, no un
  guion ASCII) que ya usa `pdf_templates._pedido_html` para el Presupuesto, por consistencia visual.
- **Tests.** `tests/test_facturacion_pdf.py` (nuevo): reconciliación exacta bruto→bonif→neto con el
  ejemplo de 2 ítems de $500 + 10%, el ejemplo real de la cámara del mail, un caso de 3 líneas con brutos
  que no dividen limpio (verifica que el remanente de redondeo cierra exacto, no una aproximación), y 2
  regresiones (sin descuento no cambia nada; el fallback sin ítems persistidos sigue igual).
  `tests/test_pedido_email_context.py`: 2 casos nuevos (con descuento aparece la fila con el % y el monto
  correctos; sin descuento no aparece ninguna fila espuria).
- **Consecuencias.** Quedan 7 de los 9 hallazgos de #1209 sin tocar en esta pasada (M1-M4, M6, L2, L3) —
  cada uno es su propia rama + PR scoped, por diseño del issue ("PR como hoja de ruta", 2026-06-27); no se
  cierra el tracking #1209 (issue madre, sigue con 7 pendientes). El supervisor marca una línea de factura
  o de mail que vuelva a mostrar el bruto sin reconciliar contra el total declarado, o un
  `bonif`/`% Bonif.` hardcodeado reintroducido.

### 2026-07-03 — `routes/facturacion.py`: rate limit + mapeo de errores en las escrituras (gap de la auditoría de #1184, #1209)

- **Contexto.** Hallazgo de severidad baja detectado por la auditoría cruzada de plata (2026-07-02,
  #1184): esa pasada blindó `contabilidad.py`/`pagos.py`/`reportes.py` con `@limiter.limit(ADMIN_WRITE_LIMIT)`
  + `@map_pg_errors` en sus 13 endpoints de escritura, pero **no tocó** `backend/routes/facturacion.py` —
  que también escribe plata/estado (facturas, emisores ARCA) y además pega a un webservice externo (ARCA)
  por cada llamada. Sin rate limit, una sesión admin comprometida o un bug de front en loop podía golpear
  ARCA/Postgres sin ningún freno server-side (riesgo de gatillar límites del lado de ARCA). Sin
  `map_pg_errors`, un `UniqueViolation` no anticipado (ej. crear un emisor con un `nombre` duplicado —
  la columna es `UNIQUE` en `emisores_arca`) subía crudo como 500 con el mensaje interno de Postgres, en
  vez de un 400 limpio.
- **Decisión.** Se identificaron los 7 endpoints de escritura reales del módulo (`crear_emisor`,
  `actualizar_emisor`, `cargar_cert`, `desactivar_emisor`, `facturar_pedido`, `nota_credito`,
  `enviar_mail_factura`) y se les agregó el mismo patrón, **reusado tal cual** de `routes/contabilidad.py`
  (`from routes.contabilidad import map_pg_errors`, `from rate_limit import limiter, ADMIN_WRITE_LIMIT`) —
  ninguna reimplementación nueva. `ADMIN_WRITE_LIMIT` (60/minute) en los 7; `@map_pg_errors` en los 6
  sync (compone alrededor del `except ValueError`/`except RuntimeError` que cada handler ya tenía, sin
  reemplazarlos). El único endpoint async, `enviar_mail_factura`, lleva solo el rate limit — **no**
  `@map_pg_errors`, porque el decorator hace `return fn(*args, **kwargs)` sin `await`: para una corrutina
  eso solo captura el objeto coroutine (nunca ejecutado en ese punto), así que el `try/except` nunca vería
  la excepción real — mismo motivo por el que `subir_comprobante` (también async) en `contabilidad.py`
  tampoco lo lleva. No se identificaron endpoints de "subida de archivo" reales en el módulo (`cargar_cert`
  recibe el PEM como texto en el body JSON, no como `UploadFile` multipart) — así que ninguno usa
  `ADMIN_UPLOAD_LIMIT`, a diferencia de `subir_comprobante` en contabilidad.
- **Why.** "Una sola forma de cada cosa": el patrón de rate-limit + mapeo de errores para escrituras admin
  ya existe y está probado en `contabilidad.py`/`pagos.py` — inventar una variante nueva para facturación
  hubiera sido drift. Componer alrededor de los `except ValueError`/`except RuntimeError` existentes (en
  vez de tocarlos) preserva el contrato HTTP ya testeado (`ValueError`→400, `RuntimeError`→503) mientras
  cierra el hueco real: un `UniqueViolation` no es ni `ValueError` ni `RuntimeError`, así que antes escapaba
  ambos catches.
- **Consecuencias.** `tests/test_facturacion_routes.py`: el helper `_fake_request()` pasó de un
  `SimpleNamespace` a un `starlette.requests.Request` real y mínimo (scope manual, sin transporte ASGI) —
  necesario porque `slowapi` exige `isinstance(request, Request)` en el wrapper de `@limiter.limit`, y los
  4 tests existentes que llamaban a `facturar_pedido`/`nota_credito` directo (sin pasar por FastAPI/ASGI)
  lo necesitaban para no romperse. 2 tests nuevos: (1) un loop de 65 requests contra
  `POST /admin/emisores-arca` con una IP dedicada (`TestClient(..., client=("203.0.113.9", ...))`, distinta
  de la IP default `"testclient"` que usan los demás tests del archivo) confirma que el request #61+ corta
  con 429 — la IP dedicada evita compartir el bucket del limiter (en memoria, singleton de proceso) con el
  test del gate de admin o el de nombre duplicado, sin depender del orden de ejecución; (2) un `UniqueViolation`
  simulado sobre `create_emisor` confirma que `crear_emisor` devuelve 400 con el mensaje genérico
  ("Ya existe un registro con ese valor.") en vez de 500. Suite completa (2550 tests, sin DB) + pyflakes en
  verde. Rama `fix/facturacion-rate-limit-errores` (PR sin mergear); tracking #1209.

### 2026-07-03 — La vista multi-mes/anual de reportes ahora respeta los meses cerrados (`liquidar_rango`)

- **Contexto.** Otro hallazgo de severidad media de la auditoría cruzada de plata (2026-07-02, tracking
  #1209): `backend/reportes/cierres.py` ya implementaba correctamente "cerrar un mes" = congelar una foto
  inmutable del reporte de liquidación (`liquidacion_cierres`, `snapshot_de`), y `_data_liquidacion`
  (`routes/reportes.py`) ya la usaba bien para la vista de UN mes puntual (`mes_de_rango` detecta el rango
  exacto → `snapshot_de` directo). Pero cuando el rango pedido cubre VARIOS meses o un año completo (la
  vista "Mes a mes · {año}" y el total anual del front, `LiquidacionReporte.tsx`), el código llamaba a
  `liquidar()` en vivo sobre TODO el rango, sin chequear si alguno de esos meses individuales estaba
  cerrado — ignoraba la foto congelada para esos meses dentro del rango largo. Escenario de falla
  concreto: se cierra junio con el modelo de comisiones Pablo{50/45/5} (la foto congela ese reparto);
  después se edita `comisiones_modelo` a Pablo{60/40} (o se edita/anula un pago de un pedido de junio ya
  cerrado); al abrir el reporte anual, la TARJETA de junio (que sí usa `snapshot_de`) mostraba el reparto
  viejo, pero la FILA de junio dentro de "Mes a mes · 2026" y el total anual (ambos calculados en vivo
  sobre el rango largo) mostraban el reparto nuevo — misma plata, misma pantalla, dos cifras de payout
  distintas para Pablo/Rambla/Tincho. El semáforo de reconciliación no lo detectaba (solo mira actividad
  de pedidos/pagos, no cambios al modelo de comisiones).
- **Decisión.** `reportes/liquidacion.py` gana una función pura nueva, `combinar_meses(meses_data)`: junta
  N reportes por-mes (cada uno con la forma completa de `liquidar`) en un solo reporte multi-mes, sumando
  resumen/por_mes/por_dia/por_dueno — seguro porque un pedido se atribuye a un ÚNICO mes de saldado, nunca
  se solapan entre los reportes de entrada, así que sumar no duplica nada. `reportes/cierres.py` gana
  `liquidar_rango(conn, desde, hasta)`: parte el rango en los meses calendario que cubre
  (`_meses_en_rango`), y para cada mes que el rango cubre COMPLETO usa `snapshot_de` si está cerrado o
  `liquidar()` en vivo si no —nunca mezcla las dos fuentes para el mismo mes—, y combina todo con
  `combinar_meses`. Los fragmentos de mes en los bordes (el rango no arranca/termina en un límite de mes
  calendario) siguen en vivo, como antes — no hay foto posible para un pedazo de mes.
  `routes/reportes.py::_data_liquidacion` (la fuente única usada por JSON/CSV/PDF/mail) delega en
  `liquidar_rango` cuando el rango NO es un único mes calendario exacto; el camino de un mes puntual no
  cambió una línea.
- **Why.** Se evaluó reimplementar el chequeo de "está cerrado" inline en el route, pero eso hubiera
  duplicado la lógica que `cierres.py` ya tiene bien hecha ("una sola forma de cada cosa" — la memoria ya
  marca a `reportes/` como motor único). Extraer `combinar_meses` como función pura (en vez de mezclarla
  con el pipeline SQL→filas→`agregar` de `liquidacion.py`) preserva el contrato "pipeline testeable sin
  DB" del `CLAUDE.md` local del paquete: a `combinar_meses` no le importa si un mes vino de una foto o de
  un cálculo en vivo, solo suma dicts con la misma forma — eso es lo que permite mezclar fuentes sin
  condicionales especiales por mes. Nota de precisión: los totales/reparto por-beneficiario de nivel
  "resumen" ahora se arman sumando los enteros YA REDONDEADOS de cada mes (en vez de redondear una sola
  vez al final sobre floats de todo el rango) — coincide con cómo `agregar()` ya redondeaba `por_mes` en
  el código viejo, así que puede diferir del cálculo anterior por, a lo sumo, unos pocos pesos por mes
  involucrado (redondeo ARS enteros); es una mejora, no una regresión, porque ahora la suma de las filas
  de "Mes a mes" cuadra exacto con el total mostrado.
- **Consecuencias.** Sin cambio de contrato público (mismo shape de respuesta JSON). Tests: pure
  (`TestCombinarMeses`, `TestCierresPuros::test_meses_en_rango` en `test_reportes_liquidacion.py`) +
  integración con Postgres real (`test_liquidar_rango_multimes_respeta_mes_cerrado` en
  `test_reportes_cierres_db.py`) que reproduce el escenario exacto: cierra junio, agrega un pedido en
  julio (abierto), cambia el modelo, y verifica que la tarjeta de junio, la fila de junio dentro del año,
  el resumen anual y el detalle por dueño coincidan — junio con la foto vieja, julio con el modelo nuevo,
  el total la suma correcta de ambos (no 140k recalculado enteros con el modelo nuevo, que hubiera sido
  el bug). El supervisor marca un cálculo de reporte multi-mes que recalcule en vivo sin chequear
  `cierre_de`/`snapshot_de` por mes, o lógica de "está cerrado" reimplementada fuera de
  `reportes/cierres.py`. PR sin mergear (rama `fix/reportes-anual-usa-foto-cerrada`), tracking #1209.

### 2026-07-03 — dataio export/import perdía `anulado` de `alquiler_pagos`: un pago anulado revivía activo tras backup/restore

- **Contexto.** La auditoría de bordes de `contabilidad/` (2026-07-02) le agregó soft-delete a
  `alquiler_pagos` (`anulado`/`anulado_por`/`anulado_at`/`anulado_motivo`) y actualizó las 7 queries
  "vivas" del sistema para filtrar `NOT anulado`. Quedó afuera de esa pasada `backend/dataio/` — el
  exportador/importador de backup/restore/clonado (distinto del `pg_dump` que se usa normalmente para
  clonar staging), que sigue siendo el camino que usa el dueño para bajar un backup completo o migrar
  datos entre ambientes. Encontrado por auditoría dirigida sobre `dataio/exporters.py` (#1209), no por
  la auditoría cruzada de plata del 2026-07-02 (que no llegó a cubrir `dataio`).
- **Bug.** `export_alquileres` (`dataio/exporters.py`) exportaba el pago embebido con solo
  `monto`/`concepto`/`fecha` — sin `anulado` ni sus columnas de auditoría. `import_alquileres`
  (`dataio/importers.py`) sigue la política REPLACE para pagos (`DELETE FROM alquiler_pagos WHERE
  pedido_id = %s` + re-`INSERT` de lo que traiga el JSON) — con el `INSERT` sin esas columnas, Postgres
  aplicaba el **default de la columna**, `anulado=FALSE`. Escenario de falla concreto: un pago de
  $100.000 cargado por error se anula (con motivo, actor y timestamp); se corre `dataio export`
  (backup) y después `dataio import` (restore, o clonado a otro ambiente); el pago **vuelve a la vida
  como activo** — `monto_pagado` del pedido sube $100.000 de la nada, la caja del socio destinatario
  sube, la liquidación lo cuenta como saldado. La anulación desaparece sin dejar rastro y sin que nadie
  lo pida.
- **Fix.** `AlquilerPagoRef` (`dataio/schema.py`) suma `anulado: bool = False` +
  `anulado_por`/`anulado_at`/`anulado_motivo` (opcionales, default `False`/`None` — no rompe JSONs viejos
  ya exportados sin esas claves; `extra="forbid"` de `_Base` no afecta porque son campos nuevos CON
  default, no extra). El `SELECT` de `export_alquileres` suma las 4 columnas (`COALESCE(anulado, FALSE)`
  por si alguna fila legacy quedó con `NULL`); el `INSERT` de `import_alquileres` las reinserta tal cual,
  sin defaultear. Deliberadamente **no** se tocó ninguna otra columna del pago (`destinatario`/`metodo`/
  `created_by` siguen sin exportar) — fuera del alcance de este fix, que es específicamente sobre las
  columnas de soft-delete. Se revisó si el mismo patrón (tabla con soft-delete tocada incompleta por
  `dataio`) aparecía en otro lado: `movimientos` (contabilidad, también tiene `anulado`) **no está en
  `EXPORTERS`/`IMPORTERS`** — `dataio` no exporta contabilidad hoy, así que no había nada más que
  arreglar en este alcance.
- **Consecuencias.** `test_dataio_pagos_anulado_roundtrip_db.py` (Postgres real, opt-in vía
  `RESERVAS_DB_TEST=1`) cubre: (1) el export incluye `anulado`+auditoría del pago; (2) round-trip
  completo export→(se borra el pago, simulando un ambiente fresco donde el backup se restaura)→import→
  el pago vuelve anulado, no activo. Verificado **empíricamente** que el test caza el bug: revertidos
  temporalmente los 3 archivos del fix (`git stash`), corridos los 2 tests nuevos → ambos fallan con el
  síntoma exacto (`KeyError: 'anulado'` en el export; `assert False is True` en el roundtrip); restaurado
  el fix → ambos pasan. Suite completa (2548 tests) + los otros `*_db.py` de dataio existentes
  (`test_dataio_roundtrip_db.py`, `test_dataio_export_readonly_db.py`) siguen en verde — no se rompió
  ningún round-trip existente. `pyflakes` limpio en los 3 archivos tocados + el test nuevo. El
  supervisor marca una entidad nueva de `dataio` que toque una tabla con soft-delete
  (`anulado`/`eliminado_at`) sin exportar/importar esas columnas.

### 2026-07-03 — El pipeline de carritos activos (dashboard admin) incluye el precio derivado de un combo

- **Contexto.** Uno de los 14 hallazgos priorizados de la auditoría cruzada de plata (issue #1209, severidad
  BAJA): `_enrich_items` (`backend/services/carrito/activos.py`), la función que arma el `monto_estimado` de
  cada carrito y el `pipeline_ars` total que ve el dueño en `/admin/carritos`, leía la columna
  `equipos.precio_jornada` **cruda** por ítem (`SELECT e.nombre, e.precio_jornada FROM equipos e WHERE e.id
  = %s`). Para un equipo `tipo='combo'` esa columna es **NULL a propósito** — el precio de un combo se
  DERIVA en vivo de sus componentes vía `services.precios.precio_combo`/`precio_jornada_efectivo` (C3
  #635), no vive en esa columna. `int(row["precio_jornada"] or 0)` coercía el NULL a `0`, y el filtro
  `if precio > 0:` que decide si el ítem entra a `items_precio` (los que `calcular_total` suma) descartaba
  el combo por completo. Resultado: un carrito activo con un combo aportaba **$0** al estimado — el dueño
  veía menos plata "en camino" de la real en el dashboard de funnel.
- **Alcance del bug.** Solo la **métrica interna** del dashboard admin (`stats.pipeline_ars` +
  `carritos[].monto_estimado`). No afecta `cotizado == cobrado`: el carrito NO crea la reserva (eso lo hace
  `create_pedido_retry`, que sigue el camino de `readiness.precios_catalogo_para_reserva` →
  `precio_jornada_efectivo`, ya correcto desde #635/#1110), y el cliente nunca ve este número — es puramente
  informativo para el dueño.
- **Decisión.** `_enrich_items` ahora resuelve el precio de cada ítem con la fuente única
  `services.precios.precio_jornada_efectivo(conn, equipo_id)` (la misma que usa `readiness.py` para el
  camino de creación real) en vez de leer `precio_jornada` crudo. La query de nombre se separó
  (`SELECT e.nombre FROM equipos e WHERE e.id = %s`) del precio, que ahora delega en el resolutor.
- **Por qué fetch por-ítem y no un batch.** El módulo `services/carrito/` ya tiene un batch seguro
  (`precios.precios_combo_batch`), pero se usa en el **catálogo** (`services/catalogo/proyeccion.py`) para
  resolver de una sola vez el precio de TODOS los combos listados — un contexto distinto (sin fechas, sin
  descuentos, batch homogéneo de un solo tipo). Acá el precedente directo es el opuesto: `/api/cotizar`
  **revirtió** su propio batch `IN (...)` de precios (#643) porque devolvió el mapa vacío en prod → total
  $0 en producción — literalmente el mismo síntoma que este bug, por la razón opuesta (un batch roto en vez
  de un batch ausente). `readiness.py` (mismo paquete, camino de creación real) ya resuelve **por-ítem** con
  este mismo resolutor. Con ese precedente + el tamaño acotado del carrito de un heartbeat (unos pocos
  ítems, no cientos), no vale el riesgo de escribir una query batch nueva para un endpoint de dashboard
  (no hot-path de cliente): se mantiene el patrón per-item ya usado en `readiness.py`.
- **Consecuencias.** `int` extra de queries por ítem (1 para nombre + 1-2 dentro del resolutor si es
  combo) en cada heartbeat — irrelevante dado el tamaño típico de un carrito. Test nuevo
  `test_carritos_activos_precio_combo.py` (unit, `FakeConn` que resuelve las 3 queries encadenadas
  nombre→`precio_jornada_efectivo`→`precio_combo`, sin mockear el resolutor en sí) fija el escenario: un
  carrito con un combo aporta su precio derivado real al estimado, no $0. El supervisor marca un ítem de
  carrito/dashboard cuyo precio salga de `equipos.precio_jornada` crudo en vez de
  `precio_jornada_efectivo`, o una query batch nueva de precios sin evaluar el precedente de #643. Issue
  #1209.

### 2026-07-03 — `backend/descuentos/` reorganizado CQRS-lite (`queries/`+`commands/`), espejo de `contabilidad/`/`services/specs/`

- **Contexto.** El dueño reportó no poder aplicar un descuento manual en el back-office — investigado y
  resuelto (bug de auth en `/api/cotizar`, no respetaba `dev_bypass_enabled()`, ya en `dev`). En la misma
  conversación, el dueño adelantó mecanismos de descuento nuevos para más adelante (jerarquía manual>cliente/
  jornadas, descuento en $ fijo, combos no acumulables — ver Fase C en la issue #1219) y pidió organizar la
  lógica actual en un módulo propio ANTES de sumarlos, mismo "CQRS liviano" que ya usa `contabilidad/`/
  `services/specs/`.
- **Decisión.** Split **move-verbatim** (cero cambio de lógica/SQL) de `services/precios.py::
  descuento_aplicable`, la reimplementación duplicada de `descuento_origen` en `cotizacion.py`, y
  `routes/alquileres/core.py::_get_descuento_jornadas` + el CRUD de `descuentos_jornada` hacia
  `backend/descuentos/` (`queries/decision.py`, `queries/jornadas.py`, `commands/jornadas.py`). Cambio
  deliberado de firma: `calcular_descuento_aplicable` toma un dict de fuentes con nombre
  (`{"cliente": pct, "jornadas": pct}`) en vez de 2 floats posicionales — mismo resultado numérico hoy, pero
  sumar una fuente nueva (ej. Fase C) es agregar una key, no rediseñar la función ni sus callers. Fold-in
  trivial: `CotizarRequest.descuento_pct` no tenía validador de rango 0-100 (a diferencia de
  `PedidoDatos.descuento_pct`) — sumado en el mismo archivo que ya se tocaba.
- **Why.** `_recalcular_total_pedido`/`propagar_descuento_a_presupuestos` (`core.py`) se evaluaron para
  mover también, pero se descartó: son orquestación de PEDIDOS (se disparan también por cambios de fecha/
  ítems, no solo de descuento) — moverlas invertiría la dirección de dependencia (`descuentos/` importando
  de un módulo de rutas), algo que ningún paquete CQRS-lite del repo hace hoy. `services/precios.py::
  calcular_total` tampoco se mueve — es el motor de TOTALES (IVA, combos), no de descuento; solo pasa a
  importar la decisión desde el paquete nuevo.
- **Consecuencias.** Cero cambio de contrato HTTP (`test_routes_contract.py` sin tocar, verde). Candado: 19
  tests puros nuevos (`test_descuentos_decision.py`) + 5 de integración Postgres real
  (`test_descuentos_jornada_db.py` — cierra un gap real: ningún test ejercitaba la interpolación de la
  escala contra un `Decimal` real de psycopg, pese a un fix histórico de `Decimal × float → TypeError` en
  esa función). Suite completa 2717 passed; integración (contabilidad/alembic/gate de reservas/descuentos)
  verde contra Postgres real, confirmado que las fallas de un barrido `-m integration` completo son
  preexistentes (reproducidas idénticas en `dev` sin tocar — contaminación de estado entre tests de DB de
  dominios no relacionados). Rama aislada `feature/descuentos-cqrs`, PR #1220 sin mergear (convención "PR
  como hoja de ruta"), issue de tracking #1219 con Fase B (hardening, 5 hallazgos colaterales) y Fase C
  (features nuevas) sin comprometer. De paso, aparte de esta iniciativa: se encontró y arregló un bug real
  en `routes/clientes.py::update_cliente` (placeholders `?` de sqlite3 nunca migrados a `%s`, cualquier
  edición de cliente fallaba en runtime) — pusheado directo a `dev` (commit `5eb5e18`), con test de
  regresión.
