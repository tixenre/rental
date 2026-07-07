import type * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Sparkles, ExternalLink, Bug, Wrench, Plus, FileText, Tag } from "lucide-react";

import { AdminPage } from "@/components/admin/AdminPage";
import { Badge } from "@/design-system/ui/badge";
import { changelog, type ChangelogEntry } from "@/data/changelog";

export const Route = createFileRoute("/admin/novedades")({
  head: () => ({ meta: [{ title: "Novedades · Back Office" }] }),
  component: NovedadesPage,
});

function NovedadesPage() {
  return (
    <AdminPage title="Novedades" maxW="form" description="Cambios recientes en el sistema.">
      <ol className="space-y-4 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-px before:bg-border before:hairline">
        {changelog.map((entry) => (
          <EntryCard key={entry.number} entry={entry} />
        ))}
      </ol>
    </AdminPage>
  );
}

function EntryCard({ entry }: { entry: ChangelogEntry }) {
  const kind = kindFor(entry.type);
  return (
    <li className="relative pl-9">
      <div
        className={`absolute left-0 top-3 grid h-6 w-6 place-items-center rounded-full ring-4 ring-background ${kind.color}`}
      >
        {kind.icon}
      </div>
      <article className="card p-5 hover:border-ink/20 transition">
        <header className="flex items-start gap-3 mb-2">
          <div className="flex-1 min-w-0">
            <h2 className="font-display text-base text-ink leading-snug">{entry.title}</h2>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="t-eyebrow">{fmtDate(entry.date)}</span>
              {entry.labels?.map((l) => (
                <Badge key={l} variant="outline" className="text-2xs py-0 h-5">
                  {l}
                </Badge>
              ))}
            </div>
          </div>
          <span className="shrink-0 t-eyebrow">#{entry.number}</span>
        </header>
        {entry.body && (
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{entry.body}</p>
        )}
      </article>
    </li>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("es-AR", { day: "numeric", month: "short", year: "numeric" });
}

// Tier 3 (categórico): un color por tipo de cambio del changelog, elegidos
// para distinguirse entre sí, no semánticos. Ver docs/DESIGN_SYSTEM.md.
/* eslint-disable no-restricted-syntax */
function kindFor(type: ChangelogEntry["type"]): { icon: React.ReactNode; color: string } {
  switch (type) {
    case "fix":
      return { icon: <Bug className="h-3 w-3 text-white" />, color: "bg-amber-600" };
    case "feat":
      return { icon: <Sparkles className="h-3 w-3 text-white" />, color: "bg-green-600" };
    case "chore":
    case "refactor":
      return { icon: <Wrench className="h-3 w-3 text-white" />, color: "bg-slate-500" };
    case "docs":
      return { icon: <FileText className="h-3 w-3 text-white" />, color: "bg-blue-500" };
    case "style":
      return { icon: <Tag className="h-3 w-3 text-white" />, color: "bg-purple-500" };
    default:
      return { icon: <Plus className="h-3 w-3 text-white" />, color: "bg-ink" };
  }
}
/* eslint-enable no-restricted-syntax */
