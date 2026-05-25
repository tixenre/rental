# Memoria viva — Rambla Rental

> **Decisiones de criterio + preferencias.** Curado (no exhaustivo): solo lo que tiene
> consecuencia duradera o se repite. Append-only, fechado. **El supervisor lo lee y lo hace
> cumplir** (caza contradicciones = drift).
>
> Las **decisiones de arquitectura fundacionales** viven en [`MANIFIESTO.md`](../MANIFIESTO.md) §6
> (baseline congelado). Acá van las **nuevas**. El **trabajo pendiente** vive en GitHub Issues;
> el **registro de cambios**, en el commit history.
>
> **Cómo se escribe acá:** la sesión agrega entradas **solo con aprobación explícita del dueño**.
> El supervisor **propone** entradas pero no escribe. Cuando una decisión tiene fecha de
> vencimiento, anotar el **disparador** que obliga a revisarla.

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
