---
name: design-system
description: Gobernador del Design System — audita sistémicamente el DS de la app (drift de tokens, componentes reimplementados, adopción, violaciones a los 11 principios, drift del doc), trackea su estado con el dashboard "/ds", y propone issues para que pulido-frontend los aplique. Es read-only — nunca edita código. Disparadores: "auditá el DS", "el DS está drifting", "cómo está el DS", "qué tan adoptado está el DS", "buscá reimplementaciones", "colores hardcodeados", "cuántos CTAs crudos hay", "violaciones a los 11 principios", "mantenimiento del DS". NO mejora pantallas puntuales (→ pulido-frontend), NO busca bugs de flujo (→ auditoria-profunda), NO audita código/seguridad/perf (→ otros skills).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# design-system — gobernador del Design System

El DS de Rambla tiene estructura sólida (tokens OKLCH modulares, 4 piezas `kit/` con fuente única,
guardrails ESLint), pero la **adopción es continua** y el drift entra en cada PR. Este skill es el
que **detecta el drift antes de que acumule deuda**, propone los fixes en issues, y deja que
`pulido-frontend` los aplique.

Blueprint: el mismo ciclo propone-aprobás que `gobernanza` y `pendientes` — **lee, razona, propone; nunca
edita código**.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`design-system`** (este) | "¿el DS está sano? ¿qué driftea?" | DS sistémico: tokens, adopción, doc, 11 principios |
| `pulido-frontend` | "esta pantalla está rara — mejorarla" | Pantalla puntual: UX/UI en vivo, improve |
| `auditoria-profunda` | "¿tiene fallas / bugs?" | Flujo de negocio, edge cases, stress |
| `mantenimiento` | "¿hay deuda de código?" | Código muerto, modularidad, splits |
| `gobernanza` | "¿cómo están los skills?" | Meta-nivel: skills y docs de gobernanza |

**Cadencia:** correr mensualmente o tras un merge grande que toque `src/design-system/` o
`docs/DESIGN_SYSTEM.md`. También invocable puntualmente para responder una pregunta específica.

## Fuentes de datos

- `frontend/src/design-system/` — tokens CSS + primitivos UI + kit
- `frontend/src/components/rental/` + `admin/` — componentes de aplicación
- `docs/DESIGN_SYSTEM.md` — source of truth (la filosofía + tokens + componentes)
- `frontend/eslint.config.mjs` — guardrails que ya bloquean en CI (conocer excepciones)
- GitHub Issues — issues de DS abiertos (para no duplicar)

## El método: leer → auditar → proponer → aprobar → ejecutar (vía pulido-frontend)

### 1 · `/ds` — dashboard de estado (el comando liviano)

Responde "¿cómo está el DS?" sin auditoría completa. Corré cuando el dueño pida un resumen rápido:

```
Estado del Design System — <fecha>
────────────────────────────────────
Tokens adoptados:
  Color    → uso de tokens vs. genéricos Tailwind / hex crudos
  Motion   → --duration-*/--ease-* vs. hardcoded
  Z-index  → --z-* vs. hardcoded z-[N]
  Shadows  → --shadow-* vs. Tailwind shadow-sm

Componentes canónicos: 4 kit + N presentacionales
  Reimplementaciones detectadas: X instancias
  CTAs crudos (<button>): Y instancias
  Pills manuales: Z instancias

Issues de DS abiertos: N  (<títulos>)
Drift del doc: <última vez sincronizado / pendientes>
```

Fuentes: grep mecánico sobre `frontend/src/` + `mcp__github__list_issues` con label `design-system`.
Es read-only. Tarda < 2 minutos.

### 2 · Auditoría mecánica (Fase 1) — grep + regex

**2a. Colores genéricos o hardcodeados**

> **Patrones legítimos que NO son violaciones** — no los marques como drift:
> - `bg-[var(--area-accent)]`, `text-[var(--area-accent)]`, `border-[var(--area-accent)]` — theming por área (cascade `[data-area]`)
> - `bg-[color-mix(in_oklch,var(--area-accent)_N%,...)]` — tints del accent de área (canonical)
> - `bg-[color-mix(in_oklch,var(--color-ink)_N%,var(--area-accent))]` — hover mix ink+area (canonical)
> - `bg-estudio`, `text-estudio` en `src/data/areas.ts` y el topbar — colores de área en la capa de chrome
> - El hex `#e9552f` en `estudio.tsx` (theme-color de la ruta) — metadata de navegador, no color de app
>
> Sí marcar como drift: `bg-naranja` (o `text-naranja`) en **superficies de marketing del Estudio** — debe ser `bg-[var(--area-accent)]`.

```bash
# Tailwind genérico (debería haber 0 — ESLint los bloquea, pero buscar residuales o excepciones no documentadas)
grep -rn 'bg-\(slate\|gray\|red\|green\|blue\|yellow\|purple\|pink\)-\|text-\(green\|blue\|red\|yellow\|purple\|pink\|gray\)-[0-9]' frontend/src/ --include="*.tsx" --include="*.ts" | grep -v eslint-disable

# Hex crudos fuera de constantes Tier 3-4 documentadas (AVATAR_COLORS, WhatsApp, etc.)
grep -rn '#[0-9a-fA-F]\{6\}' frontend/src/ --include="*.tsx" --include="*.ts" | grep -v 'AVATAR_COLORS\|25D366\|// Tier\|eslint-disable\|e9552f\|theme-color'
```

**2b. Magic font-sizes** — `text-[Nrem]` (ESLint bloquea `px`; los `rem` pueden escapar):

```bash
grep -rn 'text-\[[0-9.]*\(px\|rem\|em\)\]' frontend/src/ --include="*.tsx" --include="*.ts"
```

**2c. Magic spacing** — `p-[Npx]`, `gap-[Npx]`, `m-[Npx]`:

```bash
grep -rn '\(p\|m\|gap\|space\)-\[[0-9.]*px\]' frontend/src/ --include="*.tsx" --include="*.ts"
```

**2d. Componentes reimplementados** — las tres reimplementaciones más frecuentes:

```bash
# Spinner reimplementado (debería ser <Spinner> de design-system/ui/)
grep -rn 'Loader2.*animate-spin' frontend/src/ --include="*.tsx"

# Button crudo (candidatos a <Button> de design-system/ui/)
grep -rn '<button\b' frontend/src/ --include="*.tsx" | grep -v 'eslint-disable\|// ok:'

# Pill manual de estado (debería ser <Pill tone="..."> del kit)
grep -rn 'bg-\(verde\|azul\|naranja\|rosa\)/1[05]' frontend/src/ --include="*.tsx" | grep -v 'EstadoBadge\|PagoBadge\|Pill\|eslint-disable'
```

**2e. Focus rings inconsistentes** — `focus:` crudo en vez de `focus-visible:`:

```bash
grep -rn '\bfocus:\(ring\|outline\|border\)' frontend/src/ --include="*.tsx" | grep -v 'focus-visible'
```

**2f. Aria labels faltantes en icon-buttons**:

```bash
grep -rn '<button[^>]*>[^<]*<[A-Z][a-zA-Z]*Icon' frontend/src/ --include="*.tsx" -A1 | grep -v 'aria-label'
```

**2g. Inputs sin anti-zoom mobile** — font-size < 16px en inputs:

```bash
grep -rn '<\(Input\|input\|textarea\)[^>]*text-xs' frontend/src/ --include="*.tsx"
```

**2h. Tokens de motion sin adoptar** — `transition-all duration-200` hardcoded:

```bash
grep -rn 'duration-[0-9]\{3\}' frontend/src/ --include="*.tsx" --include="*.ts" | wc -l
grep -rn '\-\-duration-' frontend/src/ --include="*.tsx" --include="*.ts" --include="*.css" | wc -l
```

**2i. Z-index hardcoded**:

```bash
grep -rn 'z-\[[0-9]*\]' frontend/src/ --include="*.tsx" | grep -v '\-\-z-'
```

Para cada hallazgo: contar instancias, listar archivos, clasificar 🔴/🟡.

### 3 · Auditoría de criterio (Fase 2) — razonar sobre el código

**3a. Contraste WCAG** — calcular ratios reales desde tokens OKLCH (`frontend/src/design-system/styles/tokens/colors.css`):

Hallazgos conocidos a re-verificar en cada auditoría:
- `text-verde` sobre `bg-surface` (N8: ~3.4:1 — falla AA 4.5:1) → necesita `text-verde-ink`
- `bg-verde/15 text-verde` en chip admin (N1: ~2.8:1 — falla AA) → necesita `text-verde-ink`

Para calcular desde tokens OKLCH:
```python
# Convertir OKLCH → sRGB → luminance relativa (WCAG 2.1)
import math
def oklch_to_srgb(L, C, H):
    # Convertir a OKLab
    h_rad = math.radians(H)
    a = C * math.cos(h_rad)
    b = C * math.sin(h_rad)
    # OKLab → LMS → XYZ → sRGB (fórmula estándar)
    ...
```

O bien: usar las utilidades de `frontend/src/` que ya hacen el cálculo si existen.

**3b. Los 11 principios** — leer `docs/DESIGN_SYSTEM.md` §Filosofía (11 principios) y evaluar:
- P3 (un foco por pantalla): ¿hay dos CTAs de igual peso en alguna pantalla clave?
- P4 (una sola forma): ¿hay controles duplicados para la misma acción?
- P9 (DS-first: reusar no recrear): ¿hay one-offs ad-hoc que dupliquen algo del kit?
- P10 (mobile + a11y): ¿tap targets ≥ 44px? ¿inputs ≥ 16px? ¿aria-labels?

Recorrer las áreas clave: catálogo, portal cliente, back-office admin.

**3c. Adopción de tokens** — evaluar % real:
- Motion: instancias de `--duration-*` / total `duration-` classes
- Z-index: instancias de `--z-*` / total `z-` classes
- Shadows brand: instancias de `--shadow-*` / total `shadow-` classes
- Clasificar: < 10% → 🔴, 10-50% → 🟡, > 50% → ✅

### 4 · Gobernanza del doc (Fase 3)

Leer `docs/DESIGN_SYSTEM.md` y contrastar con el código:
- ¿Los paths de componentes citados son correctos? (`kit/`, `equipment/shared/`, etc.)
- ¿Los valores de tokens coinciden con `tokens/*.css`?
- ¿Hay componentes citados que no existen, o componentes nuevos que no están en el doc?
- ¿Las reglas del doc (ej. "única fuente de pills") siguen siendo ciertas?

Si hay drift: proponer actualizar el doc (es código de gobernanza, no de app — se puede editar
con aprobación del dueño).

### 5 · Dashboard + propuesta de issues

Formato de reporte completo:

```
ESTADO DEL DS — <fecha>
────────────────────────────────────────────
Tokens color:  ✅ / 🟡 N genéricos  |  Motion: 🔴 N% adoptado  |  Z-index: 🟡 M%
Reimplementaciones: 🔴 CTAs crudos ×N · 🟡 pills manuales ×M · 🟡 Loader2 ×P
Contraste WCAG: 🔴 N fallos (texto sobre tint sin token -ink)
Doc drift: 🟡 Y secciones desactualizadas

🔴 Crítico:
  - N3: 19 CTAs crudos (<button>) → reemplazar con <Button> → ejecutar con pulido-frontend
  - N8: texto-verde sobre surface (3.4:1 < AA) → usar text-verde-ink → ejecutar con pulido-frontend
  - N1: chip admin contraste 2.8:1 → idem

🟡 Advertencia:
  - O1/N2: 52 magic rem escapados → ejecutar con pulido-frontend
  - N5: motion tokens 0% adoptado → mejora gradual en pulido-frontend
  - N7: doc DESIGN_SYSTEM.md tiene X entradas desactualizadas → actualizar doc

✅ OK:
  - Guardrails ESLint: hex y genéricos bloqueados en CI
  - 4 piezas kit/ como fuente única (Pill, EstadoBadge, PagoBadge, ClienteAvatar)
  - StepperPill, PriceBlock, FavButton: sin reimplementaciones
  - ...

Propuestas de issues (esperando aprobación del dueño):
  1. "DS: reemplazar CTAs crudos por <Button>" — 19 instancias, scope: CatalogoMovil/ClientePortal/estudio
  2. "DS: verde-ink en montos positivos (N8)" — 49 usos text-verde → text-verde-ink
  3. "DS: adopción tokens de motion" — 0% → meta 30%
  4. "DS: sincronizar DESIGN_SYSTEM.md (N7)" — actualizar rutas/valores/componentes
```

**No crea issues sin confirmación** — muestra los drafts, el dueño aprueba, la sesión crea con
`mcp__github__issue_write` + label `design-system` + label de área correspondiente.

## Regla de oro

**Proponer, no aplicar.** Este skill detecta y razona — `pulido-frontend` y el dueño aplican.
Nunca edita código de la app, nunca toca `frontend/src/` ni `docs/DESIGN_SYSTEM.md` sin aprobación
explícita. La honestidad vale más que el movimiento: si el DS está sano, la respuesta correcta es
decirlo.

**Cero falsos positivos.** Antes de reportar un hallazgo, confirmar que no es una excepción
documentada (Tier 3-4, `eslint-disable` justificado, caso borde del kit). Un hallazgo incorrecto
erosiona la confianza en el dashboard.

## Anti-objetivos (cuándo NO es este skill)

- **Mejorar una pantalla específica** → `pulido-frontend`.
- **Buscar fallas de seguridad o performance** → otros skills.
- **Buscar bugs de flujo de negocio** → `auditoria-profunda`.
- **Auditar la capa de skills** → `gobernanza`.
- **Editar código de la app sin aprobación** → nunca.

## Auto-mejora (correr al cerrar cada uso)

Preguntate, crítico: ¿alguna regla me desorientó o quedó vieja porque el repo cambió?
¿Los comandos de grep siguen matcheando bien? ¿El doc DESIGN_SYSTEM.md driftea de este método?
¿Overlap con `pulido-frontend` o `auditoria-profunda`?

Si **SÍ** → anotá la propuesta en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md)
(formato: `fecha · skill · qué cambiar · por qué`). Proponés, no aplicás — el dueño aprueba.

Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
/ds  →  dashboard rápido (tokens + reimplementaciones + issues abiertos) — read-only

Auditoría completa:
  1. Mecánica: grep colores/sizes/componentes/a11y (Fase 1)
  2. Criterio: contraste WCAG + 11 principios + adopción tokens (Fase 2)
  3. Gobernanza: drift entre doc y código (Fase 3)
  4. Reporte 🔴/🟡/✅ + draft de issues → dueño aprueba → crear con mcp__github__issue_write

Ejecutores de fixes (no son este skill):
  pulido-frontend  → aplica fixes de pantalla
  mantenimiento    → limpia deuda de código (no DS)

Cadencia: mensual o tras merge que toque src/design-system/ o docs/DESIGN_SYSTEM.md
```
