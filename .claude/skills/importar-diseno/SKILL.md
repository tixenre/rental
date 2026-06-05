---
name: importar-diseno
description: Importa un handoff de Claude Design (carpeta design_handoff_<feature>/ con un HTML de referencia visual + uno o más .tsx que espejan rutas/componentes reales del repo + README de specs) y lo convierte en front-end real de este repo. Úsalo cuando el usuario pase una carpeta de handoff de Claude Design (o diga "importá este diseño / handoff / pantalla de Claude Design", "implementá este TSX", "conectá este diseño con datos reales"). El skill orienta TODO el recorrido: ver el render, leer el README, reusar la librería de componentes del repo, implementar, conectar el backend y verificar contra la referencia. Incluye un motor visual (render.mjs) que rasteriza el HTML/ruta a PNG para que Claude pueda VER el resultado (sirve los .html por HTTP; anda local y en la nube).
---

# importar-diseno — del handoff de Claude Design al front real del repo

## Qué es Claude Design

**Claude Design** es una instancia de Claude especializada en diseño de UI, en un proyecto aparte.
Su flujo es **Leer el repo → Diseñar pensando en el backend → Exportar**. Te entrega un **handoff**:
una carpeta `design_handoff_<feature>/` que **espeja los paths reales del repo**.

| Pieza                 | Qué es                                                                   | Cómo la tratás                                                |
| --------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------- |
| `<Feature>.html`      | **Referencia visual** (Tailwind CDN + mocks, todos los estados).         | La **mirás** (rasterizada). Verdad de _cómo se ve_.           |
| `src/<path-real>.tsx` | **TSX base** (ruta o componente) que ya usa componentes/tokens del repo. | Tu **base de implementación**. Verdad de _cómo se construye_. |
| `README.md`           | Specs por pantalla: secciones, componentes a reusar, datos, checklist.   | Tu **lista de tareas**.                                       |

> El contrato de entrega (lado Claude Design) y la fuente de verdad de este flujo viven en el repo:
> [`INSTRUCCIONES_CLAUDE_DESIGN.md`](./INSTRUCCIONES_CLAUDE_DESIGN.md). El molde técnico para
> implementar (librería de componentes, data layer, backend) está en
> [`referencia-repo.md`](./referencia-repo.md).

## Regla de verdad (una sola, por plano)

- **El HTML manda para la fidelidad visual** — cómo se ve: layout, jerarquía, espaciados, estados,
  mobile. Es la intención de diseño aprobada.
- **El TSX manda para estructura / lógica / implementación** — cómo se construye: qué componentes y
  tokens del repo se usan, props, comportamiento. (Coherente con MEMORIA _2026-05-28_.)

No están en conflicto: son planos distintos. El markup/clases del HTML **no se copian** a producción
(usa Tailwind CDN + mocks); se traduce a los componentes/tokens reales del repo.

## Marcadores en el TSX

- **`TODO:`** → dónde conectar el dato/endpoint real (ver backend abajo).
- **`// CAMBIO N:`** → en un handoff _patch_, el diff puntual a aplicar sobre el archivo existente.

## Tipos de handoff (detectalo y actuá distinto)

| Tipo           | Señal                                                               | Qué hacés                                                                   |
| -------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Ruta nueva** | `src/routes/<ruta>.tsx` completo, ruta que no existe                | Crear la ruta usando el TSX como base.                                      |
| **Patch**      | comentarios `// CAMBIO N:`, "reemplaza partes de…"                  | Aplicar cada cambio sobre el archivo existente, sin tocar la lógica.        |
| **Módulo**     | `src/components/<path>/` con varios `.tsx` + README clase-por-clase | Reemplazar/crear los componentes; el README es muy preciso, seguilo al pie. |

## Input: la carpeta del handoff

El usuario descomprime el bundle de Claude Design y deja la carpeta del feature —la que Claude Design
exporta como `design_handoff_<feature>/`— dentro de `docs/handoffs/` del repo (puede acortar el nombre
a `<feature>/`). Le pasás esa ruta:

```
/importar-diseno docs/handoffs/portal/
```

(En estos ejemplos `docs/handoffs/portal/` es la carpeta `design_handoff_portal/` ya colocada en el
repo.)

**El bundle real puede venir obeso** (un export trae todo el proyecto de diseño: `fonts/`, `assets/`,
`kit/`, `preview/`, HTML duplicados, copias de `colors_and_type.css`, etc.). **Ignorá todo eso** —
solo te interesan las carpetas `design_handoff_<feature>/` (su `.html`, sus `src/**.tsx`, su README).
Las **reglas del repo NO vienen del bundle**: vienen del repo (`docs/DESIGN_SYSTEM.md` + este skill +
[`referencia-repo.md`](./referencia-repo.md)). Si el bundle trae su propio `HANDOFF.md`/`CONTEXT.md`,
son referencia, pero el repo manda.

## Recorrido (lo que ejecuta Claude Code)

1. **Inventariar.** Listá la carpeta, ignorá el peso muerto, identificá el/los `.tsx` (y su path real),
   el `.html` y el `README.md`. Detectá el **tipo** (ruta / patch / módulo). Reportá en una línea.
2. **Leer.** README del handoff de punta a punta + el/los `.tsx` completos. Si es patch, leé también el
   archivo existente del repo que se va a tocar.
3. **VER la referencia.** Rasterizá el `.html` en **desktop y mobile** (`--both` saca las dos de una) y
   leé los PNG:
   ```bash
   node .claude/skills/importar-diseno/render.mjs docs/handoffs/portal/*.html --both
   ```
   El `.html` puede **no ser self-contained** (depende de hermanos: css/js/`.jsx`/CDN). render.mjs ya
   lo **sirve por HTTP local** y le sube la espera, así que prototipos con React/Babel por CDN + scripts
   `text/babel` montan bien (no en blanco). Si igual sale en blanco, subí más la espera (`--wait 5000`)
   o revisá la consola del prototipo.
   - **Estados no-default (editor, modales, dark mode).** Un prototipo interactivo suele rutear por
     **estado interno de React, no por URL** → render.mjs captura solo el estado inicial (la lista). Para
     llegar al **editor / un modal / dark** antes del screenshot, manejá el prototipo con
     `--click "<selector>"` o `--eval "<js>"` (ej. dark: `--eval "document.documentElement.classList.add('dark')"`).
     Sin esto te perdés justo las vistas que vas a construir (caso testigo: el editor de Pedidos no era
     rasterizable sin driver → se construyó "a ciegas" contra el código del proto, no contra su render).
4. **Reuse-first (obligatorio).** Antes de escribir nada, mirá el **catálogo de componentes canónicos**
   en [`referencia-repo.md`](./referencia-repo.md). Si el primitivo ya existe (`StepperPill`,
   `PriceBlock`, `EstadoBadge`, `StatCard`, `Button`, `FavButton`…) → **reusalo**. Si el diseño trae un
   primitivo nuevo reutilizable → **extraelo a la librería**, no lo inlinees. (Barra de calidad MEMORIA:
   modularidad a prueba de balas.)
5. **Implementar.** Partiendo del `.tsx`: traducí el markup a componentes/tokens reales, aplicá los
   `// CAMBIO N:` si es patch, y conectá cada `TODO:` con el dato real (ver backend). Mobile-first.
6. **Conectar el backend** (política híbrida — detalle en [`referencia-repo.md`](./referencia-repo.md)):
   - **Chequeá primero el data layer EXISTENTE** (`src/lib/api.ts`, `src/lib/admin/api.ts`, `src/hooks/*`).
     El README suele listar "hooks a implementar", pero muchas veces **ya existen** en el repo (caso
     testigo: `adminApi` ya tenía todos los endpoints de `alquileres`). Reusá, no recrees.
   - **Existe el endpoint** → conectá con el molde del repo (`useQuery`+hook, `authedFetch`, tipos de
     `src/lib/api.ts`, `formatARS`).
   - **Falta un endpoint de SOLO LECTURA simple** → crealo full-stack (router en `backend/routes/*.py`
     con `require_cliente`/`require_admin` → registrar en `main.py` con `prefix="/api"` → tipo+helper en
     `src/lib/api.ts` → consumir con `useQuery`).
   - **PARÁ y avisá en el PR** si requiere migración de schema, escribe datos sensibles
     (pagos/estados/permisos) o toca disponibilidad/overlap (**core de reservas, sagrado**).
7. **Verificar (render-compare).** Con `npm run dev` corriendo, rasterizá la **ruta real de la app** en
   desktop y mobile y compará contra el HTML de referencia. Iterá hasta que matcheen (HTML = verdad
   visual):
   ```bash
   node .claude/skills/importar-diseno/render.mjs /cliente/portal --mobile
   ```
   **Rutas autenticadas (admin / portal con login + datos):** el render-compare en vivo puede **no ser
   posible** (necesita sesión + backend + datos reales — imposible en la nube efímera). Ahí: construí
   **fiel al render del prototipo** (que sí podés rasterizar — usá `--click`/`--eval` para alcanzar los
   estados internos, ver paso 3) y verificá con **screenshots del dueño en staging** (su captura vs el
   render del prototipo). Funciona igual de bien. El agujero conocido —no poder auto-render-comparar el
   **componente real** de una ruta autenticada— se cierra con un harness de preview con mocks: tracking
   en **#743**.

## Patrones útiles

- **Handoff grande o sensible → por fases + v2 al lado de v1.** Si la pantalla es grande (lista +
  editor + modales) o toca **escritura sensible** (estados, pagos, permisos), implementá **por fases**
  (ej. Fase 1 = lista read-only; Fase 2 = editor/mutaciones) en una **ruta nueva** (`/x-v2`) dejando la
  **vieja intacta como fallback** hasta confirmar. Las acciones mutantes de la Fase 1 pueden **delegar
  en la pantalla existente** (no reimplementes la máquina de estados en paralelo). La Fase 2 va con
  rama + PR dedicada y aviso antes de mergear (por tocar escritura sensible).
- **Al crear una v2, marcá la v1 como legacy y anotala en el tracker de cleanup** (si no, la v1 queda
  para siempre). Cada archivo v1 superado lleva arriba un banner grep-able:
  `// LEGACY — <qué es> v1. Reemplazo en curso por <ruta v2> (ver #<tracker>). … Se elimina cuando la
v2 alcance paridad y esté confirmada en prod.` Listalas con `grep -rn "LEGACY —" src/`. Sumá el par
  v1→v2 al **issue tracker único de cleanup (#744)**. **No marques** lo que la v2 **reusa** (ej.
  `usePedidoDraft`) ni lo que aún **no tiene** equivalente v2 (no está superado). La v1 se borra recién
  cuando la v2 confirma paridad + prod — el banner lo dice para que nadie borre antes de tiempo.
- **La Fase 2 (el editor) es piel nueva sobre el MISMO core de escritura.** Si la v1 ya encapsula su
  lógica sensible en un hook (caso testigo: `usePedidoDraft` = autosave de datos/items + mutación de
  estado), la v2 **reusa ese hook tal cual** — no reescribe la mutación ni la máquina de estados en
  paralelo. Un solo camino de escritura para las dos pantallas → la garantía "escritura sensible
  sagrada" se mantiene sola (hay una única dirección física de la mutación). Esto es el **reuse-first
  del paso 4 aplicado a la lógica, no solo a los componentes visuales**: antes de escribir mutaciones,
  buscá el hook/data-layer que la pantalla vieja ya usa.
- **La máquina de estados de la UI se DERIVA, no se inventa.** El "próximo paso" / qué transición
  ofrecer sale de dos fuentes: (a) lo que la pantalla vieja ya hace, y (b) las precondiciones que
  valida el backend (caso testigo: `ESTADOS_VALIDOS` + checks en `routes/alquileres.py` — el backend
  valida **estado-válido + precondición**, NO un grafo de transiciones). El flujo "feliz" (qué botón
  de avance mostrar) lo guía la UI espejando la v1; el backend es la red que rechaza lo inválido. No
  hardcodees un grafo nuevo que pueda divergir de cualquiera de las dos.
- **Qué del handoff se commitea (y qué no).** El registro durable en el repo = `README.md` + `proto/*`
  (la conducta de referencia, que se **lee**) + los scaffolds `src/`. El **`.html` de referencia y su
  `assets/` (fuentes vendoreadas + `proto.css`) son de import-time y NO se commitean** — pesan y traen
  fuentes licenciadas (~1 MB), y los tokens/reglas reales viven en el repo, no en el bundle. Se
  rasterizan desde el bundle del dueño **durante** el import y listo. **No commitees un `.html` huérfano**
  (sin sus assets queda irrenderizable = peso muerto); si querés dejarlo igual, tiene que ser
  self-contained.

## Motor visual (render.mjs)

Corré siempre desde la **raíz del repo** (resuelve `@playwright/test` de `node_modules`):

```bash
node .claude/skills/importar-diseno/render.mjs <target> [flags]
```

`<target>`: una ruta a `.html` (→ `file://`), una URL `http(s)://` completa, o una ruta de la app
(`/cliente/...` → `http://localhost:3000`).

Flags:

- `--mobile` viewport Pixel 5 (375×667, touch) · `--desktop` 1280×900 (default). Matchean
  `playwright.config.ts`.
- `--both` renderiza **desktop Y mobile** en una sola corrida (dos PNG; a `--out` se le sufija
  `-desktop`/`-mobile`).
- `--click "<css>"` clickea ese selector tras cargar · `--eval "<js>"` corre JS en la página tras
  cargar. **Drivers de estado**: llevan un prototipo interactivo (que rutea por estado interno) al
  editor / un modal / dark mode **antes** del screenshot.
- `--fold` solo lo visible (above-the-fold). Default: **página completa**.
- `--selector "<css>"` recorta a un componente puntual.
- `--wait <ms>` espera extra para fuentes/animaciones (default 300).
- `--out <path>` ruta de salida (default `/tmp/diseno-<ts>-<viewport>.png`).

El script imprime una línea `PNG: /tmp/...` por cada render → Claude **lee ese/esos PNG** con la tool de
imágenes. Para revisar mobile-first, usá `--both` y compará. (`DISENO_BASE_URL` overridea el
`http://localhost:3000` por defecto.)

## Requisitos / errores comunes

- **Render del prototipo: anda también en la nube.** El browser se baja con
  `npx playwright install chromium`; render.mjs sirve el `.html` por HTTP y usa `ignoreHTTPSErrors`
  (proxy TLS de la nube). Si el browser **no está y no se puede instalar** → **avisá y frená**, no
  inventes cómo se ve un render que no produjiste. (El render-compare de la **ruta real autenticada**
  sí puede necesitar local/staging — ver paso 7.)
- **`npm install`** hecho en la raíz (para `@playwright/test`).
- **Browser:** si no puede lanzar Chromium → `npx playwright install chromium`.
- **Para verificar la ruta real:** `npm run dev` corriendo (puerto 3000).

## Restricciones

- El **render** es read-only de cara al proyecto. La **implementación** escribe front (y, en el caso
  híbrido, un endpoint de lectura simple) — siempre reusando la librería del repo, nunca tocando el
  core de reservas ni metiendo migraciones/escrituras sensibles sin avisar.
- **Una iniciativa de import = una rama + PR.** El handoff se implementa, se verifica con render-compare,
  pasa el supervisor, y recién ahí se propone merge.
