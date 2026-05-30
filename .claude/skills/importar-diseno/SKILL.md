---
name: importar-diseno
description: Importa un handoff de Claude Design (carpeta design_handoff_<feature>/ con un HTML de referencia visual + uno o más .tsx que espejan rutas/componentes reales del repo + README de specs) y lo convierte en front-end real de este repo. Úsalo cuando el usuario pase una carpeta de handoff de Claude Design (o diga "importá este diseño / handoff / pantalla de Claude Design", "implementá este TSX", "conectá este diseño con datos reales"). El skill orienta TODO el recorrido: ver el render, leer el README, reusar la librería de componentes del repo, implementar, conectar el backend y verificar contra la referencia. Incluye un motor visual (render.mjs) que rasteriza el HTML/ruta a PNG para que Claude pueda VER el resultado. Solo local (necesita el browser de Playwright).
---

# importar-diseno — del handoff de Claude Design al front real del repo

## Qué es Claude Design

**Claude Design** es una instancia de Claude especializada en diseño de UI, en un proyecto aparte.
Su flujo es **Leer el repo → Diseñar pensando en el backend → Exportar**. Te entrega un **handoff**:
una carpeta `design_handoff_<feature>/` que **espeja los paths reales del repo**.

| Pieza | Qué es | Cómo la tratás |
|---|---|---|
| `<Feature>.html` | **Referencia visual** (Tailwind CDN + mocks, todos los estados). | La **mirás** (rasterizada). Verdad de *cómo se ve*. |
| `src/<path-real>.tsx` | **TSX base** (ruta o componente) que ya usa componentes/tokens del repo. | Tu **base de implementación**. Verdad de *cómo se construye*. |
| `README.md` | Specs por pantalla: secciones, componentes a reusar, datos, checklist. | Tu **lista de tareas**. |

> El contrato de entrega (lado Claude Design) y la fuente de verdad de este flujo viven en el repo:
> [`INSTRUCCIONES_CLAUDE_DESIGN.md`](./INSTRUCCIONES_CLAUDE_DESIGN.md). El molde técnico para
> implementar (librería de componentes, data layer, backend) está en
> [`referencia-repo.md`](./referencia-repo.md).

## Regla de verdad (una sola, por plano)

- **El HTML manda para la fidelidad visual** — cómo se ve: layout, jerarquía, espaciados, estados,
  mobile. Es la intención de diseño aprobada.
- **El TSX manda para estructura / lógica / implementación** — cómo se construye: qué componentes y
  tokens del repo se usan, props, comportamiento. (Coherente con MEMORIA *2026-05-28*.)

No están en conflicto: son planos distintos. El markup/clases del HTML **no se copian** a producción
(usa Tailwind CDN + mocks); se traduce a los componentes/tokens reales del repo.

## Marcadores en el TSX

- **`TODO:`** → dónde conectar el dato/endpoint real (ver backend abajo).
- **`// CAMBIO N:`** → en un handoff *patch*, el diff puntual a aplicar sobre el archivo existente.

## Tipos de handoff (detectalo y actuá distinto)

| Tipo | Señal | Qué hacés |
|---|---|---|
| **Ruta nueva** | `src/routes/<ruta>.tsx` completo, ruta que no existe | Crear la ruta usando el TSX como base. |
| **Patch** | comentarios `// CAMBIO N:`, "reemplaza partes de…" | Aplicar cada cambio sobre el archivo existente, sin tocar la lógica. |
| **Módulo** | `src/components/<path>/` con varios `.tsx` + README clase-por-clase | Reemplazar/crear los componentes; el README es muy preciso, seguilo al pie. |

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
3. **VER la referencia.** Rasterizá el `.html` en **desktop y mobile** y leé los PNG:
   ```bash
   node .claude/skills/importar-diseno/render.mjs docs/handoffs/portal/*.html
   node .claude/skills/importar-diseno/render.mjs docs/handoffs/portal/*.html --mobile
   ```
   El `.html` puede **no ser self-contained** (depende de hermanos como su css/js). Renderizalo
   **dentro de su carpeta** (rutas relativas intactas), no lo copies suelto. Si sale en blanco, subí
   la espera (`--wait 2500`) — algunos prototipos montan el DOM por JS.
4. **Reuse-first (obligatorio).** Antes de escribir nada, mirá el **catálogo de componentes canónicos**
   en [`referencia-repo.md`](./referencia-repo.md). Si el primitivo ya existe (`StepperPill`,
   `PriceBlock`, `EstadoBadge`, `StatCard`, `Button`, `FavButton`…) → **reusalo**. Si el diseño trae un
   primitivo nuevo reutilizable → **extraelo a la librería**, no lo inlinees. (Barra de calidad MEMORIA:
   modularidad a prueba de balas.)
5. **Implementar.** Partiendo del `.tsx`: traducí el markup a componentes/tokens reales, aplicá los
   `// CAMBIO N:` si es patch, y conectá cada `TODO:` con el dato real (ver backend). Mobile-first.
6. **Conectar el backend** (política híbrida — detalle en [`referencia-repo.md`](./referencia-repo.md)):
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
- `--fold` solo lo visible (above-the-fold). Default: **página completa**.
- `--selector "<css>"` recorta a un componente puntual.
- `--wait <ms>` espera extra para fuentes/animaciones (default 300).
- `--out <path>` ruta de salida (default `/tmp/diseno-<ts>-<viewport>.png`).

El script imprime `PNG: /tmp/...` en la última línea → Claude **lee ese PNG** con la tool de imágenes.
Para revisar mobile-first, renderizá **las dos** vistas y compará. (`DISENO_BASE_URL` overridea el
`http://localhost:3000` por defecto.)

## Requisitos / errores comunes

- **Solo local.** En la nube el entorno es efímero y la red no deja bajar el browser (MEMORIA
  *2026-05-26 — Sesión local para trabajo visual*). Si el browser no está y no se puede instalar →
  **avisá y frená**, no inventes cómo se ve un render que no produjiste.
- **`npm install`** hecho en la raíz (para `@playwright/test`).
- **Browser:** si no puede lanzar Chromium → `npx playwright install chromium`.
- **Para verificar la ruta real:** `npm run dev` corriendo (puerto 3000).

## Restricciones

- El **render** es read-only de cara al proyecto. La **implementación** escribe front (y, en el caso
  híbrido, un endpoint de lectura simple) — siempre reusando la librería del repo, nunca tocando el
  core de reservas ni metiendo migraciones/escrituras sensibles sin avisar.
- **Una iniciativa de import = una rama + PR.** El handoff se implementa, se verifica con render-compare,
  pasa el supervisor, y recién ahí se propone merge.
