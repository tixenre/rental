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

2026-06-29 · mantenimiento · La lista "**nunca se borra**" de motores únicos (sección 2, "Respetar la MEMORIA":
`backend/{reservas,reportes,busqueda,services/branding}/`) quedó atrás de la familia: **omite `contabilidad`
(2026-06-07) y `services/contenido` (2026-06-29)**. Proponer agregarlos · Por qué: lo cazó el barrido de
cross-refs del **retro de iniciativa**; una lista incompleta podría no frenar el borrado de un módulo vivo.

2026-06-25 · gobernanza · Agregar un check de **"staleness por divergencia" de los manuales de sistema**
(`docs/SISTEMA_*.md`, convención _2026-06-25 — Manuales técnicos por sistema_): detectar si un manual no se
tocó mientras su motor (los paths que referencia) cambió N veces en git → proponer revisarlo en el cierre
de gobernanza. **Detecta + propone, no mantiene solo** (el supervisor por cambio + quien toca el código siguen
siendo el mantenimiento real). · Por qué: hoy los manuales los vigila el supervisor (por cambio) + `check-docs`
(links/estructura), pero **nada detecta el desfase de CONTENIDO**. Un check periódico sería la red de seguridad
que cierra el círculo. **Prematuro con 1 solo manual (fotos)** — activar cuando haya varios (ver el issue de
relevamiento de manuales).

2026-06-30 · calidad-tests · Caso testigo: un test que compara fechas contra `now_ar()` (hora de Argentina, la
convención del repo) debe construir sus fechas con `now_ar().date()`, **NO** con `datetime.date.today()` (UTC en
CI) → si no, falla ~00:00–03:00 UTC (UTC ya es el día siguiente que AR). Sumarlo como gotcha de "tests frágiles /
edge cases de fecha" · Por qué: apareció como **flake real** en `test_check_fechas_pasada_cliente` (#1131) — tapó
el CI verde de un cambio no relacionado y costó un diagnóstico; el test usaba un reloj distinto al del código bajo
prueba. Patrón repetible en cualquier test de fechas (now_ar es la convención en todo el backend).
