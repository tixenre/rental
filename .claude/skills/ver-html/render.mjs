#!/usr/bin/env node
// render.mjs — rasteriza un HTML (file://) o una ruta de la app (http://localhost:3000/...)
// a un PNG, usando el Chromium de Playwright que ya trae el repo. Imprime la ruta del PNG
// para que Claude pueda leerlo con la tool de imágenes.
//
// Uso:
//   node .claude/skills/ver-html/render.mjs <target> [opciones]
//
//   <target>  Puede ser:
//             - una ruta a un archivo .html      → se abre como file://
//             - una URL http(s):// completa       → se abre tal cual
//             - una ruta de la app (/cliente/...) → se prefija con http://localhost:3000
//
// Opciones:
//   --mobile           Viewport mobile (Pixel 5, 375×667, touch)  [default: desktop]
//   --desktop          Viewport desktop (1280×900)                [default]
//   --fold             Captura solo lo visible (above-the-fold). Default: página completa.
//   --selector <sel>   Captura solo ese elemento CSS (recorta al componente).
//   --wait <ms>        Espera extra tras cargar (fuentes/animaciones). Default: 300.
//   --out <path>       Ruta de salida. Default: /tmp/ver-html-<ts>-<viewport>.png
//
// Salida: imprime "PNG: <ruta-absoluta>" en stdout (la última línea siempre es la ruta).

import { resolve, isAbsolute } from "node:path";
import { existsSync } from "node:fs";
import { pathToFileURL } from "node:url";

let chromium, devices;
try {
  ({ chromium, devices } = await import("@playwright/test"));
} catch {
  console.error(
    "✗ No encuentro @playwright/test. Corré `npm install` en la raíz del repo.",
  );
  process.exit(2);
}

const BASE_URL = process.env.VER_HTML_BASE_URL || "http://localhost:3000";

// ── parse args ───────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
if (argv.length === 0 || argv[0].startsWith("--")) {
  console.error("Uso: node render.mjs <target> [--mobile|--desktop] [--fold] [--selector <sel>] [--wait <ms>] [--out <path>]");
  process.exit(2);
}
const target = argv[0];
const opts = { mobile: false, fullPage: true, wait: 300, selector: null, out: null };
for (let i = 1; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--mobile") opts.mobile = true;
  else if (a === "--desktop") opts.mobile = false;
  else if (a === "--fold") opts.fullPage = false;
  else if (a === "--selector") opts.selector = argv[++i];
  else if (a === "--wait") opts.wait = parseInt(argv[++i], 10) || 0;
  else if (a === "--out") opts.out = argv[++i];
  else {
    console.error(`✗ Opción desconocida: ${a}`);
    process.exit(2);
  }
}

// ── resolver target → URL ──────────────────────────────────────────────────────
function toUrl(t) {
  if (/^https?:\/\//.test(t) || t.startsWith("file://")) return t;
  if (t.startsWith("/") && !existsSync(t)) {
    // ruta de la app (ej. /cliente/pedidos), no un archivo del FS
    return BASE_URL.replace(/\/$/, "") + t;
  }
  // ruta de archivo
  const abs = isAbsolute(t) ? t : resolve(process.cwd(), t);
  if (!existsSync(abs)) {
    console.error(`✗ No existe el archivo: ${abs}`);
    process.exit(2);
  }
  return pathToFileURL(abs).href;
}

const url = toUrl(target);
const viewport = opts.mobile ? "mobile" : "desktop";
const out =
  opts.out || `/tmp/ver-html-${Date.now()}-${viewport}.png`;

// ── render ─────────────────────────────────────────────────────────────────────
let browser;
try {
  browser = await chromium.launch();
} catch (e) {
  console.error(
    "✗ No pude lanzar Chromium. Instalá el browser con:\n    npx playwright install chromium\n" +
      `(detalle: ${e.message})`,
  );
  process.exit(3);
}

const contextOpts = opts.mobile
  ? { ...devices["Pixel 5"], viewport: { width: 375, height: 667 } }
  : { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } };

const context = await browser.newContext(contextOpts);
const page = await context.newPage();

try {
  await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
} catch (e) {
  await browser.close();
  if (url.startsWith("http") && /ERR_CONNECTION_REFUSED|net::|Timeout/.test(e.message)) {
    console.error(
      `✗ No pude abrir ${url}.\n  ¿Está corriendo la app? Levantá el dev server con \`npm run dev\` (puerto 3000).`,
    );
  } else {
    console.error(`✗ Falló la carga de ${url}: ${e.message}`);
  }
  process.exit(4);
}

if (opts.wait > 0) await page.waitForTimeout(opts.wait);
try {
  await page.evaluate(() => document.fonts && document.fonts.ready);
} catch {
  /* document.fonts no disponible — seguir */
}

try {
  if (opts.selector) {
    const el = await page.$(opts.selector);
    if (!el) {
      console.error(`✗ No encontré el selector "${opts.selector}" en la página.`);
      await browser.close();
      process.exit(5);
    }
    await el.screenshot({ path: out });
  } else {
    await page.screenshot({ path: out, fullPage: opts.fullPage });
  }
} finally {
  await browser.close();
}

console.error(`✓ ${viewport} · ${url}`);
console.log(`PNG: ${out}`);
