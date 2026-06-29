# Bitácora del consejo — memoria propia, curada, independiente

> Memoria **propia del consejo**, separada de `docs/MEMORIA.md` (la del repo). Acá viven solo los
> veredictos **cruciales** y qué se decidió finalmente — **curada y podada, no un log gigante** (mismo
> espíritu que `MEMORIA.md`). La del repo registra lo que **el dueño** decidió; ésta, lo que el
> **consejo** juzgó. Tienen **autoridad distinta** y por eso viven separadas: el consejo es un crítico
> independiente y **no acata** las decisiones del repo como verdad (ver `SKILL.md` → _Independencia
> crítica_). El consejo **no escribe** la memoria del repo; promover algo a `docs/MEMORIA.md` es un acto
> del dueño, aparte.
>
> **Curación:** la sesión propone qué guardar y poda lo viejo/redundante; el dueño aprueba. Solo lo
> crucial entra; los usos menores no dejan rastro.
>
> **Formato** por entrada (1-3 líneas, lo mínimo para calibrar después):
>
> ```
> ### <fecha> — <qué se juzgó (una línea)>
> - Veredicto del consejo: <AVANZAR / CON-CAMBIOS / NO / FALTA-INFO — una línea>
> - Qué se decidió: <lo que eligió el dueño finalmente>
> - ¿Coincidieron?: <sí · validación independiente | no · el consejo sostuvo: …>
> - Calibrar: <cuándo/qué revisitar para ver si el consejo tenía razón>
> ```

---

### 2026-06-26 — ¿Debería el skill consejo tener entradas en MEMORIA.md + DECISIONES.md?
- Veredicto del consejo: AVANZAR CON CAMBIOS — sí, pero con las 3 reglas durables concretas (fuente única, separación de memorias, gradiente de rigor); una entrada meramente descriptiva sería ruido sin enforcement.
- Qué se decidió: se escribieron las entradas con las 3 reglas; luego se mergeó el PR.
- ¿Coincidieron?: sí · validación independiente — el dueño acordó con el veredicto y las condiciones.
- Calibrar: en la práctica, ¿el supervisor usa las reglas de la entrada para marcar violaciones? Revisar en el próximo uso real del consejo.

### 2026-06-26 — Recolor del Estudio a su color de área (naranja) + saneamiento del DS de marca
- Veredicto del consejo: AVANZAR CON CAMBIOS — la dirección era correcta, pero NO era un "recolor a medias": era pasar de single-accent global a **accent semántico por área**. Condiciones: token propio `--color-estudio` (no reusar el status `--naranja`), decidir el CTA por área, y actualizar DS + memoria en la misma pasada.
- Qué se decidió: el dueño eligió la versión completa (capa `--area-accent` por área), mismo hue `#e9552f` en token propio, CTA que invierte al accent del área. Clave de marca: la marca del topbar va **blanca sobre el color** (revirtió el logo en negro que metió otra sesión). A prod fue **solo el theming (#1063)**; el resto de `dev` quedó en test.
- ¿Coincidieron?: sí · validación independiente — el dueño acordó con el veredicto y las condiciones; el `design-system` (gobernanza) aprobó la arquitectura, el `supervisor` la promoción.
- Calibrar: ¿el límite de los 3 roles del amber aguanta? Revisar si migrar el rental al token, o agregar un área nueva, reintroduce drift; y si "marca blanca sobre el color" mantiene contraste aceptable en áreas futuras.

### 2026-06-27 — DB: ¿endurecer wrapper / migrar nativo / psycopg3 / SQLAlchemy / SQLModel / async?
- Veredicto del consejo: endurecer el wrapper (AVANZAR) · `?`→`%s` idiomático (CON-CAMBIOS: vale como craft, no como función) · psycopg3 (DIFERIR — beneficios no aterrizan en sync+PgBouncer, pero el wrapper lo deja barato después) · SQLAlchemy Core (NO — problemas que no tenemos) · SQLModel (NO — ORM rechazado, peor encaje) · async (NO — app DB-bound, sync es el fit).
- Qué se decidió: sync + psycopg3 + wrapper fino idiomático + guardas; sin ORM, sin async. (La raíz de la consulta del dueño: el wrapper EMULA formas peores —`lastrowid` vía `lastval()`, `?`— cuando hay nativas mejores; el plan saca cada emulación, deja solo infra genuina.)
- ¿Coincidieron?: sí en casi todo — el dueño llegó a la misma conclusión tras entender cada tradeoff (proceso largo, no acatamiento). Divergió en psycopg3 (consejo: diferir; dueño: hacerlo sync ahora — override consciente, costo bajo, por el driver al día).
- Calibrar: revisitar ORMs/async si el equipo crece >10, aparece multi-DB, o tiempo-real/escala. ¿El supervisor usa la entrada de MEMORIA para marcar `?` nuevo y CTAs de ORM?

### 2026-06-29 — Alta passwordless: ¿passkey-pura sin contacto, o capturar un mail?
- Veredicto del consejo (Nivel 1): AVANZAR CON CAMBIOS — passkey-first signup SÍ (es el norte del dueño), pero NO passkey-pura-contactless. El golpe: cuenta **huérfana pre-Didit** (sin contacto para avisar/recuperar). Lo desinfla que las passkeys **sincronizan** (iCloud/Google → "perder el device" ≠ perder la passkey) + Didit devuelve mail/tel al primer pedido. Condiciones: prompt de mail **suave/skippeable**, recuperación = sync+Didit (device-bound sin backup → pedir contacto), rate-limit + livianas **inertes hasta Didit** + cleanup de stale, lifecycle claro (liviana→Didit→completa). Prior art: Vercel/GitHub agregan passkey a cuenta-con-mail (no puro); bancos anclan identidad fuerte+temprano → Rambla en el medio.
- Qué se decidió: <pendiente — recomendé opción A (mail skippeable, contacto fuerte vía Didit); el dueño decide A/B/C>
- ¿Coincidieron?: <pendiente>
- Calibrar: ¿cuántas cuentas livianas quedan sin verificar/sin contacto en la práctica? ¿el UX "crear vs entrar con passkey" deja de confundir (probado en device real)? ¿la ventana huérfana pre-pedido pega de verdad?
