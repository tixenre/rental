import { test, expect } from "@playwright/test";

/**
 * Guard de regresión: cascada [data-area] en rutas accesibles en mobile.
 * /rental en mobile renderiza CatalogoMovil (sin PublicLayout → sin data-area),
 * por eso se omite aquí — ver area-accent-cascade.desktop.spec.ts.
 */
test("cascada [data-area] — estudio tiene atributo correcto", async ({ page }) => {
  await page.goto("/estudio");
  await page.waitForLoadState("networkidle");

  const estudioArea = await page.evaluate(() =>
    document.querySelector("[data-area]")?.getAttribute("data-area"),
  );
  expect(estudioArea).toBe("estudio");
});

test("cascada [data-area] — --area-accent resuelve al color de estudio", async ({ page }) => {
  await page.goto("/estudio");
  await page.waitForLoadState("networkidle");

  const [accent, color] = await page.evaluate(() => {
    const el = document.querySelector("[data-area='estudio']");
    if (!el) throw new Error("data-area='estudio' no encontrado");
    const cs = getComputedStyle(el);
    return [
      cs.getPropertyValue("--area-accent").trim(),
      cs.getPropertyValue("--color-estudio").trim(),
    ];
  });
  expect(accent).toBe(color);
});
