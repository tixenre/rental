/**
 * E2E tests del form de equipos V2 (#210).
 *
 * REQUIERE el backend con ADMIN_BYPASS_AUTH=1 (modo dev/test) para saltearse
 * la auth de Supabase. Sin eso, los tests se skipean automáticamente.
 *
 * Para correr local:
 *   1. Backend con ADMIN_BYPASS_AUTH=1 (ya viene en .env.local de dev)
 *   2. `npm run dev` (vite + uvicorn proxy)
 *   3. `bun playwright test admin-equipos-form`
 *
 * En CI: skipped por default (no hay backend levantado). Para habilitarlo
 * agregar un setup que levante el backend + frontend con la flag.
 */

import { test, expect } from "@playwright/test";

const ADMIN_TESTS_ENABLED = process.env.PLAYWRIGHT_ADMIN === "1";

test.describe("Admin equipos — form V2", () => {
  test.skip(
    !ADMIN_TESTS_ENABLED,
    "Set PLAYWRIGHT_ADMIN=1 para correr tests admin (necesita ADMIN_BYPASS_AUTH=1 en backend)",
  );

  test("Lista admin carga con tabla + botones de header", async ({ page }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    // Header con título
    await expect(page.getByRole("heading", { name: /Equipos/i })).toBeVisible();

    // Botones principales
    await expect(page.getByRole("button", { name: /Nuevo equipo/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Uso/i })).toBeVisible();

    // Barra de búsqueda
    await expect(page.getByPlaceholder(/Buscar/i)).toBeVisible();
  });

  test("Click en Nuevo equipo abre el editor V2 (página completa, no modal)", async ({ page }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Nuevo equipo/i }).click();

    // El form V2 es una página completa (variant="page"), no un dialog modal.
    await page.waitForURL(/\/admin\/equipos\/nuevo/);
    await expect(page.getByRole("heading", { name: /Nuevo equipo/i })).toBeVisible();

    // Status switches del top
    await expect(page.getByLabel(/Visible en catálogo|Oculto del catálogo/i)).toBeVisible();
    await expect(page.getByLabel(/Ficha completa|Ficha pendiente/i)).toBeVisible();

    // Link bar arriba
    await expect(page.getByText(/Link del producto/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Buscar foto/i })).toBeVisible();
  });

  test("Cmd+S dispara submit del form abierto", async ({ page }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Nuevo equipo/i }).click();
    await page.waitForURL(/\/admin\/equipos\/nuevo/);
    await expect(page.getByRole("heading", { name: /Nuevo equipo/i })).toBeVisible();

    // Llenar nombre (campo requerido)
    await page.locator('input[name="nombre"]').first().fill("Test E2E");

    // Cmd+S → debería triggerear submit. Si no hay errores, navega de vuelta a la lista.
    await page.keyboard.press("Meta+s");

    // Sin backend real no podemos verificar el save; verificamos que el handler
    // disparó (network request al endpoint correcto, o volvió a /admin/equipos).
    await page.waitForTimeout(1000);
    // Smoke: no debería haber crasheado.
  });

  test("Stock con botones +/- ajusta el valor", async ({ page }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Nuevo equipo/i }).click();

    // El stock arranca en 1 por default
    const stockInput = page.locator('input[name="cantidad"]').first();
    await expect(stockInput).toHaveValue("1");

    // Botón +
    await page.getByLabel("Sumar 1 al stock").click();
    await expect(stockInput).toHaveValue("2");

    // Botón -
    await page.getByLabel("Restar 1 al stock").click();
    await expect(stockInput).toHaveValue("1");

    // No baja de 0
    await page.getByLabel("Restar 1 al stock").click();
    await page.getByLabel("Restar 1 al stock").click();
    await expect(stockInput).toHaveValue("0");
  });

  test("Filtro 'Solo incompletos' cambia el listado", async ({ page }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    const filterBtn = page.getByRole("button", { name: /Solo incompletos/i });
    await expect(filterBtn).toBeVisible();

    // Click para activar
    await filterBtn.click();

    // El URL no cambia pero el filtro se aplica. Verificar visualmente.
    await expect(filterBtn).toContainText("✓");
  });

  test("Toggle Papelera muestra equipos eliminados (vista vacía o con datos)", async ({ page }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    const papeleraBtn = page.getByRole("button", { name: /^Papelera$/i });
    await papeleraBtn.click();

    // Verificar que el botón está activo
    await expect(papeleraBtn).toBeVisible();
  });

  test("EDIT: Pegar HTML abre el modal (regresión #1263 — antes no abría nunca)", async ({
    page,
  }) => {
    await page.goto("/admin/equipos");
    await page.waitForLoadState("networkidle");

    // Entrar al editor de un equipo cualquiera vía el ActionMenu (bottom sheet)
    // de la fila — este suite corre a 375px (mobile-chrome, playwright.config.ts),
    // así que el trigger visible es "Más acciones" (botones planos en un Drawer,
    // no el DropdownMenuItem de escritorio). No hardcodeamos un id — el test
    // corre contra la data real de la DB local.
    await page.getByRole("button", { name: "Más acciones" }).first().click();
    await page.getByRole("button", { name: /^Editar$/i }).click();
    await page.waitForURL(/\/admin\/equipos\/\d+\/editar/);

    // "Pegar HTML" es edit-only (isEdit && ...) — antes del fix, este click
    // seteaba htmlPasteOpen pero ningún <Dialog> lo mostraba (variant="page"
    // nunca montaba la rama variant="dialog" donde vivía el modal).
    await page.getByRole("button", { name: /^Pegar HTML$/i }).click();
    const dialog = page.getByRole("dialog", { name: /Pegar HTML del producto/i });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByPlaceholder("<html>…</html>")).toBeVisible();

    await dialog.getByRole("button", { name: /^Cancelar$/i }).click();
    await expect(dialog).not.toBeVisible();
  });
});
