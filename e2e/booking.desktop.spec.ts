import { test, expect } from "@playwright/test";

/**
 * E2E del modal de fechas (desktop) — horarios habilitados.
 *
 * La lógica de jornadas (stepper + aviso de jornada extra) se cubre en
 * `booking.mobile.spec.ts` (mismo util compartido `rental-dates`) y en pytest;
 * el calendario grid del desktop es propenso a flakiness por overlays, así que
 * acá verificamos lo específico del desktop: que los días cerrados según los
 * horarios configurados queden deshabilitados en el calendario.
 */

async function abrirModal(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Elegir fechas" }).first().click();
  await expect(page.getByRole("heading", { name: "Elegí tus fechas" })).toBeVisible();
}

test("horarios: los días cerrados quedan deshabilitados en el calendario", async ({ page }) => {
  await page.route("**/api/disponibilidad-dias**", (r) =>
    r.fulfill({ json: { dias_bloqueados: [] } }),
  );
  // Sáb y dom cerrados.
  await page.route("**/api/settings/horarios_retiro", (r) =>
    r.fulfill({
      json: {
        key: "horarios_retiro",
        value: JSON.stringify({
          lun: { desde: "08:00", hasta: "18:00" },
          mar: { desde: "08:00", hasta: "18:00" },
          mie: { desde: "08:00", hasta: "18:00" },
          jue: { desde: "08:00", hasta: "18:00" },
          vie: { desde: "08:00", hasta: "18:00" },
          sab: null,
          dom: null,
        }),
      },
    }),
  );

  await abrirModal(page);

  // 6 de junio de 2026 = sábado (cerrado) → deshabilitado.
  await expect(page.locator('[data-day="6/6/2026"]')).toBeDisabled();
  // 5 de junio de 2026 = viernes (abierto) → habilitado.
  await expect(page.locator('[data-day="6/5/2026"]')).toBeEnabled();
});
