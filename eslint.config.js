import js from "@eslint/js";
import eslintPluginPrettier from "eslint-plugin-prettier/recommended";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

// Guardrail del design system: prohíbe las escalas de color genéricas de
// Tailwind (ej. `text-green-700`, `bg-blue-500`) en className. El diseño sale
// de los tokens de marca (`verde`, `azul`, `destructive`, `amber`, surfaces).
// Ver docs/DESIGN_SYSTEM.md → Tiers de color.
//
// NOTA: `amber-NNN` (escala genérica) NO se prohíbe todavía — el tratamiento
// del amber-texto está en revisión visual diferida con el dueño. Cuando se
// resuelva, sumar `amber` a la lista de escalas de abajo.
const GENERIC_COLOR_RE =
  "(?:text|bg|border|ring|ring-offset|outline|divide|from|via|to|fill|stroke|decoration|accent|caret|placeholder|shadow)-" +
  "(?:slate|gray|zinc|neutral|stone|red|orange|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-" +
  "(?:50|[1-9]00|950)";
const GENERIC_COLOR_MSG =
  "Usá tokens del design system (verde/azul/destructive/amber/surfaces) en vez de colores genéricos de Tailwind. " +
  "Excepciones Tier 3 (paletas categóricas) y Tier 4 (marcas de terceros) van con eslint-disable + comentario. " +
  "Ver docs/DESIGN_SYSTEM.md → Tiers de color.";

export default tseslint.config(
  // `docs/design-kit/` es un snapshot del kit exportado por Claude Design
  // (artefacto de documentación, no código de prod). No lo lintamos —
  // sus .tsx vienen con su propio estilo upstream y no aportan calidad al
  // chequearlos acá. El supervisor cuida la consistencia del kit en sus PRs.
  { ignores: ["dist", ".output", ".vinxi", "docs/**"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "server-only",
              message:
                "TanStack Start does not use the Next.js `server-only` package. Rename the module to `*.server.ts` or mark it with `@tanstack/react-start/server-only`.",
            },
          ],
        },
      ],
      "react-hooks/exhaustive-deps": "error",
      "react-refresh/only-export-components": ["error", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": "off",
      "no-restricted-syntax": [
        "error",
        { selector: `Literal[value=/${GENERIC_COLOR_RE}/]`, message: GENERIC_COLOR_MSG },
        {
          selector: `TemplateElement[value.raw=/${GENERIC_COLOR_RE}/]`,
          message: GENERIC_COLOR_MSG,
        },
      ],
    },
  },
  {
    // Tier 4 (marca de terceros): el componente es enteramente la identidad de
    // WhatsApp (verde de WhatsApp). Ver docs/DESIGN_SYSTEM.md → Tiers de color.
    files: ["src/components/admin/WhatsAppButton.tsx"],
    rules: { "no-restricted-syntax": "off" },
  },
  eslintPluginPrettier,
);
