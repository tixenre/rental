#!/usr/bin/env node
/**
 * ui-states.mjs — Auditoría de ESTADOS INTERACTIVOS (lo que el static no ve):
 * modal de fechas, sheet de filtros, carrito abierto, card expandida, pedido del
 * portal expandido. Clickea de verdad (Playwright/Chrome real), mide y guarda 1
 * screenshot por estado×viewport en docs/audit-ui-screenshots/states/.
 * Uso (desde frontend/):  node ../.claude/skills/auditoria-profunda/ui-states.mjs
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { MEASURE, scrollLoad, safe } from "./ui-audit.mjs";

const BASE = process.env.BASE || "http://localhost:3000";
const SECRET = process.env.STAGING_LOGIN_SECRET || "dev-local-secret";
const CLIENTE_ID = Number(process.env.CLIENTE_ID || 209);
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const OUT = resolve(REPO, "docs/audit-ui-screenshots", process.env.LABEL || "states");
mkdirSync(OUT, { recursive: true });
const VIEWPORTS = process.env.VIEWPORTS ? process.env.VIEWPORTS.split(",").map(Number) : [375, 1280];

const shot = async (page, tag) => {
  const f = resolve(OUT, tag + ".png");
  const dlg = page.locator('[role=dialog]').first();
  try { if (await dlg.count()) { await dlg.screenshot({ path: f }); return; } } catch {}
  try { await page.screenshot({ path: f }); } catch {}
};
const seedCart = (page) => page.evaluate(() => localStorage.setItem("rental-cart", JSON.stringify({ state:{ items:{"213":2,"261":1}, startDate:"2026-12-08T03:00:00.000Z", endDate:"2026-12-10T03:00:00.000Z", startTime:"10:00", endTime:"12:00" }, version:0 })));

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + "/rental", { waitUntil: "domcontentloaded" });
  const login = await page.evaluate(async ({ SECRET, CLIENTE_ID }) => {
    const r = await fetch("/auth/staging-login", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ secret:SECRET, target:"cliente", cliente_id:CLIENTE_ID }), credentials:"include" });
    return r.status;
  }, { SECRET, CLIENTE_ID });
  console.log("login:", login);

  const report = { results: [] };
  const run = async (name, w, fn) => {
    const tag = `${name}__${w}`;
    try {
      await page.setViewportSize({ width: w, height: w < 640 ? 780 : 900 });
      await fn();
      await page.waitForTimeout(700);
      const m = await page.evaluate(MEASURE);
      await shot(page, tag);
      const flags = (m.hScroll?1:0)+m.tap_lt44.length+m.font_lt_min.length+m.contrast_lt_AA.length+m.h_overflow.length;
      report.results.push({ state:name, w, ...m });
      console.log(`✓ ${tag} flags=${flags} tap<44=${m.tap_lt44.length} font=${m.font_lt_min.length} contrast=${m.contrast_lt_AA.length}`);
    } catch (e) { console.log(`✗ ${tag} ${e.message}`); report.results.push({ state:name, w, error:e.message }); }
  };
  const click = async (loc) => { const l = page.locator(loc).first(); if (await l.count()) { await l.click({ timeout: 4000 }).catch(()=>{}); return true; } return false; };
  const clickText = async (re) => { const l = page.getByText(re).first(); if (await l.count()) { await l.click({ timeout: 4000 }).catch(()=>{}); return true; } return false; };

  for (const w of VIEWPORTS) {
    // date modal
    await run("datemodal", w, async () => { await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await page.waitForTimeout(500); await page.getByRole("button",{name:/elegir fechas|jorn/i}).first().click({timeout:5000}).catch(()=>{}); });
    // filtros sheet
    await run("filtros", w, async () => { await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await scrollLoad(page); await page.getByRole("button",{name:/filtros|marca/i}).first().click({timeout:5000}).catch(()=>{}); });
    // cart open
    await run("cart", w, async () => { await page.goto(BASE+"/rental",{waitUntil:"domcontentloaded"}); await seedCart(page); await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await page.waitForTimeout(800); if(!(await click('div.sticky.bottom-0'))) await page.getByRole("button",{name:/tu rental|carrito|solicitar|item/i}).first().click({timeout:5000}).catch(()=>{}); });
    // card expanded (click first card chevron/name)
    await run("card_expanded", w, async () => { await page.goto(BASE+"/rental",{waitUntil:"networkidle"}); await scrollLoad(page); const card=page.locator('[aria-label^="Ver"], button:has-text("ver ficha")').first(); await card.click({timeout:4000}).catch(()=>{}); });
    // portal pedido expanded
    await run("portal_pedido", w, async () => { await page.goto(BASE+"/cliente/portal",{waitUntil:"networkidle"}); await page.waitForTimeout(800); await page.getByText(/^#?\d{2,}/).first().click({timeout:4000}).catch(()=>{}); });
  }
  writeFileSync(resolve(OUT, "_report.json"), JSON.stringify(report, null, 2));
  console.log("\nReport:", resolve(OUT, "_report.json"));
  await browser.close();
})();
