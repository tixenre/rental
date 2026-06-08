#!/usr/bin/env node
// check-docs.mjs — guardrail de gobernanza (drift de docs).
//
// El CI de código (`ci.yml`) IGNORA los cambios de docs (`paths-ignore: **/*.md`, `docs/**`),
// así que el drift documental nunca se cazaba mecánicamente (caso testigo: "MANIFIESTO 671
// líneas" cuando tenía 287). Este script lo caza, y corre en su propio workflow `docs-lint.yml`
// (que SÍ se dispara con cambios de docs) y en el hook SessionStart.
//
// Chequea tres cosas:
//   1. PARIDAD digest↔log: `docs/MEMORIA.md` (digest) y `docs/DECISIONES.md` (log) tienen que tener
//      EXACTAMENTE el mismo conjunto de headers `### fecha — título`. Es el contrato de la decisión
//      2026-06-08 (memoria en dos sub-capas): toda regla del digest tiene su desarrollo en el log.
//   2. IMPORT presente: `CLAUDE.md` tiene que seguir auto-cargando `@docs/MEMORIA.md`.
//   3. LINKS vivos: todo link markdown a un `*.md` o a una ruta `.claude/` desde los docs de
//      gobernanza tiene que resolver a un archivo/carpeta que exista (cross-refs no rotas).

import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { join, dirname, resolve, relative } from "node:path";

const ROOT = process.cwd();
if (!existsSync(join(ROOT, "CLAUDE.md"))) {
  console.error("✗ No existe CLAUDE.md (¿corriendo desde la raíz del repo?).");
  process.exit(2);
}

const errors = [];
const read = (p) => readFileSync(p, "utf8");
const headersOf = (p) =>
  read(p)
    .split("\n")
    .filter((l) => l.startsWith("### "))
    .map((l) => l.slice(4).trim());

// ── 1. Paridad digest (MEMORIA) ↔ log (DECISIONES) ──────────────────────────────────────────
const DIGEST = "docs/MEMORIA.md";
const LOG = "docs/DECISIONES.md";
for (const p of [DIGEST, LOG]) {
  if (!existsSync(join(ROOT, p))) errors.push(`Falta ${p} (la memoria vive en digest + log).`);
}
if (existsSync(join(ROOT, DIGEST)) && existsSync(join(ROOT, LOG))) {
  const d = headersOf(join(ROOT, DIGEST));
  const l = headersOf(join(ROOT, LOG));
  const ds = new Set(d);
  const ls = new Set(l);
  for (const h of d) if (!ls.has(h)) errors.push(`Header en ${DIGEST} sin par en ${LOG}: "${h}"`);
  for (const h of l) if (!ds.has(h)) errors.push(`Header en ${LOG} sin par en ${DIGEST}: "${h}"`);
  if (d.length !== ds.size)
    errors.push(`${DIGEST} tiene headers \`### fecha — título\` duplicados.`);
  if (l.length !== ls.size) errors.push(`${LOG} tiene headers \`### fecha — título\` duplicados.`);
}

// ── 2. El import auto-cargado tiene que seguir presente ──────────────────────────────────────
if (!/^@docs\/MEMORIA\.md\s*$/m.test(read(join(ROOT, "CLAUDE.md")))) {
  errors.push(
    "CLAUDE.md ya no auto-carga `@docs/MEMORIA.md` (se rompería el digest en cada sesión).",
  );
}

// ── 3. Links vivos en los docs de gobernanza ─────────────────────────────────────────────────
function mdFilesIn(dir) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "archive") continue; // docs/archive/ = histórico congelado, no se mantiene
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...mdFilesIn(p));
    else if (e.name.endsWith(".md")) out.push(p);
  }
  return out;
}

const govFiles = [
  join(ROOT, "CLAUDE.md"),
  join(ROOT, "MANIFIESTO.md"),
  join(ROOT, "README.md"),
  ...mdFilesIn(join(ROOT, "docs")),
  ...mdFilesIn(join(ROOT, ".claude")),
].filter(existsSync);

const LINK_RE = /\[[^\]]*\]\(([^)]+)\)/g;
for (const file of govFiles) {
  const src = read(file);
  let m;
  while ((m = LINK_RE.exec(src))) {
    let target = m[1].trim();
    if (/^(https?:|mailto:|#)/.test(target)) continue; // externos / anclas → fuera de alcance
    target = target.split("#")[0]; // sacar ancla
    if (!target) continue;
    // Solo chequeamos el grafo de gobernanza: links a *.md o a rutas .claude/
    const isGov = target.endsWith(".md") || target.includes(".claude/");
    if (!isGov) continue;
    const resolved = resolve(dirname(file), target);
    if (!existsSync(resolved)) {
      errors.push(`Link roto en ${relative(ROOT, file)}: "${target}" no existe.`);
    } else if (target.endsWith(".md") && statSync(resolved).isDirectory()) {
      errors.push(
        `Link en ${relative(ROOT, file)}: "${target}" apunta a una carpeta, no a un .md.`,
      );
    }
  }
}

// ── Veredicto ────────────────────────────────────────────────────────────────────────────────
if (errors.length) {
  console.error("✗ Drift de docs de gobernanza:\n");
  for (const e of errors) console.error(`  • ${e}`);
  console.error(
    `\n${errors.length} problema(s). Ver decisión 2026-06-08 (memoria en dos sub-capas).`,
  );
  process.exit(1);
}

console.log(
  `✓ Docs de gobernanza OK — paridad digest↔log (${headersOf(join(ROOT, DIGEST)).length} entradas), ` +
    `import presente, links vivos en ${govFiles.length} archivos.`,
);
