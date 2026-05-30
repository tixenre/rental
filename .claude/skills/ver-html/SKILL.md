---
name: ver-html
description: Renderiza un HTML estático (handoff de diseño, .html con file://) o una ruta de la app corriendo (http://localhost:3000/...) a una imagen PNG con el Chromium de Playwright, para que Claude pueda VER el resultado renderizado (layout, jerarquía, espaciados, estado mobile) y no solo leer el código fuente. Solo funciona en sesión LOCAL (necesita el motor de navegador instalado — ver decisión de MEMORIA "sesión local para trabajo visual"). Útil para revisar los `-preview.html` de los handoffs de Claude Design y, mejor aún, el `.tsx` real servido por la app.
---

# ver-html — que Claude vea el HTML renderizado

Claude percibe **texto** e **imágenes**, pero no tiene un motor de navegador adentro: no puede
"ver" un HTML/`.tsx` renderizado, solo leer su código. Este skill pone la cocina al lado —
rasteriza el render a un PNG con el Chromium de Playwright (el mismo que usan los tests mobile del
repo) — y Claude lee ese PNG.

> **Solo local.** En la nube el entorno es efímero y la política de red no deja bajar el browser.
> Esto encaja con la decisión de MEMORIA *2026-05-26 — Sesión local para trabajo visual/testeable*.

## Triggers

El usuario invoca con:

- `/ver-html <archivo.html>` — renderiza un HTML estático (ej. un `-preview.html` de un handoff).
- `/ver-html <ruta-app>` — renderiza una ruta de la app corriendo (ej. `/cliente/pedidos`,
  `/admin/equipos`). Requiere `npm run dev` levantado.
- `/ver-html <url>` — cualquier `http(s)://` o `file://` explícito.

Modificadores en lenguaje natural que Claude traduce a flags: "en mobile", "solo lo visible",
"solo el header / tal componente".

## Qué fuente conviene mirar

| Fuente | Fidelidad | Cuándo |
|---|---|---|
| `*-preview.html` vía `file://` | Aproximación — **puede estar desfasada** del `.tsx` | Vistazo rápido sin levantar la app |
| `.tsx` real vía `http://localhost:3000/<ruta>` | **La verdad** (tokens + componentes reales) | Revisión de diseño en serio |

Esto refleja la decisión *2026-05-28 — el TSX manda, el HTML es solo para visualizar*: el
`-preview.html` es una simulación; el `.tsx` servido por la app es el contrato. Para revisar
diseño en serio, preferir la ruta de la app corriendo.

## Cómo lo ejecuta Claude

1. Correr el renderer desde la **raíz del repo** (resuelve `@playwright/test` de `node_modules`):

   ```bash
   node .claude/skills/ver-html/render.mjs <target> [flags]
   ```

   Flags:
   - `--mobile` viewport Pixel 5 (375×667, touch) · `--desktop` 1280×900 (default desktop).
     Estos viewports matchean `playwright.config.ts`.
   - `--fold` solo lo visible (above-the-fold). Default: **página completa**.
   - `--selector "<css>"` recorta a un componente puntual.
   - `--wait <ms>` espera extra para fuentes/animaciones (default 300).
   - `--out <path>` ruta de salida (default `/tmp/ver-html-<ts>-<viewport>.png`).

2. El script imprime la ruta del PNG en la última línea (`PNG: /tmp/...`). Claude **lee ese PNG**
   con la tool de lectura de imágenes.

3. Claude describe lo que ve y/o detecta problemas (layout roto, jerarquía, espaciados,
   comportamiento mobile). Para revisar mobile-first, renderizar **las dos** vistas
   (`--mobile` y `--desktop`) y comparar.

### Ejemplos

```bash
# Handoff de diseño, página completa, desktop
node .claude/skills/ver-html/render.mjs docs/design-kit/kit-preview.html

# La app real en mobile (requiere `npm run dev`)
node .claude/skills/ver-html/render.mjs /cliente/pedidos --mobile

# Solo un componente del handoff
node .claude/skills/ver-html/render.mjs docs/design-kit/extended.html --selector ".card"
```

## Requisitos / errores comunes

- **`npm install`** hecho en la raíz (para tener `@playwright/test`).
- **Browser instalado:** si el script dice que no puede lanzar Chromium → `npx playwright install chromium`.
- **Para rutas de la app:** `npm run dev` corriendo en el puerto 3000 (o setear `VER_HTML_BASE_URL`).
- Los PNG van a `/tmp` por defecto → no ensucian el repo ni hace falta `.gitignore`.

## Restricciones

- Es **read-only de cara al proyecto**: solo renderiza y captura. No toca código, BD ni el core de
  reservas.
- No es para la nube — si el browser no está y no se puede instalar, avisar y frenar (no inventar
  cómo se ve un render que no se pudo producir).
