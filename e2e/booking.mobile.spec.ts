import { test, expect } from "@playwright/test";

/**
 * E2E del DateSheet mobile (CatalogoMovil) — jornadas y aviso de jornada extra
 * en un navegador real (viewport mobile). API mockeada con page.route().
 */

test.beforeEach(async ({ page }) => {
  await page.route("**/api/settings/horarios_retiro", (r) =>
    r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
  );
  await page.route("**/api/disponibilidad-dias**", (r) =>
    r.fulfill({ json: { dias_bloqueados: [] } }),
  );
});

async function abrirDateSheet(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Elegir fechas" }).first().click();
  await expect(page.getByText("Período de alquiler")).toBeVisible();
}

test("stepper de jornadas suma y resta", async ({ page }) => {
  await abrirDateSheet(page);
  await page.locator('input[type="date"]').fill("2026-06-02");

  const count = page.getByTestId("jornadas-count");
  await expect(count).toContainText("3"); // default

  const stepper = count.locator("xpath=..");
  await stepper.getByRole("button").first().click(); // −
  await expect(count).toContainText("2");
  await stepper.getByRole("button").last().click(); // +
  await stepper.getByRole("button").last().click(); // +
  await expect(count).toContainText("4");
});

test("aviso: devolver más tarde que el retiro suma una jornada", async ({ page }) => {
  await abrirDateSheet(page);
  await page.locator('input[type="date"]').fill("2026-06-02");

  // Default: retiro y devolución 10:00 → sin aviso.
  await expect(page.getByText(/suma 1 jornada/i)).toHaveCount(0);

  // Devolución más tarde que el retiro → aparece el aviso.
  await page.getByLabel("Hora de devolución").selectOption("11:00");
  await expect(page.getByText(/suma 1 jornada/i)).toBeVisible();
});
