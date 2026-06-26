import { test, expect } from "@playwright/test";

/**
 * Guard de regresión: cascada [data-area] en rutas que requieren viewport desktop.
 * /rental en mobile renderiza CatalogoMovil (sin PublicLayout), por eso este
 * archivo usa el sufijo .desktop.spec.ts (solo corre en el proyecto desktop-chrome).
 */
test("cascada [data-area] — estudio y rental tienen atributo correcto", async ({ page }) => {
  await page.goto("/estudio");
  await page.waitForLoadState("networkidle");
  const estudioArea = await page.evaluate(() =>
    document.querySelector("[data-area]")?.getAttribute("data-area"),
  );
  expect(estudioArea).toBe("estudio");

  await page.goto("/rental");
  await page.waitForLoadState("networkidle");
  const rentalArea = await page.evaluate(() =>
    document.querySelector("[data-area]")?.getAttribute("data-area"),
  );
  expect(rentalArea).toBe("rental");
});

test("cascada [data-area] — --area-accent resuelve diferente en estudio vs rental", async ({
  page,
}) => {
  await page.goto("/estudio");
  await page.waitForLoadState("networkidle");

  const [estudioAccent, estudioColor] = await page.evaluate(() => {
    const el = document.querySelector("[data-area='estudio']");
    if (!el) throw new Error("data-area='estudio' no encontrado");
    const cs = getComputedStyle(el);
    return [
      cs.getPropertyValue("--area-accent").trim(),
      cs.getPropertyValue("--color-estudio").trim(),
    ];
  });
  expect(estudioAccent).toBe(estudioColor);

  await page.goto("/rental");
  await page.waitForLoadState("networkidle");

  const [rentalAccent, rentalColor] = await page.evaluate(() => {
    const el = document.querySelector("[data-area='rental']");
    if (!el) throw new Error("data-area='rental' no encontrado");
    const cs = getComputedStyle(el);
    return [
      cs.getPropertyValue("--area-accent").trim(),
      cs.getPropertyValue("--color-amber").trim(),
    ];
  });
  expect(rentalAccent).toBe(rentalColor);
  expect(estudioAccent).not.toBe(rentalAccent);
});
