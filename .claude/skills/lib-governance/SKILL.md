---
name: lib-governance
model: opus
last-reviewed: 2026-06-26
version: 1.0
description: Gobernador de tlibs — audita el estado de las librerías propias (repo `tlibs`) y su consumo en Rambla. DISPARADORES — "¿está actualizado photo-engine?", "¿hay algo para extraer a tlibs?", "¿el paquete sigue el estándar?", "auditá las librerías", "¿hay código duplicado con tlibs?", "¿cuándo bump la versión?". NO es para pulir código interno de Rambla (→ `pulido-frontend` / `calidad-codigo`); NO es para crear la librería desde cero (seguí `docs/tlibs/NEW_LIBRARY.md` en el repo tlibs).
---

# lib-governance — gobernador de tlibs y su consumo en Rambla

Materializa la decisión de extraer motores reutilizables a librerías propias (`tlibs`) con
versionado semántico, publicadas como paquetes privados. Asegura que Rambla **consuma**, no
duplique, lo que ya existe en tlibs; y que tlibs crezca cuando hay lógica reutilizable que
justifique la extracción.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Entrada → Salida |
|---|---|---|
| **`lib-governance`** (este) | "¿tlibs y Rambla están sincronizados?" | código + CHANGELOG de tlibs → diagnóstico + propuestas |
| `calidad-codigo` | "¿el código de Rambla está bien escrito?" | fuente de Rambla → hallazgos de calidad |
| `mantenimiento` | "¿hay deuda / código muerto en Rambla?" | repo Rambla → frentes A-E |
| `pendientes` | "¿cómo está la cola de issues?" | issues abiertos → triage |

## El método

### 1 · Estado de consumo en Rambla (read-only)

Chequeá qué paquetes de tlibs consume Rambla y en qué versión:

- Buscá en `backend/pyproject.toml` o `backend/requirements*.txt` la línea `tixen-*`
- Compará la versión usada contra el `CHANGELOG.md` de cada paquete en tlibs
- Marcá como **desactualizado** si la versión local < última release estable

### 2 · Detección de duplicación (read-only)

Buscá código en Rambla que reimplemente lo que ya está en un paquete tlibs:

- `grep -r "strip_exif\|optimize_image\|generate_lqip\|validate_and_detect"` en Rambla
- Si aparece fuera de `backend/services/media/` (que delega a tlibs) → duplicación
- Marcá con el archivo, línea y función duplicada

### 3 · Candidatos a extracción (read-only)

Detectá lógica en Rambla candidata a vivir en tlibs en el futuro:

Criterios de extracción (los tres deben cumplirse):
1. **Agnóstica**: no depende de modelos de Rambla, R2, PostgreSQL, ni FastAPI
2. **Reutilizable**: ya existe o existirá en otro proyecto tuyo
3. **Estable**: la API no cambia cada semana (función madura, no en desarrollo activo)

Si cumple los tres → proponer extracción. Si solo 1-2 → anotar como "candidato futuro".

### 4 · Salud de los paquetes tlibs (read-only sobre el repo tlibs)

Para cada paquete en `tlibs/packages/`:

- ¿Tiene `README.md` con API documentada, ejemplos y sección "Qué necesita"?
- ¿Tiene `ARCHITECTURE.md` con las decisiones de diseño?
- ¿Tiene `CHANGELOG.md` actualizado?
- ¿Los tests pasan en CI? (verificar el badge o el último run)
- ¿La versión en `pyproject.toml` tiene su entrada en `CHANGELOG.md`?
- ¿El `__init__.py` exporta solo la API pública (nada con `_` prefijo)?

Marcá cada paquete como **Saludable / Con deuda / Roto**.

### 5 · Propuestas (nunca aplica — solo propone)

Devolvé un reporte con secciones:

```
## Estado de consumo
- tixen-photo-engine X.Y.Z (Rambla) vs X.Y.Z (último) → [OK | DESACTUALIZADO]

## Duplicaciones detectadas
- [archivo:línea] función `X` duplica `tixen_photo_engine.processing.X`

## Candidatos a extracción
- `backend/services/Y.py::función_Z` — agnóstica, usada en N lugares, estable

## Salud de paquetes tlibs
- photo-engine: Saludable ✓ / Con deuda: [falta CHANGELOG de v0.2] / Roto: [CI rojo]

## Propuestas
1. Bumpar tixen-photo-engine a X.Y.Z en Rambla
2. Extraer `Y` a tlibs como `tixen-Z` (propuesta, no ejecutar sin aprobación)
```

## Regla de oro

**Propone, no aplica.** Ningún cambio a MEMORIA.md, pyproject.toml, ni código de Rambla
sin aprobación del dueño. Un hallazgo de duplicación no significa que haya que migrar ya —
puede ser técnicamente correcto mantenerlo en Rambla si la extracción tiene más costo que
beneficio ahora mismo.

## Anti-objetivos (cuándo NO es este skill)

- **Pulir el código de Rambla** → `pulido-frontend` o `calidad-codigo`.
- **Crear un paquete nuevo desde cero** → seguí `docs/tlibs/NEW_LIBRARY.md` en el repo tlibs.
- **Revisar si Rambla tiene bugs** → `auditoria-profunda`.
- **Gestionar los issues de tlibs** → `pendientes` (aplica a tlibs también si se configura).

## Auto-mejora (correr al cerrar cada uso)

Preguntate: ¿algún criterio de extracción quedó viejo? ¿Hay un paquete tlibs nuevo que este
skill no conoce? ¿El método de detección de duplicación perdió algún patrón nuevo?
Si SÍ → anotá en `docs/PROPUESTAS_SKILLS.md`. Si NO → no fabriques churn.

## Cheatsheet

```
1. Consumo: grep tixen-* en pyproject.toml → comparar con CHANGELOG de tlibs
2. Duplicación: grep funciones clave fuera de services/media/ → reportar archivo:línea
3. Candidatos: buscar lógica pura agnóstica → aplicar criterios (3/3 → proponer)
4. Salud: README + ARCHITECTURE + CHANGELOG + tests + API pública limpia
5. Output: reporte con propuestas — NUNCA aplicar sin aprobación
```
