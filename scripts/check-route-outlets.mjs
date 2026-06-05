#!/usr/bin/env node
// check-route-outlets.mjs — guardrail de ruteo.
//
// Caza un bug SILENCIOSO de TanStack Router: un archivo de ruta "hoja" (ej. una lista)
// se vuelve el route-PARENT de sus sub-rutas (`$id`, `nuevo`, …) por la convención de
// nombres, pero su componente NO renderiza `<Outlet/>`. Resultado: navegar a un hijo
// cambia la URL pero la pantalla hija no aparece (te quedás viendo la lista). No lo cazan
// build, lint ni tsc — solo aparece abriendo la pantalla a mano. Pasó con `pedidos-v2`
// (#752). La cura: la lista va como ruta `.index` (TanStack crea el parent con Outlet) o
// el parent renderiza `<Outlet/>`.
//
// Heurística (sobre `src/routes/`): un archivo F es "parent" si existe otra ruta cuyo
// route-key arranca con `F.key + "."` o `F.key + "/"` (F tiene hijos). Todo parent debe
// proveer `<Outlet/>`: directo en el archivo, o vía un componente que importa (1 nivel de
// indirección — ej. un layout). Si ninguno lo provee, falla con el archivo culpable.

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, relative, dirname, resolve } from "node:path";

const ROUTES = "src/routes";
const SRC = "src";

if (!existsSync(ROUTES)) {
  console.error(`✗ No existe ${ROUTES} (¿corriendo desde la raíz del repo?).`);
  process.exit(2);
}

function walk(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else if (e.name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

const files = walk(ROUTES).filter((f) => !f.includes("-preview") && !f.endsWith(".gen.ts"));

const keyOf = (f) =>
  relative(ROUTES, f)
    .replace(/\.lazy\.tsx$/, "")
    .replace(/\.tsx$/, "");

const hasOutlet = (src) => /\bOutlet\b/.test(src);

// Resuelve un import (`@/…` o relativo) a un archivo real del repo.
function resolveImport(spec, fromFile) {
  let base;
  if (spec.startsWith("@/")) base = join(SRC, spec.slice(2));
  else if (spec.startsWith(".")) base = resolve(dirname(fromFile), spec);
  else return null; // node_modules → fuera de alcance
  for (const c of [base + ".tsx", base + ".ts", join(base, "index.tsx"), join(base, "index.ts")]) {
    if (existsSync(c)) return c;
  }
  return null;
}

function importSpecs(src) {
  const specs = [];
  const re = /(?:from|import)\s+["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;
  let m;
  while ((m = re.exec(src))) specs.push(m[1] ?? m[2]);
  return specs;
}

// ¿el parent provee Outlet, directo o vía un componente que importa (1 nivel)?
function providesOutlet(entry) {
  if (hasOutlet(entry.src)) return true;
  for (const spec of importSpecs(entry.src)) {
    const f = resolveImport(spec, entry.f);
    if (f && hasOutlet(readFileSync(f, "utf8"))) return true;
  }
  return false;
}

const entries = files.map((f) => ({ f, key: keyOf(f), src: readFileSync(f, "utf8") }));

const errors = [];
for (const e of entries) {
  if (e.key === "__root") continue; // el root siempre tiene Outlet
  const isParent = entries.some(
    (o) => o !== e && (o.key.startsWith(e.key + ".") || o.key.startsWith(e.key + "/")),
  );
  if (isParent && !providesOutlet(e)) errors.push(e);
}

if (errors.length) {
  console.error("✗ Rutas PARENT sin <Outlet/> — las pantallas hijas NO van a renderizar:\n");
  for (const e of errors) {
    console.error(`  • ${e.f}`);
    console.error(
      `    tiene sub-rutas pero ni el archivo ni su layout renderizan <Outlet/>. Convertila en`,
    );
    console.error(`    ruta .index (ej. ${e.key}.index.lazy.tsx) o agregá <Outlet/>. Ver #752.`);
  }
  console.error(`\n${errors.length} ruta(s) rota(s).`);
  process.exit(1);
}

console.log(`✓ ${entries.length} rutas chequeadas — todo route-parent provee <Outlet/>.`);
