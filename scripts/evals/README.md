# `scripts/evals/` — harness de medición de cambios de gobernanza

> **Por qué existe.** Materializa la decisión _2026-06-27 — Medir lo barato-e-incierto; juicio +
> reversibilidad para el resto (empirismo proporcional)_ (ver `docs/MEMORIA.md`). Cada cambio que "paga"
> se valida con la **señal más barata** que conteste "¿ayudó o perjudicó?". Lo reversible-y-obvio se
> decide con juicio + git, **no** con un eval. **La medición nunca cuesta más que lo medido.**

Código net-new acá ≈ **un solo script** (`context-size.mjs`); el resto es **data + runbook**, y casi todo
lo ejecutable se **reusa** (pytest, `ui-audit.mjs`, dispatch del `supervisor`). Ese es el techo proporcional.

## Las 4 señales

| Señal | Pregunta | Cómo se corre |
| --- | --- | --- |
| **A · Tamaño de contexto** | ¿El prefijo auto-cargado encogió/engordó, y cuánto? | `node scripts/evals/context-size.mjs` (+ `--save <label>` / `--diff <a> <b>`) |
| **B · El supervisor sigue cazando** | ¿Trimear el digest debilita la enforcement de una decisión? | Despachar el agente `supervisor` contra cada `fixtures/*.diff`; confirmar que el `Drift:` del veredicto nombra la decisión correcta. **Manual, in-session** (se corre ~3 veces en la vida → no se escribe orquestador). |

### Esperados de la señal B (fuera de los fixtures, para no contaminar la medición)

| Fixture | Decisión que debe cazar |
| --- | --- |
| `hero-picture.diff` | 2026-06-25 — Hero (LCP) = AVIF-directo + preload AVIF |
| `reservas-inline-expand.diff` | 2026-05-31 — Expansión recursiva del motor de reservas |
| `create-pedido-no-lock.diff` | 2026-06-22 — Creación de pedidos concurrente: advisory lock |
| `asset-path-file-parent.diff` | 2026-06-20 — Gate de "frontend servible" + paths de assets a la raíz |

Catch-rate baseline (digest completo) = **4/4**. Tras el trim del digest debe **seguir siendo 4/4**; una
caída → el 1-liner perdió el trigger → revert/engrosar esa entrada (keep/revert por-entrada).
| **C · El routing sobrevive** | ¿Mergear skills rompe qué skill se dispara? | LLM-as-judge sobre `routing-cases.jsonl`: dadas las descripciones (6 viejas vs 2 merged) + el árbol de decisión de `CLAUDE.md`, ¿qué skill matchea cada frase? Baseline vs after. **In-session.** |
| **D · Paridad de hallazgos** | ¿El skill merged encuentra lo que encontraban los originales? | Invocar el merged contra `fixtures/auditoria-codigo-smoke.*` (un defecto plantado por lente); **ojo del dueño, una vez**. No es gate automático. |

## El golden set v1

Índice curado de escenarios decisivos, **casi todo reusado** (no machinery nueva):

- **Backend** → `cd backend && python -m pytest -m golden` (marcador `golden` en `pytest.ini`; decora tests
  que YA existen: concurrencia de reservas, gate de frontend-servible, ítem oculto).
- **UI** → `node .claude/skills/auditoria-profunda/ui-audit.mjs` con `LABEL=before|after` (el diff de flags
  del `_report.json` es el eval before/after).
- **Gobernanza** → señales B y C de arriba, in-session, **solo cuando el cambio toca el digest o las skills**.

## Cuándo corre (gate proporcional)

- Los tests `-m golden` **ya gatean** en CI (jobs `python-tests` / `db-migrations`). No se agrega workflow nuevo.
- B / C / D se corren **solo cuando su target cambia** (digest → B; capa de skills → C/D), no en cada push:
  B necesita dispatch de agente y C una llamada a modelo (caro + no determinista en CI; un gate flaky de
  gobernanza va contra el ethos anti-bloat).

## Cláusula de retiro

Cada eval lleva fecha de revisión: **si gatea 0 regresiones reales en N meses → se retira** (igual que el
self-revert de `consejo`). El golden set es **curado, no append-only** (misma disciplina que la memoria).
