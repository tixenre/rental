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

## 2 · Categorías — propuesta basada en el inventario real

> **Hallazgo crítico de la auditoría**: la tabla `equipo_categorias` está
> **VACÍA**. Tenés 156 equipos cargados y **ninguno tiene categoría asignada**
> (0/156 = 0%). El árbol del seed existe (12 raíces + 52 sub) pero nadie lo
> está usando. La asignación masiva forma parte del rediseño.

### 2.1 · Estructura actual del seed (12 raíces existentes)

```
Cámaras (Video, Foto, Acción)
Lentes (Zoom E-mount, Zoom EF, Fijos EF, Especiales, Vintage)
Adaptadores y Filtros (Adaptadores de montura, Filtros 82mm)
Iluminación (LED daylight/bicolor, LED RGB, Tungsteno, Fluorescente, On-camera/Flash, Práctica/efecto)
Modificadores
Soportes (Trípodes video, Trípodes foto, C-Stands, Estabilización, Slider/Dolly, Car Mount)
Grip (Brazos, Clamps, Wall plates, Pinzas, Líneas seguridad, Sopapa, Lastre)
Sonido (Inalámbricos/Lavalier, Shotgun/Boom, On-camera, Estudio/Podcast, Intercom)
Monitores y Video (Monitores, Grabadores, Transmisión inalámbrica, Follow Focus/Matebox)
Energía (V-Mount, NP/LP-E6, Distribución eléctrica)
Media y Datos (Tarjetas SD, CFexpress, Lectores)
Estudio y Producción (Set/Backdrops, Paquetes)
```

### 2.2 · Mi recomendación

**Mantener el árbol como está, no tocar nada del seed.** Las 12 raíces cubren bien los 156 equipos del inventario real (cámaras, lentes, luces, soportes, grip, sonido, monitores, energía, media, modificadores, adaptadores, estudio).

Lo que sí cambia: **deprecar `Estabilización` como subcategoría de Soportes** y crearla como subcategoría hija de **Soportes → Estabilización (gimbals)**. Mejor aún, crear una raíz dedicada si se llena (Tilta Gravity G2X, Ronin, etc.). Por ahora dentro de Soportes está bien.

### 2.3 · Asignación masiva (paso crítico de la migración)

Como hay 156 equipos sin categoría, parte del trabajo es **asignar categoría a cada uno**. Plan en 3 pasos:

1. **Auto-clasificación con la IA** (`/api/admin/categorias/clasificar` ya existe, lo reutilizamos):
   - La IA mira `nombre + marca + modelo` y propone una categoría raíz + sub.
   - Modo `dry_run` → reporte por equipo: "Sony FX3 → Cámaras / Video".
2. **Revisión humana** en una pantalla `/admin/clasificar`:
   - Lista paginada con la propuesta + dropdown editable + checkbox "confirmar".
   - Botón "aplicar todos los confirmados".
3. **Lo que la IA no clasifica con confianza** queda en una bucket "sin categoría" para que vos asignes a mano.

Esto es **separado** de la tarea de specs/templates — primero ponemos a todos en su lugar, después atacamos los specs por categoría.

### 2.4 · Cómo se usa el template de specs

**Nuevo en este rediseño**: cada categoría (raíz o hija) puede tener un template de specs.

Cuando se asigna una categoría a un equipo, el form muestra los specs de ese template. Si un equipo está en múltiples categorías, **se mergean** los templates (con dedup por key, gana el del más específico).

### 2.5 · Salud del inventario (problema separado, importante)

Para resolver junto con el rediseño:
- **132/156 sin foto** (85%) — proyecto aparte, podés ir cargándolas con el flow que ya hay
- **132/156 sin ficha técnica** (85%) — la IA puede llenarlas en bulk con el flow de "enriquecer"
- **27 sin marca** — necesitan revisión manual (son equipos genéricos: bandera negra, generador, alargue, etc.)
- **4 sin modelo** — agregar modelo o usar nombre como fallback
- **0 con categoría** — el plan de 2.3 lo resuelve

Estos puntos no bloquean el rediseño, pero son la "deuda de data" que va a salir como output del nuevo sistema (panel de "salud del inventario" en `/admin/settings`).

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

### 3.3 · Templates iniciales — 12 templates basados en el inventario real

> Los 122 labels únicos que aparecen en el `specs_json` actual del inventario
> guían las keys de cada template. Los más comunes (Peso, Dimensiones, Montura,
> Material, Formato, Sensor, Tipo, Batería) se usan en varios templates.

#### 1. **Cámara** — categoría "Cámaras" y sus hijas

```
sensor              string  visible_en_card, en_nombre  ej "Full-frame CMOS 12.1MP"
montura             enum    visible_en_card, en_filtros, en_nombre  [E, RF, EF, L, Z, X, MFT, PL, BMD]
formato             enum    [Full-frame, Super 35, APS-C, MFT, M4/3]
video_max           enum    visible_en_card, en_filtros, en_nombre  [4K, 6K, 8K, 12K, FHD]
fps_max             number  unidad="fps"
iso_max             number  unidad="ISO"
estabilizacion      bool    en_filtros
autofocus           bool
peso                string
incluye             string  ej "Cuerpo, batería, cargador"
```

#### 2. **Lente**

```
montura             enum    obligatorio, en_card, en_filtros, en_nombre  [E, RF, EF, L, Z, X, MFT, PL, M42]
focal_min           number  unidad="mm"  en_card, en_nombre
focal_max           number  unidad="mm"  en_card, en_nombre  (vacío si fijo)
apertura_max        string  en_card, en_nombre  ej "f/1.4"
formato             enum    en_filtros  [Full-frame, APS-C, MFT, S35]
linea               string  ej "Art, GM, L, Cinema, Master Prime"
distancia_minima_m  number  unidad="m"
construccion_optica string  ej "11/9 elementos en 9 grupos"
peso                string
estabilizacion      bool
autofocus           bool
```

#### 3. **Iluminación** — Categoría "Iluminación"

Aplica a sub: LED daylight, LED RGB, Tungsteno, Fluorescente, Flash. Las keys cambian según subcategoría (`bicolor`/`rgb` solo aplican a LED, `temperatura` fija para tungsteno, etc).

```
potencia_w          number  unidad="W"  visible_en_card, en_filtros, en_nombre
lumens              number  unidad="lm"
cri                 number  rango=[0,100]  en_filtros
temperatura_k       string  ej "3200K-5600K" o "5600K"
bicolor             bool    en_filtros
rgb                 bool    en_filtros
dimming             bool
control_inalambrico string  ej "DMX, Lumenradio"
alimentacion        enum    en_filtros  [V-mount, NP-F, D-Tap, AC, USB-C, Batería integrada]
montaje             string  ej "Bowens, Profoto, fija"
peso                string
```

#### 4. **Modificador de luz** — Categoría "Modificadores"

```
tipo                enum    obligatorio, en_card, en_nombre  [Softbox, Frame de difusión, Bandera, Reflector, Octobox, Strip, Beauty Dish, Fresnel, Snoot]
medidas             string  obligatorio, en_card  ej "60x90 cm" o "2x2 m"
material            enum    [Difusor, Negro, Plata, Oro, Mixto]
montura             string  ej "Bowens, varillas, libre"
plegable            bool
```

#### 5. **Soporte** — Categoría "Soportes"

```
tipo                enum    obligatorio, en_card, en_nombre  [Trípode video, Trípode foto, C-Stand, Slider, Dolly, Car Mount, Camera Cage]
altura_max_m        number  unidad="m"
altura_min_m        number  unidad="m"
peso_max_kg         number  unidad="kg"  en_filtros
cabeza              string  ej "504HD, 502AH, fluida"
nivel               bool
material            enum    [Aluminio, Acero, Fibra de carbono, Mixto]
patas               number  ej 2 (boom)
peso                string
```

#### 6. **Grip** — Categoría "Grip"

```
tipo                enum    obligatorio, en_card, en_nombre  [Brazo, Clamp, Wall plate, Pinza, Línea de seguridad, Sopapa, Lastre, Cage, Plate]
material            enum    [Aluminio, Acero, Plástico, Goma, Mixto]
peso_max_kg         number  unidad="kg"
montaje             string  ej "1/4-20, 3/8-16, baby pin"
medidas             string
peso                string
```

#### 7. **Estabilizador / Gimbal** — Categoría "Soportes / Estabilización"

```
ejes                enum    en_card  [2, 3]
peso_max_kg         number  unidad="kg"  en_card, en_filtros
control             string  ej "App, joystick, follow focus"
alimentacion        enum    [Batería integrada, NP-F, USB-C]
autonomia_h         number  unidad="h"
peso                string
```

#### 8. **Sonido / Micrófono** — Categoría "Sonido"

```
tipo                enum    obligatorio, en_card, en_nombre  [Lavalier, Shotgun, On-camera, Estudio, Inalámbrico, Boom, Intercom]
patron              enum    [Cardioide, Supercardioide, Omni, Bidireccional, Hipercardioide]
banda_freq          string  ej "2.4 GHz, UHF 470-608 MHz"
canales             number
alimentacion        enum    [Phantom 48V, AA, USB-C, NP-F, Batería integrada]
conexion            enum    [XLR, 3.5mm TRS, 3.5mm TRRS, USB-C, Inalámbrico]
incluye             string  ej "Tx + Rx, deadcat, soporte de cámara"
peso                string
```

#### 9. **Monitor / Grabador / Transmisión**

```
tipo                enum    obligatorio, en_card, en_nombre  [Monitor, Grabador, Tx wireless, Rx wireless, Combo Tx/Rx]
pulgadas            number  unidad='"'  en_card, en_nombre
resolucion          string  ej "1920x1080"
brillo_nits         number  en_filtros
entradas            string  ej "HDMI 2.0, SDI 12G, BNC"
salidas             string
graba_a             enum    [SD, CFast, NVMe, SSD externo]
codecs              string  ej "ProRes, DNxHR"
alimentacion        enum    [NP-F, V-mount, USB-C, AC]
peso                string
```

#### 10. **Adaptador / Filtro** — Categoría "Adaptadores y Filtros"

```
tipo                enum    obligatorio, en_card, en_nombre  [Adaptador montura, Speedbooster, Filtro ND, Filtro polarizador, Filtro UV, Macro tube]
montura_in          enum    en_card  [E, RF, EF, L, Z, X, MFT, PL, M42]
montura_out         enum    en_card  [E, RF, EF, L, Z, X, MFT, PL]
diametro_mm         number  unidad="mm"  (para filtros)
densidad            string  ej "ND 0.6, ND variable 2-8"
electronica         bool    ej true para EF→E con AF
incluye_iris        bool    ej true para variable ND
```

#### 11. **Energía / Batería** — Categoría "Energía"

```
tipo                enum    obligatorio, en_card, en_nombre  [V-mount, NP-F, LP-E6, BP-U, Generador, Distribución, Cargador, Alargue]
capacidad_wh        number  unidad="Wh"  en_card  (para baterías)
voltaje             string  ej "14.8V, 220V"
salidas             string  ej "D-Tap, USB-C PD, P-Tap"
canales             number  (para distribución)
amperaje            string  ej "10A"
peso                string
```

#### 12. **Media / Tarjetas** — Categoría "Media y Datos"

```
tipo                enum    obligatorio, en_card, en_nombre  [SD, microSD, CFexpress B, CFexpress A, CFast, SSD externo, Lector]
capacidad_gb        number  unidad="GB"  en_card, en_nombre
velocidad_lectura   number  unidad="MB/s"  en_filtros
velocidad_escritura number  unidad="MB/s"
clase               string  ej "V90, UHS-II, U3"
interfaz            string  ej "SD UHS-II, USB-C, Thunderbolt 3"  (para lectores)
```

### 3.4 · Cobertura del inventario actual con estos 12 templates

Estos 12 templates cubren ~95% del inventario real. Los ~5% restantes son equipos genéricos (apple box, junior pin, alargue eléctrico, generador) que pueden ir bajo:
- Apple box / lastre / pin → **Grip**
- Generador / alargue → **Energía**

Si aparece algo nuevo que no encaja, el admin puede agregar un template a una categoría desde `/admin/settings` (editor de templates).

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

> **Decisión Tincho**: el `nombre_publico` lo usan TODOS — cliente, admin,
> seguro, albarán, presupuesto, contrato. Tiene que ser **completo, claro y
> descriptivo SIN ser un choclo**.

### 4.1 · Reglas para que el nombre quede bien

El nombre se construye juntando piezas, pero con reglas que evitan choclos:

1. **Marca + modelo siempre** (la espina dorsal). `Sony FX3`, `RED Komodo X`.
2. **Tipo solo si no es obvio del modelo**. "Sony FX3" no necesita "Cámara". "Falcam F38" sí porque "Quick Release" no se entiende solo.
3. **Una o dos specs discriminadoras** (las que distinguen este equipo de otro de la misma marca/modelo: variante, montura, focal).
4. **Sin repeticiones**: si la marca aparece en el modelo (ej. "Tilta Tilta-Cage") → dedup automático.
5. **Cap suave**: `nombre_publico` corto ~30-40 chars; si supera, se priorizan las piezas más importantes según el template.

Ejemplos representativos:

| Antes (interno) | Nombre público propuesto | Por qué |
|---|---|---|
| `FX3 Cuerpo` | `Sony FX3 (cuerpo)` | Marca + modelo + qué viene |
| `Komodo X 6K` | `RED Komodo-X 6K` | Resolución ya viene en el modelo |
| `MC-11 EF-E` | `Sigma MC-11 (adaptador EF→E)` | Tipo + dirección montura |
| `600d Pro` | `Aputure 600d Pro (LED daylight)` | Specs clave |
| `Sigma 35 1.4` | `Sigma Art 35mm f/1.4 (E-mount)` | Línea + focal + apertura + montura |
| `V-Mount 150Wh` | `V-mount 150Wh (batería)` | Genérico → categoría en paréntesis |

### 4.2 · Implementación: backend genera, frontend lee

Endpoint `/api/equipos` y `/api/equipos/:id` agregan dos campos calculados:

```json
{
  "id": 42,
  "nombre": "FX3 Cuerpo",                                       // interno
  "nombre_publico": "Sony FX3 (cuerpo)",                        // corto
  "nombre_publico_largo": "Sony FX3 Cinema Line · Cuerpo · Montura E · 4K 120fps"
}
```

Dos variantes según el contexto:

| Variante | Largo | Dónde se usa |
|---|---|---|
| `nombre_publico` | ~30-40 chars | Catálogo público, card, lista admin, app cliente, mensajes |
| `nombre_publico_largo` | ~80-120 chars | Albarán, presupuesto, contrato, seguro |

### 4.3 · Lógica del builder

```
1. Si equipo tiene `nombre_publico_template` (override en ficha) →
   render con tokens. El admin tiene control total cuando lo necesita.
2. Sino → auto-build:
   a. piezas = [marca, modelo] + specs marcadas `en_nombre` en el template
   b. dedup case-insensitive (saca palabras repetidas entre piezas)
   c. si "tipo" es ambiguo → agrega "(tipo)" según categoría
   d. cap a 4 piezas en el corto, todas en el largo
3. Fallback: equipo.nombre interno
```

Algoritmo de "tipo ambiguo":
- Cámara / lente → modelo es claro, no agregar tipo.
- Iluminación → agregar "(LED)" / "(Tungsteno)" / "(Flash)" según subcategoría.
- Soporte / Grip / Cable / Sonido / Adaptador → siempre agregar tipo.

### 4.4 · Tokens disponibles

Cualquier `spec_key` del template de la categoría + `marca`, `modelo`, `nombre`, `tipo`. El admin define el template y los nombres aprovechan las specs estructuradas — sin necesidad de un template por equipo (a menos que quiera overridear).

### 4.5 · Persistencia y cache

- Los dos `nombre_publico*` se calculan al guardar (hook en `setFicha`/`setCategorias`/PATCH equipo) y se persisten en columnas `equipos.nombre_publico` y `equipos.nombre_publico_largo`.
- Permite hacer queries / búsquedas full-text directamente sobre el nombre público sin recalcular.
- Endpoint `POST /api/admin/equipos/regenerar-nombres` para forzar re-cálculo masivo (útil después de cambiar un template).

### 4.6 · Albarán, presupuesto, contrato

Hoy renderizan `equipo.nombre` (interno). Cambian a:
- **Presupuesto / cotización**: `nombre_publico` (corto).
- **Albarán** (firma del cliente al recibir): `nombre_publico_largo` para que el cliente vea claramente qué recibe.
- **Contrato / seguro**: `nombre_publico_largo` + número de serie.

### 4.7 · Validación de calidad

Panel en `/admin/settings` listando equipos con nombres "sospechosos":
- Más de 80 chars (probablemente un choclo)
- Sin marca cargada
- Tokens vacíos del template (ej. `Sony FX3 ()` por montura faltante)
- Repetición de palabras detectadas (`Tilta Tilta`)

Permite revisar y limpiar progresivamente. No bloquea nada.

---

## 5 · Relevancia / orden de equipos (sistema híbrido manual + popularidad)

> **Decisión Tincho**: combinar la importancia que vos definís a mano + el
> historial de uso real (pedidos + ingreso). El admin sigue mandando, pero
> entre dos equipos con la misma importancia gana el que más se alquila.

### 5.1 · Modelo de datos

```sql
ALTER TABLE equipos ADD COLUMN relevancia_manual INT NOT NULL DEFAULT 100;
ALTER TABLE equipos ADD COLUMN cant_pedidos      INT NOT NULL DEFAULT 0;
ALTER TABLE equipos ADD COLUMN ingreso_total_ars BIGINT NOT NULL DEFAULT 0;
ALTER TABLE equipos ADD COLUMN popularidad_score INT NOT NULL DEFAULT 0;
ALTER TABLE equipos ADD COLUMN ranking_actualizado TIMESTAMP;

CREATE INDEX idx_equipos_ranking
  ON equipos(relevancia_manual ASC, popularidad_score DESC, nombre ASC);
```

### 5.2 · Cálculo de `popularidad_score` (job nightly)

Endpoint `POST /api/admin/equipos/recalcular-ranking` (también corre nightly via cron):

```python
# Para cada equipo, calcular:
cant_pedidos      = SELECT COUNT(*) FROM alquiler_items WHERE equipo_id = X
ingreso_total_ars = SELECT SUM(precio_unitario * cantidad * dias_efectivos)
                    FROM alquiler_items JOIN alquileres ON ...
                    WHERE equipo_id = X AND alquileres.estado IN ('confirmado','entregado','cerrado')
                    AND alquileres.fecha_desde >= NOW() - INTERVAL '180 days'

# popularidad_score normalizado 0..100 dentro de su categoría
# (un equipo no compite con todo el inventario, sino con sus pares):
# Ranking dual: 50% por pedidos, 50% por ingreso
score = round(
    50 * (cant_pedidos / max_cant_en_categoria) +
    50 * (ingreso_total_ars / max_ingreso_en_categoria)
)
```

**Por qué normalizar por categoría**: una GoPro tiene 50 pedidos pero $500 USD/jornada, una RED Komodo X tiene 10 pedidos pero $5000 USD/jornada. Sin normalizar, compararlos en bruto desfavorece al de mayor ticket. Normalizando dentro de su categoría, cada uno se mide contra sus pares.

### 5.3 · Cómo combinan ambas señales

Sort final del catálogo:

```sql
ORDER BY
  relevancia_manual ASC,        -- el admin manda primero (10 < 100)
  popularidad_score DESC,       -- entre empates, gana el más usado
  nombre ASC                    -- desempate alfabético
```

Convención de `relevancia_manual` (lo que ponés a mano):
- `10` — flagship: el equipo "estrella" de la rental (RED Komodo X, FX9, Alexa Mini). Aparece arriba siempre.
- `30` — premium: FX3, A7S III, Sigma Art, Aputure 600d Pro. Top de su categoría.
- `60` — workhorse: BMPCC 6K, A7 III, lentes Sigma Contemporary. Caballitos de batalla.
- `100` — default: cualquier equipo nuevo arranca acá.
- `200` — secundarios: accesorios genéricos, cables, baterías sueltas.

Si dejás todo en 100 y no querés tocar nada → el orden lo decide solo `popularidad_score`. **Sistema funciona sin que vos hagas nada**, pero podés overridear cuando importa.

### 5.4 · UI

- **Lista admin** (`/admin/equipos`) → columna "★" editable inline con la convención. Tooltip: "Equipo destacado en catálogo".
- **Detalle del equipo en admin** → panel "Estadísticas" que muestra:
  - Pedidos en últimos 6 meses
  - Ingreso generado
  - `popularidad_score` actual (0-100)
  - Última fecha de cálculo
  - Botón "Recalcular ahora" para refresh on-demand
- **Catálogo público** → ordena por el sort compuesto. Los flagship arriba siempre, el resto se autoordena según uso.
- **Card del equipo** → badge "🏆 Destacado" si `relevancia_manual <= 30` (umbral ajustable).
- **Settings** → botón "Recalcular ranking de todos" (corre el job manualmente).

### 5.5 · Categorías ya tienen `prioridad`

Mantenemos. Los filtros del catálogo siguen ordenados por `categorias.prioridad ASC`.

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

### 6.4 · UI en el back-office (Tincho-only, no cliente)

> **Decisión Tincho**: modelo + vista de admin desde día 1. Sin UI cliente.

En el form de equipo (`EquipoFormDialog`), nuevo tab **"Compatibilidades"** que aparece solo en modo edición (no al crear). Permite:

1. **Listar lo ya definido** para este equipo:
   - "✅ Compatible con: Sony A7S III, Sony FX9 (lente E-mount)"
   - "🔧 Requiere adaptador: lentes Canon EF + Sigma MC-11"
   - "❌ Incompatible con: cuerpos Canon RF nativos"

2. **Agregar nueva compatibilidad**:
   - Dropdown 1: "este equipo"
   - Selector tipo: `compatible | requiere_adaptador | incompatible`
   - Dropdown 2 (search-as-you-type sobre `equipos`): el otro equipo
   - Si tipo=`requiere_adaptador` → dropdown 3: equipo adaptador
   - Campo nota (opcional)
   - Save

3. **Editar / borrar** entradas existentes desde la lista.

Backend:
- `GET /api/admin/equipos/:id/compatibilidades` → lista con info expandida (nombres, fotos pequeñas)
- `POST /api/admin/equipos/:id/compatibilidades` → crea
- `DELETE /api/admin/equipos/:id/compatibilidades/:compat_id` → borra
- `PATCH /api/admin/equipos/:id/compatibilidades/:compat_id` → edita nota/tipo

**Importante**: las relaciones son **bidireccionales semánticamente** pero **unidireccionales en la DB** para no duplicar. Cuando consultás "compatibilidades de A", se buscan tuplas donde `a_id=A OR b_id=A`. Lo expone el endpoint en formato canónico.

**Vista pública (cliente)**: NO. El cliente no ve compatibilidades. Si un cliente arma un pedido con FX3 + lente Sigma EF sin el adaptador, queda como un warning interno para vos cuando lo revisás. Eso podría ser un feature futuro ("validar pedido contra compatibilidades") pero está fuera de alcance.

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

## 10 · Decisiones tomadas (resumen)

Las 5 preguntas originales ya están respondidas e integradas al doc:

1. **Categorías** ✅ El seed actual sirve. Mantener sin cambios. Lo crítico es **asignar categoría a los 156 equipos que están sin nada** (ver sección 2.3).
2. **Templates** ✅ **12 templates** (no 6) basados en el inventario real (sección 3.3). Cubren ~95% del inventario.
3. **Relevancia** ✅ Sistema **híbrido manual + popularidad** (sección 5). El admin define `relevancia_manual`, el sistema calcula `popularidad_score` automáticamente desde pedidos + ingresos.
4. **Compatibilidades** ✅ Modelo de datos + **vista en backoffice** (tab en form de equipo). Sin UI cliente (sección 6.4).
5. **Nombre público** ✅ Dos variantes: `nombre_publico` (corto, para catálogo y app) + `nombre_publico_largo` (extendido, para albarán/contrato/seguro). Reglas explícitas para evitar choclos (sección 4).

---

## 11 · Estado de salud del inventario (datos reales auditados)

Lo que la auditoría detectó en los 156 equipos cargados:

| Métrica | Valor | Acción |
|---|---|---|
| Equipos totales | 156 | — |
| Visibles en catálogo | 146 (94%) | OK |
| Con foto | 24 (15%) | 🟠 Cargar las 132 restantes (proyecto aparte, flow ya existe) |
| Con ficha técnica | 24 (15%) | 🟠 Llenarlas con bulk-enriquecer con IA |
| **Con categoría asignada** | **0 (0%)** | 🔴 **Prerequisito del rediseño** — ver sección 2.3 |
| Sin marca | 27 | 🟡 Revisión manual (genéricos: bandera, generador, etc.) |
| Sin modelo | 4 | 🟡 Agregar o usar nombre fallback |
| Top marcas | Avenger (11), Sony (9), Tilta (7), Godox (7), Manfrotto (7), Impact (6), Rode (6), Tiffen (6), Sigma (5), Canon (5) | — |

**Insight clave**: el sistema actual de categorías existe pero **nunca se usó**. Migrar significa primero asignarle categoría a cada equipo. Eso es parte del rediseño y se hace con asistencia de IA + revisión humana.

---

## 12 · Plan de PRs actualizado

| PR | Alcance | LOC aprox | Dependencias |
|---|---|---|---|
| **A. Modelo + seed** | Tablas nuevas (templates, equipo_specs, equipo_compatibilidad), columnas (relevancia_manual, popularidad_score, nombre_publico*), seed de los 12 templates | 500 | — |
| **B. Backend specs API** | CRUD templates, CRUD specs, builder de nombres, ranking job | 700 | A |
| **C. Asignación masiva de categorías** | Endpoint clasificar bulk + UI en `/admin/clasificar` con revisión humana | 400 | A |
| **D. Form admin** | Tab "Ficha técnica" template-based, columna relevancia, tab Compatibilidades | 800 | A, B |
| **E. Catálogo público** | Sort por relevancia compuesta, render `nombre_publico` desde backend, filtros por specs | 500 | A, B |
| **F. Migración specs viejos** | Script idempotente con dry-run + UI de revisión | 300 | A, B |
| **G. Documentos** | Albarán y presupuesto usan `nombre_publico_largo` | 150 | B |

Total: ~3350 LOC en 7 PRs reviewables y reversibles.

**Sugerencia de orden de ataque**:
1. **A** primero (estructura, no toca UI). Listo para mergear sin afectar nada.
2. **C** en paralelo con **B** (asignación masiva mientras se construye la API).
3. **D + E + G** en paralelo.
4. **F** (migración) al final, ya con los templates completos y testeados.

---

## 13 · Próximo paso

Listame cualquier ajuste/duda sobre este doc actualizado, o si está OK arranco con la **PR A** (modelo + seed). PR A es 100% aditiva: crea las tablas nuevas, agrega las columnas, no toca el flow existente. Se puede mergear y desplegar sin que nada del frontend cambie todavía.

Después de A: te muestro el panel de salud del inventario para que sepas dónde estás parado, y arrancamos C (asignar categorías a los 156 con asistencia de IA).
