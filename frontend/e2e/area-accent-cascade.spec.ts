import { test, expect } from "@playwright/test";

/**
 * Guard de regresión: verifica que la cascada [data-area] inyecte el atributo
 * correcto en cada ruta y que el override de estudio esté activo.
 * Blinda que un refactor no rompa el theming por área.
 */
test("cascada [data-area] — estudio y rental tienen atributo correcto", async ({ page }) => {
  // /estudio debe tener data-area="estudio"
  await page.goto("/estudio");
  await page.waitForLoadState("networkidle");

  const estudioArea = await page.evaluate(() =>
    document.querySelector("[data-area]")?.getAttribute("data-area"),
  );
  expect(estudioArea).toBe("estudio");

  // /rental debe tener data-area="rental"
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
  // Medimos el --area-accent declarado en el elemento [data-area].
  // En estudio: debe contener "estudio" (referencia a --color-estudio).
  await page.goto("/estudio");
  await page.waitForLoadState("networkidle");

  const estudioProp = await page.evaluate(() => {
    const el = document.querySelector("[data-area='estudio']");
    if (!el) throw new Error("data-area='estudio' no encontrado");
    return getComputedStyle(el).getPropertyValue("--area-accent").trim();
  });
  expect(estudioProp).toContain("estudio");

  // En rental: debe contener "amber".
  await page.goto("/rental");
  await page.waitForLoadState("networkidle");

  const rentalProp = await page.evaluate(() => {
    const el = document.querySelector("[data-area='rental']");
    if (!el) throw new Error("data-area='rental' no encontrado");
    return getComputedStyle(el).getPropertyValue("--area-accent").trim();
  });
  expect(rentalProp).toContain("amber");
});
