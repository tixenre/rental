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

// "Hoy" congelado al 2026-06-01 (lunes). El calendario deshabilita las fechas
// pasadas con `new Date()` (DateRangePickerModal: `date < startOfDay(new Date())`),
// así que un test que afirma sobre fechas fijas (vie 5/6, sáb 6/6) se rompe solo
// cuando el reloj real pasa esas fechas (time-bomb). Fijar el reloj las deja
// siempre a futuro → el resultado depende solo del día de semana (vie abierto,
// sáb cerrado), no de cuándo corre el CI. setFixedTime no pausa los timers.
const HOY_FIJO = new Date("2026-06-01T12:00:00");

// El ViewIntroDialog se auto-abre 400ms después del primer render cuando no
// hay localStorage.rambla.view_intro_seen. En CI esa key nunca existe → el
// Dialog abre → su overlay bloquea los clicks. addInitScript inyecta la key
// antes de que la página cargue, igual que si el usuario ya lo hubiera visto.
test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HOY_FIJO);
  await page.addInitScript(() => {
    localStorage.setItem("rambla.view_intro_seen", "1");
  });
});

async function abrirModal(page: import("@playwright/test").Page) {
  await page.goto("/rental");
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
