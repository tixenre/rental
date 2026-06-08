#!/usr/bin/env node
// walk.mjs — "agente de navegación" para auditar flujos de la app real.
//
// Recorre una secuencia de pasos en la app local (un browser de verdad, vía el
// Chromium de Playwright que ya trae el repo), capturando en cada paso:
//   • screenshot desktop y/o mobile (PNG)
//   • errores de consola del browser (page errors + console.error)
//   • requests HTTP fallidos (status >= 400)
//   • tap targets interactivos por debajo de 44×44 px (regla HIG, MEMORIA 2026-06-05)
//
// Es el instrumento del skill `auditar-flujos`: el loop walk → observar →
// auditar. NO modifica nada del proyecto (solo lee la app corriendo).
//
// Pre-auth (las superficies privadas necesitan sesión; en local el bypass de
// admin y el dev-login de cliente lo habilitan — NUNCA en Railway):
//   --as none      catálogo público (default)
//   --as admin     navega /auth/dev-login          (sesión admin dev@local)
//   --as cliente   navega /auth/dev-login-cliente   (sesión del primer cliente)
//
// Uso:
//   node .claude/skills/auditar-flujos/walk.mjs --as cliente \
//        --routes "/cliente/portal,/cliente/perfil" --both --out /tmp/audit/portal
//   node .claude/skills/auditar-flujos/walk.mjs --flow flows/pedido.json --out /tmp/audit/pedido
//
// Salida: un PNG por (paso × viewport) en --out, y un <out>/report.json con los
// hallazgos por paso. Imprime un resumen en stdout.

import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

let chromium, devices;
try {
  ({ chromium, devices } = await import("@playwright/test"));
} catch {
  console.error("✗ Falta @playwright/test. Corré `npm ci` en la raíz del repo.");
  process.exit(2);
}

const BASE_URL = process.env.AUDIT_BASE_URL || "http://localhost:3000";

// ── args ─────────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
const opt = (name, def = null) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : def;
};
const has = (name) => argv.includes(name);

const as = opt("--as", "none");
const out = resolve(opt("--out", `/tmp/audit-${Date.now()}`));
const wait = parseInt(opt("--wait", "600"), 10);
const viewports = has("--both")
  ? ["desktop", "mobile"]
  : has("--mobile")
    ? ["mobile"]
    : has("--desktop")
      ? ["desktop"]
      : ["desktop", "mobile"]; // default: ambos (mobile-first)

// Pasos: o --routes "a,b,c" (cada ruta = un paso simple), o --flow file.json
// (array de {name, goto?, click?, eval?, fill?:[sel,val], waitFor?}).
let steps = [];
const flowFile = opt("--flow");
if (flowFile) {
  const mod = await import(resolve(flowFile), { with: { type: "json" } }).catch(() => null);
  steps = (mod?.default ?? []).map((s, i) => ({ name: s.name || `paso-${i + 1}`, ...s }));
} else {
  const routes = (opt("--routes", "/") || "/").split(",").map((r) => r.trim()).filter(Boolean);
  steps = routes.map((r) => ({ name: r.replace(/[^\w]+/g, "_").replace(/^_|_$/g, "") || "root", goto: r }));
}

const DEVICE = {
  desktop: { viewport: { width: 1280, height: 900 }, isMobile: false },
  mobile: { ...devices["Pixel 5"] },
};

mkdirSync(out, { recursive: true });

// Mide tap targets interactivos < 44px (HIG). Devuelve los más chicos.
const TAP_PROBE = `(() => {
  const sel = 'a,button,[role=button],input,select,textarea,[onclick],[tabindex]';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;            // oculto
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    if (r.width < 44 || r.height < 44) {
      out.push({
        tag: el.tagName.toLowerCase(),
        w: Math.round(r.width), h: Math.round(r.height),
        text: (el.innerText || el.getAttribute('aria-label') || el.name || '').trim().slice(0, 40),
      });
    }
  }
  // dedup aproximado + top 12
  const seen = new Set(); const uniq = [];
  for (const t of out) { const k = t.tag+t.w+t.h+t.text; if (!seen.has(k)) { seen.add(k); uniq.push(t); } }
  return uniq.slice(0, 12);
})()`;

async function preAuth(context) {
  if (as === "none") return;
  const url =
    as === "admin"
      ? `${BASE_URL}/auth/dev-login`
      : `${BASE_URL}/auth/dev-login-cliente`;
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "domcontentloaded" }).catch(() => {});
  await page.waitForTimeout(500); // dejar que el JS-redirect setee la cookie
  await page.close();
}

const report = [];

for (const vp of viewports) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ ...DEVICE[vp], ignoreHTTPSErrors: true });
  await preAuth(context);

  const page = await context.newPage();
  const errors = [];
  const httpErrors = [];
  page.on("pageerror", (e) => errors.push(String(e.message || e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("response", (r) => {
    const s = r.status();
    if (s >= 400 && new URL(r.url()).host === new URL(BASE_URL).host) {
      httpErrors.push({ status: s, url: r.url().replace(BASE_URL, "") });
    }
  });

  for (const step of steps) {
    errors.length = 0;
    httpErrors.length = 0;
    const target = step.goto?.startsWith("http") ? step.goto : `${BASE_URL}${step.goto ?? ""}`;
    try {
      if (step.goto) await page.goto(target, { waitUntil: "networkidle", timeout: 20000 });
      if (step.fill) for (const [sel, val] of step.fill) await page.fill(sel, val).catch(() => {});
      if (step.click) await page.click(step.click, { timeout: 8000 }).catch((e) => errors.push(`click "${step.click}": ${e.message}`));
      if (step.eval) await page.evaluate(step.eval).catch(() => {});
      if (step.waitFor) await page.waitForSelector(step.waitFor, { timeout: 8000 }).catch(() => {});
      await page.waitForTimeout(wait);
    } catch (e) {
      errors.push(`navegación: ${e.message}`);
    }
    const file = `${out}/${step.name}-${vp}.png`;
    await page.screenshot({ path: file, fullPage: true }).catch(() => {});
    const title = await page.title().catch(() => "");
    const url = page.url().replace(BASE_URL, "");
    const smallTaps = vp === "mobile" ? await page.evaluate(TAP_PROBE).catch(() => []) : [];
    report.push({
      step: step.name, viewport: vp, url, title,
      png: file,
      console_errors: [...new Set(errors)],
      http_errors: [...httpErrors],
      small_tap_targets: smallTaps,
    });
    const flag = (errors.length || httpErrors.length) ? "⚠" : "·";
    console.log(`${flag} [${vp}] ${step.name} → ${url}  (errs:${errors.length} http:${httpErrors.length} taps<44:${smallTaps.length})`);
  }
  await browser.close();
}

writeFileSync(`${out}/report.json`, JSON.stringify(report, null, 2));
console.log(`\nReporte: ${out}/report.json  ·  PNGs en ${out}/`);
