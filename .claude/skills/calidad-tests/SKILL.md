---
name: calidad-tests
description: Auditor de calidad y cobertura de tests — identifica paths críticos sin tests, evalúa si los tests existentes prueban comportamiento real (no solo implementación), y propone casos de prueba faltantes para edge cases y flujos de error. Disparadores: "cómo están los tests?", "hay paths sin tests?", "qué falta testear?", "auditá la cobertura", "los tests son buenos?", "qué casos borde no están testeados?", "el CI es suficiente?". NO ejecuta tests (usá el CI), NO audita calidad de código en general (→ calidad-codigo), NO busca bugs de negocio corriendo en el browser (→ auditoria-profunda).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# calidad-tests — auditor de calidad y cobertura de tests

Un test que siempre pasa no protege nada. Una suite que solo cubre el happy path da falsa
confianza. Este skill evalúa **qué está cubierto, qué falta y si los tests son útiles** — y
propone casos de prueba concretos para los gaps más peligrosos.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`calidad-tests`** (este) | "¿los tests son buenos y suficientes?" | Cobertura, calidad, edge cases sin tests |
| `auditoria-profunda` | "¿tiene fallas?" | Bugs en vivo (browser/manual), no en tests |
| `calidad-codigo` | "¿bien escrito?" | Calidad del código de tests incluida, pero foco en app |
| `mantenimiento` | "¿hay deuda?" | Tests obsoletos o que ya no corren |

## Fuentes de datos

- `backend/tests/` — suite pytest
- `frontend/src/**/*.test.*` — tests de frontend (si existen)
- `.github/workflows/ci.yml` — qué corre en CI y qué no
- `backend/reservas/`, `backend/contabilidad/`, `backend/auth.py` — los módulos críticos

## El método: mapear → evaluar → proponer

### 1 · Mapa de lo que existe

```bash
# Tests de backend: cuántos y qué cubren
find backend/tests/ -name "test_*.py" -o -name "*_test.py" 2>/dev/null | sort
wc -l backend/tests/test_*.py 2>/dev/null | sort -rn

# Tests de frontend (si hay)
find frontend/src/ -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.spec.ts" 2>/dev/null | head -20

# Cobertura actual (si hay reporte)
cat backend/.coverage 2>/dev/null || echo "no hay reporte de coverage"
```

### 2 · Evaluar cobertura de los módulos críticos

Los módulos que NO pueden fallar sin consecuencias graves:

**Backend:**
- `backend/reservas/` — motor de reservas (core sagrado)
- `backend/contabilidad/` — plata interna
- `backend/auth.py` — autenticación
- `backend/reportes/` — reportes financieros

```bash
# ¿Qué tests tocan el motor de reservas?
grep -rn 'reservas\|create_pedido\|disponibilidad\|overlap' backend/tests/ --include="*.py" | head -20

# ¿Qué tests tocan contabilidad?
grep -rn 'contabilidad\|caja\|movimiento\|cierre' backend/tests/ --include="*.py" | head -20

# ¿Qué tests tocan auth?
grep -rn 'auth\|login\|logout\|session\|cookie' backend/tests/ --include="*.py" | head -20
```

Para cada módulo crítico: clasificar cobertura estimada:
- ✅ Happy path testeado
- ⚠️ Solo happy path (faltan edge cases y error paths)
- ❌ Sin tests

### 3 · Evaluar calidad de los tests existentes

Leer los tests más importantes y evaluar:

**3a. ¿Testean comportamiento o implementación?**

Un test de comportamiento verifica "dado input X, obtengo output Y" independientemente de cómo
está implementado internamente. Un test de implementación verifica "se llamó la función Z con
parámetros W" — frágil, falla si refactorizas sin cambiar el comportamiento.

Señales de tests de implementación:
```bash
grep -rn 'mock\|patch\|MagicMock\|call_count\|assert_called' backend/tests/ --include="*.py" | head -20
```

¿Los mocks son necesarios (aislar IO externo) o están mockeando lógica de negocio propia?

**3b. ¿Los fixtures son realistas?**

```bash
# ¿Los equipos/pedidos/clientes en fixtures tienen datos realistas?
grep -rn 'equipo_id\|precio_por_dia\|fecha_desde' backend/tests/ --include="*.py" | head -20
```

Un test con `precio_por_dia=0` o `fecha_desde=None` puede pasar en un escenario imposible en prod.

**3c. ¿Los assertions son específicos?**

```bash
# Assertions demasiado vagos (solo verifican 200 OK, no el contenido)
grep -rn 'assert.*status_code == 200' backend/tests/ --include="*.py" | wc -l
grep -rn 'assert.*response.*json\|assert.*"id"\|assert.*"precio"' backend/tests/ --include="*.py" | wc -l
```

Ratio alto de "solo 200 OK" vs "verifica el contenido" → tests superficiales.

### 4 · Identificar gaps críticos

Los edge cases más peligrosos que frecuentemente no están testeados:

**Reservas (el core sagrado):**
- [ ] Reserva concurrente del mismo equipo (→ ya hay un test tras PR #969?)
- [ ] Equipo con stock = 0 (no debería poder reservarse)
- [ ] Rango de fechas que cruza el buffer de bloqueo
- [ ] Equipo compuesto: disponibilidad cuando una pieza hija no está disponible
- [ ] `fecha_desde >= fecha_hasta` (fechas inválidas)
- [ ] Reserva en fechas pasadas

**Auth:**
- [ ] Token expirado → responde 401, no 500
- [ ] Cookie manipulada → responde 401, no 500
- [ ] Acceso a endpoint de admin siendo cliente → 403

**Contabilidad:**
- [ ] Movimiento con monto negativo
- [ ] Cierre de mes cuando ya hay un cierre en esa fecha
- [ ] Reconciliación con movimientos faltantes

**API en general:**
- [ ] Inputs con caracteres especiales (SQL injection attempt, XSS en JSON)
- [ ] IDs inexistentes → 404, no 500
- [ ] Paginación con `page=0` o `page=-1`

```bash
# Buscar tests de edge cases ya existentes
grep -rn 'fecha_hasta.*fecha_desde\|stock.*0\|id.*inexistente\|404\|expires\|invalid' backend/tests/ --include="*.py" | head -20
```

### 5 · Evaluar el CI

Leer `.github/workflows/ci.yml`:

```bash
cat .github/workflows/ci.yml | grep -A5 'pytest\|test\|coverage'
```

- ¿El CI corre con `--cov` para reportar cobertura?
- ¿Hay un gate de cobertura mínima?
- ¿Los tests de CI usan una BD de prueba (Postgres real, como en el CI actual)?
- ¿Hay tests de integración E2E o solo unitarios?

### 6 · Reporte y propuestas de tests

```
CALIDAD DE TESTS — <fecha>
───────────────────────────
Backend tests: N archivos, M tests
Frontend tests: P archivos (o "ninguno todavía")

Cobertura estimada de módulos críticos:
  reservas/:       ✅ happy path | ⚠️ edge cases | ❌ sin tests
  contabilidad/:   ...
  auth.py:         ...
  reportes/:       ...

Calidad de tests existentes:
  - Assertions: N tests solo verifican 200 OK (sin verificar contenido)
  - Mocks: M mocks de lógica propia (frágiles ante refactor)
  - Fixtures: K fixtures con datos poco realistas

Gaps críticos identificados:
  🔴 Sin tests:
    - Reserva concurrente mismo equipo (core sagrado — aunque en PR #969 puede estar)
    - Token expirado → 401 (no 500)
    - IDOR: acceso a pedido ajeno → 403

  🟡 Solo happy path:
    - Cierre de mes: no hay test de doble cierre
    - Búsqueda: no hay test con caracteres especiales

  ✅ Bien cubiertos:
    - Flujo básico de reserva
    - Login/logout

Propuestas (esperando aprobación):
  1. "Tests: edge cases de reservas concurrentes" (si no está post-PR #969)
  2. "Tests: auth — token expirado, cookie manipulada, IDOR"
  3. "Tests: contabilidad — doble cierre, monto negativo"
```

**No escribe tests sin confirmación** — propone los casos, el dueño aprueba, la sesión implementa.

## Regla de oro

**Un test que no puede fallar no protege nada.** Antes de proponer un test, imaginar qué bug
detectaría. Si no se puede imaginar un bug real que ese test atraparía → no vale la pena escribirlo.

**Cobertura de líneas ≠ calidad.** El 100% de cobertura con fixtures irreales y assertions de solo
"200 OK" da falsa confianza. Preferir 40% de cobertura con tests que detectan bugs reales.

## Anti-objetivos

- **Ejecutar tests / correr CI** → `Bash` directo, no este skill.
- **Buscar bugs en vivo** → `auditoria-profunda`.
- **Código de tests mal escrito** → `calidad-codigo`.
- **Tests obsoletos / código muerto de tests** → `mantenimiento`.
- **Escribir los tests** → la sesión los escribe tras aprobación del dueño.

## Auto-mejora (correr al cerrar cada uso)

¿Hubo casos de prueba propuestos que el dueño descartó por irrelevantes? ¿Cambió la arquitectura
de tests (nuevo framework, nueva estructura)? ¿Hay módulos nuevos críticos no cubiertos en el método?

Si **SÍ** → anotar en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md).
Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
Disparadores: "cómo están los tests?", "paths sin tests?", "qué falta testear?",
              "cobertura?", "los tests son buenos?", "casos borde sin tests?"

4 pasos:
  1. Mapa: qué tests existen (backend/tests/, frontend/*.test.*)
  2. Cobertura: módulos críticos (reservas, contabilidad, auth, reportes)
  3. Calidad: comportamiento vs implementación, assertions específicos, fixtures realistas
  4. Gaps: edge cases sin tests (concurrencia, expiración, IDOR, inputs inválidos)

Reporte ✅/⚠️/❌ por módulo + draft de casos de prueba → dueño aprueba → sesión escribe
```
