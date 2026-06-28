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

// Guardrail de contraste (solo back-office): prohíbe los tokens de marca/status
// como COLOR DE TEXTO (`text-amber`, `text-verde`, `text-rosa`…). Son tokens de
// FONDO/acento: sobre bone/blanco dan 1.7-2.9:1 (fallan WCAG AA). El texto sobre
// tints usa los tokens `-ink` (`text-verde-ink`/`text-azul-ink`) o el primitivo
// `Pill`/`EstadoBadge`. El lookahead `(?![\w-])` deja pasar `-ink`/`-soft`/`-hot`.
// El `(?!.*bg-ink)` permite el "inverted badge" (amber sobre bg-ink oscuro pasa
// contraste — ej. filtro activo, badge "Nuevo"). El `\/` escapa la opacidad
// (text-amber/70) para no cerrar la regex de esquery. Scope admin: el lado
// público usa estos tokens como accent de marca de área.
// Ver docs/DESIGN_SYSTEM.md → Filosofía de diseño (contraste real).
const BRAND_TEXT_RE =
  "^(?!.*bg-ink).*text-(?:amber|verde|azul|rosa|naranja|estudio)(?:\\/[0-9]+)?(?![\\w-])";
const BRAND_TEXT_MSG =
  "No uses tokens de marca/status como color de TEXTO (text-amber/verde/rosa…): fallan contraste WCAG sobre fondo claro. " +
  "Usá text-ink, los tokens -ink (text-verde-ink/text-azul-ink) o el primitivo Pill/EstadoBadge. " +
  "Para énfasis cromático: bg-amber/15 + text-ink. Ver docs/DESIGN_SYSTEM.md → contraste.";

// Selectores base (aplican a toda la app).
const BASE_RESTRICTED = [
  { selector: `Literal[value=/${GENERIC_COLOR_RE}/]`, message: GENERIC_COLOR_MSG },
  { selector: `TemplateElement[value.raw=/${GENERIC_COLOR_RE}/]`, message: GENERIC_COLOR_MSG },
  { selector: `Literal[value=/${MAGIC_SIZE_RE}/]`, message: MAGIC_SIZE_MSG },
  { selector: `TemplateElement[value.raw=/${MAGIC_SIZE_RE}/]`, message: MAGIC_SIZE_MSG },
];
// Selectores extra solo-admin (contraste).
const BRAND_TEXT_RESTRICTED = [
  { selector: `Literal[value=/${BRAND_TEXT_RE}/]`, message: BRAND_TEXT_MSG },
  { selector: `TemplateElement[value.raw=/${BRAND_TEXT_RE}/]`, message: BRAND_TEXT_MSG },
];

// Guardrail de "reusar no recrear" (solo back-office): obliga a usar los
// componentes del DS en vez de campos de formulario nativos. El DS es la fuente
// única — un <input>/<textarea> a mano se desvía (pierde foco/altura/16px-mobile
// + no lo alcanza el futuro editor de temas). Excepciones legítimas (input file,
// custom borderless) van con: eslint-disable-next-line no-restricted-syntax + motivo.
// (No se prohíbe <select> —el picker nativo es mejor UX en mobile— ni <button>
// —demasiados usos legítimos: toggles, icon-only, action-links—; esos los cuida
// el supervisor / skill design-system.) Ver docs/DESIGN_SYSTEM.md.
const RAW_FORM_RESTRICTED = [
  {
    selector: "JSXOpeningElement[name.name='input']",
    message:
      "Usá <Input> del DS (o <Checkbox> para checkbox) en vez de <input> nativo. " +
      "Excepción (file / custom borderless): eslint-disable-next-line no-restricted-syntax + motivo.",
  },
  {
    selector: "JSXOpeningElement[name.name='textarea']",
    message: "Usá <Textarea> del DS en vez de <textarea> nativo.",
  },
];

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
      "no-restricted-syntax": ["error", ...BASE_RESTRICTED],
    },
  },
  {
    // Guardrail de contraste — solo back-office: a los selectores base les suma
    // la prohibición de tokens de marca/status como color de texto (ver arriba).
    files: ["src/routes/admin/**/*.{ts,tsx}", "src/components/admin/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...BASE_RESTRICTED,
        ...BRAND_TEXT_RESTRICTED,
        ...RAW_FORM_RESTRICTED,
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
