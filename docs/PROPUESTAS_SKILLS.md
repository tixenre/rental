# Buzón de propuestas de skills

> **Solo proponer, no aplicar.** Este archivo es el inbox durable de mejoras detectadas durante el uso
> de los skills. La sesión deposita acá; el dueño aprueba (igual que la memoria). El supervisor puede
> validar las propuestas antes de aplicarlas. **Git guarda todo** — no se borra, solo se archiva.
>
> Formato por entrada: `fecha · skill · qué cambiar · por qué`.
> Una vez aprobada una propuesta, marcarla con `✅ aplicada — <PR o commit>`.

---

<!-- Ejemplo de entrada:
2026-06-23 · pendientes · Agregar paso de "cerrar stale issues automáticamente si > 90 días sin actividad y
etiquetados como `someday`" al paso 2 (Triage con evidencia) · Detecté que hay 8 issues con >90 días
sin actividad que bloquean la vista real de la cola activa; el criterio es claro y no requiere criterio
del dueño.
-->

2026-06-24 · pendientes · La nota de "Herramientas" dice "acá **no hay `gh` CLI** → todo por `mcp__github__*`",
pero en la app de Mac (esta sesión) el `gh` CLI **sí está disponible y funciona** (creé el tracker #1029,
listé labels, todo con `gh`). Proponer: cambiar la nota a "usá `gh` CLI cuando esté disponible (app de
Mac/terminal); caé a `mcp__github__*` solo si no lo está" · Por qué: la nota actual desorienta — manda a
usar MCP cuando `gh` es más directo y ya funciona; primer uso real del skill lo destapó.
  ↳ 2026-06-29 · corroboración (retro de iniciativa) · una sesión en la **web/nube** confirma la otra
    mitad: acá `gh` **no** está disponible y hay que caer a `mcp__github__*` sí o sí → la verdad es
    **dependiente del entorno**, lo que valida el wording **condicional** por sobre cualquier absoluto.
  ✅ aplicada — cierre de gobernanza 2026-06-30 (wording condicional en `pendientes/SKILL.md`)

2026-06-29 · mantenimiento · La lista "**nunca se borra**" de motores únicos (sección 2, "Respetar la MEMORIA":
`backend/{reservas,reportes,busqueda,services/branding}/`) quedó atrás de la familia: **omite `contabilidad`
(2026-06-07) y `services/contenido` (2026-06-29)**. Proponer agregarlos · Por qué: lo cazó el barrido de
cross-refs del **retro de iniciativa**; una lista incompleta podría no frenar el borrado de un módulo vivo.
✅ aplicada — cierre de gobernanza 2026-06-30 (`mantenimiento/SKILL.md`)

2026-06-25 · gobernanza · Agregar un check de **"staleness por divergencia" de los manuales de sistema**
(`docs/SISTEMA_*.md`, convención _2026-06-25 — Manuales técnicos por sistema_): detectar si un manual no se
tocó mientras su motor (los paths que referencia) cambió N veces en git → proponer revisarlo en el cierre
de gobernanza. **Detecta + propone, no mantiene solo** (el supervisor por cambio + quien toca el código siguen
siendo el mantenimiento real). · Por qué: hoy los manuales los vigila el supervisor (por cambio) + `check-docs`
(links/estructura), pero **nada detecta el desfase de CONTENIDO**. Un check periódico sería la red de seguridad
que cierra el círculo. ~~Prematuro con 1 solo manual (fotos)~~ — al cierre 2026-06-30 ya hay **9 manuales**
(`ARCA, AUTH, CARRITO, CHECKOUT, CONTENIDO, FACTURACION, FOTOS, IDENTITY, SPECS`) → la condición de diferido
ya no aplica.
✅ aplicada — cierre de gobernanza 2026-06-30 (check agregado al método de `gobernanza/SKILL.md` §2)

2026-06-30 · calidad-tests · Caso testigo: un test que compara fechas contra `now_ar()` (hora de Argentina, la
convención del repo) debe construir sus fechas con `now_ar().date()`, **NO** con `datetime.date.today()` (UTC en
CI) → si no, falla ~00:00–03:00 UTC (UTC ya es el día siguiente que AR). Sumarlo como gotcha de "tests frágiles /
edge cases de fecha" · Por qué: apareció como **flake real** en `test_check_fechas_pasada_cliente` (#1131) — tapó
el CI verde de un cambio no relacionado y costó un diagnóstico; el test usaba un reloj distinto al del código bajo
prueba. Patrón repetible en cualquier test de fechas (now_ar es la convención en todo el backend).
  ↳ 2026-06-30 · corroboración (retro #1136) · el mismo anti-patrón apareció en **código de producción**, no solo
    tests: `tablero.mes_actual()`, `movimientos._mes_de_fecha` y `pagos.py` usaban `date.today()` (UTC) donde debía
    ir `now_ar()`. Se corrigieron en #1136 (vía `services.fechas.mes_actual_ar`). El gotcha **se generaliza**: "el
    ahora/hoy del repo es `now_ar()`, nunca `date.today()`" — vale para prod y tests. Patrón repetido → señal fuerte.
  ✅ aplicada — cierre de gobernanza 2026-06-30 (caso testigo 3d en `calidad-tests/SKILL.md`)

2026-06-30 · mantenimiento · Método: para decidir **qué consolidar en un módulo fuente-única** (y qué dejar en su
motor), despachar un **workflow de lectores paralelos** que clasifiquen cada uso por categoría —
PRIMITIVA-DAL / DOMINIO-MOTOR / DISPLAY-FORMATO / CANDIDATO-CONSOLIDAR. La clasificación hace el corte objetivo:
solo los CANDIDATO se mueven; el dominio de cada motor se queda. · Por qué: en el retro de `services/fechas` (#1136)
este barrido (4 lectores sobre reservas/precios/alquileres/portal/jobs/reportes/contabilidad/auth/ical/pdf) cazó
los candidatos reales (ventana de modificación, horarios) y **descartó con fundamento** los falsos (buffer→reservas,
jornadas→precios) — evitó mover lógica de dominio por "parece fecha". Repetible para cualquier consolidación grande.
✅ aplicada — cierre de gobernanza 2026-06-30 (método sumado a "Más allá del código muerto" en `mantenimiento/SKILL.md`)

2026-06-30 · mantenimiento · Gotcha de verify al **cambiar el contrato de props de un componente compartido**:
(a) el `tsc` local con **cache incremental** puede dar OK falso tras un merge (no rechequea todo) → correr fresco
(`rm tsconfig.tsbuildinfo`) o `tsc -b --force`; (b) el CI de un PR **mergea con el `dev` actual**, que puede tener
**call-sites nuevos** aparecidos después de tu último merge → re-mergear `dev` y re-verificar antes de cerrar. ·
Por qué: en #1136 un 3er call-site de `CartDrawerView` (`catalogo-organismos.tsx`) llegó de `dev` después del merge
→ `tsc` local pasó (cache) pero el CI del PR falló; costó 2 vueltas de CI. Pasó **dos veces** en la misma sesión
(dev se movió 3×). Sumar a la disciplina de "verificar antes de cantar verde".
✅ aplicada — cierre de gobernanza 2026-06-30 (gotcha en `mantenimiento/SKILL.md` Frente E + puntero en
`pulido-frontend/SKILL.md` §4 VERIFICAR, porque también aplica fuera de splits)

2026-06-30 · design-system · Caso testigo (autoría de specimens de la vitrina): un componente de
producción afinado para su contenedor real —`content-visibility` + `aspect-ratio` + intrinsic-size
(ej. `EquipmentCard`: `aspect-square` + `content-visibility:auto` con `contain-intrinsic-size 280px`,
pensado para la grilla **angosta** del catálogo)— se **rompe visualmente** en el lienzo genérico
(ancho) de la vitrina: la foto cuadrada se dispara (~600px) y las cards se solapan. Regla a sumar al
método: al embeber un componente real en la vitrina, **espejar las restricciones de su contenedor de
producción** (ancho de grilla / columnas), no un grid genérico ancho. · Por qué: el specimen de
`EquipmentCard` se shippeó a staging con las cards pisándose (`grid-cols-1→sm:2→xl:3`, demasiado
ancho); lo cazó el **dueño visualmente**, no los checks estáticos (tsc/eslint/prettier no ven layout,
y la ruta `/admin/diseño` es admin-gated → no se renderiza local). Fix `f465a18d`: espejar
`categoria.$slug.tsx` (`grid-cols-2→md:4` + cap de ancho). Repetible para cualquier futuro specimen de
un componente container-coupled.
✅ aplicada — cierre de gobernanza 2026-06-30 (caso testigo 3d en `design-system/SKILL.md`)
