---
name: importar-diseno
description: Importa un handoff de Claude Design (un bundle con HTML de referencia visual + TSX borrador de implementación + README de specs) y lo convierte en front-end real de este repo. Úsalo cuando el usuario pase una carpeta-bundle de Claude Design (o diga "importá este diseño / handoff / pantalla de Claude Design", "implementá este TSX", "conectá este diseño con datos reales"). El skill orienta TODO el recorrido: ver el render, leer el contrato, implementar con los componentes/tokens reales del repo, conectar endpoints y verificar contra la referencia. Incluye un motor visual (render.mjs) que rasteriza el HTML/ruta a PNG para que Claude pueda VER el resultado. Solo local (necesita el browser de Playwright).
---

# importar-diseno — del handoff de Claude Design al front real del repo

## Qué es Claude Design (contexto para Claude Code)

**Claude Design** es una instancia de Claude especializada en diseño de interfaces, que corre en
un entorno de proyecto con filesystem. Trabaja la UI en HTML y la traduce a TSX. Te entrega un
**bundle** (handoff) con tres piezas:

| Archivo | Qué es | Cómo lo tratás |
|---|---|---|
| `*.html` | **Referencia visual.** Tailwind CDN + datos mock. **NO es código de producción.** | Lo **mirás** (rasterizado a PNG). Nunca lo portás tal cual. |
| `*.tsx` | **Borrador de implementación.** Ya usa los componentes y tokens del repo real. | Es tu **base**. Lo completás, no lo reescribís de cero. |
| `README.md` / `HANDOFF.md` | **Specs + checklist** de implementación. | Tu **lista de tareas**. Lo seguís paso a paso. |

> Le estás recibiendo una **especificación visual ejecutable + un borrador de implementación**.
> Tu trabajo es completar el borrador y conectar la lógica real.

## Reglas de oro (no negociables)

1. **El TSX manda.** Si el `.html` y el `.tsx` difieren, gana el **`.tsx`** — usa los componentes
   y tokens reales del repo; el HTML es una simulación que **puede estar desfasada**. (Decisión de
   MEMORIA *2026-05-28 — el TSX manda, el HTML es solo para visualizar*.)
2. **El HTML es solo referencia visual.** Tailwind CDN + mocks. **Nunca** copies su markup/clases a
   producción; sirve para *ver* la intención de diseño (layout, jerarquía, espaciados, mobile).
3. **`// TODO`** en el TSX marca **dónde conectar datos/endpoints reales** del repo.
4. **`// KEEP`** marca sub-componentes/bloques del original que hay que **traer tal cual** del HTML
   al TSX (no reinventarlos).
5. **Componentes y tokens del repo, no ad-hoc.** La implementación usa el design system real
   (`docs/DESIGN_SYSTEM.md`, `src/components/ui/*`, `src/components/kit/*`). Si el TSX trae un estilo
   suelto que ya existe como componente/token, se reusa el del repo. (Barra de calidad de MEMORIA:
   consistencia + modularidad.)

## Input: la carpeta-bundle

El usuario deja una **carpeta** con el bundle (los 3 archivos juntos) y te pasa la ruta:

```
/importar-diseno docs/handoffs/portal-pedidos/
```

Detectás las piezas por extensión/nombre dentro de la carpeta (`*.html`, `*.tsx`, README/HANDOFF).
Puede faltar el README, o haber varios `.html`/`.tsx` (una pantalla con sub-componentes) — armá el
contexto con lo que haya y avisá si falta algo clave.

## Recorrido (lo que ejecuta Claude Code)

1. **Inventariar el bundle.** Listá la carpeta y clasificá cada archivo (HTML ref / TSX base /
   README spec). Reportá en una línea qué encontraste.
2. **Leer el contrato.** Leé el README/HANDOFF de punta a punta → de ahí sale el **checklist** de
   implementación y dónde van los datos reales. Leé el `.tsx` completo (es la base).
3. **VER la referencia.** Rasterizá cada `.html` del bundle con el motor visual, en **desktop y
   mobile**, y leé los PNG. Así *ves* el diseño en vez de adivinarlo del markup:

   ```bash
   node .claude/skills/importar-diseno/render.mjs docs/handoffs/portal-pedidos/screen.html
   node .claude/skills/importar-diseno/render.mjs docs/handoffs/portal-pedidos/screen.html --mobile
   ```

4. **Implementar en el repo.** Partiendo del `.tsx`:
   - Traé los bloques `// KEEP` del original.
   - Reemplazá estilos sueltos por los componentes/tokens reales del repo donde corresponda.
   - Conectá cada `// TODO` con el endpoint/estado real (hooks, queries, stores existentes).
   - Seguí el checklist del README; mobile-first (la decisión de calidad lo exige).
5. **Verificar contra la referencia.** Con `npm run dev` corriendo, rasterizá la **ruta real de la
   app** (no el HTML) en desktop y mobile y compará contra la referencia visual:

   ```bash
   node .claude/skills/importar-diseno/render.mjs /cliente/pedidos --mobile
   ```

   La ruta servida por la app es **la verdad** (tokens + componentes reales). Iterá hasta que el
   render real matchee la intención del diseño.

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

El script imprime `PNG: /tmp/...` en la última línea → Claude **lee ese PNG** con la tool de
imágenes. Para revisar mobile-first, renderizá **las dos** vistas y compará.

(`DISENO_BASE_URL` overridea el `http://localhost:3000` por defecto.)

## Requisitos / errores comunes

- **Solo local.** En la nube el entorno es efímero y la red no deja bajar el browser. Encaja con la
  decisión de MEMORIA *2026-05-26 — Sesión local para trabajo visual/testeable*. Si el browser no
  está y no se puede instalar → **avisá y frená**, no inventes cómo se ve un render que no produjiste.
- **`npm install`** hecho en la raíz (para `@playwright/test`).
- **Browser:** si no puede lanzar Chromium → `npx playwright install chromium`.
- **Para verificar la ruta real:** `npm run dev` corriendo (puerto 3000).

## Restricciones

- El **render** es read-only de cara al proyecto (solo captura). La **implementación** sí escribe
  código del front — pero usando los componentes/tokens del repo, nunca tocando BD ni el core de
  reservas (sagrado).
- Una iniciativa de import = una rama + PR (flujo del repo). El handoff se implementa, se verifica
  contra la referencia, y recién ahí se propone merge.
