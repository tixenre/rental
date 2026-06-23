---
name: specs
description: Gobernador del sistema de specs de equipos — audita que la taxonomía de especificaciones técnicas sea consistente, completa y bien tipada (sin duplicados con nombres distintos, sin specs informales que deberían ser formales, sin categorías huérfanas). Lee y razona; propone cambios. Disparadores: "auditá las specs", "las specs están inconsistentes?", "qué specs faltan?", "hay specs duplicadas con nombres distintos?", "el sistema de specs está sano?", "normalizá las specs". NO razona sobre compatibilidad entre equipos (→ gear-compatibility), NO audita completitud del catálogo (→ catalogo).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# specs — gobernador del sistema de especificaciones técnicas

Las specs son el motor del catálogo técnico de Rambla: permiten filtrar, comparar y razonar sobre
compatibilidad. Sin consistencia en la taxonomía, la búsqueda falla y `gear-compatibility` razona
sobre datos sucios. Este skill mantiene ese sistema **sano y sin drift**.

Contexto completo del sistema: [`docs/SISTEMA_SPECS.md`](../../../docs/SISTEMA_SPECS.md).

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`specs`** (este) | "¿la taxonomía de specs está sana?" | Consistencia, duplicados, gaps, tipos |
| `gear-compatibility` | "¿estos equipos son compatibles?" | Razonar sobre qué specs significan |
| `catalogo` | "¿los equipos están completos?" | Datos faltantes: fotos, descripciones, precios |
| `mantenimiento` | "¿hay deuda de código?" | Código del motor de specs, no los datos |
| `calidad-codigo` | "¿bien escrito?" | Código del sistema de specs, no la taxonomía |

## Fuentes de datos

- `docs/SISTEMA_SPECS.md` — el manual del sistema: qué es una spec, cómo se estructura, categorías canónicas
- `backend/specs/` (o el módulo equivalente) — lógica del motor
- Base de datos: tabla `spec_types`, `spec_values`, `equipo_specs` (o nombres equivalentes)
- Los equipos en `backend/` o vía API staging — para ver qué specs tienen asignadas

## El método: leer → auditar → proponer

### 1 · Leer la arquitectura actual

Antes de auditar, entender el estado del sistema:

```bash
# ¿Dónde vive la lógica de specs?
find backend/ -name "*.py" | xargs grep -l "spec" | grep -v __pycache__ | head -10

# ¿Hay una tabla de tipos de spec?
grep -rn 'spec_type\|SpecType\|spec_categoria' backend/ --include="*.py" | head -20

# ¿Cómo se modela una spec en la BD?
grep -rn 'class Spec\|class EquipoSpec\|spec_types' backend/ --include="*.py" | head -10
```

Leer `docs/SISTEMA_SPECS.md` completo para entender la taxonomía vigente.

### 2 · Auditar consistencia de nombres

El riesgo principal: la misma spec con nombres distintos en distintos equipos.
Ejemplos típicos: "Montura" vs "Mount", "Resolución" vs "Resolución sensor", "ISO max" vs "ISO máximo".

Revisar los spec_types registrados:

```bash
# Listar todos los tipos de spec del sistema (si hay endpoint o acceso a BD)
# Vía staging-login y API:
# GET /admin/specs/types  (verificar si existe este endpoint)
```

O leer directamente las migraciones/seeds para ver los tipos canónicos:

```bash
grep -rn 'spec_type\|spec_name\|INSERT INTO spec' backend/ --include="*.py" | head -30
grep -rn "'montura'\|'mount'\|'resolución'\|'resolution'" backend/ --include="*.py" -i
```

Buscar:
- Duplicados obvios (mismo concepto, nombre distinto)
- Mezcla de idiomas (español vs inglés en el mismo nivel)
- Nombres demasiado genéricos ("Otro", "Extra", "Valor")
- Nombres con typos o capitalización inconsistente

### 3 · Auditar gaps en categorías de equipos

¿Hay tipos de equipo sin specs formalizadas cuando claramente deberían tenerlas?

Por ejemplo: un trípode sin spec de "carga máxima" o "altura máxima"; una cámara sin "montura";
un lente sin "focal" ni "apertura".

Leer los equipos por categoría y verificar qué specs tienen asignadas:

```bash
# Categorías de equipo
grep -rn 'categoria\|EquipoCategoria\|equipo_tipo' backend/ --include="*.py" | head -20
```

Cruzar: si la categoría "Lentes" tiene 10 equipos y 6 tienen spec "Focal" → ¿los otros 4 no la
tienen o la spec tiene nombre distinto?

### 4 · Auditar specs informales

¿Hay atributos que se describen en texto libre cuando deberían ser specs formales con tipo?
Señales: campo `descripcion` o `notas` que repite la misma información estructurada en cada equipo.

```bash
# Campos de texto largo que podrían ser specs estructuradas
grep -rn 'descripcion_tecnica\|notas_specs\|specs_texto' backend/ --include="*.py"
```

### 5 · Auditar el motor de specs

¿El código del motor procesa los tipos de spec de forma robusta?

```bash
# ¿Hay validación de tipos? (int/float/enum/texto)
grep -rn 'spec_tipo\|spec_value_type\|validate.*spec' backend/ --include="*.py"

# ¿Hay unit tests del motor?
find backend/ -name "test_spec*" -o -name "*test*spec*" 2>/dev/null
```

### 6 · Reporte y propuestas

```
SPECS — <fecha>
────────────────
Tipos de spec registrados: N
Equipos con al menos 1 spec: M / Total
Categorías auditadas: K

Inconsistencias detectadas:
  - Duplicados: <lista>
  - Gaps críticos: <categorías sin specs que deberían tenerlas>
  - Specs informales: <texto libre que debería ser formal>
  - Typos/capitalización: <lista>

🔴 Crítico (afecta búsqueda o gear-compatibility):
  - "Montura" y "Mount" → el mismo concepto, genera split en filtros

🟡 Advertencia:
  - Trípodes sin spec "carga máxima" (afecta recomendaciones)

✅ OK:
  - Cámaras: focal, apertura, montura → bien formalizadas

Propuestas (esperando aprobación):
  1. "Specs: normalizar 'Mount' → 'Montura' en N equipos"
  2. "Specs: formalizar spec 'Carga máxima (kg)' para categoría Trípodes"
  3. "Specs: agregar spec 'Focal (mm)' a N lentes que la tienen en texto libre"
```

**No aplica cambios sin confirmación** — muestra los drafts, el dueño aprueba.

## Regla de oro

**Leer SISTEMA_SPECS.md antes de auditar.** El sistema puede tener convenciones intencionales
que parezcan inconsistencias (ej. español en todo salvo términos técnicos universales en inglés).
Un hallazgo incorrecto que lleve a renombrar specs puede romper datos existentes — confirmar con
el dueño antes de ejecutar cualquier migración de datos.

**Las specs son datos, no código.** Cambiar un nombre de spec puede requerir migración de filas
en la BD. Siempre proponer con impacto estimado (N equipos afectados).

## Anti-objetivos

- **Razonar sobre compatibilidad** → `gear-compatibility`.
- **Datos faltantes en equipos (fotos, descripciones)** → `catalogo`.
- **Bugs en el motor de specs** → `auditoria-profunda`.
- **Código del motor de specs** → `calidad-codigo` o `mantenimiento`.
- **Aplicar cambios de datos** → la sesión aplica tras aprobación + migración aprobada.

## Auto-mejora (correr al cerrar cada uso)

¿Se agregaron categorías de equipo nuevas que no están en el método? ¿Cambió la estructura de la BD
de specs? ¿Los greps apuntan a los paths correctos del motor?

Si **SÍ** → anotar en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md).
Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
Disparadores: "auditá las specs", "specs inconsistentes?", "qué specs faltan?",
              "specs duplicadas con nombres distintos?", "normalizá las specs"

Fuente: docs/SISTEMA_SPECS.md (leer primero)

4 frentes de auditoría:
  1. Consistencia de nombres: duplicados, bilingüismo, typos
  2. Gaps por categoría: equipos sin specs que deberían tener
  3. Specs informales: texto libre que debería ser estructurado
  4. Motor: validación de tipos, tests

Reporte 🔴/🟡/✅ + draft issues → dueño aprueba → sesión aplica (con migración de datos)
```
