#!/usr/bin/env node
/**
 * Guardrail: "cero fotos de contenido en el repo" (F0f).
 *
 * Busca en los archivos trackeados por git imágenes de contenido (fotos de
 * equipos, estudio, marcas, talleres). Las falla para que no entren al repo.
 * Las imágenes de UI permitidas (iconos, favicon, og-image, email assets) están
 * en la allowlist explícita.
 *
 * Uso en CI: node scripts/check-no-content-images.mjs
 * Uso como pre-commit: llamar con `git diff --cached --name-only` en stdin
 *   o pasar los archivos como argumentos.
 *
 * Devuelve exit 1 si encuentra imágenes fuera de la allowlist.
 */
import { execSync } from "child_process";

const IMAGE_EXTS = /\.(jpg|jpeg|png|webp|gif|avif|bmp|tiff?)$/i;

// Allowlist de imágenes de UI que SÍ pueden estar en el repo.
// Comparación relativa a la raíz del repo.
const ALLOWLIST = new Set([
  "frontend/public/favicon.png",
  "frontend/public/icon-512.png",
  "frontend/public/apple-touch-icon.png",
  "frontend/public/og-image.png",
  "frontend/public/email-logo.png",
  "frontend/public/email-wordmark-white.png",
  // Screenshots de auditorías UI (en docs/, no sirven en prod)
  // — se permiten porque viven en docs/ y no en ningún bundle.
]);

// Prefijos que SIEMPRE se permiten (screenshots de auditorías, etc.)
const ALLOWED_PREFIXES = [
  "docs/audit-ui-screenshots/",
  "frontend/src/design-system/", // si algún token tiene una img de referencia
];

function isAllowed(relPath) {
  if (ALLOWLIST.has(relPath)) return true;
  for (const prefix of ALLOWED_PREFIXES) {
    if (relPath.startsWith(prefix)) return true;
  }
  return false;
}

// Lee los archivos trackeados por git.
// En CI corremos sobre el worktree completo. En pre-commit, `git diff --cached`.
let trackedFiles;
try {
  // git ls-files solo muestra archivos trackeados (no .gitignored).
  trackedFiles = execSync("git ls-files", { encoding: "utf-8" })
    .trim()
    .split("\n")
    .filter(Boolean);
} catch (err) {
  console.error("check-no-content-images: no se pudo ejecutar git ls-files:", err.message);
  process.exit(2);
}

const violations = trackedFiles
  .filter((f) => IMAGE_EXTS.test(f))
  .filter((f) => !isAllowed(f));

if (violations.length === 0) {
  console.log("✓ check-no-content-images: sin imágenes de contenido en el repo.");
  process.exit(0);
}

console.error("✗ check-no-content-images: imágenes de contenido encontradas en el repo.");
console.error("  Las fotos de equipos/estudio/marcas deben vivir en R2, no en el repo.");
console.error("  Si es una imagen de UI nueva, agregala a la allowlist en:");
console.error("  scripts/check-no-content-images.mjs (constante ALLOWLIST).");
console.error("");
console.error("  Archivos encontrados:");
for (const f of violations) {
  console.error(`    ${f}`);
}
process.exit(1);
