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
