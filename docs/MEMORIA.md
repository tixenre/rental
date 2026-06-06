# Memoria viva — Rambla Rental

> **Decisiones de criterio + preferencias.** Curado (no exhaustivo): solo lo que tiene
> consecuencia duradera o se repite. Fechado. **El supervisor lo lee y lo hace cumplir** (caza
> contradicciones = drift) **y lo cura** (propone podar lo viejo/redundante).
>
> **Este doc = la verdad curada del presente, NO un log.** Se **edita y poda** para que quede
> chico y vigente. El "append-only / nada se pierde" lo cumple el **historial de git** (inmutable);
> acá vive solo lo que sigue valiendo hoy. Una decisión que se reemplaza se **actualiza o retira en
> el lugar** (no se apilan contradicciones); su versión vieja queda en git. Ver decisión
> _2026-05-26 — Curación de la memoria_.
>
> Las **decisiones de arquitectura fundacionales** viven en [`MANIFIESTO.md`](../MANIFIESTO.md) §6
> (baseline congelado). Acá van las **nuevas**. El **trabajo pendiente** vive en GitHub Issues;
> el **registro de cambios**, en el commit history.
>
> **Cómo se escribe acá:** la sesión agrega, **edita o poda** entradas **solo con aprobación
> explícita del dueño**. El supervisor **propone** (agregar, retirar, fusionar) pero no escribe.
> Cuando una decisión tiene fecha de vencimiento, anotar el **disparador** que obliga a revisarla.

---

## Decisiones (ADR-lite)

### 2026-05-25 — Branch + PR siempre (se deprecá local-first sobre main)

- **Contexto:** el manifiesto documentaba un flujo local-first commiteando directo a `main`, que
  ya no es como se trabaja (las sesiones corren en la nube desde apps Mac/iPhone).
- **Decisión:** todo cambio va en una rama dedicada y se mergea por PR. No se commitea directo a
  `main`. Una iniciativa = una rama = una PR con N commits atómicos.
- **Consecuencias:** trazabilidad uniforme corra Claude donde corra; se descarta el modo
  local-first.
- **Matiz (2026-06-03):** el "rama+PR siempre" se relajó **solo para bugfixes chicos**, que pueden
  ir **directo a `dev`** sin PR por feature (ver decisión _2026-06-03 — Bugfixes chicos_). Lo
  inamovible es **nunca commitear directo a `main`** — eso no cambió.

### 2026-05-25 — Merge según tamaño

- **Contexto:** auto-merge para todo era riesgoso para cambios sensibles; bloquear todo era lento.
- **Decisión:** trivial/small con CI verde + supervisor OK → auto-merge. Sensible / arquitectónico
  / grande, o que toca lo que ve el usuario → PR draft + el dueño prueba antes de mergear.
- **Consecuencias:** el supervisor clasifica el tamaño en su veredicto.
- **Matiz (2026-06-03):** en el flujo de dos etapas, el "el dueño prueba antes de mergear" se
  **reubica** — el dueño prueba en **staging** (después del merge a `dev`), no antes; lo que el dueño
  mergea con su criterio es la **promoción `dev → main`** (la puerta a prod). El merge a `dev` lo
  hace la **sesión** (ver decisión _2026-06-03 — Quién clickea el merge_).

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

### 2026-06-01 — Staging → Prod: flujo desde v1.0.0 (reemplaza "producción = ambiente de prueba")

- **Contexto:** v1.0.0 en prod. Se creó un ambiente Railway `dev` (rama `dev`) como staging.
  El disparador ⏰ de la entrada anterior se cumplió — hay staging, no se prueba en prod.
- **Decisión:** **prod es sagrado — no se prueba ahí.** El flujo es:
  trabajar en `dev` (o branches que mergean a `dev`) → ver en Railway staging → PR `dev → main` → prod.
- **Why:** prod tiene clientes potenciales y datos reales; un error visible no tiene red de contención.
  El staging de Railway cubre la necesidad de ver cambios en vivo antes de mandar a prod.
- **How to apply:** todo cambio va a `dev` primero. Solo se mergea a `main` cuando el staging
  muestra que funciona. La BD de staging es una copia de prod del 2026-06-01; las migraciones
  de `dev` corren en staging y no tocan prod hasta el merge.

### 2026-05-25 — Gate de estilo en CI: formato bloquea, lógica de React avisa

- **Contexto:** el repo tenía `eslint.config.js` pero el tooling nunca se instaló ni corría; al
  medir, ~98% de la deuda era formato auto-arreglable (prettier), no bugs.
- **Decisión:** el CI bloquea por **formato (prettier)** — es automático y sin criterio, mantiene el
  código parejo. Las **reglas de lógica de React** (`exhaustive-deps`, `react-refresh`) quedan como
  **aviso, no bloqueante**, para no frenar el trabajo por deuda preexistente.
- **Consecuencias:** los cambios nuevos deben pasar `npm run lint` sin errores de formato; los
  avisos de React se revisan pero no impiden mergear.
- **Pendiente (para que el aviso no se vuelva ruido permanente):** triagear los ~22 avisos, arreglar
  los bugs reales (sobre todo `exhaustive-deps`) y promover a bloqueante las reglas que valgan →
  issue de tracking **#476**.

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

### 2026-06-01 — Método de merge según etapa del flujo (squash a `dev`, merge-commit a `main`)

- **Contexto:** el flujo es de dos etapas (`rama → dev → main`, decisión 2026-06-01 Staging→Prod).
  Las ramas de feature suelen tener commits de ruido ("wip", "fix lint") que no aportan al historial.
- **Decisión:** el método de merge depende de la etapa:
  - **`rama → dev` = squash.** Cada PR queda como **un commit limpio** en staging (1 PR = 1 unidad de
    cambio entendible, con su `#PR`). El detalle commit-por-commit no se pierde: vive en la PR.
  - **`dev → main` = merge commit** (NO squash). Así cada PR ya squasheada en `dev` fluye a `main`
    como **su propio commit**, preservando la trazabilidad PR-por-PR en prod.
- **Why:** el _registro de cambios vive en el commit history_ (decisión Memoria en capas) y _prod es
  sagrado_. Squashear `dev → main` aplastaría N PRs en un commit gigante → se pierde poder revertir
  **una PR puntual** en prod. El patrón (squash en feature, merge en promoción) mantiene `dev`
  prolijo **y** `main` con revert quirúrgico.
- **How to apply:** al mergear una rama a `dev`, usar squash con título `tipo: desc (#PR)`. Al promover
  `dev → main`, usar merge commit. No squashear nunca la PR de promoción a prod.
- **Alcance (2026-06-03):** el `rama → dev = squash` aplica a las PRs que **sí** pasan por rama —es
  decir, lo grande/sensible/arquitectónico. Los **bugfixes chicos van directo a `dev`** sin PR
  (ver decisión _2026-06-03 — Bugfixes chicos_); ahí no hay squash. El `dev → main = merge commit`
  no cambia: sigue siendo la única vía a prod y conserva el revert por unidad.

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

### 2026-06-03 — Bugfixes chicos: push directo a `dev`; rama+PR solo para lo grande

- **Contexto:** abrir un PR a `dev` por cada bug chico, solo para verlo en staging, era pura fricción
  cuando hay **varios fixes en paralelo** (el modo de trabajo habitual del dueño). El paso "PR para
  previsualizar" no aportaba: el dueño no revisa diffs y prod no se toca en esa etapa.
- **Decisión:** los **bugfixes chicos van directo a `dev`** (sin PR por feature). Se ven juntos en
  staging y se abre **un** PR `dev → main` cuando el lote está listo. Lo **grande / sensible /
  arquitectónico / que toca el core de reservas o lo que ve el usuario** sigue en **rama + PR
  dedicada** — la regla _Merge según tamaño_ (2026-05-25) queda intacta; esto solo define el camino
  del caso chico. El triage honesto es la pieza que carga el peso: en el momento en que un fix deja
  de ser trivial, gradúa a rama+PR.
- **Why (es seguro):** **prod es sagrado y no se toca acá** — solo se alcanza por el PR `dev → main`,
  que conserva su gate completo (supervisor + CI + el dueño prueba). CI corre en cada push a `dev`;
  la BD de staging es copia de prod (2026-06-01), no prod. Lo peor que puede pasar es romper staging,
  que es justamente para lo que existe. Es trunk-based con rama de integración (`dev`): patrón sano
  para un dueño solo + Claude + CI + supervisor al promover, no un atajo.
- **Barandas:** (1) commits atómicos con Conventional Commits → revert por commit posible en `main`
  aunque no se agrupe por PR; (2) el **supervisor corre antes de promover `dev → main`** (sobre el
  lote); (3) **mantener `dev` cerca de `main`** (promover seguido, no dejar laburo a medias en `dev`
  al promover) para no perder el todo-o-nada de la promoción.
- **Consecuencias:** matiza _Branch + PR siempre_ (2026-05-25) y _Método de merge según etapa_
  (2026-06-01) — ver las notas agregadas ahí. Lo inamovible: **nunca directo a `main`**.

### 2026-06-03 — Quién clickea el merge: la sesión mergea a `dev`; el dueño gatea staging + promoción

- **Contexto:** el dueño no quiere ser el botón de merge de cambios que la sesión ya aprobó
  (supervisor OK) y con CI verde. El criterio de "el código está bien" lo cubren supervisor + CI;
  clickear merge es trabajo mecánico sin valor.
- **Decisión:** **mergear a `dev` = mostrar en staging**, no es la puerta a prod → lo hace **la
  sesión**, no el dueño:
  - **Chico / mediano** con supervisor OK + checks verdes → la sesión mergea a `dev` (directo si ya
    están verdes; con **auto-merge de GitHub** si están corriendo, mergea solo al ponerse verde).
    El dueño no toca nada.
  - **Grande / sensible / que toca reservas o lo que ve el usuario** → la sesión **avisa antes** de
    meterlo a `dev` (el dueño puede frenarlo), y recién después mergea.
- **Los gates del dueño** (donde sí aporta criterio) quedan en: (1) **probar la conducta en
  staging**, y (2) **aprobar la promoción `dev → main`** — esa es la puerta a prod (sagrada),
  siempre manual del dueño. Nunca se mergea con **CI en rojo**.
- **Consecuencias:** refina _Merge según tamaño_ (2026-05-25). Cada PR a `dev` llega con su plan de
  prueba en lenguaje claro para que el dueño sepa qué tocar en staging. El supervisor sigue corriendo
  antes de cada merge a `dev` (chico/mediano) y antes de la promoción.

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

### 2026-06-06 — Design system consolidado en la app; un solo skill de UI

- **Contexto:** convivían DOS implementaciones del DS: el paquete workspace
  `@rambla/design-system` (tokens/CSS/fuentes — consumidos vía `@import` — **+** copias paralelas de
  componentes que **driftearon** de la app, ej. EquipmentCard 317 líneas distintas) y los componentes
  reales de la app en `src/components` (los que usó el rediseño de Pedidos v2 = lo último/canónico). El
  paquete no se consumía para componentes (0 imports JS), solo para CSS. Además había dos skills de
  diseño (`design-system` para el paquete, `importar-diseno` para implementar handoffs).
- **Decisión (del dueño):** **todo lo de UI / front-end / design system / Claude Design / import +
  implementación vive en UN solo lugar, con lo último y lo mejor.** (1) El DS canónico es la app:
  componentes en `src/components/{ui,kit,rental}`, tokens/tipografía/utilities/fuentes en `src/styles/`
  (entry `src/ds-styles.css`, cableado desde `src/styles.css`). (2) El paquete `@rambla/design-system`
  y su workspace se **retiraron** (los tokens/CSS/fuentes se migraron a `src/` **verbatim** — CSS
  compilado verificado como subconjunto del previo, cero regresión visual; las copias de componentes
  drifteadas se descartaron, gana la app). (3) **Un solo skill: `importar-diseno`** — implementa
  diseños Y mantiene/consume la librería (reuse-first). El skill `design-system` se retiró.
- **Cómo aplica / quién hace cumplir:** un token/utility se edita en `src/styles/`, una pieza en
  `src/components/`; **no se recrea un paquete workspace** ni se duplica una pieza que ya existe. El
  supervisor marca como hallazgo cualquier intento de reintroducir el paquete o un segundo skill de DS.
  Cierra la iniciativa #662 (invertir la fuente de verdad hacia el paquete — abandonada por esta
  decisión); los trackers de migración por pantalla (#612) y handoff (#605) siguen vigentes sobre `src/`.

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

### 2026-05-26 — Sesión local para trabajo visual/testeable _(reemplazada 2026-06-01)_

- _(Reemplazada por la decisión 2026-06-01 — Staging → Prod. El staging de Railway cubre
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
