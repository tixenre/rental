/**
 * ds-thumbs.mjs — genera las MINIATURAS de los arquetipos de página de la vitrina
 * del DS (sección "Páginas & Patterns" → `components/admin/ds-catalog/sections/pages.tsx`).
 *
 * Reusa el patrón del harness `auditoria-profunda/ui-audit.mjs` (Chrome real +
 * staging-login). Para cada arquetipo: loguea según el área (admin/cliente/público),
 * navega a su ruta canónica, scrollea para disparar reveals, y guarda un PNG recortado
 * en `frontend/public/ds-thumbs/<arquetipo>.png` (mismo nombre que usa la card).
 *
 * ⚠️ Necesita un BACKEND con datos: las rutas admin/data no renderizan contra el vite
 * dev solo (sin backend). Correlo contra STAGING o un backend local con BD clonada:
 *
 *   BASE=https://<staging> STAGING_LOGIN_SECRET=<secreto> node scripts/ds-thumbs.mjs
 *   ONLY=marketing-landing,legal-prose,auth NOLOGIN=1 node scripts/ds-thumbs.mjs   # público, anda local
 *
 * Las miniatorias faltantes no rompen nada: la card las oculta con onError (fallback a texto+link).
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = process.env.BASE || "http://localhost:3000";
const SECRET = process.env.STAGING_LOGIN_SECRET || "dev-local-secret";
const CLIENTE_ID = Number(process.env.CLIENTE_ID || 209);
const OUT = resolve(REPO, "frontend/public/ds-thumbs");
const W = Number(process.env.W || 1280);
const Hh = Number(process.env.H || 800);

// arquetipo → ruta canónica + área de auth. Espeja la data de `pages.tsx`
// (el nombre = el archivo del thumb: /ds-thumbs/<name>.png).
const ARCHETYPES = [
  { name: "list-table", path: "/admin/pedidos", auth: "admin" },
  { name: "dashboard", path: "/admin", auth: "admin" },
  { name: "legal-prose", path: "/preguntas-frecuentes", auth: null },
  { name: "marketing-landing", path: "/", auth: null },
  { name: "form-detail", path: "/admin/equipos/nuevo", auth: "admin" },
  { name: "settings", path: "/admin/settings", auth: "admin" },
  { name: "auth", path: "/admin/login", auth: null },
  { name: "form-wizard", path: "/admin/pedidos/nuevo", auth: "admin" },
  { name: "report", path: "/admin/contabilidad/reporte", auth: "admin" },
  { name: "public-grid", path: "/rental", auth: null },
  { name: "detail", path: "/equipo/213", auth: null },
  { name: "list-cards", path: "/cliente/portal", auth: "cliente" },
  { name: "detail-editor", path: "/admin/pedidos/393", auth: "admin" },
  { name: "ds-showcase", path: "/admin/diseno", auth: "admin" },
];

const only = process.env.ONLY ? new Set(process.env.ONLY.split(",")) : null;
const TARGETS = only ? ARCHETYPES.filter((a) => only.has(a.name)) : ARCHETYPES;

async function login(page, target) {
  if (process.env.NOLOGIN) return "skipped";
  return page.evaluate(
    async ({ SECRET, CLIENTE_ID, target }) => {
      const body =
        target === "cliente"
          ? { secret: SECRET, target: "cliente", cliente_id: CLIENTE_ID }
          : { secret: SECRET, target: "admin" };
      const r = await fetch("/auth/staging-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "include",
      });
      return r.status;
    },
    { SECRET, CLIENTE_ID, target },
  );
}

async function scrollLoad(page) {
  await page.evaluate(async () => {
    const max = document.body.scrollHeight;
    for (let y = 0; y <= max; y += innerHeight * 0.8) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 200));
    }
    window.scrollTo(0, 0);
    await new Promise((r) => setTimeout(r, 300));
  });
}

const main = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ deviceScaleFactor: 1, viewport: { width: W, height: Hh } });
  const page = await ctx.newPage();
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" }).catch(() => {});

  let lastAuth = "none";
  for (const { name, path, auth } of TARGETS) {
    try {
      if (auth && auth !== lastAuth) {
        const st = await login(page, auth);
        console.log(`login(${auth}) → ${st}`);
        lastAuth = auth;
      }
      await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 25000 }).catch(() => {});
      await page.waitForTimeout(700);
      await scrollLoad(page);
      await page.screenshot({ path: resolve(OUT, `${name}.png`), clip: { x: 0, y: 0, width: W, height: Hh } });
      console.log(`✓ ${name}  (${path})`);
    } catch (e) {
      console.log(`✗ ${name}  ${e.message}`);
    }
  }
  await browser.close();
  console.log("\nThumbs en:", OUT);
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
