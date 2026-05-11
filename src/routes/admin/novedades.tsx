import type * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Sparkles, ExternalLink, RefreshCw, Loader2,
  Bug, Wrench, Plus, FileText, Tag,
} from "lucide-react";

import { authedJson } from "@/lib/authedFetch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/admin/novedades")({
  head: () => ({ meta: [{ title: "Novedades — Rambla Rental" }] }),
  component: NovedadesPage,
});

type ChangelogPR = {
  number: number;
  title: string;
  body: string;
  html_url: string;
  merged_at: string | null;
  closed_at: string | null;
  user: string;
  labels: string[];
  is_merged: boolean;
};

type ChangelogResp = {
  items: ChangelogPR[];
  cached: boolean;
  age_seconds: number;
};

function NovedadesPage() {
  const q = useQuery<ChangelogResp>({
    queryKey: ["admin", "changelog"],
    queryFn: () => authedJson<ChangelogResp>("/api/admin/changelog?limit=30"),
    staleTime: 60_000,
  });

  const refetchForce = async () => {
    // Force=true bust del cache backend
    await authedJson<ChangelogResp>("/api/admin/changelog?limit=30&force=true");
    q.refetch();
  };

  return (
    <div className="px-4 md:px-8 py-6 md:py-10 max-w-3xl mx-auto">
      <div className="mb-8 flex items-end justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office
          </div>
          <h1 className="font-display text-3xl md:text-4xl text-ink flex items-center gap-2">
            <Sparkles className="h-7 w-7 text-amber" />
            Novedades
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cambios recientes en el sistema. Se actualiza automáticamente desde GitHub.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refetchForce}
          disabled={q.isFetching}
          className="shrink-0"
        >
          {q.isFetching ? (
            <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          )}
          Refrescar
        </Button>
      </div>

      {q.isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-32 rounded-xl border hairline bg-surface animate-pulse" />
          ))}
        </div>
      )}

      {q.isError && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-6 text-sm text-destructive">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] mb-2">Error</div>
          <div>{(q.error as Error)?.message ?? "No se pudo cargar las novedades"}</div>
        </div>
      )}

      {q.data && q.data.items.length === 0 && (
        <div className="rounded-xl border hairline p-8 text-center text-sm text-muted-foreground">
          Todavía no hay cambios para mostrar.
        </div>
      )}

      {q.data && q.data.items.length > 0 && (
        <ol className="space-y-4 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-px before:bg-border before:hairline">
          {q.data.items.map((pr) => (
            <PRCard key={pr.number} pr={pr} />
          ))}
        </ol>
      )}

      {q.data?.cached && (
        <p className="text-[10px] text-muted-foreground/70 mt-6 text-center font-mono">
          Caché de hace {Math.round(q.data.age_seconds / 60)} min
        </p>
      )}
    </div>
  );
}

function PRCard({ pr }: { pr: ChangelogPR }) {
  const kind = inferKind(pr.title);
  return (
    <li className="relative pl-9">
      <div className={`absolute left-0 top-3 grid h-6 w-6 place-items-center rounded-full ring-4 ring-background ${kind.color}`}>
        {kind.icon}
      </div>
      <article className="rounded-xl border hairline bg-surface p-5 hover:border-ink/20 transition">
        <header className="flex items-start gap-3 mb-2">
          <div className="flex-1 min-w-0">
            <h2 className="font-display text-base text-ink leading-snug">
              {stripPrefix(pr.title)}
            </h2>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {pr.merged_at ? fmtDate(pr.merged_at) : "—"} · @{pr.user}
              </span>
              {pr.labels.map((l) => (
                <Badge key={l} variant="outline" className="text-[10px] py-0 h-5">
                  {l}
                </Badge>
              ))}
            </div>
          </div>
          <a
            href={pr.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition"
          >
            #{pr.number} <ExternalLink className="h-3 w-3" />
          </a>
        </header>
        {pr.body && (
          <div className="mt-2 text-xs text-muted-foreground whitespace-pre-line line-clamp-6">
            {cleanBody(pr.body)}
          </div>
        )}
      </article>
    </li>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", { day: "numeric", month: "short", year: "numeric" });
}

/** Quita el prefijo `fix:` / `feat:` / `chore:` del título. */
function stripPrefix(t: string): string {
  return t.replace(/^(fix|feat|chore|docs|refactor|test|style|perf|build|ci)(\([^)]+\))?:\s*/i, "");
}

function cleanBody(body: string): string {
  // Cortar antes de la línea del footer de Claude
  let b = body.split(/🤖 Generated with/)[0].trim();
  // Cortar líneas demasiado largas de checkboxes
  b = b.replace(/\n## Test plan[\s\S]*/i, "").trim();
  return b;
}

function inferKind(title: string): { icon: React.ReactNode; color: string } {
  const t = title.toLowerCase();
  if (t.startsWith("fix")) {
    return { icon: <Bug className="h-3 w-3 text-white" />, color: "bg-amber-600" };
  }
  if (t.startsWith("feat")) {
    return { icon: <Sparkles className="h-3 w-3 text-white" />, color: "bg-green-600" };
  }
  if (t.startsWith("chore") || t.startsWith("refactor")) {
    return { icon: <Wrench className="h-3 w-3 text-white" />, color: "bg-slate-500" };
  }
  if (t.startsWith("docs")) {
    return { icon: <FileText className="h-3 w-3 text-white" />, color: "bg-blue-500" };
  }
  if (t.startsWith("style")) {
    return { icon: <Tag className="h-3 w-3 text-white" />, color: "bg-purple-500" };
  }
  return { icon: <Plus className="h-3 w-3 text-white" />, color: "bg-ink" };
}
