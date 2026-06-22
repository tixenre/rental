#!/usr/bin/env node
/**
 * ui-edge.mjs — Estados DINÁMICOS difíciles de ver: error de API, vacíos,
 * tabs del portal, discovery sheet mobile, panel de verificación.
 * Usa **route interception** de Playwright para forzar 500/vacío SIN tocar el
 * backend real. Screenshots en docs/audit-ui-screenshots/edge/.
 * Uso (desde frontend/):  node ../.claude/skills/auditoria-profunda/ui-edge.mjs
 *   VERIF=1 node ...ui-edge.mjs   → sólo el escenario de verificación (correr con cliente 209 NO verificado)
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { MEASURE, scrollLoad } from "./ui-audit.mjs";

const BASE = process.env.BASE || "http://localhost:3000";
const SECRET = process.env.STAGING_LOGIN_SECRET || "dev-local-secret";
const CLIENTE_ID = Number(process.env.CLIENTE_ID || 209);
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const OUT = resolve(REPO, "docs/audit-ui-screenshots", process.env.LABEL || "edge");
mkdirSync(OUT, { recursive: true });
const VIEWPORTS = process.env.VIEWPORTS ? process.env.VIEWPORTS.split(",").map(Number) : [375, 1280];

const seedCart = (page) => page.evaluate(() => localStorage.setItem("rental-cart", JSON.stringify({ state:{ items:{"213":1,"261":1}, startDate:"2026-12-08T03:00:00.000Z", endDate:"2026-12-10T03:00:00.000Z", startTime:"10:00", endTime:"12:00" }, version:0 })));

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + "/rental", { waitUntil: "domcontentloaded" });
  await page.evaluate(async ({ SECRET, CLIENTE_ID }) => { await fetch("/auth/staging-login", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ secret:SECRET, target:"cliente", cliente_id:CLIENTE_ID }), credentials:"include" }); }, { SECRET, CLIENTE_ID });

  const report = { results: [] };
  const run = async (name, w, fn) => {
    const tag = `${name}__${w}`;
    try {
      await page.setViewportSize({ width: w, height: w < 640 ? 780 : 900 });
      await fn();
      await page.waitForTimeout(700);
      const m = await page.evaluate(MEASURE);
      const f = resolve(OUT, tag + ".png");
      const dlg = page.locator('[role=dialog]').first();
      try { if (await dlg.count()) await dlg.screenshot({ path: f }); else await page.screenshot({ path: f, fullPage: true }); } catch { try { await page.screenshot({ path: f }); } catch {} }
      // capturar texto visible clave para juzgar el estado (error/empty/etc.)
      const txt = await page.evaluate(() => document.body.innerText.replace(/\s+/g," ").slice(0, 260));
      report.results.push({ scenario:name, w, snippet: txt, hScroll:m.hScroll, tap_lt44:m.tap_lt44.length, font:m.font_lt_min.length });
      console.log(`✓ ${tag}  tap<44=${m.tap_lt44.length} font=${m.font_lt_min.length} | ${txt.slice(0,90)}`);
    } catch (e) { console.log(`✗ ${tag} ${e.message}`); report.results.push({ scenario:name, w, error:e.message }); }
  };

  if (process.env.VERIF) {
    // correr con cliente 209 NO verificado (setearlo por psql antes)
    for (const w of VIEWPORTS) {
      await run("verif-portal-banner", w, async () => { await page.goto(BASE+"/cliente/portal",{waitUntil:"networkidle"}); await page.waitForTimeout(800); });
      await run("verif-cart-panel", w, async () => { await page.goto(BASE+"/rental",{waitUntil:"domcontentloaded"}); await seedCart(page); await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await page.waitForTimeout(700); await page.locator('div.sticky.bottom-0').first().click({timeout:4000}).catch(()=>{}); await page.waitForTimeout(500); await page.getByRole("button",{name:/solicitar|confirmar/i}).first().click({timeout:4000}).catch(()=>{}); });
    }
  } else {
    for (const w of VIEWPORTS) {
      // 1. catálogo con error 500
      await run("catalog-error-500", w, async () => { await page.route(/\/api\/equipos\?/, r=>r.fulfill({status:500, contentType:"application/json", body:'{"detail":"boom"}'})); await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await page.unroute(/\/api\/equipos\?/); });
      // 2. catálogo vacío
      await run("catalog-empty", w, async () => { await page.route(/\/api\/equipos\?/, r=>r.fulfill({status:200, contentType:"application/json", body:'{"items":[]}'})); await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await page.unroute(/\/api\/equipos\?/); });
      // 3. portal sin pedidos
      await run("portal-empty", w, async () => { await page.route("**/api/cliente/pedidos**", r=>r.fulfill({status:200, contentType:"application/json", body:'[]'})); await page.goto(BASE+"/cliente/portal",{waitUntil:"networkidle"}); await page.waitForTimeout(600); await page.unroute("**/api/cliente/pedidos**"); });
      // 4. cotizar 500 con carrito
      await run("cotizar-error", w, async () => { await page.route("**/api/cotizar**", r=>r.fulfill({status:500, contentType:"application/json", body:'{"detail":"boom"}'})); await page.goto(BASE+"/rental",{waitUntil:"domcontentloaded"}); await seedCart(page); await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await page.waitForTimeout(600); await page.locator('div.sticky.bottom-0').first().click({timeout:4000}).catch(()=>{}); await page.unroute("**/api/cotizar**"); });
      // 5. portal tab Notificaciones
      await run("portal-notificaciones", w, async () => { await page.goto(BASE+"/cliente/portal",{waitUntil:"networkidle"}); await page.waitForTimeout(700); await page.getByRole("button",{name:/entendido/i}).first().click({timeout:2500}).catch(()=>{}); await page.getByText(/notificaciones/i).first().click({timeout:3000}).catch(()=>{}); });
      // 6. portal tab Perfil
      await run("portal-perfil-tab", w, async () => { await page.goto(BASE+"/cliente/portal",{waitUntil:"networkidle"}); await page.waitForTimeout(700); await page.getByRole("button",{name:/entendido/i}).first().click({timeout:2500}).catch(()=>{}); await page.getByText(/^perfil$/i).first().click({timeout:3000}).catch(()=>{}); });
      // 7. discovery sheet (mobile: abrir búsqueda/filtros)
      if (w < 640) await run("discovery-sheet", w, async () => { await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await scrollLoad(page); await page.getByPlaceholder(/buscar/i).first().click({timeout:3000}).catch(()=>{}); });
    }
  }
  writeFileSync(resolve(OUT, "_report.json"), JSON.stringify(report, null, 2));
  console.log("\nReport:", resolve(OUT, "_report.json"));
  await browser.close();
})();
