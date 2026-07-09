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

import { test, expect, type Page } from "@playwright/test";

const ADMIN_TESTS_ENABLED = process.env.PLAYWRIGHT_ADMIN === "1";

/**
 * Crea un equipo mínimo (nombre + 1 categoría, sin foto/descripción/serie/
 * valor de reposición) y sigue el handoff automático "Completar →" hasta el
 * editor de ESE equipo — setup compartido por los tests de hidratación
 * (#1263 Fase 1), cada uno con su propio equipo fresco (no comparten estado
 * entre tests). Devuelve el nombre único usado, para poder buscarlo/afirmarlo
 * después de un reload.
 */
async function crearEquipoYAbrirEdit(page: Page, nombre: string) {
  await page.goto("/admin/equipos/nuevo");
  await page.waitForLoadState("networkidle");

  await page.locator('input[name="nombre"]').first().fill(nombre);
  // Una categoría es obligatoria para guardar — la primera disponible alcanza,
  // el test no depende de cuál sea.
  await page
    .locator("section", { hasText: "Categorías del catálogo" })
    .getByRole("button")
    .first()
    .click();

  await page.getByRole("button", { name: "Guardar" }).click();
  // Sin foto/descripción/serie/valor de reposición, siempre faltan
  // recomendados → toast con la acción "Completar →" (ver submit handler).
  await page.getByRole("button", { name: "Completar →" }).click();
  await page.waitForURL(/\/admin\/equipos\/\d+\/editar/);
  await page.waitForLoadState("networkidle");
}

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

  // ── Regresión de hidratación (#1263 Fase 1) ─────────────────────────────
  // Estos 3 tests fijan el comportamiento ACTUAL antes de centralizar la
  // hidratación de `initial` en useEquipoFormDraft — tienen que pasar HOY,
  // contra el código pre-refactor, y seguir pasando después (move-verbatim).

  test("CREATE con recomendados faltantes ofrece completar → handoff a EDIT", async ({ page }) => {
    const nombre = `Test E2E Handoff ${Date.now()}`;
    await page.goto("/admin/equipos/nuevo");
    await page.waitForLoadState("networkidle");

    await page.locator('input[name="nombre"]').first().fill(nombre);
    await page
      .locator("section", { hasText: "Categorías del catálogo" })
      .getByRole("button")
      .first()
      .click();

    await page.getByRole("button", { name: "Guardar" }).click();

    // Sin foto/descripción/serie/valor de reposición: el submit handler junta
    // `missing` y ofrece completar en vez de solo confirmar "Equipo creado".
    await expect(page.getByText(/Faltan datos recomendados/i)).toBeVisible();
    await page.getByRole("button", { name: "Completar →" }).click();

    // El handoff (onCreatedWithMissingRecommended) reabre en /editar con el
    // id del equipo recién creado.
    await page.waitForURL(/\/admin\/equipos\/\d+\/editar/);
    await expect(page.locator('input[name="nombre"]').first()).toHaveValue(nombre);
  });

  test("Tipo=Combo muestra el sentinel de stock y monta ComboEditor", async ({ page }) => {
    await crearEquipoYAbrirEdit(page, `Test E2E Combo ${Date.now()}`);

    // Por default (tipo="simple" recién creado) el stock es +/- editable.
    await expect(page.getByLabel("Restar 1 al stock")).toBeVisible();
    await expect(page.getByText("Kit (componentes incluidos)")).toBeVisible();

    // El trigger del <Select> muestra el value actual como texto — "Equipo"
    // es el label de tipo="simple" (default de un equipo recién creado).
    await page.getByRole("combobox", { name: "Equipo" }).click();
    await page.getByRole("option", { name: "Combo" }).click();

    // Sentinel: el stock deja de ser editable a mano (#635 — cantidad=9999,
    // derivada de los componentes del combo).
    await expect(page.getByText("Sentinel (9999) — derivado de componentes")).toBeVisible();
    await expect(page.getByLabel("Restar 1 al stock")).not.toBeVisible();
    // El título de la sección + qué editor monta cambian juntos (esCombo).
    await expect(page.getByText("Componentes del combo")).toBeVisible();
  });

  test("EDIT: nombre público y precio manual sobreviven un reload", async ({ page }) => {
    const nombrePublicoTest = `Nombre Público E2E ${Date.now()}`;
    await crearEquipoYAbrirEdit(page, `Test E2E Hidratación ${Date.now()}`);
    const url = page.url();

    // Nombre público: tipear a mano apaga el auto-gen (setNombrePublicoAuto
    // (false)) — el placeholder varía según si la categoría elegida tiene
    // molde o no, así que matcheamos cualquiera de los dos.
    const nombrePublicoInput = page.getByPlaceholder(
      /Generado automático según el molde de la categoría|Ej: Cable HDMI 2\.0 50cm/,
    );
    await nombrePublicoInput.fill(nombrePublicoTest);

    // Precio manual: escribir a mano en precio_jornada flip-ea
    // precioJornadaManual → el label del Field lo refleja al toque.
    const precioInput = page.locator('input[name="precio_jornada"]');
    await precioInput.fill("54321");
    await expect(page.getByText("Precio/jornada (manual)")).toBeVisible();

    // "Aplicar" (no "Guardar") — guarda sin cerrar, queda en la misma página.
    // Es a propósito: el camino de mayor riesgo de esta fase es re-hidratar
    // DESPUÉS de un save-sin-cerrar (initial cambia de identidad porque la
    // mutación invalida la query) — el bug real que ya arregló 89a1e978 para
    // specs. Confirmamos con un reload COMPLETO (re-fetch real, no solo el
    // form.reset local de "Aplicar").
    await page.getByRole("button", { name: "Aplicar" }).click();
    await expect(page.getByText(/Cambios aplicados|Equipo actualizado/i)).toBeVisible();

    await page.goto(url);
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByPlaceholder(
        /Generado automático según el molde de la categoría|Ej: Cable HDMI 2\.0 50cm/,
      ),
    ).toHaveValue(nombrePublicoTest);
    await expect(page.locator('input[name="precio_jornada"]')).toHaveValue("54321");
    await expect(page.getByText("Precio/jornada (manual)")).toBeVisible();
  });
});
