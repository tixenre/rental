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
