---
name: performance
description: Auditor de performance — evalúa sistemáticamente la velocidad de la app (Core Web Vitals, bundle size, re-renders de React, N+1 en queries, caching). Lee y razona; propone issues con fixes concretos. Disparadores: "está lenta la app?", "el bundle es muy pesado?", "hay N+1?", "Core Web Vitals", "qué tan rápido carga?", "auditá la performance", "optimizá el bundle", "hay queries lentas?". NO busca bugs de negocio (→ auditoria-profunda), NO audita calidad de código (→ calidad-codigo), NO audita seguridad (→ auditoria-seguridad).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# performance — auditor de performance de la app

Una app lenta es una app que pierde ventas. Este skill evalúa la **performance real** de Rambla:
desde el bundle que descarga el usuario hasta las queries que corren en Postgres. Read-only —
propone issues con prioridad; el dueño aprueba; la sesión aplica.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`performance`** (este) | "¿está rápido?" | Bundle, CWV, re-renders, N+1, caching |
| `auditoria-profunda` | "¿tiene fallas?" | Bugs de negocio, edge cases |
| `auditoria-seguridad` | "¿está seguro?" | OWASP, auth, headers |
| `calidad-codigo` | "¿bien escrito?" | Patterns, tipado, complejidad |
| `design-system` | "¿el DS driftea?" | Tokens, adopción, 11 principios |

## El método: medir → analizar → proponer

### 1 · Bundle size (frontend)

```bash
cd frontend

# Analizar el bundle actual
npm run build -- --mode production 2>&1 | grep -E 'dist/|kB|MB'

# Top chunks por tamaño
ls -lh dist/assets/*.js | sort -rh | head -10
```

Buscar:
- **Chunk total > 500 KB gzipped** → analizar con `rollup-plugin-visualizer` (ya en `package.json`)
- **Dependencias pesadas sin lazy load** (PDF renderers, chart libs, date libs)
- **Re-exports de íconos completos** (Lucide shake automático, pero verificar)

```bash
# ¿Se importa todo Lucide o selectivamente?
grep -rn "from 'lucide-react'" frontend/src/ --include="*.tsx" | grep -v '{ ' | head -5

# Dependencias más pesadas en package.json
node -e "const p=require('./package.json'); const d={...p.dependencies,...p.devDependencies}; console.log(Object.keys(d).join('\n'))" | head -20
```

### 2 · Code splitting y lazy loading

```bash
# Routes con lazy loading (React.lazy / dynamic import)
grep -rn 'React.lazy\|lazy(() =>\|import(' frontend/src/ --include="*.tsx" --include="*.ts" | grep -v '// import\|\.css\|\.svg'

# Routes que NO tienen lazy (candidatas si son páginas grandes)
grep -rn "component:" frontend/src/ --include="*.tsx" | grep -v 'lazy\|Lazy'
```

Evaluar: ¿las rutas admin y las rutas cliente están en chunks separados? ¿Los componentes pesados
(tablas grandes, PDF viewers, calendarios) tienen lazy load?

### 3 · React rendering

**3a. Re-renders innecesarios** — leer los componentes más visitados (catálogo, portal cliente,
admin dashboard) y evaluar:
- ¿Las props que se pasan son objetos/arrays creados inline (nuevas referencias en cada render)?
- ¿Hay `useCallback`/`useMemo` donde la prop es costosa de calcular?
- ¿Los context providers tienen valores estables (no `{{ objeto: nuevo }}`)?

```bash
# Context providers con objetos inline (anti-pattern: nueva referencia en cada render)
grep -rn 'value={{' frontend/src/ --include="*.tsx"

# Componentes que reciben callbacks sin useCallback
grep -rn 'onChange={(' frontend/src/ --include="*.tsx" | head -20
```

**3b. Listas largas sin virtualización:**

```bash
# .map() en listas que podrían ser largas (>50 items) sin VirtualList
grep -rn '\.map((.*) =>' frontend/src/components/ --include="*.tsx" | grep -v 'className\|style\|filter\|reduce' | wc -l
```

Leer los contextos de uso — el catálogo de equipos, la lista de pedidos en admin.

### 4 · N+1 y queries lentas (backend)

**4a. Detectar N+1 potenciales:**

```bash
# Queries dentro de loops (señal de N+1)
grep -rn -A3 'for .*in\|for.*range' backend/ --include="*.py" | grep 'db.execute\|session.query\|\.scalar\|\.fetchone'

# SELECT sin límite en endpoints de lista
grep -rn 'SELECT.*FROM\|session.query' backend/ --include="*.py" | grep -v 'LIMIT\|\.limit(\|pagina'
```

**4b. Índices faltantes** — leer las migraciones Alembic más recientes y `backend/database.py::init_db()`:

```bash
grep -rn 'Index\|index=True\|CREATE INDEX' backend/ --include="*.py" | head -30
```

Cruzar con queries frecuentes: ¿`WHERE equipo_id =` tiene índice? ¿`WHERE cliente_id AND estado =`?
¿`ORDER BY fecha_desde` en reservas?

**4c. Queries de búsqueda:**

```bash
# Verificar que búsqueda use pg_trgm (el motor canónico de backend/busqueda/)
grep -rn 'pg_trgm\|similarity\|word_similarity' backend/ --include="*.py"
# Y que no haya ILIKE/LIKE ad-hoc
grep -rn 'ILIKE\|\.like\b' backend/ --include="*.py" | grep -v 'busqueda/'
```

### 5 · Caching

**5a. React Query staleTime:**

```bash
# Queries sin staleTime explícito (se re-fetchean en cada mount)
grep -rn 'useQuery\|useSuspenseQuery' frontend/src/ --include="*.ts" --include="*.tsx" | grep -v 'staleTime\|gcTime'
```

Evaluar: ¿datos que no cambian frecuentemente (equipos del catálogo, áreas, config) tienen
`staleTime: Infinity` o al menos varios minutos?

**5b. HTTP cache headers:**

```bash
# Assets estáticos del frontend — ¿Vite genera hashes en nombres?
ls dist/assets/*.js 2>/dev/null | head -5  # buscar fingerprint en el nombre

# Railway — headers de cache para assets estáticos
grep -rn 'Cache-Control\|cache_control\|max-age' backend/ --include="*.py"
```

### 6 · Fuentes y assets

```bash
# ¿Las fuentes se precargan?
grep -rn 'preload\|font-display' frontend/index.html frontend/src/ --include="*.css" 2>/dev/null

# ¿Imágenes tienen tamaños explícitos (evita CLS)?
grep -rn '<img\b' frontend/src/ --include="*.tsx" | grep -v 'width=\|height=\|className.*w-\|className.*h-' | head -10
```

### 7 · Reporte

```
PERFORMANCE — <fecha>
─────────────────────
Bundle: <N KB gzip total>, <M KB chunk más grande>
Code splitting: <N routes con lazy / M sin>
React renders: <N contextos con objetos inline, M callbacks sin useCallback>
N+1: <ok / N endpoints con riesgo>
Índices faltantes: <ok / N queries sin índice>
Cache React Query: <N queries sin staleTime>
Fuentes: <preload ok / ausente>

🔴 Impacto alto (usuario lo nota):
  - ...

🟡 Impacto medio:
  - ...

✅ OK:
  - ...

Propuestas (esperando aprobación):
  1. "Perf: lazy load rutas admin" → separar del chunk cliente
  2. "Perf: índice en reservas(equipo_id, estado)" → N consultas lo usan
  ...
```

## Regla de oro

**Medir antes de optimizar.** Un `useCallback` sin profiling puede ser ruido (React es rápido).
Un `useMemo` en un cálculo de 0.1ms es prematura optimización. Priorizar lo que el usuario siente
(LCP, tiempo de carga inicial, queries lentas visibles) sobre micro-optimizaciones.

## Anti-objetivos

- **Bugs de negocio** → `auditoria-profunda`.
- **Seguridad** → `auditoria-seguridad`.
- **Calidad de código** → `calidad-codigo`.
- **Aplicar fixes** → la sesión aplica tras aprobación.

## Auto-mejora (correr al cerrar cada uso)

¿Cambió el stack de bundling? ¿Hay dependencias nuevas pesadas? ¿Los greps de N+1 tienen muchos
falsos positivos? ¿Falta algún frente (WebSockets, SSE, streaming)?

Si **SÍ** → anotar en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md).
Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
Disparadores: "está lenta la app?", "bundle pesado?", "N+1?", "Core Web Vitals",
              "queries lentas?", "auditá la performance"

6 frentes:
  1. Bundle: tamaño total, chunks grandes, deps pesadas
  2. Code splitting: lazy en routes/componentes pesados
  3. React renders: contextos inline, callbacks sin useCallback, listas sin virtual
  4. N+1: queries en loops, SELECTs sin límite, índices faltantes
  5. Cache: staleTime en React Query, HTTP cache en assets
  6. Fuentes/assets: preload, imágenes con dimensiones (evitar CLS)

Reporte 🔴/🟡/✅ + draft issues → dueño aprueba → sesión aplica
```
