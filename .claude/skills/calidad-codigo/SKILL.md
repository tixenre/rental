---
name: calidad-codigo
description: Auditor de calidad de código — evalúa si el código está bien escrito, modular y escalable (TypeScript preciso, React patterns correctos, sin duplicación lógica, complejidad baja, naming claro). Lee y razona; propone issues con fixes concretos. Disparadores: "el código está bien escrito?", "hay anti-patrones?", "qué tan escalable está el repo?", "auditá la calidad del código", "hay duplicación lógica?", "los patterns de React están bien usados?". NO busca bugs de negocio (→ auditoria-profunda), NO busca código muerto o god-modules (→ mantenimiento), NO audita tests (→ calidad-tests).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# calidad-codigo — auditor de calidad y escalabilidad del código

El repo crece sesión a sesión. Este skill evalúa si el código que está activo está **bien escrito**:
tipado preciso, patterns de React correctos, sin duplicación lógica, complejidad manejable y naming
que comunica intención. El resultado son propuestas de issue — el dueño aprueba, la sesión aplica.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`calidad-codigo`** (este) | "¿está bien escrito? ¿va a escalar?" | Patterns, tipado, duplicación lógica, naming, complejidad |
| `mantenimiento` | "¿hay deuda/legacy?" | Código muerto, god-modules, splits estructurales, branches viejas |
| `calidad-tests` | "¿los tests son buenos?" | Cobertura, calidad, paths sin tests |
| `auditoria-profunda` | "¿tiene fallas?" | Bugs de flujo de negocio, edge cases |
| `auditoria-seguridad` | "¿está seguro?" | OWASP, auth, CORS, headers |
| `design-system` | "¿el DS driftea?" | Tokens, componentes, 11 principios |

## El método: leer → evaluar → proponer

### 1 · Frente TS — TypeScript preciso

Busca degradación del tipo:

```bash
# `any` explícito en código de aplicación (excluir .d.ts y tests)
grep -rn '\bany\b' frontend/src/ --include="*.ts" --include="*.tsx" | grep -v '\.d\.ts\|// ok:\|eslint-disable'

# `as` casts sospechosos (ocultan errores reales)
grep -rn ' as [A-Z][a-zA-Z]*\b' frontend/src/ --include="*.ts" --include="*.tsx" | grep -v '// ok:\|as const\|as unknown'

# `@ts-ignore` / `@ts-expect-error` sin justificación
grep -rn '@ts-ignore\|@ts-expect-error' frontend/src/ --include="*.ts" --include="*.tsx"
```

Para el backend Python:

```bash
# `# type: ignore` sin comentario
grep -rn '# type: ignore' backend/ --include="*.py" | grep -v '# type: ignore\[.*\]  #'
```

Evaluar: ¿los types son informativos (dicen lo que son) o defensivos (ocultan lo que no se sabe)?

### 2 · Frente React — patterns correctos

**2a. Custom hooks que no deberían serlo** (lógica de negocio en componentes):

```bash
# Estado derivado calculado en el render (debería ser useMemo o variable local)
grep -rn 'const \[.*\] = useState.*\.filter\|useState.*\.map\|useState.*\.reduce' frontend/src/ --include="*.tsx"
```

**2b. Dependencias de useEffect incorrectas** (ya lo caza ESLint `exhaustive-deps`, pero revisar residuales):

```bash
grep -rn 'eslint-disable.*exhaustive-deps' frontend/src/ --include="*.tsx" --include="*.ts"
```

**2c. Props drilling excesivo** (>3 niveles de props que no se consumen en el nivel intermedio):

Lectura manual: buscar componentes que reciban props y las pasen sin usarlas.

**2d. Componentes que hacen demasiado** (>200 líneas JSX + lógica de negocio + efectos = candidato a split):

```bash
# Archivos grandes en components/
wc -l frontend/src/components/**/*.tsx | sort -rn | head -20
```

**2e. `useEffect` para derivar estado** (anti-pattern: `useEffect + setState` cuando basta `useMemo`):

```bash
grep -rn -A5 'useEffect' frontend/src/ --include="*.tsx" | grep -B3 'set[A-Z].*(' | head -40
```

### 3 · Frente de duplicación lógica

Busca la misma lógica reimplementada en distintos lugares (más sutil que reimplementaciones de componentes del DS):

```bash
# Cálculos de fechas hardcoded fuera de src/lib/rental-dates.ts
grep -rn 'new Date\(\|dayjs\|differenceInDays\|addDays' frontend/src/ --include="*.ts" --include="*.tsx" | grep -v 'src/lib/rental-dates'

# Normalización de texto fuera de src/lib/search/
grep -rn 'toLowerCase\(\).*replace\|normalize.*NFD\|removeAccents' frontend/src/ --include="*.ts" --include="*.tsx" | grep -v 'src/lib/search'

# Cálculos de precio fuera de la capa de helpers canónicos
grep -rn 'precio.*\*.*días\|total.*precio\|subtotal' backend/ --include="*.py" | grep -v 'reservas/\|reportes/'
```

### 4 · Frente de naming y legibilidad

```bash
# Nombres de 1-2 letras fuera de iteradores (i, j, k, e son ok)
grep -rn '\bconst [a-z]{1,2} =\b' frontend/src/ --include="*.ts" --include="*.tsx" | grep -v 'const [ijk] =\|const e =\|for '

# Funciones sin tipo de retorno explícito en módulos lib/ (inferencia opaca)
grep -rn 'export function\|export const.*=.*(' frontend/src/lib/ --include="*.ts" | grep -v ': [A-Z<]'
```

### 5 · Frente de complejidad

```bash
# Funciones con muchos niveles de anidamiento (heurística: 3+ if/for anidados)
grep -rn -A2 'if .*{' backend/ --include="*.py" | grep -c 'if.*:'

# Condicionales ternarios anidados
grep -rn '? .* ? ' frontend/src/ --include="*.tsx" --include="*.ts"
```

### 6 · Reporte y propuestas

Formato:

```
CALIDAD DE CÓDIGO — <fecha>
────────────────────────────
TS: N `any`, M casts sospechosos, P `@ts-ignore`
React: Q useEffect→setState (candidatos a useMemo), R props-drilling > 3 niveles
Duplicación: S cálculos fuera de helpers canónicos
Naming: T funciones sin retorno explícito en lib/
Complejidad: U ternarios anidados

🔴 Crítico: <lo que activamente introduce bugs o dificulta el mantenimiento>
🟡 Advertencia: <anti-patterns que escalan mal pero no rompen hoy>
✅ OK: <áreas limpias — honestidad > actividad>

Propuestas (esperando aprobación):
  1. "Calidad: eliminar N `any` en capa de API types" → fix concreto + archivo
  2. "Calidad: extraer lógica de fechas a rental-dates.ts" → N instancias
  ...
```

**No crea issues sin confirmación** — muestra los drafts, el dueño aprueba, la sesión los crea.

## Regla de oro

**Leer antes de opinar.** Un hallazgo es hipótesis hasta que se confirma en el código. Un `any`
justificado con `// ok: tipo externo sin tipos` no es deuda — es documentación. Un cast `as X` que
protege una frontera de API externa tampoco. Reportar solo lo que realmente es deuda.

## Anti-objetivos

- **Código muerto, god-modules, ramas viejas** → `mantenimiento`.
- **Calidad de tests** → `calidad-tests`.
- **Bugs de flujo de negocio** → `auditoria-profunda`.
- **Vulnerabilidades de seguridad** → `auditoria-seguridad`.
- **Drift del Design System** → `design-system`.
- **Aplicar los fixes** → la sesión aplica tras aprobación del dueño.

## Auto-mejora (correr al cerrar cada uso)

¿Algún frente fue un falso positivo sistemático? ¿Los greps matchean demasiado (ruido) o muy poco
(ciegos)? ¿Hay anti-patterns nuevos que aparecieron en la sesión y no están cubiertos? ¿Overlap
nuevo con `mantenimiento` o `calidad-tests`?

Si **SÍ** → anotar en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md)
(`fecha · skill · qué cambiar · por qué`). Proponés, no aplicás.

Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
Disparadores: "bien escrito?", "anti-patrones?", "qué tan escalable?", "duplicación lógica?",
              "patterns de React bien usados?"

6 frentes:
  1. TS: any / casts / ts-ignore
  2. React: useEffect→setState, props drilling, componentes gordos, exhaustive-deps bypassed
  3. Duplicación: lógica fuera de helpers canónicos (fechas, búsqueda, precios)
  4. Naming: variables cortas, funciones sin tipo de retorno
  5. Complejidad: anidamiento profundo, ternarios nested
  6. Reporte 🔴/🟡/✅ + draft de issues → dueño aprueba → sesión aplica
```
