# Memoria viva — Rambla Rental

> **Decisiones de criterio + preferencias.** Curado (no exhaustivo): solo lo que tiene
> consecuencia duradera o se repite. Fechado. **El supervisor lo lee y lo hace cumplir** (caza
> contradicciones = drift) **y lo cura** (propone podar lo viejo/redundante).
>
> **Este doc = la verdad curada del presente, NO un log.** Se **edita y poda** para que quede
> chico y vigente. El "append-only / nada se pierde" lo cumple el **historial de git** (inmutable);
> acá vive solo lo que sigue valiendo hoy. Una decisión que se reemplaza se **actualiza o retira en
> el lugar** (no se apilan contradicciones); su versión vieja queda en git. Ver decisión
> *2026-05-26 — Curación de la memoria*.
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

### 2026-05-25 — Merge según tamaño
- **Contexto:** auto-merge para todo era riesgoso para cambios sensibles; bloquear todo era lento.
- **Decisión:** trivial/small con CI verde + supervisor OK → auto-merge. Sensible / arquitectónico
  / grande, o que toca lo que ve el usuario → PR draft + el dueño prueba antes de mergear.
- **Consecuencias:** el supervisor clasifica el tamaño en su veredicto.

### 2026-05-25 — Modus operandi durable, sesión efímera
- **Contexto:** las sesiones son efímeras; el plan de una iniciativa larga no puede vivir solo en
  la conversación o se pierde.
- **Decisión:** el cómo-se-trabaja vive en docs durables (MANIFIESTO + esta memoria + `CLAUDE.md`),
  no se re-discute por sesión. Plan de tarea: si cabe en una sesión → plan en sesión; iniciativa
  multi-sesión → **un issue de tracking por iniciativa** (checklist de fases adentro, NO un issue
  por fase), auto-mantenido por la sesión que ejecuta.
- **Consecuencias:** una sesión nueva retoma una iniciativa larga sin contexto perdido.

### 2026-05-25 — Memoria en capas
- **Contexto:** "todo en GitHub Issues" enterraba el *por qué* en issues cerrados, imposible de
  hacer cumplir por un agente.
- **Decisión:** Issues = cola de trabajo; commits/PRs = registro de cambios; `docs/MEMORIA.md` =
  decisiones de criterio + preferencias (curado, enforceable por el supervisor).
- **Consecuencias:** el criterio del proyecto queda cargado en cada sesión y revisable.

### 2026-05-25 — Pre-lanzamiento: producción = ambiente de prueba ⏰
- **Contexto:** la web aún no es pública; el dueño es el único usuario de prueba.
- **Decisión:** probar en producción está OK por ahora (no hay clientes que se crucen algo roto).
  No se arma preview/staging todavía (infra prematura).
- **⏰ Disparador (vence esta decisión):** cuando la web salga al público (haya clientes reales),
  esto deja de valer → ahí sí hace falta preview/staging y dejar de probar en prod. **El supervisor
  debe avisar al acercarse el lanzamiento** (ej. issues con `launch-blocker`, o pedido explícito de
  publicar).

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
     correcta siempre.
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
  `priority:low`; la cola *es* el backlog); **pregunta** → respuesta; **idea cruda / "más adelante"**
  → igual va a issue. **Nada se borra.** Si la sesión nota algo y no lo arregla en el momento, lo
  deja como issue, no lo descarta.

### 2026-05-25 — Minutos de GitHub Actions: cuota a cuidar SOLO si el repo vuelve a privado ⏰
- **What:** en **público** (estado actual) Actions es **ilimitado** — no hay cuota que cuidar. Esta
  regla aplica **solo si el repo vuelve a privado**: en plan Free, privado da **2.000 min/mes**, y
  el CI corre 6 jobs por cada push a una PR, así que ahí sí hay que no quemar minutos al pedo.
- **Why:** que el CI no se pause a fin de mes por consumir la cuota — pero eso es un riesgo solo en
  privado.
- **How to apply (vale siempre, buena higiene):** (1) **batch de commits** — pushear cuando el
  cambio está listo, no por cada ajuste chico (cada push = una corrida completa). (2) Los cambios de
  solo-docs/memoria **no deberían disparar los jobs pesados** (build, tests, mobile-smoke) — ver
  issue #487 (path filters). (3) `concurrency: cancel-in-progress` ya cancela corridas viejas al
  re-pushear.
- **⏰ Disparador (activa la parte de cuota):** si el repo vuelve a privado, los 2.000 min/mes pasan
  a valer; en público queda dormida.

### 2026-05-26 — Sesión local para trabajo visual/testeable; la sesión avisa ⏰
- **What:** cuando una tarea se hace mejor en **local** —porque hay que correr y *ver* la app
  (trabajo visual/UX, template del PDF, mobile, o validar un flujo con la app andando y datos
  reales)— la sesión lo **avisa** y se arranca local. Para lo demás (lógica de backend, refactors,
  fixes con tests, planificación, gobernanza) se sigue en la nube, que es lo que el dueño usa desde
  las apps Mac/iPhone.
- **Why:** la sesión en la nube corre en un contenedor efímero y aislado: no puede mostrar la app
  corriendo ni tiene la BD real. Local es el **preview** que hoy falta y reduce el "probar directo
  en prod" (ver decisión 2026-05-25 — producción = ambiente de prueba).
- **How to apply:** la sesión detecta cuándo el trabajo es visual o necesita testeo en vivo y lo
  **señala explícitamente antes de arrancar**; el dueño inicia la sesión local (el stack se levanta
  con el script de #467 — Postgres + backend). El costo es el setup una vez (node/python/postgres).
- **⏰ Disparador (revisar):** cuando exista preview/staging (post-launch), reevaluar si esto sigue
  valiendo o si el preview reemplaza la necesidad de la sesión local.

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
  **supervisor** lo verifica en su revisión. Extiende la decisión *2026-05-26 — Curación de la
  memoria* (que cura *dentro* de MEMORIA) a la **consistencia ENTRE docs**.

### 2026-05-26 — Eficiencia de sesión: modelo según tarea + limpiar contexto
- **What:**
  - **Auditar / planificar / decidir / arquitectura** → Opus (effort alto).
  - **Ejecutar** (implementar un prompt bien especificado, bug fixes con tests, trabajo mecánico) →
    **Sonnet** (effort medio). No usar la variante de ventana **1M** salvo que la tarea necesite
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
