#!/usr/bin/env node
// context-size.mjs — mide el tamaño del prefijo AUTO-CARGADO (CLAUDE.md + sus @-imports).
//
// Es la señal A del harness de evals (ver scripts/evals/README.md): cuantifica el "impuesto de
// contexto" que se paga en CADA sesión. Sirve para el lado VALOR del trim del digest (Exp 1) y el
// lado COSTO del merge de skills (Exp 2).
//
// Uso:
//   node scripts/evals/context-size.mjs                      → reporta el tamaño actual
//   node scripts/evals/context-size.mjs --save before        → guarda un snapshot
//   node scripts/evals/context-size.mjs --diff before after  → compara dos snapshots
//
// Token proxy = chars/4 (heurística zero-dep; para un DELTA el ratio importa más que el absoluto).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const SNAP_DIR = join(ROOT, "scripts/evals/.snapshots");
const FRONT_DOOR = "CLAUDE.md";

// Resuelve los @-imports de un archivo markdown (1 nivel — es lo que auto-carga el front door).
function collectAutoloaded(entry) {
  const files = [entry];
  const src = readFileSync(join(ROOT, entry), "utf8");
  for (const m of src.matchAll(/^@(\S+)\s*$/gm)) files.push(m[1]);
  return files;
}

function measure() {
  const rows = collectAutoloaded(FRONT_DOOR).map((f) => {
    const chars = readFileSync(join(ROOT, f), "utf8").length;
    return { file: f, chars, tokens: Math.round(chars / 4) };
  });
  const total = rows.reduce(
    (a, r) => ({ chars: a.chars + r.chars, tokens: a.tokens + r.tokens }),
    { chars: 0, tokens: 0 },
  );
  return { rows, total };
}

const fmt = (n) => n.toLocaleString("en-US");

function printMeasure(m) {
  for (const r of m.rows)
    console.log(`  ${r.file.padEnd(28)} ${fmt(r.chars).padStart(8)} chars  ~${fmt(r.tokens).padStart(6)} tok`);
  console.log(`  ${"TOTAL".padEnd(28)} ${fmt(m.total.chars).padStart(8)} chars  ~${fmt(m.total.tokens).padStart(6)} tok`);
}

const [cmd, a, b] = process.argv.slice(2);

if (cmd === "--save") {
  const m = measure();
  mkdirSync(SNAP_DIR, { recursive: true });
  writeFileSync(join(SNAP_DIR, `${a}.json`), JSON.stringify(m.total));
  console.log(`Prefijo auto-cargado (snapshot "${a}"):`);
  printMeasure(m);
} else if (cmd === "--diff") {
  const read = (l) => JSON.parse(readFileSync(join(SNAP_DIR, `${l}.json`), "utf8"));
  const A = read(a);
  const B = read(b);
  const dC = B.chars - A.chars;
  const dT = B.tokens - A.tokens;
  const pct = ((dC / A.chars) * 100).toFixed(1);
  console.log(`Delta ${a} → ${b}:`);
  console.log(`  chars : ${fmt(A.chars)} → ${fmt(B.chars)}  (${dC >= 0 ? "+" : ""}${fmt(dC)}, ${pct}%)`);
  console.log(`  tokens: ~${fmt(A.tokens)} → ~${fmt(B.tokens)}  (${dT >= 0 ? "+" : ""}${fmt(dT)})`);
} else {
  console.log("Prefijo auto-cargado (CLAUDE.md + @-imports):");
  printMeasure(measure());
}
