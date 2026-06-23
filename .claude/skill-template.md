<!--
PLANTILLA DE SKILL — copiá este archivo a `.claude/skills/<nombre>/SKILL.md` para crear un skill nuevo
ya en forma canónica (pasa el linter de `scripts/check-docs.mjs` sin pelear). NO es un skill: vive
fuera de `skillsDir` a propósito, así Claude Code no lo descubre y los Bloques 4/5 no lo cuentan.

Al crear un skill nuevo, además:
  1. Llená el frontmatter (name, description con DISPARADORES + "NO es para X", model, last-reviewed, version).
  2. Agregá su fila a la tabla "Skills — cuál uso para qué" de CLAUDE.md (si no, el Bloque 4 falla).
  3. Borrá este comentario y los placeholders `<...>`.
-->
---
name: <nombre-del-skill>
model: <opus|sonnet|haiku|inherit>
last-reviewed: <YYYY-MM-DD>
version: 1.0
description: <El go-to para X. Qué hace en una frase. DISPARADORES — "frase que diría el dueño", "otra frase". El corazón es el MÉTODO Y. NO es para Z (eso es el skill `otro`).>
---

# <nombre-del-skill> — <subtítulo de una línea>

Codifica **cómo** se hace <X> en este repo: no la lista de lo ya hecho, sino el **método** para que
cada pasada futura sea rigurosa y segura. <1-2 líneas de qué decisión/principio de la memoria materializa.>

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Entrada → Salida |
|---|---|---|
| **`<este>`** (este) | "<disparador>" | <entrada> → <salida> |
| `<vecino>` | "<su disparador>" | <su entrada> → <su salida> |

Qué reusás de los otros (NO lo re-expliques acá): <punteros a método/herramientas que ya viven en otros skills>.

## El método: <paso → paso → paso>

### 1 · <PASO> (read-only / diagnóstico)

<Qué se mira antes de tocar nada.>

### 2 · <PASO>

<...>

## Regla de oro

**Verificá antes de actuar.** <Por qué "actuar" es irreversible acá: qué se rompe/entierra si te
equivocás.> Ante la duda, se **deja y se reporta**. **Honestidad > actividad:** si ya está bien, decilo,
no fabriques churn.

## Anti-objetivos (cuándo NO es este skill)

- **<caso límite>** → `<otro skill>`.
- **<otro caso>** → `<otro skill>`.

## Auto-mejora (correr al cerrar cada uso)

Preguntate, crítico: ¿alguna regla me desorientó o quedó vieja porque el repo cambió? ¿pegué un gotcha
que merece ser "caso testigo"? ¿overlap con otro skill? ¿repetí a mano un paso que debería estar
codificado acá? Si SÍ → **anotá la propuesta en `docs/PROPUESTAS_SKILLS.md`** (proponés, no aplicás — el
dueño aprueba, igual que la memoria; el supervisor puede validar). Si NO → no fabriques churn.

## Cheatsheet

```
1. <PASO>: <una línea>
2. <PASO>: <una línea>
3. <PASO>: <una línea>
```
