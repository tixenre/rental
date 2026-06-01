#!/usr/bin/env node
/**
 * migrate-imports.mjs — adopción de @rambla/design-system en tixenre/rental
 * ------------------------------------------------------------------------
 * Reescribe los imports del código de la app para que apunten al paquete,
 * y lista los archivos duplicados del repo que ahora viven en el DS.
 *
 * Uso:
 *   node scripts/migrate-imports.mjs            # dry-run (no toca nada)
 *   node scripts/migrate-imports.mjs --apply    # escribe los cambios
 *   node scripts/migrate-imports.mjs --app src  # raíz a escanear (default: src)
 *
 * Sin dependencias — sólo Node built-ins.
 */

import { readdirSync, readFileSync, writeFileSync, statSync } from "node:fs";
import { join, extname } from "node:path";

const args = process.argv.slice(2);
const APPLY = args.includes("--apply");
const APP_DIR = (() => {
  const i = args.indexOf("--app");
  return i !== -1 && args[i + 1] ? args[i + 1] : "src";
})();

const PKG = "@rambla/design-system";

/* Mapeo de import specifiers: prefijo viejo → nuevo.
   El orden importa: los más específicos primero. */
const MAP = [
  ["@/components/ui", `${PKG}/components/ui`],
  ["@/components/kit", `${PKG}/components/kit`],
  ["@/components/rental", `${PKG}/components/rental`],
  ["@/lib/format", `${PKG}/lib/format`],
  ["@/assets/brand", `${PKG}/brand`],
  // NOTA: @/lib/utils NO se reescribe por defecto — el repo puede tener
  // helpers extra ahí además de cn(). Si tu utils.ts es sólo cn(), descomentá:
  // ["@/lib/utils",      `${PKG}/lib/utils`],
];

/* Archivos del repo que el paquete ahora reemplaza (candidatos a borrar
   una vez verificado el build). Relativos a APP_DIR. */
const DUPLICATES = [
  "styles.css",
  "lib/format.ts",
  "components/ui",
  "components/kit",
  "components/rental",
  "assets/fonts",
  "assets/brand",
  // lib/utils.ts → revisá manualmente (puede tener helpers propios)
];

const EXTS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (EXTS.has(extname(name))) out.push(p);
  }
  return out;
}

/* Reescribe sólo dentro de strings de import/export y de import() dinámico.
   Matchea `from "X"`, `from 'X'`, `import("X")`. */
function rewrite(src) {
  let count = 0;
  const out = src.replace(/(from\s*|import\s*\(\s*)(['"])([^'"]+)\2/g, (full, lead, q, spec) => {
    for (const [oldP, newP] of MAP) {
      if (spec === oldP || spec.startsWith(oldP + "/")) {
        count++;
        return `${lead}${q}${newP + spec.slice(oldP.length)}${q}`;
      }
    }
    return full;
  });
  return { out, count };
}

let root;
try {
  root = walk(APP_DIR);
} catch {
  console.error(`✗ No pude leer "${APP_DIR}". Pasá --app <dir> con la raíz del código.`);
  process.exit(1);
}

let touched = 0,
  total = 0;
for (const file of root) {
  const src = readFileSync(file, "utf8");
  const { out, count } = rewrite(src);
  if (count > 0) {
    touched++;
    total += count;
    console.log(`${APPLY ? "✎" : "·"} ${file}  (${count} import${count > 1 ? "s" : ""})`);
    if (APPLY) writeFileSync(file, out, "utf8");
  }
}

console.log("\n" + "─".repeat(56));
console.log(`${APPLY ? "APLICADO" : "DRY-RUN"}: ${total} imports en ${touched} archivos.`);
if (!APPLY) console.log("Volvé a correr con --apply para escribir los cambios.");

console.log("\nDuplicados a borrar tras verificar el build (revisá uno por uno):");
for (const d of DUPLICATES) console.log(`  ${join(APP_DIR, d)}`);
console.log(
  '\nManual: cambiá en tu entry  import "./styles.css"  →  import "' + PKG + '/styles.css"',
);
console.log("Manual: @/lib/utils — repointá a mano sólo si tu utils.ts es únicamente cn().");
