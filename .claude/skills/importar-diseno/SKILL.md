---
name: importar-diseno
description: Implementa un diseño de Claude Design en el repo real — su front-end (rutas/componentes React) Y sus documentos PDF (presupuesto, albarán/remito, contrato, packing list, reportes). Úsalo siempre que el usuario pase un handoff de Claude Design (carpeta design_handoff_<feature>/ con HTML de referencia + .tsx + README), O simplemente pegue imágenes/mockups y pida que algo "quede así", "se vea como el diseño", "alineá X al mockup". Dispará también cuando el pedido sea sobre un DOCUMENTO/PDF — "rediseñá el presupuesto / remito / contrato / packing / reporte", "que el PDF quede como el diseño", "alineá los documentos al mockup" — aunque no mencione "Claude Design" ni una carpeta de handoff. El skill orienta TODO el recorrido: VER el render (rutas web con render.mjs; documentos PDF con render-doc.py), reusar la librería/infra del repo (componentes React o helpers de pdf_templates.py), implementar, conectar los datos reales y verificar contra el mockup. Su corazón es el loop render-compare: renderizar el output real → comparar con el mockup → implementar → re-renderizar hasta que coincidan. También MANTENÉS y CONSUMÍS la librería del design system, que vive EN LA APP (`src/design-system/{ui,kit} + src/components/rental` + tokens/tipografía/utilities/fuentes en `src/design-system/styles/`): reuse-first (chequear si un botón/badge/precio/stepper/estado ya existe antes de recrearlo), agregar/editar tokens o piezas, no duplicar. Es el lugar para IMPLEMENTAR un diseño ya hecho (handoff/mockup) y mantener la librería del design system en el código real. NO es para diseñar pantallas/documentos desde cero (eso lo hace Claude Design, en otro proyecto). Tampoco es para AUDITAR/MEJORAR una pantalla que ya existe y funciona pero "está rara" o se puede pulir (UX/UI/performance/modularización sin un diseño dado) — para eso está el skill `pulido-frontend`, que diagnostica con rúbrica y delega en ESTE skill la implementación fiel y el motor render-compare.
---

# importar-diseno — del handoff de Claude Design al front real del repo

## Qué es Claude Design

**Claude Design** es una instancia de Claude especializada en diseño de UI, en un proyecto aparte.
Su flujo es **Leer el repo → Diseñar pensando en el backend → Exportar**. Te entrega un **handoff**:
una carpeta `design_handoff_<feature>/` que **espeja los paths reales del repo**.

> **El loop completo arranca con un BRIEF.** Antes del handoff, el dueño escribe un **brief**
> (`docs/design-brief-<feature>.md`): _qué_ rediseñar + contexto + objetivo (no _cómo_ se ve — eso
> lo decide Claude Design). Lo abre en Claude Design, que con eso produce el handoff. Flujo de punta
> a punta: **brief → Claude Design (handoff) → implementar (este skill) → borrar el handoff** (ciclo
> de vida en _Patrones útiles_). El **brief se queda mientras el rediseño esté pendiente**; se retira
> cuando se implementa (caso testigo: el brief `design-brief-documentos.md` de los 5 PDF se retiró
> al implementarlos — ver la sección **Handoff de documentos (PDF)** más abajo).

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
  tokens del repo se usan, props, comportamiento.

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
   **Rutas autenticadas (admin / portal con login + datos):** en la nube efímera no hay sesión+datos, pero
   el render-compare en vivo **sí es posible localmente** montando el **entorno local con datos reales** —
   backend local + **BD de staging clonada a Postgres local** (dump read-only) + **`staging-login`**
   (`target:"cliente"|"admin"`) para impersonar— y corriendo el render-compare sobre el **componente real**
   logueado (MEMORIA *2026-06-20 — Iteración local con datos reales*; setup en `docs/DEPLOY_RAILWAY.md`).
   **Nunca** apuntar el backend local a la base remota (`init_db()` le escribe el esquema; es PII). Esto es
   clave porque los **bugs de theming/datos no se ven con mocks** (caso: el wordmark custom del admin se veía
   amber sobre los topbars de color, invisible con el SVG bundleado) — verificá **con datos/assets reales**.
   Alternativa sin montar el entorno: construir fiel al render del prototipo y verificar con **screenshots
   del dueño en staging**. El harness de preview con mocks queda como tracking en **#743**.

## Handoff de documentos (PDF) — el mismo loop, otro medio

El recorrido de arriba asume un target **front-end** (rutas/componentes React). Pero los **PDF que
genera el sistema** —presupuesto, albarán/remito, contrato, packing list y el reporte— también se
rediseñan por este flujo. Cambia el medio, no el corazón: **render-compare** (render del documento
real → comparar con el mockup → implementar → re-renderizar). Caso testigo: los 5 PDF alineados al
mockup de Claude Design en una sola iniciativa.

Diferencias clave respecto del track web:

- **No hay ruta web ni `npm run dev`.** Un PDF se genera server-side: una función-template de Python
  devuelve HTML, y Playwright (Python) lo rasteriza a PDF A4. Para VERLO, usá el helper
  **`render-doc.py`** (análogo a `render.mjs`):
  ```bash
  source backend/.venv/bin/activate
  python .claude/skills/importar-diseno/render-doc.py presupuesto   # o albaran/contrato/packing/reportes/todos
  ```
  Imprime `PNG: /tmp/doc-<tipo>.png` → leelo con la tool de imágenes y compará con el mockup. El
  helper trae un **dict de muestra rico** (ítems con specs, componentes, contenido, serie, valor de
  reposición, fecha de compra, cliente RI) para que cada documento rinda todas sus partes. Si el
  modelo de datos gana un campo que un documento muestra, sumalo al sample del helper.

  - **Screenshot de HTML vs PDF REAL — `--real` (clave para layout de impresión).** Por default
    `render-doc.py` saca un **screenshot del HTML** (rápido, muestra todo el flujo en una imagen).
    PERO el screenshot **ignora `@page`** y clipea distinto los márgenes negativos → **no refleja la
    paginación ni el sangrado reales**. Para layout sensible a la impresión (headers full-bleed,
    márgenes, saltos de página) usá **`--real`**: genera el PDF A4 real (`pdf._render_pdf`) y lo
    rasteriza con PyMuPDF (`pip install pymupdf`), una imagen por página con `--all-pages`. Caso
    testigo: un header con barra full-bleed que sangra al borde (`@page:first{margin-top:0}`) se ve
    **cortado** en el screenshot de HTML pero **correcto** en el PDF real — sin `--real` lo
    "arreglás" a ciegas contra un render mentiroso.
    ```bash
    python .claude/skills/importar-diseno/render-doc.py reportes --real --all-pages
    ```

- **El input suele ser solo imágenes**, no una carpeta `design_handoff_<feature>/` con `.tsx`. No hay
  TSX porque los documentos no son React — son templates de Python. El loop es: **renderizá el output
  REAL actual** (con `render-doc.py`) → **compará contra las imágenes que pegó el dueño** → implementá
  → re-renderizá. La verdad visual la manda el mockup; la estructura, el template existente.

- **Reuse-first = la infra de PDFs, no el catálogo de componentes React.** Antes de tocar nada, mirá
  qué ya existe en **`backend/pdf_templates.py`**: los **tokens** del DS (`--amber #FAB428`, `--ink`,
  `--surface`, `--hairline`, `--muted`, `--font-sans` TT Commons, `--font-mono`), el **shell** común
  (`_document`/`_membrete`/`_footer`/`_fonts_css`), helpers ya escritos (`_nombre_con_incluye` para la
  línea "INCLUYE…", `total-box--light` para la caja de totales clara, `_thumb`, la paleta de estado
  `_ESTADOS`). El 5º documento (Reportes) vive en **`backend/pdf.py`** (`_liquidacion_html`). Muchas
  veces el token/variante que necesitás **ya está** (caso testigo: `total-box--light` existía en el CSS
  antes de que el presupuesto lo usara). Si extraés algo reusable nuevo, va a un helper único
  (`_nombre_con_incluye` unificó la línea INCLUYE de 3 documentos) — no lo copies por documento.

- **Conectar el dato = el dict que ya recibe el template.** No hay `api.ts`/`useQuery`: el documento se
  renderiza desde un `pedido` (o `stats`) que arma el backend. Para datos nuevos, buscá si ya se
  computan (caso testigo: el "Resumen general" del reporte salía entero de `get_estadisticas`; se
  extrajo a `compute_estadisticas(conn)` —función pura reutilizable— para que el endpoint **y** el PDF
  lo compartan, sin duplicar SQL). Leé la función-template para descubrir qué campos espera.

- **Los documentos esconden decisiones de negocio.** Un presupuesto/contrato/remito codifica reglas de
  **plata o legales** (IVA, descuentos, condición fiscal, cláusulas). El mockup puede implicar un
  cambio de esas reglas sin decirlo (caso testigo: el presupuesto pasó a mostrar el **IVA aparte**, no
  sumado al total — cambia la cifra que ve el cliente). **No lo infieras: preguntale al dueño** y, si
  hay una decisión durable, proponé registrarla en la memoria (regla al digest `docs/MEMORIA.md` +
  desarrollo al log `docs/DECISIONES.md`, en paridad) para que una sesión futura no la "corrija"
  pensando que es un bug.

El resto del flujo es igual: una iniciativa = rama + PR, supervisor antes de mergear, y el dueño
prueba en staging (genera el PDF real desde `/admin/pedidos` o `/admin/reportes`). El core de reservas
y los cálculos de plata son sagrados — el rediseño es **presentación**, no toca el motor.

## Patrones útiles

- **El tablero de la migración al DS vive en [#612](https://github.com/tixenre/rental/issues/612)**
  (pantalla × estado de rediseño: ✅/🟡/⬜). Cada pantalla se migra por este loop; al migrar una,
  **marcá su fila en #612 en la misma PR** (es cómo "sabemos dónde estamos" y elegimos la próxima por
  prioridad). El progreso es página-por-página, no un sprint — cada PR deja el front más consistente.
- **Handoff grande o sensible → por fases + v2 al lado de v1.** Si la pantalla es grande (lista +
  editor + modales) o toca **escritura sensible** (estados, pagos, permisos), implementá **por fases**
  (ej. Fase 1 = lista read-only; Fase 2 = editor/mutaciones) en una **ruta nueva** (`/x-v2`) dejando la
  **vieja intacta como fallback** hasta confirmar. Las acciones mutantes de la Fase 1 pueden **delegar
  en la pantalla existente** (no reimplementes la máquina de estados en paralelo). La Fase 2 va con
  rama + PR dedicada y aviso antes de mergear (por tocar escritura sensible).
- **Ruteo: la LISTA de una pantalla con sub-rutas va como ruta `.index`.** Si una pantalla v2 tiene
  lista + sub-rutas (`/x-v2/$id`, `/x-v2/nuevo`), la lista debe ser `x-v2.index.lazy.tsx`
  (`createLazyFileRoute("/admin/x-v2/")`, con barra final), NO `x-v2.lazy.tsx`. Si es `x-v2.lazy.tsx`,
  TanStack la convierte en el **route-parent** de sus sub-rutas, y como su componente (la lista) no
  renderiza `<Outlet/>`, **navegar al editor cambia la URL pero la pantalla hija no aparece** (bug
  silencioso — caso testigo #752, Pedidos v2). Mirá cómo lo hace la v1 (`pedidos.index.lazy.tsx`). Lo
  hace cumplir el CI: `npm run check:routes` (`scripts/check-route-outlets.mjs`) falla si una ruta
  parent no provee `<Outlet/>`.
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
- **Ciclo de vida: un handoff implementado se borra — no se acumulan.** Una vez que el handoff está
  **implementado en el front real y confirmado en prod**, la fuente de verdad pasa a ser el código +
  el design system, no el handoff. Borrá la carpeta `docs/handoffs/<feature>/` — era input de import, ya
  cumplió. (Caso testigo: el handoff de Pedidos se retiró tras implementar Pedidos v2.) Un brief que
  **todavía no** se implementó (ej. `docs/design-brief-*.md`) **se queda** — es trabajo futuro que entra
  por este loop.

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
