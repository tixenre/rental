# Diseño — Sistema bulletproof de specs / categorías / relevancia / compatibilidad

> **Estado**: borrador para revisión. **Fecha**: 2026-05-10.
> Este documento NO se implementa hasta que esté revisado y aprobado.

## 0 · Objetivo

Resolver la fricción actual del modelo de datos para representar equipos heterogéneos (cámara, lente, luz, grip, cable…) de manera que:

1. **Cada categoría tenga sus specs propias** (sensor para cámara, CRI para luz, focal para lente). No un `[{label, value}]` genérico.
2. La **IA llene los specs correctos** al importar desde URL, usando el template de la categoría como schema esperado.
3. Los **nombres** se construyan de **una sola fuente de verdad** y se vean iguales en todos lados (catálogo, ficha, lista admin, albarán, presupuesto).
4. Se pueda **ordenar por relevancia** (RED Komodo > GoPro), no sólo alfabético.
5. Se pueda **definir compatibilidades** entre equipos (FX3 + Sigma → necesita adaptador), aunque la UI venga después.
6. La **migración** de los 163 equipos actuales no pierda data ni rompa pedidos en curso.

---

## 1 · Resumen de cambios al modelo de datos

| Cosa | Antes | Después |
|---|---|---|
| **Specs** | `equipo_fichas.specs_json` (lista libre `[{label, value}]`) | `equipo_specs` (key/value tipados) + `categoria_spec_templates` (schema por categoría) |
| **Keywords** | `keywords_json` editorial + `equipo_etiquetas` con `origen='auto'\|'manual'` | Igual — funciona bien, mantenemos. Las auto se generan también desde specs estructuradas. |
| **Nombre público** | `buildPublicName()` en frontend + `nombre_publico_template` en ficha | Helper único en backend que devuelve `nombre_publico` ya armado. Frontend lo lee y lo muestra. |
| **Orden / Relevancia** | `ORDER BY equipos.nombre` (alfabético) | Nueva columna `equipos.relevancia INT DEFAULT 100` + sort por `relevancia ASC, nombre ASC`. Categorías ya tienen `prioridad`. |
| **Compatibilidades** | `compatible_con_json` (lista de strings sueltos en ficha) | Tabla `equipo_compatibilidad` (id_a, id_b, tipo) + opción "requiere adaptador" |
| **Categorías** | Árbol 2 niveles, ya está OK | Mantener. Confirmar con usuario las que están de más. |

---

## 2 · Categorías (sin tocar la jerarquía actual)

El sistema ya tiene un árbol decente de 2 niveles. Lo dejamos:

```
Cámaras: Video, Foto, Acción
Lentes: Zoom E-mount, Zoom EF, Fijos EF, Especiales, Vintage
Adaptadores y Filtros: Adaptadores de montura, Filtros 82mm
Iluminación: LED daylight/bicolor, LED RGB, Tungsteno, Fluorescente, On-camera/Flash, Práctica/efecto
Modificadores
Soportes: Trípodes video, Trípodes foto, C-Stands, Estabilización, Slider/Dolly, Car Mount
Grip: Brazos, Clamps, Wall plates, Pinzas, Líneas seguridad, Sopapa, Lastre
Sonido: Inalámbricos/Lavalier, Shotgun/Boom, On-camera, Estudio/Podcast, Intercom
Monitores y Video: Monitores, Grabadores, Transmisión inalámbrica, Follow Focus/Matebox
Energía: V-Mount, NP/LP-E6, Distribución eléctrica
Media y Datos: Tarjetas SD, CFexpress, Lectores
Estudio y Producción: Set/Backdrops, Paquetes
```

**Nuevo en este rediseño**: cada categoría (raíz o hija) puede tener un **template de specs**.

Cuando se asigna una categoría a un equipo, el form muestra los specs de ese template. Si un equipo está en múltiples categorías, **se mergean** los templates (con dedup por key).

---

## 3 · Specs por categoría (template-based)

### 3.1 · Tabla nueva: `categoria_spec_templates`

```sql
CREATE TABLE categoria_spec_templates (
  id            SERIAL PRIMARY KEY,
  categoria_id  INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
  spec_key      VARCHAR(64) NOT NULL,        -- ej. 'sensor', 'montura', 'cri'
  label         VARCHAR(120) NOT NULL,       -- ej. 'Sensor', 'Montura', 'CRI'
  tipo          VARCHAR(16) NOT NULL,        -- 'string'|'number'|'enum'|'bool'
  unidad        VARCHAR(32),                 -- ej. 'mm', 'W', 'lm'
  enum_options  JSONB,                       -- ['E', 'RF', 'EF', ...] si tipo=enum
  prioridad     INTEGER DEFAULT 100,         -- orden en la ficha
  visible_en_card BOOLEAN DEFAULT FALSE,    -- si aparece en card del catálogo
  visible_en_filtros BOOLEAN DEFAULT FALSE, -- si genera filtro en catálogo
  obligatorio   BOOLEAN DEFAULT FALSE,       -- si es requerido al crear
  ayuda         TEXT,                        -- descripción para el form

  UNIQUE (categoria_id, spec_key)
);

CREATE INDEX idx_spec_templates_cat ON categoria_spec_templates(categoria_id, prioridad);
```

### 3.2 · Tabla nueva: `equipo_specs`

```sql
CREATE TABLE equipo_specs (
  equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
  spec_key    VARCHAR(64) NOT NULL,
  value       TEXT NOT NULL,           -- siempre string, parsea el cliente según tipo
  PRIMARY KEY (equipo_id, spec_key)
);

CREATE INDEX idx_equipo_specs_key ON equipo_specs(spec_key, value);
-- Permite filtros del catálogo eficientes ("luces con cri >= 95")
```

### 3.3 · Templates iniciales (seed)

Voy a poner ~6 templates al toque. El admin puede editar después.

**Cámara** (categoría=Cámaras o cualquier hija)
```
sensor          string   visible_en_card  ej "Full-frame 12.1MP"
montura         enum     visible_en_filtros, en_card  [E, RF, EF, L, Z, X, MFT, PL, BMD]
video_max       enum     visible_en_filtros          [4K, 6K, 8K, FHD, 12K]
fps_max         number   unidad="fps"
iso_max         number   unidad="ISO"
peso            string                                ej "640 g"
estabilizacion  bool     visible_en_filtros
autofocus       bool
```

**Lente**
```
montura         enum     obligatorio, en_card, en_filtros  [E, RF, EF, L, Z, X, MFT, PL]
focal_min       number   unidad="mm"   en_card
focal_max       number   unidad="mm"
apertura_max    string   ej "f/1.4"    en_card
formato         enum     [Full-frame, APS-C, MFT, S35, M43]
peso            string
estabilizacion  bool
autofocus       bool
```

**Luz LED**
```
potencia        number   unidad="W"           en_card, en_filtros
lumens          number   unidad="lm"
cri             number   rango=[0,100]        en_filtros
temperatura     string   ej "3200K-5600K"
bicolor         bool     en_filtros
rgb             bool     en_filtros
alimentacion    enum     [V-mount, NP-F, AC, USB-C, Híbrida]
peso            string
```

**Grip / Soporte**
```
peso_max_kg     number   unidad="kg"
material        enum     [Aluminio, Acero, Carbono, Plástico, Mixto]
monturas        string   ej "1/4-20, 3/8-16"
plegado         bool
```

**Cable** (preparado para cuando los agregues)
```
tipo            enum     obligatorio, en_filtros  [HDMI, USB-C, USB-A, SDI, XLR, BNC, RJ45, DC]
version         string   ej "HDMI 2.1"
largo_m         number   unidad="m"   obligatorio, en_filtros
conector_a      string
conector_b      string
blindaje        bool
genero          enum     [M-M, M-H, H-H]
```

**Sonido / Micrófono**
```
tipo            enum     [Lavalier, Shotgun, On-camera, Estudio, Inalámbrico]
patron          enum     [Cardioide, Supercardioide, Omni, Bidireccional]
banda           string   ej "2.4 GHz"
canales         number
alimentacion    enum     [Phantom 48V, AA, USB-C, NP-F]
```

### 3.4 · Cómo se rellena al importar desde URL

1. Al importar (`/admin/equipos/enriquecer`), el backend ahora:
   - Detecta la categoría sugerida por la IA.
   - Busca el template de specs de esa categoría.
   - Pasa el template a Firecrawl como **schema esperado**: "extraé estos campos específicos".
   - Guarda los valores extraídos en `equipo_specs` con sus keys.
2. Si la IA encuentra un campo que no está en el template, lo guarda igual con prefix `_extra_` (no se pierde).
3. El admin lo edita después si quiere mover algo a "extras".

### 3.5 · Cómo se rellena manualmente

Form de equipo:

```
[Tab "Datos básicos"]
  ... como ahora

[Tab "Ficha técnica"]
  Específicas (según categoría asignada):
    Sensor:       [Full-frame CMOS 12.1MP_______]
    Montura:      [E ▼]
    Video máx:    [4K ▼]
    FPS máx:      [120 fps]
    ISO máx:      [102400]
    Peso:         [640 g________]
    Estabilización: [✓]
    Autofocus:    [✓]

  Extras (lo que la IA encontró pero no está en el template):
    Garantía:     [2 años]
  + Agregar campo extra...
```

Si no hay categoría asignada → el form muestra "Asigná una categoría primero para ver los specs específicos" + el bloque de "extras" libre (compat con flujo actual).

---

## 4 · Nombres consistentes (single source of truth)

### 4.1 · Backend genera el nombre público

Mover `buildPublicName` del frontend al **backend**, en `/api/equipos` y `/api/equipos/:id`. El response incluye:

```json
{
  "id": 42,
  "nombre": "FX3 Cuerpo",                  // interno (admin)
  "nombre_publico": "Sony FX3 Montura E",  // calculado
  ...
}
```

Frontend siempre usa `nombre_publico` (catálogo, modal, lista, albarán, presupuesto). El `nombre` interno se muestra solo en `/admin/equipos`.

### 4.2 · Lógica del nombre público

```
1. Si equipo.nombre_publico_template (definido en ficha) → render con tokens.
2. Sino → auto: [tipo, marca, modelo, ...specs marcadas en_nombre_publico]
   (fallback al template default de la categoría si existe)
3. Si todo vacío → equipo.nombre interno
```

Tokens disponibles según categoría: cualquier `spec_key` del template + `tipo` (categoría raíz) + `marca` + `modelo` + `nombre`.

### 4.3 · Albarán y presupuesto

Estos hoy renderizan `equipo.nombre` (interno). Cambian a `equipo.nombre_publico` para consistencia con lo que ve el cliente.

---

## 5 · Relevancia / orden de equipos

### 5.1 · Nueva columna

```sql
ALTER TABLE equipos ADD COLUMN relevancia INT NOT NULL DEFAULT 100;
CREATE INDEX idx_equipos_relevancia ON equipos(relevancia, nombre);
```

Convención: **menor número = más prominente**.
- `10` — flagship (RED Komodo X, FX9, Alexa Mini)
- `30` — premium (FX3, Sony A7S III, Sigma Art)
- `60` — workhorse (BMPCC 6K, A7 III)
- `100` — default
- `200` — accesorios genéricos (cables, baterías, plates)

### 5.2 · UI

- **Lista admin** (`/admin/equipos`) → nueva columna "Relevancia" editable inline (input number).
- **Catálogo público** → ordena por `relevancia ASC, nombre ASC`. Los flagship aparecen arriba.
- **Modal de detalle** → muestra "🏆 Equipo destacado" si `relevancia <= 30` (ajustable).

### 5.3 · Categorías ya tienen `prioridad`

Mantenemos el sistema actual. Los filtros del catálogo siguen ordenados por `categorias.prioridad`.

---

## 6 · Compatibilidades

### 6.1 · Tabla nueva

```sql
CREATE TABLE equipo_compatibilidad (
  id            SERIAL PRIMARY KEY,
  equipo_a_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
  equipo_b_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
  tipo          VARCHAR(32) NOT NULL,    -- 'compatible' | 'incompatible' | 'requiere_adaptador'
  nota          TEXT,                    -- ej. "necesita Sigma MC-11"
  adaptador_id  INTEGER REFERENCES equipos(id),  -- opcional: equipo que resuelve
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE (equipo_a_id, equipo_b_id, tipo),
  CHECK (equipo_a_id != equipo_b_id)
);

CREATE INDEX idx_compat_a ON equipo_compatibilidad(equipo_a_id);
CREATE INDEX idx_compat_b ON equipo_compatibilidad(equipo_b_id);
```

### 6.2 · Casos de uso

- **FX3 + Sigma EF lente** → `tipo='requiere_adaptador'`, `adaptador_id=<MC-11>`, `nota='Sigma MC-11 EF→E'`
- **Tarjeta SD UHS-II + cámara con SD UHS-I** → `tipo='compatible'`, `nota='Funciona pero a velocidad UHS-I'`
- **Lente PL + body sin montura PL** → `tipo='incompatible'`

### 6.3 · Reglas automáticas (futuro)

Si `equipo_a` es lente con `montura=E` y `equipo_b` es body con `montura=RF` → sugerir `requiere_adaptador`. Esto se puede generar a partir de las specs estructuradas. **No se implementa ahora**, queda como hook futuro.

### 6.4 · UI (futuro)

Por ahora, el modelo existe pero la UI viene después. Endpoint `GET /api/equipos/:id/compatibilidades` lee la tabla. Cuando lo necesites en el front, te aviso un punto donde enchufarlo (ej. "Compatibles con esto" en el modal de detalle).

---

## 7 · Migración (cómo no romper nada)

### Fase 1 · Aditivos (sin tocar lo viejo)

1. Crear tablas nuevas: `categoria_spec_templates`, `equipo_specs`, `equipo_compatibilidad`.
2. Agregar columna `equipos.relevancia`.
3. Backend devuelve `nombre_publico` calculado (frontend sigue usando `buildPublicName` por compat, pero ya tiene la opción de leer del backend).

### Fase 2 · Seed templates

Insertar templates iniciales (cámara, lente, luz, grip, cable, sonido). Idempotente — si existen, no se pisan.

### Fase 3 · Migración de specs viejos

Script idempotente que recorre `equipo_fichas.specs_json` y mapea a `equipo_specs`:
- Match exacto por label (case-insensitive): "Sensor" → `sensor`, "Mount" → `montura`, "ISO" → `iso_max`.
- Usar diccionario de aliases comunes: `{ "mount": "montura", "weight": "peso", "lens mount": "montura", ... }`.
- Lo que no matchee → `_extra_<slug>` con valor original.
- Reporte: cuántos específicos vs extras por equipo.

El `specs_json` se mantiene en la DB como **backup** unas semanas; después se borra.

### Fase 4 · Frontend

- `/admin/equipos` agrega columna "Relevancia" + filtro por categoría con templates aplicados.
- `EquipoFormDialog` tab "Ficha técnica" pasa de inputs libres a inputs por template.
- Catálogo público ordena por `relevancia ASC, nombre ASC`.
- `EquipmentCard` y `EquipmentDetailDialog` leen `nombre_publico` del backend.

### Fase 5 · Limpieza

- Deprecar `equipo_fichas.specs_json` (queda en DB pero no se lee desde frontend).
- Deprecar `etiquetas` legacy con `parent_id` (las jerárquicas ya están en `categorias`).

---

## 8 · Trade-offs

### Lo que ganamos

- Specs **filtrables** en catálogo (busca cámaras montura E con video 4K).
- Specs **comparables** (dos lentes lado a lado con mismas keys).
- IA **guiada por schema** → menos errores, más consistencia.
- Nombres **iguales en todos lados**.
- Relevancia visible para destacar productos.
- Base para compatibilidades (futuro).

### Lo que perdemos / cambia

- Los specs en el form ya no son texto libre — el admin tiene que respetar el template (puede agregar extras siempre).
- Migración tiene un costo: se va a hacer una pasada y revisar manualmente unos cuantos equipos para limpiar mapeos raros.
- Más complejidad en el backend (templates, equipos, specs, joins).

### Riesgos

- Si los templates están mal definidos al inicio, el admin tiene que editarlos. **Mitigación**: editor de templates en `/admin/settings` desde día 1.
- La migración mapea con fuzzy match. **Mitigación**: dry-run con reporte antes de aplicar. Reversible.
- La IA puede no llenar todos los campos del template. **Mitigación**: campos `obligatorio` se piden manualmente al crear; el resto es opcional.

---

## 9 · Plan de PRs (cuando aprobado)

| PR | Alcance | LOC aprox | Dependencias |
|---|---|---|---|
| **A. Modelo + seed** | Tablas nuevas, seed de templates, columna `relevancia` | 300 | — |
| **B. Backend specs API** | CRUD de templates, CRUD de specs, `nombre_publico` calculado | 500 | A |
| **C. Form admin** | Tab "Ficha técnica" template-based, columna relevancia en lista | 600 | A, B |
| **D. Catálogo público** | Sort por relevancia, render desde `nombre_publico`, filtros por specs | 400 | A, B |
| **E. Migración specs viejos** | Script + endpoint dry-run | 200 | A |
| **F. Compatibilidades (modelo)** | Tabla + endpoints CRUD (sin UI) | 200 | A |

Total: ~2200 LOC en 6 PRs. Reviewable. Reversible PR por PR (excepto D que necesita C).

---

## 10 · Preguntas para vos

Antes de empezar a codear esto, decime:

1. **Categorías** — ¿hay alguna del seed actual que **sobre** o que **falte**? Te paso el árbol completo arriba (sección 2).
2. **Templates iniciales** — ¿los 6 que propongo (cámara, lente, luz, grip, cable, sonido) son los correctos? ¿Falta algún tipo de equipo que ya tengas (ej. monitor, batería, modificador)?
3. **Convención de relevancia** — ¿te gustan los buckets que propuse (10 flagship / 30 premium / 60 workhorse / 100 default)? ¿O preferís 1-5 como rating?
4. **Compatibilidades** — ¿lo dejamos sólo a nivel modelo de datos (sin UI todavía)? ¿O querés que también haga una vista mínima en el modal de detalle ("X requiere adaptador Y")?
5. **Nombres en albarán/presupuesto** — ¿migrás a `nombre_publico` ya, o preferís mantener `nombre` interno para los documentos formales?

Cuando tenga tus respuestas, arranco con la **PR A** (modelo + seed) que es independiente y reversible.
