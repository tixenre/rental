#!/usr/bin/env node
// render.mjs — rasteriza un HTML (file://) o una ruta de la app (http://localhost:3000/...)
// a un PNG, usando el Chromium de Playwright que ya trae el repo. Imprime la ruta del PNG
// para que Claude pueda leerlo con la tool de imágenes.
//
// Es el "motor visual" del skill importar-diseno: rasteriza el `.html` de referencia de un
// bundle de Claude Design (o una ruta de la app real) para que Claude pueda VER el render.
//
// Uso:
//   node .claude/skills/importar-diseno/render.mjs <target> [opciones]
//
//   <target>  Puede ser:
//             - una ruta a un archivo .html      → se abre como file://
//             - una URL http(s):// completa       → se abre tal cual
//             - una ruta de la app (/cliente/...) → se prefija con http://localhost:3000
//
// Opciones:
//   --mobile           Viewport mobile (Pixel 5, 375×667, touch)  [default: desktop]
//   --desktop          Viewport desktop (1280×900)                [default]
//   --both             Renderiza desktop Y mobile en una sola corrida (dos PNG).
//   --fold             Captura solo lo visible (above-the-fold). Default: página completa.
//   --selector <sel>   Captura solo ese elemento CSS (recorta al componente).
//   --click <sel>      Clickea ese selector tras cargar (lleva un prototipo a otro estado).
//   --eval <js>        Corre JS arbitrario en la página tras cargar (driver de estado).
//   --wait <ms>        Espera extra tras cargar (fuentes/animaciones). Default: 300.
//   --out <path>       Ruta de salida. Default: /tmp/diseno-<ts>-<viewport>.png
//                      (con --both se le sufija -desktop/-mobile)
//
// Salida: imprime "PNG: <ruta-absoluta>" en stdout (la última línea siempre es la ruta).

import { resolve, isAbsolute, extname, basename, dirname, join } from "node:path";
import { existsSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { createServer } from "node:http";

let chromium, devices;
try {
  ({ chromium, devices } = await import("@playwright/test"));
} catch {
  console.error("✗ No encuentro @playwright/test. Corré `npm install` en la raíz del repo.");
  process.exit(2);
}

const BASE_URL =
  process.env.DISENO_BASE_URL || process.env.VER_HTML_BASE_URL || "http://localhost:3000";

// ── parse args ───────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
if (argv.length === 0 || argv[0].startsWith("--")) {
  console.error(
    "Uso: node render.mjs <target> [--mobile|--desktop|--both] [--fold] [--selector <sel>] [--click <sel>] [--eval <js>] [--wait <ms>] [--out <path>]",
  );
  process.exit(2);
}
const target = argv[0];
const opts = {
  mobile: false,
  both: false,
  fullPage: true,
  wait: 300,
  selector: null,
  click: null,
  eval: null,
  out: null,
};
for (let i = 1; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--mobile") opts.mobile = true;
  else if (a === "--desktop") opts.mobile = false;
  else if (a === "--both") opts.both = true;
  else if (a === "--fold") opts.fullPage = false;
  else if (a === "--selector") opts.selector = argv[++i];
  else if (a === "--click") opts.click = argv[++i];
  else if (a === "--eval") opts.eval = argv[++i];
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

// ── server estático local (para HTMLs de prototipo) ──────────────────────────
// Un .html de Claude Design suele cargar React/Babel por CDN y sus `.jsx` con
// <script type="text/babel" src="...">. Eso NO funciona por file:// (Babel no
// puede fetchear los .jsx — CORS) y el render sale en blanco. Por eso, si el
// target es un .html local, lo servimos por http://127.0.0.1 en vez de file://.
const MIME = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".jsx": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
};
function serveDir(root) {
  const server = createServer((req, res) => {
    try {
      const rel = decodeURIComponent((req.url || "/").split("?")[0]);
      const fp = join(root, rel);
      if (!fp.startsWith(root)) {
        res.statusCode = 403;
        return res.end("forbidden");
      }
      const data = readFileSync(fp);
      res.setHeader("Content-Type", MIME[extname(fp).toLowerCase()] || "application/octet-stream");
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.end(data);
    } catch {
      res.statusCode = 404;
      res.end("not found");
    }
  });
  return new Promise((ok) =>
    server.listen(0, "127.0.0.1", () => ok({ server, port: server.address().port })),
  );
}

let httpServer = null;
let url;
const _absTarget = isAbsolute(target) ? target : resolve(process.cwd(), target);
const _looksLocalHtml =
  !/^https?:\/\//.test(target) &&
  !target.startsWith("file://") &&
  extname(target).toLowerCase() === ".html" &&
  existsSync(_absTarget);
if (_looksLocalHtml) {
  const served = await serveDir(dirname(_absTarget));
  httpServer = served.server;
  url = `http://127.0.0.1:${served.port}/${encodeURIComponent(basename(_absTarget))}`;
  if (opts.wait < 2000) opts.wait = 2500; // Babel transpila los .jsx en el browser → dar tiempo a montar
} else {
  url = toUrl(target);
}
// ── render (uno o ambos viewports) ───────────────────────────────────────────
const viewports = opts.both ? ["desktop", "mobile"] : [opts.mobile ? "mobile" : "desktop"];

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

async function renderOne(viewport) {
  const isMobile = viewport === "mobile";
  const context = await browser.newContext({
    // El entorno cloud sale por un proxy TLS con cert propio que Chromium no
    // confía → sin esto, los assets de un prototipo (React/Babel por CDN) fallan
    // con ERR_CERT_AUTHORITY_INVALID y el render sale en blanco.
    ignoreHTTPSErrors: true,
    ...(isMobile
      ? { ...devices["Pixel 5"], viewport: { width: 375, height: 667 } }
      : { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } }),
  });
  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
  } catch (e) {
    if (url.startsWith("http") && /ERR_CONNECTION_REFUSED|net::|Timeout/.test(e.message)) {
      console.error(
        `✗ No pude abrir ${url}.\n  ¿Está corriendo la app? Levantá el dev server con \`npm run dev\` (puerto 3000).`,
      );
    } else {
      console.error(`✗ Falló la carga de ${url}: ${e.message}`);
    }
    await context.close();
    return { ok: false };
  }

  // Driver de estado (para prototipos interactivos que rutean por estado interno,
  // no por URL): --eval corre JS arbitrario en la página y --click clickea un
  // selector. Sirven para llegar a editor/modal/dark ANTES del screenshot.
  if (opts.eval) {
    try {
      await page.evaluate(opts.eval);
    } catch (e) {
      console.error(`⚠ --eval falló: ${e.message}`);
    }
  }
  if (opts.click) {
    try {
      await page.click(opts.click, { timeout: 5000 });
    } catch (e) {
      console.error(`⚠ --click no pudo clickear "${opts.click}": ${e.message}`);
    }
  }

  if (opts.wait > 0) await page.waitForTimeout(opts.wait);
  try {
    await page.evaluate(() => document.fonts && document.fonts.ready);
  } catch {
    /* document.fonts no disponible — seguir */
  }

  // --out se respeta tal cual en single-viewport; con --both se le sufija el viewport.
  const out =
    opts.out && !opts.both
      ? opts.out
      : opts.out
        ? opts.out.replace(/(\.png)?$/i, `-${viewport}.png`)
        : `/tmp/diseno-${Date.now()}-${viewport}.png`;

  try {
    if (opts.selector) {
      const el = await page.$(opts.selector);
      if (!el) {
        console.error(`✗ No encontré el selector "${opts.selector}" en la página.`);
        return { ok: false };
      }
      await el.screenshot({ path: out });
    } else {
      await page.screenshot({ path: out, fullPage: opts.fullPage });
    }
  } finally {
    await context.close();
  }

  console.error(`✓ ${viewport} · ${url}`);
  return { ok: true, out };
}

const results = [];
let loadFailed = false;
for (const vp of viewports) {
  const r = await renderOne(vp);
  if (r.ok) results.push(r.out);
  else {
    loadFailed = true;
    break;
  }
}
await browser.close();
httpServer?.close();

if (results.length === 0) process.exit(loadFailed ? 4 : 5);
for (const out of results) console.log(`PNG: ${out}`);
