---
name: catalogo
description: Auditor de completitud del catálogo de equipos — detecta equipos con datos faltantes o de baja calidad (sin foto, sin descripción pública, sin specs, precio cero, nombre poco claro) y propone el contenido para completarlos. Disparadores: "los equipos están completos?", "qué equipos les faltan fotos?", "hay equipos sin descripción?", "auditá el catálogo", "qué está incompleto?", "los equipos están bien cargados?", "qué le falta al catálogo?". NO audita la taxonomía de specs (→ specs), NO razona sobre compatibilidad (→ gear-compatibility), NO toca el código del catálogo (→ calidad-codigo).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# catalogo — auditor de completitud del catálogo de equipos

Un equipo sin foto no se alquila. Un equipo sin descripción genera consultas por WhatsApp. Un equipo
sin specs no aparece en los filtros. Este skill identifica los **huecos de datos** del catálogo y
propone el contenido para completarlos — para que el dueño apruebe y cargue.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Zona |
|---|---|---|
| **`catalogo`** (este) | "¿los equipos están completos?" | Completitud de datos: fotos, desc, specs, precio |
| `specs` | "¿la taxonomía de specs está sana?" | Consistencia del sistema de specs |
| `gear-compatibility` | "¿son compatibles?" | Razonar sobre specs técnicas |
| `design-system` | "¿el DS driftea?" | Cómo se presenta el catálogo (UI) |
| `auditoria-profunda` | "¿tiene fallas?" | Bugs en el flujo de reserva desde el catálogo |

## Fuentes de datos

- API de staging (vía staging-login): `GET /admin/equipos?page=1&per_page=100` o equivalente
- `backend/equipos/` — para entender campos canónicos
- `frontend/src/` — para entender qué campos muestra el catálogo público vs admin

## El método: detectar huecos → cuantificar → proponer contenido

### 1 · Inventario de completitud

Obtener todos los equipos activos y evaluar cada campo crítico:

```bash
# Vía staging-login + API (reemplazar con el endpoint correcto según el sistema)
# curl -s -b cookies.txt https://rambla-staging.railway.app/admin/equipos | jq '[.items[] | {id, nombre, tiene_foto: (.fotos | length > 0), tiene_desc: (.descripcion_publica != null and .descripcion_publica != ""), tiene_precio: (.precio_por_dia > 0), specs_count: (.specs | length)}]'
```

Campos a auditar:
- **`fotos`** — ¿tiene al menos 1 foto pública?
- **`nombre_publico`** — ¿tiene nombre para mostrar al cliente (≠ nombre interno)?
- **`descripcion_publica`** — ¿tiene descripción? ¿es más de 2 líneas?
- **`precio_por_dia`** — ¿precio > 0?
- **`specs`** — ¿tiene al menos las specs mínimas de su categoría?
- **`activo`** / **`visible`** — ¿está publicado?
- **`marca`** / **`modelo`** — ¿tiene marca y modelo explícitos?

### 2 · Clasificar por impacto en conversión

No todos los huecos son iguales:

🔴 **Bloquean la conversión** (el cliente no puede alquilar o no lo encuentra):
- Sin foto → baja confianza, tasa de conversión cae
- `precio_por_dia = 0` → puede generar pedidos a $0
- Sin `nombre_publico` → aparece el nombre interno (puede ser técnico/críptico)

🟡 **Reducen la calidad** (el cliente puede alquilar pero con fricción):
- Descripción muy corta (< 2 líneas)
- Sin specs (no aparece en filtros técnicos)
- Sin marca/modelo explícito

🟢 **Mejoras deseables** (enriquecen pero no bloquean):
- Solo 1 foto (conviene tener 3-4 ángulos)
- Descripción existe pero es genérica

### 3 · Para equipos sin descripción — proponer contenido

Si el dueño lo solicita, para equipos sin descripción pública, generar borradores:

**Formato de borrador:**
```
Equipo: <nombre>
Marca/Modelo: <marca> <modelo>
Categoría: <categoría>

Descripción propuesta (3-4 líneas):
<texto en español, tono profesional pero accesible, foco en para qué sirve y qué lo hace útil>

Specs mínimas a agregar:
- <spec>: <valor si se conoce>
- ...
```

La voz/tono sigue las guías de `docs/DESIGN_SYSTEM.md` § Voz/Tono:
- Claro y directo (sin jerga técnica innecesaria)
- Útil: el cliente entiende para qué lo necesita
- Sin exagerar

### 4 · Reporte

```
CATÁLOGO — <fecha>
──────────────────
Total equipos activos: N

Completitud:
  Sin foto:             X / N  (X%)
  Sin nombre público:   X / N
  Sin descripción:      X / N
  Precio = $0:          X / N
  Sin specs:            X / N

🔴 Bloquean conversión:
  - ID 42 "Canon R5" — sin precio
  - ID 17 "Tripode aluminio" — sin foto, sin descripción

🟡 Reducen calidad:
  - IDs 8, 23, 31 — descripción < 2 líneas
  - IDs 11-15 — sin specs de su categoría

✅ Completos: N equipos (X%) tienen foto + descripción + precio + al menos 1 spec

Propuestas (esperando aprobación del dueño):
  1. Completar precio de ID 42 → confirmar con el dueño
  2. Agregar foto de IDs 17, 33, 44 → el dueño toma las fotos / elige de stock
  3. Borradores de descripción para IDs 8, 23 → adjuntos abajo para aprobación
```

**No carga datos sin confirmación** — los borradores de texto son propuestas; el dueño aprueba y
la sesión los sube vía admin o API.

### 5 · Si hay un endpoint de admin para editar equipos

Una vez que el dueño aprueba los borradores, la sesión puede subirlos:

```bash
# Ejemplo: actualizar descripción vía API autenticada (con staging-login)
# curl -s -X PATCH -b cookies.txt -H "Content-Type: application/json" \
#   -d '{"descripcion_publica": "..."}' \
#   https://rambla-staging.railway.app/admin/equipos/8
```

Siempre verificar en staging antes de aplicar en prod.

## Regla de oro

**Los datos son del dueño, no de la sesión.** Las descripciones propuestas son borradores — el
dueño conoce los equipos, sabe qué hace único a cada uno y decide qué dice el catálogo. Nunca subir
texto sin aprobación explícita.

**Precio cero es crítico.** Un equipo con `precio_por_dia = 0` puede generar pedidos a $0 —
reportarlo como 🔴 siempre, aunque el equipo esté marcado como no-visible.

## Anti-objetivos

- **Taxonomía de specs inconsistente** → `specs`.
- **Compatibilidad entre equipos** → `gear-compatibility`.
- **Cómo se ve el catálogo en UI** → `design-system` o `pulido-frontend`.
- **Bugs en el flujo de reserva** → `auditoria-profunda`.
- **Cargar fotos** → el dueño las toma / elige; la sesión las sube si hay endpoint.

## Auto-mejora (correr al cerrar cada uso)

¿El endpoint de la API para listar equipos cambió? ¿Hay campos nuevos que deberían auditarse?
¿Los borradores de descripción que generé fueron bien recibidos o el dueño los reescribió totalmente?

Si **SÍ** → anotar en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md).
Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
Disparadores: "equipos completos?", "equipos sin fotos?", "sin descripción?",
              "auditá el catálogo", "qué le falta al catálogo?"

4 campos críticos (bloquean conversión si faltan):
  1. Foto (≥1)
  2. Nombre público
  3. Precio > $0
  4. Specs mínimas de la categoría

Flujo:
  1. Obtener lista de equipos activos vía API/staging
  2. Clasificar huecos: 🔴 bloquean / 🟡 reducen calidad / ✅ completos
  3. Generar borradores de descripción para los que no tienen
  4. Reporte con conteos → dueño aprueba → sesión sube vía API
```
