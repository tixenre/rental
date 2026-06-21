import { test, expect } from "@playwright/test";

/**
 * E2E del selector de fechas en mobile. El catálogo mobile (CatalogoMovil) ahora
 * abre el RentalDateModal compartido (mismo calendario que desktop) en vez del
 * viejo DateSheet con input nativo. Verifica el stepper de jornadas y el aviso de
 * jornada extra en un navegador real (viewport mobile). API mockeada con page.route().
 */

test.beforeEach(async ({ page }) => {
  await page.route("**/api/settings/horarios_retiro", (r) =>
    r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
  );
  await page.route("**/api/disponibilidad-dias**", (r) =>
    r.fulfill({ json: { dias_bloqueados: [] } }),
  );
});

async function abrirModalYElegirFecha(page: import("@playwright/test").Page) {
  await page.goto("/rental");
  await page.getByRole("button", { name: "Elegir fechas" }).first().click();
  await expect(page.getByRole("heading", { name: "Elegí tus fechas" })).toBeVisible();
  // Elegí el primer día disponible del calendario (independiente del reloj de CI).
  await page.locator("button[data-day]:not([disabled])").first().click();
}

test("stepper de jornadas suma y resta", async ({ page }) => {
  await abrirModalYElegirFecha(page);

  const count = page.getByTestId("jornadas-count");
  await expect(count).toHaveText("1"); // default al elegir una fecha

  await page.getByRole("button", { name: "Agregar una jornada" }).click();
  await expect(count).toHaveText("2");
  await page.getByRole("button", { name: "Agregar una jornada" }).click();
  await expect(count).toHaveText("3");
  await page.getByRole("button", { name: "Quitar una jornada" }).click();
  await expect(count).toHaveText("2");
});

test("aviso: devolver más tarde que el retiro suma una jornada", async ({ page }) => {
  await abrirModalYElegirFecha(page);

  // Default: retiro y devolución a la misma hora → sin aviso.
  await expect(page.getByText(/suma 1 jornada/i)).toHaveCount(0);

  // Devolución más tarde que el retiro → aparece el aviso.
  await page.getByLabel("Hora de devolución").selectOption("11:00");
  await expect(page.getByText(/suma 1 jornada/i)).toBeVisible();
});
