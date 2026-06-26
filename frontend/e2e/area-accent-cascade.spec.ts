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
  // Medimos el --area-accent resuelto en el elemento [data-area].
  // Chromium resuelve var() al valor final; comparamos contra el token fuente,
  // no contra el texto crudo "var(--color-estudio)".

  // En estudio: --area-accent debe resolver al mismo valor que --color-estudio.
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
  // --area-accent debe resolver al mismo color que --color-estudio (no a amber ni rosa).
  expect(estudioAccent).toBe(estudioColor);

  // En rental: --area-accent debe resolver al mismo valor que --color-amber (el default).
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
  // --area-accent en rental debe resolver al mismo color que --color-amber.
  expect(rentalAccent).toBe(rentalColor);

  // Las dos áreas deben usar colores distintos.
  expect(estudioAccent).not.toBe(rentalAccent);
});
