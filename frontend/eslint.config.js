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
const GENERIC_COLOR_RE =
  "(?:text|bg|border|ring|ring-offset|outline|divide|from|via|to|fill|stroke|decoration|accent|caret|placeholder|shadow)-" +
  "(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-" +
  "(?:50|[1-9]00|950)";
const GENERIC_COLOR_MSG =
  "Usá tokens del design system (verde/azul/destructive/amber/surfaces) en vez de colores genéricos de Tailwind. " +
  "Excepciones Tier 3 (paletas categóricas) y Tier 4 (marcas de terceros) van con eslint-disable + comentario. " +
  "Ver docs/DESIGN_SYSTEM.md → Tiers de color.";

// Guardrail tipográfico: prohíbe tamaños de fuente mágicos (text-[Npx]).
// Usá las utilidades del DS: text-3xs (9px), text-2xs (10px), text-xs (12px),
// text-sm (14px), text-15 (15px), text-base (16px), text-22 (22px) etc.
// Tamaños sin equivalente en el scale → eslint-disable-line + comentario del por qué.
// Atrapa px Y rem/em arbitrarios (text-[13px], text-[0.8125rem], text-[1.2em]) —
// el codemod tipográfico migró los rem residuales a tokens; el guardrail cierra el boquete.
const MAGIC_SIZE_RE = "text-\\[[0-9.]+(px|rem|em)\\]";
const MAGIC_SIZE_MSG =
  "Usá utilidades del DS en vez de tamaños mágicos: text-3xs/text-2xs/text-xs/text-sm/text-15/text-base/text-22… " +
  "Tamaño sin equivalente → eslint-disable-line + comentario del por qué.";

export default tseslint.config(
  { ignores: ["dist", ".output", ".vinxi", "docs/**"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    // Un `eslint-disable` que ya no silencia nada es deuda: lo tratamos como
    // error para que no se acumulen disables stale (#476).
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
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
        { selector: `Literal[value=/${MAGIC_SIZE_RE}/]`, message: MAGIC_SIZE_MSG },
        {
          selector: `TemplateElement[value.raw=/${MAGIC_SIZE_RE}/]`,
          message: MAGIC_SIZE_MSG,
        },
      ],
    },
  },
  {
    // Boundary del design-system: los archivos en design-system/ no pueden
    // importar de la app (api, stores, componentes de negocio, rutas).
    // Esto mantiene la capa portable; si necesitás algo de la app, pasalo
    // como prop/callback. Equivale al boundary de un paquete workspace, sin
    // la ceremonia de monorepo.
    files: ["src/design-system/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "server-only",
              message: "TanStack Start does not use the Next.js `server-only` package.",
            },
          ],
          patterns: [
            {
              group: [
                "@/lib/api*",
                "@/lib/*-store",
                "@/components/rental*",
                "@/components/admin*",
                "@/routes*",
                "@/hooks/use-*",
              ],
              message:
                "El design-system no puede importar de la app (lib/api, stores, rental, admin, routes). " +
                "Extraé la dependencia a un prop o callback.",
            },
          ],
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
