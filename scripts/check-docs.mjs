#!/usr/bin/env node
// check-docs.mjs — guardrail de gobernanza (drift de docs + skills).
//
// El CI de código (`ci.yml`) IGNORA los cambios de docs (`paths-ignore: **/*.md`, `docs/**`),
// así que el drift documental nunca se cazaba mecánicamente (caso testigo: "MANIFIESTO 671
// líneas" cuando tenía 287). Este script lo caza, y corre en su propio workflow `docs-lint.yml`
// (que SÍ se dispara con cambios de docs / `.claude/**`) y en el hook SessionStart.
//
// PORTABLE: el motor es genérico; lo repo-específico (rutas de memoria, front door, skills) vive en
// `.claude/governance.config.mjs`. Si no existe, se usan los defaults de abajo → para adoptar en otro
// repo basta copiar este script + `.claude/skills/` y crear esa config.
//
// Chequea cinco cosas:
//   1. PARIDAD digest↔log: el digest (`memoryDigest`) y el log (`memoryLog`) tienen EXACTAMENTE el
//      mismo conjunto de headers `### fecha — título` (decisión 2026-06-08, memoria en dos sub-capas).
//   2. IMPORT presente: el front door (`claudeMd`) sigue auto-cargando el digest (`memoryImportPattern`).
//   3. LINKS vivos: todo link markdown a un `*.md` o a una ruta `.claude/` desde los docs de
//      gobernanza resuelve a un archivo/carpeta que exista (cross-refs no rotas).
//   4. PARIDAD skills↔registro: todo skill en disco (`skillsDir/*/SKILL.md`) está linkeado en el front
//      door (si no, el mapa de skills driftea — caso testigo: `auditoria-profunda` invisible).
//   5. LINTER de skills: cada `SKILL.md` tiene frontmatter `name`/`description`/`model`/`last-reviewed`/
//      `version` bien formado. Staleness (`last-reviewed` viejo) = warning, no error.

import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { join, dirname, resolve, relative } from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = process.cwd();
if (!existsSync(join(ROOT, "CLAUDE.md"))) {
  console.error("✗ No existe CLAUDE.md (¿corriendo desde la raíz del repo?).");
  process.exit(2);
}

// ── Config portable (con fallback a defaults si no existe) ───────────────────────────────────
const DEFAULTS = {
  memoryDigest: "docs/MEMORIA.md",
  memoryLog: "docs/DECISIONES.md",
  claudeMd: "CLAUDE.md",
  memoryImportPattern: "@docs/MEMORIA.md",
  govDirs: ["docs/", ".claude/"],
  govRootFiles: ["CLAUDE.md", "MANIFIESTO.md", "README.md"],
  skillsDir: ".claude/skills",
  skillStaleDays: 120,
};
let cfg = { ...DEFAULTS };
const CONFIG_PATH = join(ROOT, ".claude", "governance.config.mjs");
if (existsSync(CONFIG_PATH)) {
  try {
    const mod = await import(pathToFileURL(CONFIG_PATH).href);
    cfg = { ...DEFAULTS, ...(mod.default ?? mod) };
  } catch (e) {
    console.error(
      `✗ No se pudo cargar ${relative(ROOT, CONFIG_PATH)}: ${e.message}`,
    );
    process.exit(2);
  }
}

const errors = [];
const warnings = [];
const read = (p) => readFileSync(p, "utf8");
const headersOf = (p) =>
  read(p)
    .split("\n")
    .filter((l) => l.startsWith("### "))
    .map((l) => l.slice(4).trim());

// ── 1. Paridad digest ↔ log ──────────────────────────────────────────────────────────────────
const DIGEST = cfg.memoryDigest;
const LOG = cfg.memoryLog;
for (const p of [DIGEST, LOG]) {
  if (!existsSync(join(ROOT, p)))
    errors.push(`Falta ${p} (la memoria vive en digest + log).`);
}
if (existsSync(join(ROOT, DIGEST)) && existsSync(join(ROOT, LOG))) {
  const d = headersOf(join(ROOT, DIGEST));
  const l = headersOf(join(ROOT, LOG));
  const ds = new Set(d);
  const ls = new Set(l);
  for (const h of d)
    if (!ls.has(h))
      errors.push(`Header en ${DIGEST} sin par en ${LOG}: "${h}"`);
  for (const h of l)
    if (!ds.has(h))
      errors.push(`Header en ${LOG} sin par en ${DIGEST}: "${h}"`);
  if (d.length !== ds.size)
    errors.push(`${DIGEST} tiene headers \`### fecha — título\` duplicados.`);
  if (l.length !== ls.size)
    errors.push(`${LOG} tiene headers \`### fecha — título\` duplicados.`);
}

// ── 2. El import auto-cargado tiene que seguir presente ──────────────────────────────────────
const CLAUDE_MD = cfg.claudeMd;
const importRe = new RegExp(
  `^${cfg.memoryImportPattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`,
  "m",
);
if (!importRe.test(read(join(ROOT, CLAUDE_MD)))) {
  errors.push(
    `${CLAUDE_MD} ya no auto-carga \`${cfg.memoryImportPattern}\` (se rompería el digest en cada sesión).`,
  );
}

// ── 3. Links vivos en los docs de gobernanza ─────────────────────────────────────────────────
function mdFilesIn(dir) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "archive" || e.name.startsWith(".")) continue; // histórico / dirs ocultos (incl. .archive/)
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...mdFilesIn(p));
    else if (e.name.endsWith(".md")) out.push(p);
  }
  return out;
}

const govFiles = [
  ...cfg.govRootFiles.map((f) => join(ROOT, f)),
  ...cfg.govDirs.flatMap((d) => mdFilesIn(join(ROOT, d))),
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
      errors.push(
        `Link roto en ${relative(ROOT, file)}: "${target}" no existe.`,
      );
    } else if (target.endsWith(".md") && statSync(resolved).isDirectory()) {
      errors.push(
        `Link en ${relative(ROOT, file)}: "${target}" apunta a una carpeta, no a un .md.`,
      );
    }
  }
}

// ── 4 + 5. Skills: paridad con el registro + linter estructural ──────────────────────────────
const SKILLS_DIR = join(ROOT, cfg.skillsDir);
const REQUIRED_KEYS = [
  "name",
  "description",
  "model",
  "last-reviewed",
  "version",
];
const VALID_MODELS = new Set(["opus", "sonnet", "haiku", "fable", "inherit"]);
let skillCount = 0;
if (existsSync(SKILLS_DIR)) {
  const claudeSrc = read(join(ROOT, CLAUDE_MD));
  for (const e of readdirSync(SKILLS_DIR, { withFileTypes: true })) {
    // Carpetas que arrancan con `.` o `_` no son skills (archivo histórico / templates).
    if (!e.isDirectory() || e.name.startsWith(".") || e.name.startsWith("_"))
      continue;
    const skillPath = join(SKILLS_DIR, e.name, "SKILL.md");
    const relPath = relative(ROOT, skillPath);
    if (!existsSync(skillPath)) {
      errors.push(
        `Carpeta de skill sin SKILL.md: ${relative(ROOT, join(SKILLS_DIR, e.name))}.`,
      );
      continue;
    }
    skillCount++;

    // 4. ¿Está linkeado en el front door? (la ruta relativa POSIX aparece en un link markdown)
    const linkTarget = `${cfg.skillsDir}/${e.name}/SKILL.md`
      .split("\\")
      .join("/");
    if (!claudeSrc.includes(linkTarget)) {
      errors.push(
        `Skill "${e.name}" existe en disco pero no está listado en ${CLAUDE_MD} (mapa de skills driftea).`,
      );
    }

    // 5. Linter estructural del frontmatter.
    const src = read(skillPath);
    const fm = src.match(/^---\n([\s\S]*?)\n---/);
    if (!fm) {
      errors.push(`${relPath}: falta el frontmatter \`---\` al inicio.`);
      continue;
    }
    const block = fm[1];
    const valueOf = (key) => {
      const mm = block.match(new RegExp(`^${key}:\\s*(.+?)\\s*$`, "m"));
      return mm ? mm[1].trim() : null;
    };
    for (const key of REQUIRED_KEYS) {
      if (valueOf(key) === null)
        errors.push(`${relPath}: falta \`${key}:\` en el frontmatter.`);
    }
    const model = valueOf("model");
    if (model && !VALID_MODELS.has(model) && !model.startsWith("claude-")) {
      errors.push(
        `${relPath}: \`model: ${model}\` no es válido (usá ${[...VALID_MODELS].join("/")} o un id claude-*).`,
      );
    }
    const reviewed = valueOf("last-reviewed");
    if (reviewed) {
      const when = new Date(reviewed);
      if (Number.isNaN(when.getTime())) {
        errors.push(
          `${relPath}: \`last-reviewed: ${reviewed}\` no es una fecha válida (YYYY-MM-DD).`,
        );
      } else {
        const days = Math.floor((Date.now() - when.getTime()) / 86400000);
        if (days > cfg.skillStaleDays) {
          warnings.push(
            `${relPath}: \`last-reviewed\` hace ${days} días (> ${cfg.skillStaleDays}) — revisá si sigue vigente.`,
          );
        }
      }
    }
    if (!/^## Auto-mejora/m.test(src)) {
      errors.push(
        `${relPath}: falta la sección \`## Auto-mejora\` (ritual post-uso que deposita en el buzón).`,
      );
    }
  }
}

// ── Bloque 6: COBERTURA de la vitrina del DS (anti-drift del catálogo) ─────────────────────────
//   Todo componente en `componentDirs` (design-system/ui + kit) debe estar demostrado en la vitrina:
//   su path (relativo a srcRoot) aparece en algún `Specimen.files` del catálogo. El manifiesto del
//   catálogo ES el registro (mismo patrón que skills↔CLAUDE.md). Un componente sin vitrina → error.
//   Solo corre si la config define `dsCatalog` y el dir existe (portable: otros repos no lo tienen).
let dsCoverChecked = 0;
const ds = cfg.dsCatalog;
if (ds && existsSync(join(ROOT, ds.catalogDir))) {
  const srcRoot = join(ROOT, ds.srcRoot);
  const catalogSrc = (function collect(dir, acc) {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, e.name);
      if (e.isDirectory()) collect(p, acc);
      else if (/\.(tsx?|ts)$/.test(e.name)) acc.push(read(p));
    }
    return acc;
  })(join(ROOT, ds.catalogDir), []).join("\n");
  const exempt = new Set(ds.exempt ?? []);
  for (const dir of ds.componentDirs ?? []) {
    const abs = join(ROOT, dir);
    if (!existsSync(abs)) continue;
    for (const e of readdirSync(abs, { withFileTypes: true })) {
      if (!e.isFile() || !e.name.endsWith(".tsx")) continue; // solo componentes (.tsx); helpers .ts no
      const rel = relative(srcRoot, join(abs, e.name)); // ej "design-system/ui/button.tsx"
      if (exempt.has(rel)) continue;
      dsCoverChecked++;
      if (!catalogSrc.includes(rel)) {
        errors.push(
          `Componente del DS sin vitrina: \`${rel}\` no está en ningún \`Specimen.files\` del catálogo ` +
            `(${ds.catalogDir}). Agregá su specimen, o exoneralo en governance.config \`dsCatalog.exempt\` (con comentario ⏰).`,
        );
      }
    }
  }
}

// ── Veredicto ────────────────────────────────────────────────────────────────────────────────
if (warnings.length) {
  console.warn("⚠ Warnings de gobernanza (no bloquean):\n");
  for (const w of warnings) console.warn(`  • ${w}`);
  console.warn("");
}

if (errors.length) {
  console.error("✗ Drift de docs/skills de gobernanza:\n");
  for (const e of errors) console.error(`  • ${e}`);
  console.error(
    `\n${errors.length} problema(s). Ver decisiones 2026-06-08 (memoria en dos sub-capas) y ` +
      `2026-06-23 (capa de skills auto-gobernada).`,
  );
  process.exit(1);
}

console.log(
  `✓ Docs/skills de gobernanza OK — paridad digest↔log (${headersOf(join(ROOT, DIGEST)).length} entradas), ` +
    `import presente, ${skillCount} skills registrados y bien formados, links vivos en ${govFiles.length} archivos` +
    (dsCoverChecked ? `, ${dsCoverChecked} componentes del DS con vitrina` : "") +
    `.`,
);
