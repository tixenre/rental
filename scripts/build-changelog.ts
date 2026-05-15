#!/usr/bin/env bun
// build-changelog.ts — genera CHANGELOG.md desde src/data/changelog.ts
// Uso: bun run changelog:build

import { changelog, type ChangelogEntry } from "../src/data/changelog";
import { writeFileSync } from "fs";
import { join } from "path";

const TYPE_LABEL: Record<ChangelogEntry["type"], string> = {
  feat: "Novedades",
  fix: "Correcciones",
  chore: "Mantenimiento",
  docs: "Documentación",
  style: "Estilo",
  refactor: "Refactor",
};

const TYPE_EMOJI: Record<ChangelogEntry["type"], string> = {
  feat: "✨",
  fix: "🐛",
  chore: "🔧",
  docs: "📝",
  style: "🎨",
  refactor: "♻️",
};

function fmtDate(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("es-AR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

// Agrupar por mes-año
const byMonth = new Map<string, ChangelogEntry[]>();
for (const entry of changelog) {
  const key = entry.date.slice(0, 7); // YYYY-MM
  if (!byMonth.has(key)) byMonth.set(key, []);
  byMonth.get(key)!.push(entry);
}

// Ordenar meses desc
const sortedMonths = [...byMonth.keys()].sort((a, b) => b.localeCompare(a));

const lines: string[] = [
  "# Changelog",
  "",
  "> Historial de cambios de Rambla Rental.",
  "> Actualizado automáticamente — fuente: `src/data/changelog.ts`.",
  "",
];

for (const month of sortedMonths) {
  const entries = byMonth.get(month)!;
  // Nombre del mes
  const [year, mo] = month.split("-");
  const monthName = new Date(`${year}-${mo}-15T12:00:00`).toLocaleDateString("es-AR", {
    month: "long",
    year: "numeric",
  });
  lines.push(`## ${monthName.charAt(0).toUpperCase() + monthName.slice(1)}`);
  lines.push("");

  // Agrupar por tipo dentro del mes
  const byType = new Map<ChangelogEntry["type"], ChangelogEntry[]>();
  for (const e of entries) {
    if (!byType.has(e.type)) byType.set(e.type, []);
    byType.get(e.type)!.push(e);
  }

  const typeOrder: ChangelogEntry["type"][] = ["feat", "fix", "refactor", "chore", "docs", "style"];
  for (const type of typeOrder) {
    if (!byType.has(type)) continue;
    const group = byType.get(type)!;
    lines.push(`### ${TYPE_EMOJI[type]} ${TYPE_LABEL[type]}`);
    lines.push("");
    for (const e of group) {
      lines.push(`- **${e.title}** *(${fmtDate(e.date)})*`);
      if (e.body) {
        // Indent body as blockquote
        lines.push(`  ${e.body}`);
      }
    }
    lines.push("");
  }
}

const output = lines.join("\n");
const outPath = join(import.meta.dir, "..", "CHANGELOG.md");
writeFileSync(outPath, output, "utf-8");
console.log(`✅ CHANGELOG.md generado (${changelog.length} entradas)`);
